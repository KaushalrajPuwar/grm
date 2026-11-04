"""Route real turns through chat, reasoning, and QA with fixed model replies."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from grm.harness import turn_loop


def test_missing_snapshot_blocks_all_model_calls(verified_session, client, adapters):
    verified_session.blob = None

    state = asyncio.run(turn_loop.handle_turn(verified_session, "My payment?", client))

    assert state.authenticated is False
    assert state.stage == "id_prompt"
    assert verified_session.stage == "id_prompt"
    assert state.blob_ref is None
    assert "Verification expired" in state.reply
    adapters["chat"].invoke.assert_not_awaited()
    adapters["reasoning"].invoke.assert_not_awaited()
    adapters["qa"].invoke.assert_not_awaited()


@pytest.mark.parametrize(
    "response",
    ["ROUTE: stay\nReference answer", "Reference answer", "ROUTE: unknown\nReference answer"],
)
def test_chat_keeps_the_turn_unless_it_requests_reasoning(
    verified_session, client, adapters, response
):
    question = "Connection number?"
    adapters["chat"].invoke.side_effect = [AIMessage(content=response)]

    state = asyncio.run(turn_loop.handle_turn(verified_session, question, client))

    assert state.owner == "chat"
    assert "Reference answer" in state.reply
    assert state.handoffs == []
    assert state.qa_verdict is None
    assert verified_session.history == state.history
    assert verified_session.history[-1] == {"role": "chat", "text": state.reply}
    adapters["reasoning"].invoke.assert_not_awaited()
    adapters["qa"].invoke.assert_not_awaited()


def test_chat_sees_reference_data_and_prior_history(verified_session, client, adapters):
    question = "Connection number?"
    prior_history = [{"role": "assistant", "text": "What brings you here?"}]
    verified_session.history = list(prior_history)
    adapters["chat"].invoke.side_effect = [
        AIMessage(content="ROUTE: stay\nYour connection is CONN-TEST-001.")
    ]

    asyncio.run(turn_loop.handle_turn(verified_session, question, client))

    prompt, context, history = adapters["chat"].invoke.await_args.args
    reference = json.loads(context)
    assert question in prompt
    assert history == prior_history
    assert set(reference) == {"foundational_id", "display_name", "programmes", "note"}
    assert reference["foundational_id"] == "TEST-001"
    assert reference["display_name"] == "Example"
    assert reference["programmes"] == [
        {
            "program_name": "Test Scheme",
            "programme_status": "ACTIVE",
            "enrolment_statuses": ["ENROLLED"],
            "connection": {
                "connection_number": "CONN-TEST-001",
                "connection_status": None,
                "distributor": None,
                "subsidy_enabled": None,
                "last_collected_cylinder_date": None,
            },
        }
    ]


def test_qa_pass_releases_the_answer(verified_session, client, adapters, blob):
    question = "Why blocked?"
    candidate = "  Supported answer.  "
    adapters["chat"].invoke.side_effect = [AIMessage(content="rOuTe: reasoning\nLet me check.")]
    adapters["reasoning"].invoke.side_effect = [AIMessage(content=candidate)]
    adapters["qa"].invoke.side_effect = [AIMessage(content="VERDICT: PASS\nChecked.")]

    state = asyncio.run(turn_loop.handle_turn(verified_session, question, client))

    assert state.reply == "Supported answer."
    assert (state.owner, state.stage) == ("reasoning", "reasoned")
    assert (state.qa_verdict, state.qa_objections, state.revision_rounds) == ("pass", None, 0)
    assert [handoff.kind for handoff in state.handoffs] == ["to_reasoning", "qa_pass"]
    reasoning_prompt, context, history = adapters["reasoning"].invoke.await_args.args
    assert question in reasoning_prompt
    assert json.loads(context) == blob.for_model()
    assert history == [{"role": "chat", "text": "Let me check."}]
    qa_prompt, qa_context = adapters["qa"].invoke.await_args.args
    assert "## Draft answer\nSupported answer." in qa_prompt
    assert qa_context == context


def test_qa_objection_reaches_the_revision(verified_session, client, adapters):
    objection = "Wrong amount.\nRead the payment record."
    adapters["chat"].invoke.side_effect = [AIMessage(content="ROUTE: reasoning\nChecking.")]
    adapters["reasoning"].invoke.side_effect = [
        AIMessage(content="Unverified draft."),
        AIMessage(content="Corrected answer."),
    ]
    adapters["qa"].invoke.side_effect = [
        AIMessage(content=f"VERDICT: fail\n{objection}"),
        AIMessage(content="VERDICT: pass"),
    ]

    state = asyncio.run(turn_loop.handle_turn(verified_session, "Payment amount?", client))

    assert state.reply == "Corrected answer."
    assert (state.qa_verdict, state.qa_objections, state.revision_rounds) == ("pass", None, 1)
    assert [handoff.kind for handoff in state.handoffs] == ["to_reasoning", "qa_fail", "qa_pass"]
    assert state.handoffs[1].reason == "Wrong amount."
    revision_prompt = adapters["reasoning"].invoke.await_args_list[1].args[0]
    assert objection in revision_prompt
    assert "Unverified draft." not in str(verified_session.history)
    qa_prompt = adapters["qa"].invoke.await_args.args[0]
    assert "## Draft answer\nCorrected answer." in qa_prompt


@pytest.mark.parametrize("verdict", ["VERDICT: fail\nUnsupported amount.", "No verdict supplied."])
def test_repeated_qa_rejection_withholds_all_drafts(verified_session, client, adapters, verdict):
    reasoning = adapters["reasoning"].invoke
    qa = adapters["qa"].invoke
    adapters["chat"].invoke.side_effect = [AIMessage(content="ROUTE: reasoning\nChecking.")]
    reasoning.side_effect = [
        AIMessage(content="Draft one."),
        AIMessage(content="Draft two."),
        AIMessage(content="Draft three."),
    ]
    qa.side_effect = [AIMessage(content=verdict)] * 3

    state = asyncio.run(turn_loop.handle_turn(verified_session, "Payment status?", client))

    assert reasoning.await_count == qa.await_count == 3
    assert state.qa_verdict == "fail"
    assert state.revision_rounds == 2
    assert state.owner == "chat"
    assert [handoff.kind for handoff in state.handoffs] == [
        "to_reasoning",
        "qa_fail",
        "qa_fail",
        "qa_fail",
    ]
    assert "not able to give you a verified answer" in state.reply
    assert "Draft" not in str(verified_session.history)
    assert verified_session.history[-1] == {"role": "chat", "text": state.reply}
    assert state.qa_objections


def test_disabled_qa_releases_the_answer_without_evaluation(
    verified_session, client, adapters, monkeypatch
):
    settings = SimpleNamespace(qa_enabled=False)
    candidate = "Candidate with QA disabled."
    monkeypatch.setattr(turn_loop, "get_settings", lambda: settings)
    adapters["chat"].invoke.side_effect = [AIMessage(content="ROUTE: reasoning\nChecking.")]
    adapters["reasoning"].invoke.side_effect = [AIMessage(content=candidate)]

    state = asyncio.run(turn_loop.handle_turn(verified_session, "Payment status?", client))

    assert state.reply == candidate
    assert state.owner == "reasoning"
    assert state.stage == "reasoned"
    assert (state.qa_verdict, state.revision_rounds) == (None, 0)
    assert [handoff.kind for handoff in state.handoffs] == ["to_reasoning"]
    assert verified_session.history[-1] == {"role": "reasoning", "text": state.reply}
    adapters["qa"].invoke.assert_not_awaited()


def test_next_turn_routes_through_chat_after_reasoning(verified_session, client, adapters):
    adapters["chat"].invoke.side_effect = [
        AIMessage(content="ROUTE: reasoning\nChecking."),
        AIMessage(content="ROUTE: stay\nReference answer."),
    ]
    adapters["reasoning"].invoke.side_effect = [AIMessage(content="Verified analysis.")]
    adapters["qa"].invoke.side_effect = [AIMessage(content="VERDICT: pass")]
    asyncio.run(turn_loop.handle_turn(verified_session, "Payment status?", client))

    state = asyncio.run(turn_loop.handle_turn(verified_session, "Which scheme?", client))

    assert state.owner == "chat"
    assert state.reply == "Reference answer."
    assert state.handoffs == []
    assert adapters["chat"].invoke.await_count == 2
    assert adapters["reasoning"].invoke.await_count == 1
    assert adapters["qa"].invoke.await_count == 1
    next_turn_history = adapters["chat"].invoke.await_args.args[2]
    assert {"role": "reasoning", "text": "Verified analysis."} in next_turn_history
