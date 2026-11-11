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
from collections.abc import Awaitable, Callable
from typing import Any

from grm.agents.base import AgentAdapter, get_adapters
from grm.auth.gate import AuthSession, drop_verification, release_blob
from grm.beneficiary360.client import Beneficiary360Client
from grm.beneficiary360.schemas import Beneficiary360Blob
from grm.config import get_settings
from grm.harness.gate_flow import LOOKING_INTO_IT, WELCOME, handle_gate_message
from grm.harness.routing import (
    HANDOFF_INTENT,
    MAX_REVISIONS,
    register_handoff,
    run_chat,
    run_qa,
    run_reasoning,
    run_single,
)
from grm.harness.state import Handoff, Owner, TurnState
from grm.observability.logging import get_logger


def _context_from_blob(blob: Any) -> str:
    return json.dumps(blob.for_model(), indent=2, ensure_ascii=False)


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
        result = await _handle_pre_auth(session, user_text, client, state, adapters)
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

    if session.stage == "confirm_identity":
        return _handle_confirmation(session, state, blob, user_text)

    result = await _handle_authenticated_turn(adapters, state, blob, context)
    session.stage = result.stage
    session.history = list(result.history)
    return result


async def _handle_pre_auth(
    session: AuthSession,
    user_text: str,
    client: Beneficiary360Client,
    state: TurnState,
    adapters: dict[str, AgentAdapter],
) -> TurnState:
    """The identity gate, before any record is open.

    The caller always speaks first. Their first turn is answered with the
    welcome, once. Every later turn is an attempt at the registration number:
    a match moves to name confirmation, and anything else gets the same request
    for the number. There is no content sniffing, because a distressed caller
    may open anywhere.
    """
    log = get_logger()

    if state.stage == "greet":
        state.stage = "id_prompt"
        state.reply = WELCOME
        state.owner = "chat"
        state.authenticated = False
        session.stage = "id_prompt"
        session.history.append({"role": "assistant", "text": state.reply})
        log.info("gate greeted", stage="gate", outcome="id_prompt")
        return state

    reply, stage = await handle_gate_message(session, user_text, client, adapters["identifier"])
    log.info("gate exchange", stage="gate", outcome=stage)

    state.stage = stage
    state.owner = "chat"
    state.authenticated = session.verified
    session.stage = stage

    if session.verified:
        state.handoffs.append(
            Handoff(frm="none", to="chat", kind="gate_open", reason="Identity verified.")
        )
        # Verification just completed. Confirm the name before opening the
        # conversation, so a wrong record is caught by the caller, not by the
        # agent reading out someone else's benefits.
        blob = release_blob(session)
        if blob is None:  # pragma: no cover - defensive
            state.reply = (
                "Verification did not complete. Please share your registration number again."
            )
            return state
        state.reply = _confirmation_prompt(blob)
        state.stage = "confirm_identity"
        state.authenticated = True
        state.blob_ref = blob.beneficiary.foundationalId
        session.stage = "confirm_identity"
        session.history.append({"role": "assistant", "text": state.reply})
        return state

    if stage == "otp_sent":
        state.reply = reply
        return state

    # Not a registration number. Ask for it again, in the same words every time.
    state.reply = LOOKING_INTO_IT
    return state


#: Words that confirm the caller is the person on the record.
_AFFIRMATIVE = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "yup",
        "correct",
        "right",
        "speaking",
        "that's me",
        "that is me",
        "it is",
        "it's me",
        "sure",
        "ok",
        "okay",
    }
)

#: Words that deny it.
_NEGATIVE = frozenset(
    {"no", "nope", "nah", "wrong", "incorrect", "not me", "that's not me", "that is not me"}
)


def _confirmation_prompt(blob: Any) -> str:
    """Ask the caller to confirm the name on the record."""
    return f"Thank you. Am I talking with {_full_name(blob)}?"


def _confirmation_retry(blob: Any) -> str:
    return f"Sorry, I did not catch that. Am I talking with {_full_name(blob)}?"


def _record_opening(blob: Any) -> str:
    """Open the conversation with what the record shows. Speech ready."""
    active = [
        program
        for program in blob.programs
        if any(entry.enrolmentStatus in {"ENROLLED", "APPLIED"} for entry in program.enrolments)
    ]
    if not active:
        return (
            "Thank you for confirming. I do not see an active benefit on your record "
            "at the moment. What would you like to ask about?"
        )
    if len(active) == 1:
        return (
            "Thank you for confirming. I am seeing that you are registered for "
            f"a benefit: {_spoken_enrolments(blob)}."
        )
    return (
        "Thank you for confirming. I am seeing that you are registered for "
        f"multiple benefits: {_spoken_enrolments(blob)}."
    )


def _full_name(blob: Any) -> str:
    """Full name from the registry attributes, never invented."""
    for registry in blob.registries:
        for register in registry.registers:
            attrs = register.attributes or {}
            first, last = attrs.get("first_name"), attrs.get("last_name")
            if first and last:
                return f"{first} {last}"
            if first:
                return str(first)
    return "the person on this record"


def _display_name(blob: Any) -> str:
    """First name, for prompts that address the caller directly."""
    return _full_name(blob).split()[0]


