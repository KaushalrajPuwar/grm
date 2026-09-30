"""Authentication gate. Deterministic, no LLM calls anywhere in this module.

This is not an agent and must never become one. It resolves identity, holds the
verification state for a session, and is the only thing permitted to release
protected beneficiary data.

Demo verification: an OTP issued by `grm.auth.otp` against a hardcoded contact.
The live path, where another team sends the OTP to the registered mobile and
returns a token, enters through `submit_otp` unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from grm.beneficiary360.client import Beneficiary360Client
from grm.beneficiary360.schemas import Beneficiary360Blob


class GateStatus(StrEnum):
    AWAITING_ID = "awaiting_id"
    OTP_SENT = "otp_sent"
    VERIFIED = "verified"
    DENIED = "denied"


@dataclass
class GateState:
    status: GateStatus = GateStatus.AWAITING_ID
    identifier: str | None = None
    masked_mobile: str | None = None
    attempts: int = 0
    note: str = ""


@dataclass
class AuthSession:
    """Per-session state. Holds no blob until VERIFIED.

    Also carries the conversation position, because that is per-session too and
    must survive across turns. Reset together with verification, never apart.
    """

    state: GateState = field(default_factory=GateState)
    expected_otp: str | None = None
    #: The authenticated snapshot. None until the gate passes, and cleared
    #: whenever verification is dropped.
    blob: Beneficiary360Blob | None = None
    stage: str = "greet"
    history: list[dict[str, str]] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return self.state.status is GateStatus.VERIFIED


def mask_mobile(mobile: str) -> str:
    """Show only the last three digits. Security default, not a preference."""
    digits = [c for c in mobile if c.isdigit()]
    if len(digits) <= 3:
        return "*" * len(digits)
    return "*" * (len(digits) - 3) + "".join(digits[-3:])


def begin_session() -> AuthSession:
    """Fresh unauthenticated session. Chat is available, data is not."""
    return AuthSession()


def submit_identifier(
    session: AuthSession,
    identifier: str,
    client: Beneficiary360Client,
    issue: Callable[[str], str],
) -> GateState:
    """Resolve the identifier. Only a matching record yields an OTP.

    `issue` is a callable rather than a code, so a code is generated only after
    a record matches. Publishing a code for an unknown identifier would leave a
    live code on the issuer's screen that can never be used.

    On success the snapshot is fetched and held on the session, never returned
    to the caller. On failure no record is disclosed: an unknown identifier and
    a wrong one are indistinguishable to the requester.
    """
    cleaned = identifier.strip().upper()
    blob = client.find_by_identifier(cleaned)

    if blob is None:
        session.state = GateState(
            status=GateStatus.DENIED,
            identifier=cleaned,
            attempts=session.state.attempts + 1,
            note="No record matched that identifier.",
        )
        session.expected_otp = None
        session.blob = None
        return session.state

    masked = mask_mobile(client.registered_mobile)
    session.state = GateState(
        status=GateStatus.OTP_SENT,
        identifier=cleaned,
        masked_mobile=masked,
        attempts=session.state.attempts + 1,
        note="OTP issued to registered contact.",
    )
    session.expected_otp = issue(cleaned)
    session.blob = blob
    return session.state


def submit_otp(session: AuthSession, code: str) -> GateState:
    """Verify the code. Constant-time compare, fail closed."""
    if not session.expected_otp:
        session.state = GateState(
            status=GateStatus.AWAITING_ID,
            attempts=session.state.attempts,
            note="No verification is pending.",
        )
        return session.state

    if not _matches(code.strip(), session.expected_otp):
        session.state = GateState(
            status=GateStatus.DENIED,
            identifier=session.state.identifier,
            masked_mobile=session.state.masked_mobile,
            attempts=session.state.attempts,
            note="That code does not match.",
        )
        return session.state

    session.state = GateState(
        status=GateStatus.VERIFIED,
        identifier=session.state.identifier,
        masked_mobile=session.state.masked_mobile,
        attempts=session.state.attempts,
        note="Verified.",
    )
    session.expected_otp = None
    return session.state


def release_blob(session: AuthSession) -> Beneficiary360Blob | None:
    """The only path from a session to protected data. None unless verified."""
    if not session.verified:
        return None
    return session.blob


def reset(session: AuthSession) -> AuthSession:
    """Drop verification and the snapshot together. No partial reset."""
    return AuthSession()


def _matches(candidate: str, expected: str) -> bool:
    if len(candidate) != len(expected):
        return False
    result = 0
    for a, b in zip(candidate, expected, strict=True):
        result |= ord(a) ^ ord(b)
    return result == 0
