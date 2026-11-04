"""One synthetic beneficiary, with model calls and OTP delivery kept offline."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from grm.agents.base import AgentAdapter
from grm.auth.gate import begin_session, submit_identifier, submit_otp
from grm.beneficiary360.client import Beneficiary360Client
from grm.beneficiary360.schemas import Beneficiary360Blob
from grm.harness import gate_flow, turn_loop


@pytest.fixture
def blob():
    return Beneficiary360Blob.model_validate(
        {
            "beneficiary": {"foundationalId": "TEST-001"},
            "programs": [
                {
                    "programId": "test-scheme",
                    "programMnemonic": "TEST",
                    "programName": "Test Scheme",
                    "programStatus": "ACTIVE",
                    "enrolments": [{"enrolmentStatus": "ENROLLED"}],
                    "lpgConnection": {"connectionNumber": "CONN-TEST-001"},
                    "disbursements": [
                        {
                            "benefitCodeMnemonic": "TEST-PAYMENT",
                            "benefitType": "CASH",
                            "disbursementQuantity": 250,
                        }
                    ],
                }
            ],
            "bridgeProcessing": [
                {
                    "benefitCodeMnemonic": "TEST-PAYMENT",
                    "benefitProgramMnemonic": "TEST",
                    "benefitType": "CASH",
                    "subsidyReleaseStatus": "BLOCKED",
                    "blocker": {
                        "blockerCode": "TEST-BLOCKER",
                        "blockerDescription": "Synthetic reconciliation pending",
                    },
                }
            ],
            "registries": [
                {
                    "registryCode": "TEST",
                    "registers": [
                        {"attributes": {"first_name": "Example", "last_name": "Citizen"}}
                    ],
                }
            ],
        }
    )


@pytest.fixture
def client(blob):
    client = Mock(spec=Beneficiary360Client, registered_mobile="0000000101")
    client.find_by_identifier.side_effect = {"TEST-001": blob}.get
    return client


@pytest.fixture
def adapters(monkeypatch):
    adapters = {role: Mock(spec=AgentAdapter) for role in ("chat", "reasoning", "qa")}
    for role, adapter in adapters.items():
        adapter.invoke.side_effect = AssertionError(f"Unexpected {role} call")
    settings = SimpleNamespace(qa_enabled=True)
    monkeypatch.setattr(turn_loop, "get_adapters", lambda: adapters)
    monkeypatch.setattr(turn_loop, "get_settings", lambda: settings)
    return adapters


@pytest.fixture
def gate_io(monkeypatch):
    issue = Mock(side_effect=["1234", "5678", "9012"])
    clear = Mock()
    monkeypatch.setattr(gate_flow, "issue_otp", issue)
    monkeypatch.setattr(gate_flow, "clear_issued", clear)
    return SimpleNamespace(issue=issue, clear=clear)


@pytest.fixture
def verified_session(client):
    session = begin_session()
    submit_identifier(session, "TEST-001", client, lambda _: "1234")
    submit_otp(session, "1234")
    session.stage = "open"
    return session