def _spoken_enrolments(blob: Any) -> str:
    """Programme names as a spoken phrase. No brackets, no status codes."""
    parts: list[str] = []
    for program in blob.programs:
        statuses = {e.enrolmentStatus for e in program.enrolments if e.enrolmentStatus}
        if "ENROLLED" in statuses:
            parts.append(f"the {program.programName}")
        elif "APPLIED" in statuses:
            parts.append(f"the {program.programName}, which is still an application")

    if not parts:
        return "no benefits at the moment"
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def _handle_confirmation(
    session: AuthSession, state: TurnState, blob: Any, user_text: str
) -> TurnState:
    """Confirm the caller is the person on the record, then open the call."""
    said = " ".join(user_text.lower().replace(".", " ").replace(",", " ").split())

    state.owner = "chat"
    state.authenticated = True
    state.blob_ref = blob.beneficiary.foundationalId

    if said in _AFFIRMATIVE or any(
        said.startswith(word + " ") for word in _AFFIRMATIVE if " " not in word
    ):
        state.stage = "open"
        state.reply = _record_opening(blob)
        session.stage = "open"
        session.history.append({"role": "assistant", "text": state.reply})
        return state

    if said in _NEGATIVE or said.startswith("no "):
        # Wrong person. Drop verification and the snapshot together, then start
        # the identity step again.
        drop_verification(session)
        state.authenticated = False
        state.stage = "id_prompt"
        state.reply = (
            "I am sorry about that. I will close this record. "
            "Could you please share the registration number again?"
        )
        session.stage = "id_prompt"
        session.history.append({"role": "assistant", "text": state.reply})
        return state

    state.stage = "confirm_identity"
    state.reply = _confirmation_retry(blob)
    session.stage = "confirm_identity"
    session.history.append({"role": "assistant", "text": state.reply})
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

    if get_settings().single_agent:
        # One agent owns the turn: reception, lookup and analysis in one call.
        # It sees the full snapshot, so there is no routing decision and no
        # discarded draft.
        log.info("single agent handling turn", stage="agent", model_role="single")
        candidate = await run_single(adapters["single"], state, context)
        candidate, verdict = await _evaluate(
            adapters,
            state,
            context,
            candidate,
            target="single",
            revise=lambda objection: run_single(adapters["single"], state, context, objection),
        )
        if verdict != "pass":
            return _fail_closed(state, "single")

        state.owner = "single"
        state.stage = "reasoned"
        state.reply = candidate
        state.record("single", candidate)
        return state

    # Two-agent flow: the front line routes, the reasoning agent analyses.
    # The front line sees enrolment only; status, blockers, and orders stay
    # behind the reasoning boundary.
    log.info("asking front line to route this turn", stage="routing")
    reply, route = await run_chat(adapters["chat"], state, _light_context(blob))
    state.record("chat", reply)
    log.info("routing decided", stage="routing", route=route, reply_chars=len(reply))

    if route != "reasoning":
        state.owner = "chat"
        state.reply = reply
        return state

    register_handoff(state, "reasoning", HANDOFF_INTENT)
    log.info("handed to reasoning", stage="handoff", owner="reasoning")

    candidate = await run_reasoning(adapters["reasoning"], state, context)
    candidate, verdict = await _evaluate(
        adapters,
        state,
        context,
        candidate,
        target="reasoning",
        revise=lambda objection: run_reasoning(adapters["reasoning"], state, context, objection),
    )
    if verdict != "pass":
        return _fail_closed(state, "chat")

    state.owner = "reasoning"
    state.stage = "reasoned"
    state.reply = candidate
    state.record("reasoning", candidate)
    return state


async def _evaluate(
    adapters: dict[str, AgentAdapter],
    state: TurnState,
    context: str,
    candidate: str,
    target: Owner,
    revise: Callable[[str], Awaitable[str]],
) -> tuple[str, str]:
    """Run the QA gate over a candidate. Returns the possibly revised answer.

    When QA is disabled this is a pass-through. When enabled, a failure is sent
    back to the agent that produced the candidate, not to a different role.
    """
    log = get_logger()
    if not get_settings().qa_enabled:
        log.info("evaluation skipped", stage="qa", reason="QA_ENABLED is false")
        return candidate, "pass"

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
            Handoff(frm="qa", to=target, kind="qa_fail", reason=_first_line(objection))
        )
        if attempt == MAX_REVISIONS:
            log.error("evaluation never passed, failing closed", stage="qa")
            break
        state.revision_rounds += 1
        candidate = await revise(objection or "")

    if verdict == "pass":
        state.handoffs.append(
            Handoff(frm="qa", to=target, kind="qa_pass", reason="Verified against session data.")
        )
    return candidate, verdict


def _fail_closed(state: TurnState, owner: Owner) -> TurnState:
    """Never deliver an unvalidated candidate."""
    state.reply = (
        "I have your request but I am not able to give you a verified answer "
        "on it right now. I would rather not guess with your records. Could you "
        "rephrase what you are asking, or tell me a little more?"
    )
    state.owner = owner
    state.record(owner, state.reply)
    return state


def _first_line(text: str) -> str:
    return (
        (text or "").strip().splitlines()[0][:160] if (text or "").strip() else "Evaluation failed."
    )
