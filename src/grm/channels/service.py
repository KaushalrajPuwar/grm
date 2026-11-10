"""Transport-neutral dialogue service.

One service, several front doors. The REST adapter and the MCP adapter both
call this and nothing else, so a channel can never grow its own copy of the
flow. Transport concerns stop at the edge.

Nothing here knows that HTTP or JSON-RPC exists.
"""

from __future__ import annotations

from grm.beneficiary360.client import Beneficiary360Client
from grm.beneficiary360.file_backed import get_client
from grm.channels.schemas import (
    Expectation,
    HandoffEvent,
    TurnRequest,
    TurnResponse,
)
from grm.channels.speech import to_speech
from grm.harness.turn_loop import handle_turn
from grm.store.registry import SessionRegistry

#: Stage to the one thing the channel should ask for next.
_EXPECTS_BY_STAGE: dict[str, Expectation] = {
    "greet": "beneficiary_id",
    "id_prompt": "beneficiary_id",
    "otp_sent": "otp",
    "confirm_identity": "confirmation",
    "open": "message",
    "reasoned": "message",
    "verified": "message",
}


class DialogueService:
    """Holds the session registry and drives one turn at a time."""

    def __init__(self, client: Beneficiary360Client | None = None) -> None:
        self._client = client or get_client()
        self._sessions = SessionRegistry()

    async def turn(self, request: TurnRequest) -> TurnResponse:
        """Run one beneficiary turn and shape the reply for any channel."""
        session = self._sessions.get(request.session_id)
        state = await handle_turn(session, request.text, self._client)

        return TurnResponse(
            session_id=request.session_id,
            # Speech-ready: the reply may be read aloud, so notation is removed
            # before it leaves the service.
            reply=to_speech(state.reply),
            owner=state.owner,
            stage=state.stage,
            authenticated=state.authenticated,
            handoffs=[
                HandoffEvent(frm=h.frm, to=h.to, kind=h.kind, reason=h.reason)
                for h in state.handoffs
            ],
            qa_verdict=state.qa_verdict,
            revision_rounds=state.revision_rounds,
            pending_otp=state.stage == "otp_sent",
            expects=_EXPECTS_BY_STAGE.get(state.stage, "message"),
        )

    def reset(self, session_id: str) -> bool:
        """Drop verification and the snapshot together, never apart.

        A telephony client calls this on hangup. It is idempotent, so calling
        it for an unknown session is not an error.
        """
        self._sessions.drop(session_id)
        return True

    def status(self, session_id: str) -> dict[str, object]:
        """Session state safe to report to a channel.

        Deliberately narrow: whether the caller is verified, and where the
        conversation has reached. No record contents, no identifier echo.
        """
        session = self._sessions.peek(session_id)
        if session is None:
            return {
                "session_id": session_id,
                "known": False,
                "authenticated": False,
                "stage": "new",
            }
        return {
            "session_id": session_id,
            "known": True,
            "authenticated": session.verified,
            "stage": session.stage,
        }


_service: DialogueService | None = None


def get_service() -> DialogueService:
    """Process-wide service. One registry, so REST and MCP share sessions."""
    global _service
    if _service is None:
        _service = DialogueService()
    return _service
