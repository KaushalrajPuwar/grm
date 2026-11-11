"""Unit tests for spoken registration-number resolution.

No model and no server: these cover the deterministic path, which must handle
the common speech shapes before the model is consulted at all.
"""

from __future__ import annotations

import pytest

from grm.auth.identifier import candidates, match, normalise_spoken

KNOWN = ("FID9988776655",)


@pytest.mark.parametrize(
    "utterance",
    [
        "FID9988776655",
        "FID-9988776655",
        "fid 9988 776 655",
        "my FID is 9988776655",
        "my registration number is 9988776655",
        "nine nine eight eight seven seven six six five five",
        "99 88 77 66 55",
        "99, 88, 77, 66, 55",
        "99.88.77.66.55",
        "double nine double eight seven seven double six double five",
        "double nine, double eight, seventy seven, double six, double five",
        "998 and 877 and 6655",
        "nine nine eight, then eight seven seven, then six six five five",
        # ASR punctuation: commas and full stops between every word.
        "nine, nine, eight, eight, seven, seven, six, six, five, five.",
        "nine nine eight. eight seven seven. six six five five.",
        "9, 9, 8, 8, 7, 7, 6, 6, 5, 5.",
        "my FID is nine, nine, eight, eight, seven, seven, six, six, five, five.",
    ],
)
def test_spoken_variants_resolve(utterance: str) -> None:
    found = candidates(utterance)
    assert found, f"no candidate found in {utterance!r}"
    assert any(match(candidate, KNOWN) for candidate in found), (
        f"no candidate matched in {utterance!r}: {found}"
    )


@pytest.mark.parametrize(
    "utterance",
    [
        "I have a complaint",
        "my subsidy did not arrive",
        "hello",
        "nine nine eight eight",
        "998877",
    ],
)
def test_non_identifiers_do_not_resolve(utterance: str) -> None:
    assert not any(match(candidate, KNOWN) for candidate in candidates(utterance))


@pytest.mark.parametrize(
    "utterance",
    [
        "Yes, my FID is fifty five, sixty six, seventy seven, eighty eight, ninety nine.",
        "fifty-five, sixty-six, seventy-seven, eighty-eight, ninety-nine",
        "my registration number is 55 66 77 88 99",
    ],
)
def test_tens_words_in_groups(utterance: str) -> None:
    """Tens words must join into pairs, not be read as separate digits."""
    assert any(match(candidate, ("FID5566778899",)) for candidate in candidates(utterance))


def test_a_wrong_number_still_counts_as_an_attempt() -> None:
    """The gate answers a wrong number differently from plain speech."""
    assert candidates("FID0000000000")
    assert candidates("my number is 1112223334")
    assert not candidates("I have a complaint")
    assert not candidates("hello")


def test_normalisation_ignores_filler_and_separators() -> None:
    assert normalise_spoken("my FID is 99-88-77-66-55") == "9988776655"
    assert normalise_spoken("99 88 77 66 55") == "9988776655"


def test_match_compares_digits_only() -> None:
    assert match("FID-9988776655", KNOWN) == "FID9988776655"
    assert match("9988776655", KNOWN) == "FID9988776655"
    assert match("9988776656", KNOWN) is None
