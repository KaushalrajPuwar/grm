"""Turn state. Carries the conversation, not the data itself.

The snapshot lives on the auth session. This carries a reference and a short
history so each agent knows what has been said, plus the routing and gate
outcomes the front end needs to render.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Owner = Literal["chat", "reasoning", "qa", "none"]

#: Handoff events surfaced to the front end's agent panel.
HandoffKind = Literal["to_reasoning", "to_chat", "gate_open", "gate_close", "qa_pass", "qa_fail"]


@dataclass
class Handoff:
    frm: Owner
    to: Owner
    kind: HandoffKind
    reason: str


@dataclass
class TurnState:
    """Per-turn working copy. Session-scoped fields live on AuthSession."""

    #: Foundational id of the verified beneficiary, or "unverified" before the
    #: gate passes. Not a session id: the transport session id never reaches the
    #: harness, and the two must not be confused when reading a trace.
    beneficiary_id: str
    authenticated: bool = False
    owner: Owner = "none"
    user_text: str = ""
    reply: str = ""
    history: list[dict[str, str]] = field(default_factory=list)
    handoffs: list[Handoff] = field(default_factory=list)
    blob_ref: str | None = None
    qa_verdict: str | None = None
    qa_objections: str | None = None
    revision_rounds: int = 0
    stage: str = "greet"
    closed: bool = False
    context: dict[str, Any] = field(default_factory=dict)

    def record(self, role: str, text: str) -> None:
        self.history.append({"role": role, "text": text})
