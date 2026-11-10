"""Callers get the next prompt without sharing verification or history."""

import asyncio

from langchain_core.messages import AIMessage

from grm.channels.schemas import TurnRequest
from grm.channels.service import DialogueService


def test_unknown_status_and_reset_do_not_create_sessions(client):
    service = DialogueService(client)
    call_id = "new-call"
    expected = {
        "session_id": call_id,
        "known": False,
        "authenticated": False,
        "stage": "new",
    }

    assert service.status(call_id) == expected
    assert service.reset(call_id) is True
    assert service.reset(call_id) is True
    assert service.status(call_id) == expected
    client.find_by_identifier.assert_not_called()


def test_known_identifier_prompts_for_otp(client, adapters, gate_io):
    service = DialogueService(client)
    request = TurnRequest(session_id="call-a", text=" test-001 ")

    response = asyncio.run(service.turn(request))

    assert response.stage == "otp_sent"
    assert response.expects == "otp"
    assert response.pending_otp is True
    assert response.authenticated is False
    assert response.handoffs == []
    assert service.status("call-a") == {
        "session_id": "call-a",
        "known": True,
        "authenticated": False,
        "stage": "otp_sent",
    }
    gate_io.clear.assert_not_called()
    adapters["chat"].invoke.assert_not_awaited()
    adapters["reasoning"].invoke.assert_not_awaited()
    adapters["qa"].invoke.assert_not_awaited()


def test_verified_greeting_keeps_records_and_code_private(client, adapters, gate_io):
    service = DialogueService(client)
    verification = TurnRequest(session_id="call-a", text="1234")
    asyncio.run(service.turn(TurnRequest(session_id="call-a", text="TEST-001")))

    response = asyncio.run(service.turn(verification))

    assert response.stage == "open"
    assert response.expects == "message"
    assert response.pending_otp is False
    assert response.authenticated is True
    assert "Example" in response.reply
    assert "Test Scheme (enrolled)" in response.reply
    payload = response.model_dump(mode="json")
    assert payload["handoffs"] == [
        {"frm": "none", "to": "chat", "kind": "gate_open", "reason": "Identity verified."}
    ]
    assert set(payload) == {
        "session_id",
        "reply",
        "owner",
        "stage",
        "authenticated",
        "handoffs",
        "qa_verdict",
        "revision_rounds",
        "pending_otp",
        "expects",
    }
    gate_io.clear.assert_called_once_with()
    adapters["chat"].invoke.assert_not_awaited()


def test_one_calls_code_cannot_verify_another(client, adapters, gate_io):
    service = DialogueService(client)
    first_call = "call-a"
    second_call = "call-b"
    first_code = "1234"
    asyncio.run(service.turn(TurnRequest(session_id=first_call, text="TEST-001")))
    asyncio.run(service.turn(TurnRequest(session_id=second_call, text="TEST-001")))

    rejected = asyncio.run(service.turn(TurnRequest(session_id=second_call, text=first_code)))
    accepted = asyncio.run(service.turn(TurnRequest(session_id=first_call, text=first_code)))

    assert rejected.authenticated is False
    assert rejected.stage == "otp_sent"
    assert rejected.expects == "otp"
    assert accepted.authenticated is True
    assert service.status(second_call)["authenticated"] is False
    assert service.status(first_call)["authenticated"] is True
    assert gate_io.issue.call_count == 3
    gate_io.clear.assert_called_once_with()


def test_reset_requires_identity_again_for_only_that_call(client, adapters, gate_io):
    service = DialogueService(client)
    reset_call = "call-a"
    other_call = "call-b"
    asyncio.run(service.turn(TurnRequest(session_id=reset_call, text="TEST-001")))
    asyncio.run(service.turn(TurnRequest(session_id=reset_call, text="1234")))
    asyncio.run(service.turn(TurnRequest(session_id=other_call, text="TEST-001")))

    service.reset(reset_call)
    restarted = asyncio.run(service.turn(TurnRequest(session_id=reset_call, text="")))
    other = asyncio.run(service.turn(TurnRequest(session_id=other_call, text="5678")))

    assert restarted.authenticated is False
    assert restarted.stage == "id_prompt"
    assert restarted.expects == "beneficiary_id"
    assert "Example" not in restarted.reply
    assert other.authenticated is True
    assert other.session_id == other_call
    assert gate_io.issue.call_count == 2
    assert gate_io.clear.call_count == 2


def test_conversation_history_does_not_cross_sessions(client, adapters, gate_io):
    service = DialogueService(client)
    first_question = "First call question?"
    second_question = "Second question?"
    asyncio.run(service.turn(TurnRequest(session_id="call-a", text="TEST-001")))
    asyncio.run(service.turn(TurnRequest(session_id="call-a", text="1234")))
    asyncio.run(service.turn(TurnRequest(session_id="call-b", text="TEST-001")))
    greeting = asyncio.run(service.turn(TurnRequest(session_id="call-b", text="5678")))
    adapters["chat"].invoke.side_effect = [
        AIMessage(content="ROUTE: stay\nFirst call answer."),
        AIMessage(content="ROUTE: stay\nSecond call answer."),
    ]
    asyncio.run(service.turn(TurnRequest(session_id="call-a", text=first_question)))

    response = asyncio.run(service.turn(TurnRequest(session_id="call-b", text=second_question)))

    prompt, _, history = adapters["chat"].invoke.await_args.args
    assert second_question in prompt
    assert history == [{"role": "assistant", "text": greeting.reply}]
    assert response.reply == "Second call answer."
    assert response.authenticated is True
