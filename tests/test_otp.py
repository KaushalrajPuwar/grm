"""OTP generation and storage, using fixed codes and temporary files."""

import json
from unittest.mock import Mock, call

import pytest

from grm.auth import otp


def test_generated_code_keeps_its_leading_zero(monkeypatch):
    digits = "012345"
    choose = Mock(side_effect=digits)
    monkeypatch.setattr(otp.random, "choice", choose)

    assert otp.generate_otp(len(digits)) == digits
    assert choose.call_args_list == [call(otp.OTP_ALPHABET)] * len(digits)


def test_issued_code_can_be_read_until_cleared(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "pending.json"
    code = "0123"
    issued_at = 1000.0
    identifier = "TEST-001"
    monkeypatch.setattr(otp, "generate_otp", lambda: code)
    monkeypatch.setattr(otp.time, "time", lambda: issued_at)

    issued_code = otp.issue_otp(identifier, path)

    assert issued_code == code
    expected = {"code": code, "issued_at": issued_at, "identifier": identifier}
    assert json.loads(path.read_text(encoding="utf-8")) == expected
    assert otp.peek_issued(path) == expected
    assert otp.peek_issued(path) == expected

    otp.clear_issued(path)
    otp.clear_issued(path)

    assert not path.exists()
    assert otp.peek_issued(path) is None


@pytest.mark.parametrize("contents", ["not json", "[]", '"code"', "null", "42"])
def test_unusable_otp_records_are_ignored(tmp_path, contents):
    path = tmp_path / "pending.json"
    path.write_text(contents, encoding="utf-8")

    assert otp.peek_issued(path) is None
