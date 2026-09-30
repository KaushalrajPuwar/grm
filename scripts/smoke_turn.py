"""Manual Phase 1 smoke drive. Run: python scripts/smoke_turn.py

Drives the full turn loop against real models and the demo Beneficiary 360
response. The OTP is read from the shared store the standalone issuer watches,
which is how a human would read it off a second terminal.
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from grm.auth.gate import begin_session  # noqa: E402
from grm.auth.otp import clear_issued, peek_issued  # noqa: E402
from grm.beneficiary360.file_backed import get_client  # noqa: E402
from grm.harness.turn_loop import handle_turn  # noqa: E402


def banner(text: str) -> None:
    print(f"\n{'=' * 70}\n{text}\n{'=' * 70}")


def read_published_otp() -> str:
    """What a human reads off the second terminal."""
    record = peek_issued()
    return str(record.get("code", "")) if record else ""


async def send(session, text, client):
    state = await handle_turn(session, text, client)
    print(f"\n> you: {text}")
    print(f"< {state.owner}: {state.reply}")
    for h in state.handoffs:
        print(f"    {h.frm} -> {h.to} [{h.kind}]: {h.reason}")
    if state.qa_verdict:
        print(f"    qa={state.qa_verdict} revisions={state.revision_rounds}")
    return state


async def main() -> int:
    clear_issued()
    client = get_client()
    session = begin_session()
    fid = client.foundational_id

    banner("GATE: pre-authentication, no protected data may leak")
    state = await send(session, "", client)
    assert not state.authenticated, "must not authenticate on open"
    assert "Lakshmi" not in state.reply, "name leaked pre-auth"
    assert "blocked" not in state.reply.lower(), "status leaked pre-auth"

    banner("GATE: unknown identifier reveals nothing, issues no code")
    clear_issued()
    state = await send(session, "FID-0000000000", client)
    assert not state.authenticated, "unknown id authenticated"
    assert not read_published_otp(), "unknown id published an OTP"

    banner("GATE: known identifier publishes a code for the issuer process")
    clear_issued()
    state = await send(session, fid, client)
    code = read_published_otp()
    assert code, "no code published for the issuer to read"
    assert len(code) == 4 and code.isdigit(), f"malformed code: {code!r}"
    assert not state.authenticated, "ID alone must not authenticate"
    assert "*******345" in state.reply, f"contact not masked: {state.reply}"

    banner("GATE: code read off the second terminal is accepted")
    state = await send(session, code, client)
    assert state.authenticated, f"published code rejected: {state.stage}"
    assert "Lakshmi" in state.reply, "greeting did not use the registry name"
    assert not peek_issued(), "issued code was not consumed after verification"

    banner("GATE: server cannot verify without a human submitting a code")
    fresh = begin_session()
    await send(fresh, fid, client)
    assert fresh.state.status.value == "otp_sent", "verified without a code"
    await send(fresh, "", client)
    assert not fresh.verified, "empty turn verified the session"
    clear_issued()

    banner("ROUTING: reference lookup stays with the chat agent")
    state = await send(session, "what is my LPG connection number?", client)
    assert state.owner == "chat", f"expected chat, got {state.owner}"

    banner("ROUTING: cylinder dispatched, awaiting delivery")
    state = await send(
        session, "You said my cylinder is on the way. When will I actually receive it?", client
    )
    assert state.owner == "reasoning", f"expected reasoning, got {state.owner}"

    banner("ROUTING: blocked subsidy release")
    state = await send(
        session, "I did not get my gas subsidy this month. Why was it blocked?", client
    )
    assert state.owner == "reasoning", f"expected reasoning, got {state.owner}"

    banner("ROUTING: follow-up keeps context")
    state = await send(session, "what should I actually do about it?", client)
    assert "?" in state.reply, "follow-up produced no reply"

    banner("ROUTING: new topic returns to the chat agent")
    state = await send(session, "what other schemes am I on?", client)
    assert state.owner == "chat", f"expected chat, got {state.owner}"

    banner("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
