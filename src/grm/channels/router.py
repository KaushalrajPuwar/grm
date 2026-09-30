"""Turn routing seam.

REST calls this today. WebSockets will call this tomorrow. The signature does
not change, so no channel-specific code reaches flow control.
"""

from __future__ import annotations

from grm.beneficiary360.file_backed import get_client
from grm.channels.schemas import HandoffEvent, TurnRequest, TurnResponse
from grm.harness.turn_loop import handle_turn
from grm.store.registry import SessionRegistry

_registry = SessionRegistry()


def get_registry() -> SessionRegistry:
    return _registry


async def route_turn(request: TurnRequest) -> TurnResponse:
    """Drive one turn and shape the response for any channel."""
    client = get_client()
    session = _registry.get(request.session_id)
    state = await handle_turn(session, request.text, client)

    return TurnResponse(
        session_id=request.session_id,
        reply=state.reply,
        owner=state.owner,
        stage=state.stage,
        authenticated=state.authenticated,
        handoffs=[
            HandoffEvent(frm=h.frm, to=h.to, kind=h.kind, reason=h.reason) for h in state.handoffs
        ],
        qa_verdict=state.qa_verdict,
        revision_rounds=state.revision_rounds,
        pending_otp=state.stage == "otp_sent",
    )
