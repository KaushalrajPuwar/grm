"""Turn in/out contract.

This is the shape every channel speaks: REST today, MCP for the voice stack,
WebSockets later if it is ever needed. Change it here and every channel sees the
same change, which is the point of keeping it in one file.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Channel = Literal["chat", "voice"]

#: What the channel should ask the beneficiary for next. Telephony uses this to
#: decide whether to prompt for an identifier, read back a code, or let the
#: caller speak freely, without parsing the reply text.
Expectation = Literal["beneficiary_id", "otp", "message", "closed"]


class TurnRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    text: str = ""
    channel: Channel = "chat"


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
    expects: Expectation = "message"
