"""Turn in/out contract. Chat and voice bind to this, nothing else."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TurnRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    text: str = ""
    channel: Literal["chat", "voice"] = "chat"


class HandoffEvent(BaseModel):
    frm: str
    to: str
    kind: str
    reason: str


class TurnResponse(BaseModel):
    session_id: str
    reply: str
    owner: str
    stage: str
    authenticated: bool
    handoffs: list[HandoffEvent]
    qa_verdict: str | None = None
    revision_rounds: int = 0
    pending_otp: bool = False
