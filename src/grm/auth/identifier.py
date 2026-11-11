"""Resolve a spoken registration number to a canonical identifier.

Speech recognition is unreliable. A caller may say "FID9988776655", "my FID is
9988776655", or have every digit rendered as a word. Exact string matching
fails on all of those, so resolution happens in two stages:

1. Deterministic normalisation. This is a grammar over tokens, not a list of
   accepted phrases: digit words become digits, tens and teens are joined,
   "double" and "triple" are expanded, and every separator and filler word is
   dropped. Whatever remains is matched against the known identifiers by its
   digits alone. This is fast and handles most speech noise.
2. Model extraction. Only if stage one finds nothing, a small model reads the
   transcript and returns the digits it heard.

The model never decides whether a number is valid. It only proposes digits, and
the code matches them against the record. A hallucinated number cannot open a
session.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from grm.agents.base import AgentAdapter
from grm.beneficiary360.client import Beneficiary360Client
from grm.observability.logging import get_logger

#: Spoken digits, including the forms speech engines emit for zero.
_DIGIT_WORDS = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}

_DIGIT_WORD_PATTERN = re.compile(r"\b(" + "|".join(_DIGIT_WORDS) + r")\b")

#: Teens and tens, so "seventy seven" becomes 77 rather than being ignored.
_TEENS = {
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
}

_TENS = {
    "twenty": "2",
    "thirty": "3",
    "forty": "4",
    "fifty": "5",
    "sixty": "6",
    "seventy": "7",
    "eighty": "8",
    "ninety": "9",
}

_UNIT_WORDS = "one|two|three|four|five|six|seven|eight|nine"

_TENS_PHRASE = re.compile(r"\b(" + "|".join(_TENS) + r")(?:[\s-]+(" + _UNIT_WORDS + r"))?\b")

_TEENS_PATTERN = re.compile(r"\b(" + "|".join(_TEENS) + r")\b")

#: "double nine" and "triple eight", the way people read grouped digits.
_DOUBLED = re.compile(r"\b(double|triple)\s+(" + "|".join(_DIGIT_WORDS) + r"|\d)\b")

#: Filler words that sit between digit groups and carry no value.
_FILLER = re.compile(r"\b(and|then|is|my|the|number|fid|please|uh|um|er)\b")

#: `fid` followed by digits, after normalisation.
_FID_PATTERN = re.compile(r"fid\d+")

#: A bare run of digits long enough to be an identifier, not an amount.
_DIGIT_RUN = re.compile(r"\d{6,}")

#: Any digits in a model reply. Used to tell "no number was spoken" from
#: "a number was spoken but it matches no record".
_ANY_DIGITS = re.compile(r"\d+")


@dataclass(frozen=True)
class Resolution:
    """What an utterance turned out to contain.

    `attempted` distinguishes a caller who said no number at all from one who
    said a number that matches no record. The gate answers those differently.
    """

    identifier: str | None
    attempted: bool


def _expand_tens(match: re.Match[str]) -> str:
    """`seventy seven` -> `77`, `twenty` -> `20`."""
    tens = _TENS[match.group(1)]
    unit = match.group(2)
    return tens + (_DIGIT_WORDS[unit] if unit else "0")


def _expand_doubled(match: re.Match[str]) -> str:
    """`double nine` -> `99`, `triple eight` -> `888`."""
    word = match.group(2)
    digit = _DIGIT_WORDS.get(word, word)
    return digit * (2 if match.group(1) == "double" else 3)


def normalise_spoken(text: str) -> str:
    """Lowercase, expand spoken digits, drop separators and filler words.

    The result is one alphanumeric string, so "99, 88, 77" and "double nine
    double eight seven seven" both collapse to the same digits.
    """
    lowered = text.lower()
    # Speech recognition inserts commas and full stops between words, including
    # between the parts of a number word: "fifty, five". Treat punctuation as a
    # space before joining tens and units, otherwise "fifty" and "five" are read
    # as two separate numbers instead of fifty five.
    lowered = re.sub(r"[,.;:!?]", " ", lowered)
    teens = _TEENS_PATTERN.sub(lambda m: _TEENS[m.group(1)], lowered)
    tens = _TENS_PHRASE.sub(_expand_tens, teens)
    doubled = _DOUBLED.sub(_expand_doubled, tens)
    with_digits = _DIGIT_WORD_PATTERN.sub(lambda m: _DIGIT_WORDS[m.group(1)], doubled)
    without_filler = _FILLER.sub("", with_digits)
    return re.sub(r"[^a-z0-9]", "", without_filler)


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def candidates(text: str) -> list[str]:
    """Candidate identifier strings found in the utterance, best first."""
    normalised = normalise_spoken(text)
    found = _FID_PATTERN.findall(normalised) + _DIGIT_RUN.findall(normalised)

    seen: set[str] = set()
    ordered: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def match(value: str, known: Sequence[str]) -> str | None:
    """Return the canonical identifier whose digits match, or None.

    Comparison is on digits only, so the presence or absence of the FID prefix
    and any hyphens does not matter.
    """
    digits = _digits_only(value)
    if not digits:
        return None
    for identifier in known:
        if _digits_only(identifier) == digits:
            return identifier
    return None


def _model_prompt(transcript: str) -> str:
    return (
        "Read this speech transcript and return the beneficiary registration "
        "number it contains. Return only the digits, with no spaces and no "
        "punctuation. If there is no registration number, return exactly NONE.\n\n"
        f"Transcript: {transcript}"
    )


async def resolve_identifier(
    text: str, client: Beneficiary360Client, adapter: AgentAdapter
) -> Resolution:
    """Resolve an utterance to a canonical identifier, and say what happened."""
    log = get_logger()
    known = client.known_identifiers()
    found = candidates(text)

    for candidate in found:
        hit = match(candidate, known)
        if hit is not None:
            log.info("identifier resolved without a model", stage="gate", path="deterministic")
            return Resolution(hit, True)

    # Stage two. The model only proposes digits; the match below is still exact.
    try:
        message = await adapter.invoke(_model_prompt(text))
    except Exception as exc:
        log.warning(
            "identifier extraction failed",
            stage="gate",
            error=type(exc).__name__,
        )
        return Resolution(None, bool(found))

    raw = message.content if isinstance(message.content, str) else str(message.content)
    if "none" in raw.strip().lower():
        log.info("identifier not present in the utterance", stage="gate", path="model")
        return Resolution(None, bool(found))

    digits = _ANY_DIGITS.search(raw)
    if not digits:
        log.info("model returned no digits", stage="gate", path="model")
        return Resolution(None, bool(found))

    hit = match(digits.group(0), known)
    if hit is not None:
        log.info("identifier resolved by a model", stage="gate", path="model")
        return Resolution(hit, True)

    log.info("model proposed digits that match no record", stage="gate", path="model")
    return Resolution(None, True)
