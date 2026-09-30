"""The turn loop.

Order of operations, fixed:

1. Pre-auth: deterministic gate exchange, no model called.
2. Post-auth greeting: chat agent reads the enrolment picture and opens.
3. Every later turn: chat agent routes stay or reasoning.
4. Reasoning output is evaluated by the QA agent before it can be delivered.
   Failure returns the objection to the reasoning agent for a bounded number
   of revisions. Unvalidated candidates never reach the beneficiary.
5. Ownership returns to the chat agent on the next turn, not permanently.
"""

from __future__ import annotations

import json
import time
from typing import Any

from grm.agents.base import AgentAdapter, get_adapters
from grm.auth.gate import AuthSession, release_blob
from grm.beneficiary360.client import Beneficiary360Client
from grm.beneficiary360.schemas import Beneficiary360Blob
from grm.harness.gate_flow import handle_gate_message
from grm.harness.routing import (
    HANDOFF_INTENT,
    MAX_REVISIONS,
    register_handoff,
    run_chat,
    run_qa,
    run_reasoning,
)
from grm.harness.state import Handoff, TurnState
from grm.observability.logging import get_logger

WELCOME = (
    "Hello. I can help with your schemes, your payments, and any problem you "
    "have had receiving a benefit. First I need to verify your identity. "
    "Please share your beneficiary ID."
)


def _context_from_blob(blob: Any) -> str:
    return json.dumps(blob.for_model(), indent=2, ensure_ascii=False)


def _enrolment_summary(blob: Any) -> str:
    if not blob.programs:
        return "No programmes are on record."
    parts = []
    for program in blob.programs:
        statuses = {e.enrolmentStatus for e in program.enrolments if e.enrolmentStatus}
        if "ENROLLED" in statuses:
            label = "enrolled"
        elif "APPLIED" in statuses:
            label = "applied for"
        else:
            continue
        parts.append(f"{program.programName} ({label})")
    return ", ".join(parts) or "No programmes are on record."


async def handle_turn(
    session: AuthSession, user_text: str, client: Beneficiary360Client
) -> TurnState:
    """One beneficiary turn, end to end.

    Every stage announces itself, so watching the terminal shows which part of
    the turn is in flight and how long the earlier parts took.
    """
    log = get_logger()
    started = time.perf_counter()
    verified = session.verified
    log.info(
        "turn received",
        stage="turn",
        verified=verified,
        stage_now=session.stage,
        chars=len(user_text or ""),
    )

    adapters = get_adapters()
    state = TurnState(beneficiary_id=session.state.identifier or "unverified")
    state.stage = session.stage
    state.history = list(session.history)
    state.user_text = user_text

    if not session.verified:
        result = _handle_pre_auth(session, user_text, client, state)
    else:
        result = await _handle_verified(session, user_text, adapters, state, started)

    log.info(
        "turn finished",
        stage="turn",
        owner=result.owner,
        stage_now=result.stage,
        qa=result.qa_verdict,
        revisions=result.revision_rounds,
        duration_s=round(time.perf_counter() - started, 2),
    )
    return result


async def _handle_verified(
    session: AuthSession,
    user_text: str,
    adapters: dict[str, AgentAdapter],
    state: TurnState,
    started: float,
) -> TurnState:
    blob = release_blob(session)
    if blob is None:
        log = get_logger()
        log.warning("snapshot missing after verification", stage="gate")
        state.authenticated = False
        state.reply = "Verification expired. Please share your beneficiary ID again."
        state.stage = "id_prompt"
        session.stage = "id_prompt"
        return state

    state.authenticated = True
    state.blob_ref = blob.beneficiary.foundationalId
    context = _context_from_blob(blob)

    log = get_logger()
    log.info(
        "snapshot released",
        stage="snapshot",
        context_chars=len(context),
        programs=len(blob.programs),
        bridge_records=len(blob.bridgeProcessing),
        since_turn_s=round(time.perf_counter() - started, 2),
    )

    if session.stage == "greet":
        return _handle_greeting(session, state, blob)

    result = await _handle_authenticated_turn(adapters, state, blob, context)
    session.stage = result.stage
    session.history = list(result.history)
    return result


def _handle_pre_auth(
    session: AuthSession, user_text: str, client: Beneficiary360Client, state: TurnState
) -> TurnState:
    if not user_text.strip() and state.stage == "greet":
        state.stage = "id_prompt"
        state.reply = WELCOME
        state.owner = "chat"
        return state

    reply, stage = handle_gate_message(session, user_text, client)
    get_logger().info("gate exchange", stage="gate", outcome=stage)
    state.stage = stage
    state.owner = "chat"
    state.authenticated = session.verified
    session.stage = stage

    if session.verified:
        state.handoffs.append(
            Handoff(frm="none", to="chat", kind="gate_open", reason="Identity verified.")
        )
        # Verification just completed. Open immediately from the enrolment
        # picture rather than making the beneficiary speak again first.
        blob = release_blob(session)
        if blob is None:  # pragma: no cover - defensive
            state.reply = "Verification did not complete. Please send your beneficiary ID again."
            return state
        state.reply = _greeting(blob)
        state.owner = "chat"
        state.stage = "open"
        state.authenticated = True
        state.blob_ref = blob.beneficiary.foundationalId
        session.stage = "open"
        session.history.append({"role": "assistant", "text": state.reply})
        return state

    state.reply = reply
    return state


