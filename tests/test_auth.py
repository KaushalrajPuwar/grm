"""Beneficiary records stay behind verification, including retries and resets."""

from unittest.mock import Mock, call

import pytest

from grm.auth.gate import (
    GateStatus,
    begin_session,
    mask_mobile,
    release_blob,
    reset,
    submit_identifier,
    submit_otp,
)
from grm.harness.gate_flow import OTP_RETRY, handle_gate_message


def test_identifier_is_normalized_before_issuing_a_code(client, blob):
    session = begin_session()
    entered_id = "  test-001\n"
    issue = Mock(return_value="1234")

    state = submit_identifier(session, entered_id, client, issue)

    client.find_by_identifier.assert_called_once_with("TEST-001")
    client.fetch_blob.assert_not_called()
    issue.assert_called_once_with("TEST-001")
    assert state is session.state
    assert state.status is GateStatus.OTP_SENT
    assert state.identifier == "TEST-001"
    assert state.attempts == 1
    assert state.masked_mobile == "*******101"
    assert session.blob is blob
    assert release_blob(session) is None


def test_unknown_identifier_revokes_existing_verification(verified_session, client):
    issue = Mock()

    state = submit_identifier(verified_session, " unknown ", client, issue)

    issue.assert_not_called()
    assert state.status is GateStatus.DENIED
    assert state.identifier == "UNKNOWN"
    assert state.attempts == 2
    assert verified_session.expected_otp is None
    assert verified_session.blob is None
    assert release_blob(verified_session) is None


def test_unknown_identifier_cancels_pending_code(client):
    session = begin_session()
    submit_identifier(session, "TEST-001", client, lambda _: "1234")
    submit_identifier(session, "UNKNOWN", client, Mock())

    state = submit_otp(session, "1234")

    assert state.status is GateStatus.AWAITING_ID
    assert state.attempts == 2
    assert release_blob(session) is None


@pytest.mark.parametrize("code", ["", "123", "12345", "1235", "\uff11\uff12\uff13\uff14", "abcd"])
def test_wrong_code_keeps_records_locked(client, code):
    session = begin_session()
    submit_identifier(session, "TEST-001", client, lambda _: "1234")

    state = submit_otp(session, code)

    assert state.status is GateStatus.DENIED
    assert state.identifier == "TEST-001"
    assert state.masked_mobile == "*******101"
    assert state.attempts == 1
    assert session.expected_otp == "1234"
    assert release_blob(session) is None


def test_correct_code_unlocks_records_once(client, blob):
    session = begin_session()
    entered_code = " 1234\n"
    submit_identifier(session, "TEST-001", client, lambda _: "1234")

    state = submit_otp(session, entered_code)

    assert state.status is GateStatus.VERIFIED
    assert session.expected_otp is None
    assert release_blob(session) is blob
    assert state.attempts == 1


@pytest.mark.parametrize("code", ["", "1234"])
def test_code_without_pending_challenge_is_rejected(code):
    session = begin_session()

    state = submit_otp(session, code)

    assert state.status is GateStatus.AWAITING_ID
    assert state.attempts == 0
    assert release_blob(session) is None


def test_consumed_code_cannot_authenticate_again(verified_session):
    state = submit_otp(verified_session, "1234")

    assert state.status is GateStatus.AWAITING_ID
    assert not verified_session.verified
    assert release_blob(verified_session) is None


def test_codes_are_scoped_to_their_session(client, blob):
    first = begin_session()
    second = begin_session()
    first_code = "1234"
    second_code = "5678"
    submit_identifier(first, "TEST-001", client, lambda _: first_code)
    submit_identifier(second, "TEST-001", client, lambda _: second_code)

    submit_otp(second, first_code)
    submit_otp(first, first_code)

    assert release_blob(first) is blob
    assert release_blob(second) is None
    assert second.state.status is GateStatus.DENIED
    assert second.expected_otp == second_code

    submit_otp(second, second_code)

    assert release_blob(second) is blob


def test_reset_clears_verification_and_history(verified_session):
    verified_session.history.append({"role": "user", "text": "Synthetic question"})

    fresh = reset(verified_session)

    assert fresh is not verified_session
    assert fresh.state.status is GateStatus.AWAITING_ID
    assert fresh.blob is None
    assert fresh.expected_otp is None
    assert fresh.stage == "greet"
    assert fresh.history == []
    assert release_blob(fresh) is None


@pytest.mark.parametrize(
    ("mobile", "masked"),
    [("", ""), ("12", "**"), ("123", "***"), ("+00 (000) 001-01", "*******101")],
)
def test_mobile_shows_only_the_last_three_digits(mobile, masked):
    assert mask_mobile(mobile) == masked


def test_wrong_code_triggers_a_new_code(client, gate_io):
    session = begin_session()
    handle_gate_message(session, "TEST-001", client)

    reply, stage = handle_gate_message(session, "9999", client)

    assert reply == OTP_RETRY
    assert stage == "otp_sent"
    assert session.expected_otp == "5678"
    assert session.state.attempts == 2
    assert release_blob(session) is None
    gate_io.clear.assert_not_called()
    assert gate_io.issue.call_args_list == [call("TEST-001"), call("TEST-001")]


def test_old_code_stays_invalid_after_a_retry(client, gate_io, blob):
    session = begin_session()
    handle_gate_message(session, "TEST-001", client)
    handle_gate_message(session, "9999", client)

    rejected = handle_gate_message(session, "1234", client)

    assert rejected == (OTP_RETRY, "otp_sent")
    assert release_blob(session) is None
    assert session.expected_otp == "9012"
    gate_io.clear.assert_not_called()

    accepted = handle_gate_message(session, "9012", client)

    assert accepted == ("", "verified")
    assert release_blob(session) is blob
    assert gate_io.issue.call_count == 3
    gate_io.clear.assert_called_once_with()


def test_verification_clears_the_published_code(client, gate_io, blob):
    session = begin_session()
    handle_gate_message(session, "TEST-001", client)

    result = handle_gate_message(session, "1234", client)

    assert result == ("", "verified")
    assert release_blob(session) is blob
    gate_io.clear.assert_called_once_with()
    gate_io.issue.assert_called_once_with("TEST-001")
