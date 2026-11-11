"""MCP interface: the dialogue service exposed as tools.

This module owns the FastMCP server instance. Tools are declared with the
`@mcp.tool` decorator, which registers them and derives each input schema from
its signature and docstring.

Design rules:

* Tools take scalars. The caller sends a transcript, a session id and a
  channel; structured internal models stay inside our service.
* Every tool returns a JSON-safe dict. FastMCP exposes it as structured content
  and as JSON text.
* No flow logic here. Tools translate arguments, call the shared service, and
  return. REST uses the same service, so behaviour cannot diverge.
* Tool names are verbs and stay stable across deploys. The server version
  changes, not the names, so an integrated client does not break.
"""

from typing import Any, NoReturn

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from grm.channels.schemas import Channel, TurnRequest
from grm.channels.service import get_service
from grm.config import get_settings
from grm.mcp.constants import INSTRUCTIONS, SERVER_NAME, SERVER_VERSION
from grm.observability.logging import get_logger
from grm.observability.trace import trace_error, trace_inbound, trace_outbound

mcp: FastMCP = FastMCP(
    name=SERVER_NAME,
    version=SERVER_VERSION,
    instructions=INSTRUCTIONS,
)

#: One fixed sentence for every tool failure. The detail belongs in our logs,
#: not in a reply that may be read aloud to a beneficiary.
FRIENDLY_ERROR = (
    "I'm sorry, I'm having trouble connecting to our service right now. "
    "Please try again in a little while."
)


def _fail(tool: str, exc: Exception) -> NoReturn:
    """Log the real cause, return a fixed sentence to the caller."""
    get_logger().error(
        "tool failed",
        stage="tool",
        tool=tool,
        error=type(exc).__name__,
        detail=str(exc)[:800],
    )
    raise ToolError(FRIENDLY_ERROR) from exc


#: Channel aliases, so a client can send its own vocabulary without a code change.
_CHANNEL_ALIASES: dict[str, Channel] = {
    "chat": "chat",
    "web": "chat",
    "text": "chat",
    "voice": "voice",
    "telephony": "voice",
    "phone": "voice",
    "ivr": "voice",
}


def _resolve_channel(value: str) -> Channel:
    channel = _CHANNEL_ALIASES.get((value or "").strip().lower())
    if channel is None:
        raise ValueError(f"unknown channel {value!r}; expected one of: chat, voice, telephony, ivr")
    return channel


@mcp.tool(
    name="route_turn",
    description=(
        "Send one beneficiary utterance and receive the reply. Main entry "
        "point: handles identity verification, answering from the authenticated "
        "record, quality checking, and the reply. Call once per utterance, with "
        "a stable session_id for the whole call."
    ),
)
async def route_turn(session_id: str, text: str, channel: str = "voice") -> dict[str, Any]:
    """Run one beneficiary turn.

    Args:
        session_id: Stable per-call identifier. Reuse it for every utterance in
            the same call. A new id starts a fresh, unverified session.
        text: What the beneficiary said, transcribed. Empty string on the very
            first call to receive the opening prompt.
        channel: Where the turn came from. voice, telephony, ivr, chat, or web.

    Returns:
        reply, owner, stage, authenticated, handoffs, qa_verdict,
        revision_rounds, pending_otp, expects.
    """
    try:
        resolved = _resolve_channel(channel)
        trace_inbound(session_id, resolved, text or "")
        response = await get_service().turn(
            TurnRequest(session_id=session_id, text=text or "", channel=resolved)
        )
        trace_outbound(session_id, response.owner, response.reply)
        return response.model_dump(mode="json")
    except Exception as exc:
        trace_error(session_id, type(exc).__name__)
        _fail("route_turn", exc)


@mcp.tool(
    name="session_status",
    description=(
        "Report whether a call is verified and where it has reached. Use on "
        "reconnect, or before replaying an identity prompt. Never returns "
        "record contents."
    ),
)
async def session_status(session_id: str) -> dict[str, Any]:
    """Report session state that is safe to expose to a channel.

    Args:
        session_id: The identifier used for route_turn.
    """
    try:
        return get_service().status(session_id)
    except Exception as exc:
        _fail("session_status", exc)


@mcp.tool(
    name="reset_session",
    description=(
        "End a call. Drops verification and the authenticated record together, "
        "so the next utterance starts unverified. Call on hangup."
    ),
)
async def reset_session(session_id: str) -> dict[str, Any]:
    """Clear a session. Safe to call for an unknown id.

    Args:
        session_id: The identifier used for route_turn.
    """
    try:
        get_service().reset(session_id)
        return {"session_id": session_id, "reset": True}
    except Exception as exc:
        _fail("reset_session", exc)


@mcp.tool(
    name="check_connection",
    description=(
        "Connectivity check. Takes the same arguments as route_turn and returns "
        "one fixed string. Calls no model and touches no session, so it is safe "
        "to use to verify the URL, headers and response parsing."
    ),
)
async def check_connection(session_id: str, text: str, channel: str = "voice") -> str:
    """Confirm the caller can reach the server.

    Args:
        session_id: Ignored. Present so the call shape matches route_turn.
        text: Ignored. Present so the call shape matches route_turn.
        channel: Ignored. Present so the call shape matches route_turn.
    """
    return "hi you are now connected to the MCP"


@mcp.tool(
    name="describe_contract",
    description=(
        "Describe the dialogue contract: channels, agents, stages, and the "
        "meaning of expects. Use during integration instead of reading our "
        "source."
    ),
)
async def describe_contract() -> dict[str, Any]:
    """Describe the contract, for integrators.

    Returns the channels accepted, the agents that can own a turn, the stages,
    and what each expects value means.
    """
    return {
        "contract_version": "1.5",
        "architecture": "single_agent" if get_settings().single_agent else "chat_plus_reasoning",
        "evaluation": "enabled" if get_settings().qa_enabled else "disabled",
        "identity_check": "auto (demo bypass)" if get_settings().demo_auto_verify else "otp",
        "transport": "MCP Streamable HTTP (FastMCP), JSON responses, stateless",
        "tools": [
            "route_turn",
            "check_connection",
            "session_status",
            "reset_session",
            "describe_contract",
        ],
        "channels": sorted(set(_CHANNEL_ALIASES)),
        "agents": {
            "chat": "front line: greetings, clarification, lookups, presentation",
            "reasoning": "analysis across records: status, blockers, next steps",
            "single": (
                "one agent doing reception, lookups and analysis; active when SINGLE_AGENT is true"
            ),
            "qa": "internal verification only; never speaks to the beneficiary",
            "none": "no agent has claimed the turn yet",
        },
        "stages": {
            "greet": "session opened, nothing verified",
            "id_prompt": "waiting for a beneficiary identifier",
            "otp_sent": "waiting for the one-time code",
            "confirm_identity": "waiting for the caller to confirm the name on the record",
            "open": "verified, ready for a normal question",
            "reasoned": "the previous turn was answered from the record",
        },
        "expects": {
            "beneficiary_id": "ask for the identifier; send it back as text",
            "otp": "ask for the four-digit code; send it back as text",
            "confirmation": "ask whether the name is correct; send yes or no as text",
            "message": "free speech; send the transcript",
            "closed": "the session has ended",
        },
        "notes": [
            "Reuse session_id for the whole call, reset_session on hangup.",
            "Tool failures return isError true with one fixed sentence; details stay in our logs.",
            "A turn can take several seconds: three model calls may run in sequence.",
            "Never treat a reply as final until authenticated is true.",
        ],
    }
