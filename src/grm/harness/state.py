"""Graph state: turn input, session pointers, gate outcomes."""

from typing import TypedDict


class TurnState(TypedDict, total=False):
    # TODO: session id, turn text, identity verdict, blob ref, candidate, QA verdict.
    pass
