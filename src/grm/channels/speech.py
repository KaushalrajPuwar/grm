"""Speech normalisation for the reply text.

The reply is read aloud by a text-to-speech engine at the other end of the
channel. Markdown markers, currency symbols and bracketed asides either get
spoken literally or trip the engine, so they are removed at the boundary.

This is a safety net, not the primary fix. The constitutions already forbid
markdown and symbols. This runs afterwards so a model slip cannot reach a
caller's ear as "asterisk asterisk three hundred".

It is deliberately conservative: it never deletes words, only notation.
"""

from __future__ import annotations

import re

#: `**bold**`, `*italic*`, `__bold__`, `_italic_`, and inline code.
_EMPHASIS = re.compile(r"(\*{1,3}|_{1,3}|`)(.+?)\1", re.DOTALL)

#: A leading list marker: `* `, `- `, `• `, `1. `, `1) `.
_LIST_MARKER = re.compile(r"^\s*(?:[*\-•]|\d+[.)])\s+", re.MULTILINE)

#: A heading marker: `## Title`.
_HEADING = re.compile(r"^\s*#{1,6}\s*", re.MULTILINE)

#: Currency, turned into words before the symbol is dropped.
_CURRENCY = (
    (re.compile(r"₹\s?(\d[\d,]*\.?\d*)"), r"\1 rupees"),
    (re.compile(r"\$\s?(\d[\d,]*\.?\d*)"), r"\1 dollars"),
    (re.compile(r"€\s?(\d[\d,]*\.?\d*)"), r"\1 euros"),
    (re.compile(r"£\s?(\d[\d,]*\.?\d*)"), r"\1 pounds"),
)

#: A bracketed aside. Kept as words, with the brackets turned into pauses.
_BRACKETED = re.compile(r"\(([^()]*)\)")

#: Dashes used as punctuation.
#: Written as escapes so the source itself contains no ambiguous characters.
_DASHES = re.compile(r"\s*[\u2014\u2013]\s*")

#: Symbols that should be words.
_SYMBOLS = (
    ("&", " and "),
    ("%", " percent"),
    ("+", " plus "),
    ("=", " equals "),
)


def to_speech(text: str) -> str:
    """Return text that reads cleanly aloud. Idempotent."""
    if not text:
        return ""

    out = text
    out = _HEADING.sub("", out)
    out = _LIST_MARKER.sub("", out)
    out = _EMPHASIS.sub(r"\2", out)

    for pattern, replacement in _CURRENCY:
        out = pattern.sub(replacement, out)

    out = _BRACKETED.sub(lambda m: f", {m.group(1).strip()}, ", out)
    out = _DASHES.sub(", ", out)

    for symbol, word in _SYMBOLS:
        out = out.replace(symbol, word)

    # A bracketed aside leaves a comma next to existing punctuation. Tidy the
    # seams so the result reads as normal prose.
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    out = re.sub(r"([,;:])\s*\.", ".", out)
    out = re.sub(r",\s*,", ",", out)
    out = re.sub(r"\.\s*,", ".", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()
