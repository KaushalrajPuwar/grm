"""Routing: chat agent decides stay or hand off, per turn.

Turn-by-turn ownership, never a permanent transfer. The chat agent evaluates
every authenticated turn against the handoff test in its constitution and emits
an explicit verdict, so routing is a decided, inspectable outcome rather than
an agent's free choice.

Verdict protocol: the chat agent returns a single line `ROUTE: stay` or
`ROUTE: reasoning` followed by its reply. Anything else is treated as `stay`.
"""

from __future__ import annotations

import re

from grm.agents.base import AgentAdapter
from grm.harness.state import Handoff, HandoffKind, Owner, TurnState

ROUTE_RE = re.compile(r"ROUTE:\s*(stay|reasoning)", re.IGNORECASE)

MAX_REVISIONS = 2

#: Handoff trigger shown in the agent panel, keyed by the route decision.
HANDOFF_INTENT = "Requires relations read across enrolment, cycle, order, and blocker records."


async def run_chat(adapter: AgentAdapter, state: TurnState, context: str) -> tuple[str, str]:
    """Chat agent turn. Returns (reply, route) where route is stay or reasoning."""
    text = _prompt_for(state)
    # The current user text is sent separately, so drop it from history.
    history = [
        e
        for e in state.history
        if not (e.get("role") == "user" and e.get("text") == state.user_text)
    ]
    message = await adapter.invoke(text, context, history)
    reply = message.content if isinstance(message.content, str) else str(message.content)

    match = ROUTE_RE.search(reply)
    if match:
        route = match.group(1).lower()
        reply = ROUTE_RE.sub("", reply).strip()
    else:
        route = "stay"

    return reply.strip(), route


async def run_reasoning(
    adapter: AgentAdapter, state: TurnState, context: str, objection: str | None = None
) -> str:
    """Reasoning agent turn. Returns the candidate answer.

    On a corrected round the specific evaluation objection is passed in, so the
    revision targets the defect rather than rewording around it.
    """
    text = _reasoning_prompt(state, objection)
    history = [
        e
        for e in state.history
        if not (e.get("role") == "user" and e.get("text") == state.user_text)
    ]
    message = await adapter.invoke(text, context, history)
    return (message.content if isinstance(message.content, str) else str(message.content)).strip()


QA_RE = re.compile(r"VERDICT:\s*(pass|fail)", re.IGNORECASE)


async def run_qa(
    adapter: AgentAdapter, state: TurnState, context: str, candidate: str
) -> tuple[str, str]:
    """QA check. Returns (verdict, objection).

    Verification only. The QA agent is not asked to produce an answer, so a
    second opinion is never substituted for the reasoning agent's work.
    """
    text = (
        "A draft answer is prepared for delivery to a beneficiary. "
        "Verify it against the session data below. Check whether each factual "
        "claim is traceable to a value in the data, whether values are correct, "
        "whether conclusions are supported, whether field meanings were read "
        "inside this scheme's own definitions, and whether claims about missing "
        "data are stated as missing rather than as fact about the person.\n\n"
        f"## Draft answer\n{candidate}\n\n"
        "Reply with the verdict on the first line in the form `VERDICT: pass` or "
        "`VERDICT: fail`. On fail, name each specific defect on its own line, "
        "referring to the claim and the data. Do not write a replacement answer."
    )
    message = await adapter.invoke(text, context)
    raw = message.content if isinstance(message.content, str) else str(message.content)
    raw = raw.strip()

    match = QA_RE.search(raw)
    if not match:
        # An unparseable verdict is not a pass. Fail closed.
        return "fail", f"QA verdict unreadable. Raw: {raw.strip()[:200]}"
    verdict = match.group(1).lower()
    objection = QA_RE.sub("", raw).strip()
    return verdict, objection if verdict == "fail" else ""


def _prompt_for(state: TurnState) -> str:
    if state.stage == "greet":
        return (
            "The beneficiary has just passed identity verification. Open the "
            "conversation using their enrolment information.\n\n---\n\n"
            "Begin your reply with `ROUTE: stay` on its own line, then your message."
        )
    return (
        f"{state.user_text}\n\n---\n\n"
        "Begin your reply with `ROUTE: stay` or `ROUTE: reasoning`, on its own line. "
        "Then write your message to the beneficiary."
    )


def _reasoning_prompt(state: TurnState, objection: str | None) -> str:
    base = (
        "The chat agent has judged that this question requires analysis "
        "across records rather than a lookup. Take the lead for this turn.\n\n"
        f"Beneficiary asked: {state.user_text}"
    )
    if objection:
        base += (
            "\n\nYour previous candidate was rejected on evaluation. The specific "
            f"objections were:\n{objection}\n\nCorrect the defect. Do not hedge "
            "language over a claim that is still there."
        )
    return base


def register_handoff(state: TurnState, to: Owner, reason: str) -> None:
    kind: HandoffKind = "to_reasoning" if to == "reasoning" else "to_chat"
    state.handoffs.append(Handoff(frm=state.owner, to=to, kind=kind, reason=reason))