def _greeting(blob: Any) -> str:
    first = _display_name(blob)
    return (
        f"Welcome, {first}. On my records you are enrolled in: "
        f"{_enrolment_summary(blob)}. What brings you here today?"
    )


def _display_name(blob: Any) -> str:
    """First name from the registry attributes, never invented."""
    for registry in blob.registries:
        for register in registry.registers:
            first = (register.attributes or {}).get("first_name")
            if first:
                return str(first)
    return "there"


def _handle_greeting(session: AuthSession, state: TurnState, blob: Any) -> TurnState:
    state.owner = "chat"
    state.stage = "open"
    state.reply = _greeting(blob)
    state.record("assistant", state.reply)
    session.stage = "open"
    session.history = list(state.history)
    return state


def _light_context(blob: Any) -> str:
    """Reference data the front line may read and quote directly.

    The line is drawn between reference data and transaction data, not between
    everything and nothing. Connection numbers, programme names, and enrolment
    state are single-record lookups, so the chat agent must be able to answer
    them itself. Anything that requires reading across cycles, dispatches,
    orders, or blockers stays behind the reasoning boundary.

    Enforcing this by what the model is given beats asking it to decline
    analysis it can already see.
    """
    programmes = []
    for program in blob.programs:
        entry: dict[str, Any] = {
            "program_name": program.programName,
            "programme_status": program.programStatus,
            "enrolment_statuses": sorted(
                {e.enrolmentStatus for e in program.enrolments if e.enrolmentStatus}
            ),
        }
        connection = program.lpgConnection
        if connection is not None:
            entry["connection"] = {
                "connection_number": connection.connectionNumber,
                "connection_status": connection.connectionStatus,
                "distributor": connection.distributorMnemonic,
                "subsidy_enabled": connection.subsidyEnabled,
                "last_collected_cylinder_date": connection.lastCollectedCylinderDate,
            }
        programmes.append(entry)

    return json.dumps(
        {
            "foundational_id": blob.beneficiary.foundationalId,
            "display_name": _display_name(blob),
            "programmes": programmes,
            "note": (
                "You can read and quote this reference data directly. You cannot "
                "see current cycle status, dispatch schedules, payment orders, or "
                "blockers. Any question about those requires a hand off."
            ),
        },
        indent=2,
        ensure_ascii=False,
    )


async def _handle_authenticated_turn(
    adapters: dict[str, AgentAdapter],
    state: TurnState,
    blob: Beneficiary360Blob,
    context: str,
) -> TurnState:
    state.record("user", state.user_text)
    log = get_logger()

    # Front line sees enrolment only. Status, blockers, and orders stay behind
    # the reasoning boundary.
    log.info("asking front line to route this turn", stage="routing")
    reply, route = await run_chat(adapters["chat"], state, _light_context(blob))
    state.record("chat", reply)
    log.info("routing decided", stage="routing", route=route, reply_chars=len(reply))

    if route != "reasoning":
        state.owner = "chat"
        state.reply = reply
        return state

    register_handoff(state, "reasoning", HANDOFF_INTENT)
    state.owner = "reasoning"
    log.info("handed to reasoning", stage="handoff", owner="reasoning")

    candidate = await run_reasoning(adapters["reasoning"], state, context)
    objection: str | None = None
    verdict = "pass"

    for attempt in range(MAX_REVISIONS + 1):
        verdict, objection = await run_qa(adapters["qa"], state, context, candidate)
        state.qa_verdict = verdict
        state.qa_objections = objection or None
        if verdict == "pass":
            log.info("evaluation passed", stage="qa", attempt=attempt + 1)
            break
        log.warning(
            "evaluation failed, sending back",
            stage="qa",
            attempt=attempt + 1,
            of=MAX_REVISIONS + 1,
            reason=_first_line(objection),
        )
        state.handoffs.append(
            Handoff(frm="qa", to="reasoning", kind="qa_fail", reason=_first_line(objection))
        )
        if attempt == MAX_REVISIONS:
            log.error("evaluation never passed, failing closed", stage="qa")
            break
        state.revision_rounds += 1
        candidate = await run_reasoning(adapters["reasoning"], state, context, objection)

    if verdict == "pass":
        state.handoffs.append(
            Handoff(
                frm="qa", to="reasoning", kind="qa_pass", reason="Verified against session data."
            )
        )

    if verdict != "pass":
        # Fail closed. Never deliver an unvalidated candidate.
        state.reply = (
            "I have your request but I am not able to give you a verified answer "
            "on it right now. I would rather not guess with your records. Could you "
            "rephrase what you are asking, or tell me a little more?"
        )
        state.owner = "chat"
        state.record("chat", state.reply)
        return state

    state.reply = candidate
    state.stage = "reasoned"
    state.record("reasoning", candidate)
    return state


def _first_line(text: str) -> str:
    return (
        (text or "").strip().splitlines()[0][:160] if (text or "").strip() else "Evaluation failed."
    )
