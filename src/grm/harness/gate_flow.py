"""Pre-authentication gate conversation. No agent model is called.

Until the Authenticator Gate passes, there is no protected data and no reasoning
to do. A deterministic script handles the exchange so no model can leak anything
by improvising. The chat agent resumes only after verification.

The OTP is issued through `grm.auth.otp`, which publishes it for the standalone
issuer process to display. A human reads it on that terminal and types it into
the chat window. The server never enters its own code.
"""

from __future__ import annotations

from grm.auth.gate import AuthSession, GateStatus, submit_identifier, submit_otp
from grm.auth.otp import clear_issued, issue_otp
from grm.beneficiary360.client import Beneficiary360Client

ID_PROMPT = "Before I can help, I need to verify your identity. Please share your beneficiary ID."

WELCOME = (
    "Hello. I can help with your schemes, your payments, and any problems "
    "you have had receiving a benefit. To get started I need to verify your identity."
)

RETRY_ID = (
    "That did not match any record. Please check the ID and try again, or "
    "type it again if you would like."
)

OTP_PROMPT = "Thank you. I have sent a four-digit code to your registered mobile {masked}."

OTP_RETRY = (
    "That code does not match. Please enter the four-digit code again, or "
    "send a new beneficiary ID if you would rather start over."
)


def handle_gate_message(
    session: AuthSession, text: str, client: Beneficiary360Client
) -> tuple[str, str]:
    """Return (reply, stage) for one pre-auth turn."""
    status = session.state.status
    cleaned = text.strip()

    if not cleaned:
        return WELCOME if status is GateStatus.AWAITING_ID else ID_PROMPT, "id_prompt"

    if status is GateStatus.OTP_SENT:
        return _handle_code(session, cleaned, client)

    return _handle_identifier(session, cleaned, client)


def _handle_identifier(
    session: AuthSession, cleaned: str, client: Beneficiary360Client
) -> tuple[str, str]:
    # issue_otp runs only once a record matches, so an unknown identifier never
    # publishes a live code to the issuer process.
    state = submit_identifier(session, cleaned, client, issue_otp)

    if state.status is GateStatus.OTP_SENT:
        return OTP_PROMPT.format(masked=state.masked_mobile), "otp_sent"

    return RETRY_ID, "id_prompt"


def _handle_code(
    session: AuthSession, cleaned: str, client: Beneficiary360Client
) -> tuple[str, str]:
    state = submit_otp(session, cleaned)

    if state.status is GateStatus.VERIFIED:
        clear_issued()
        return "", "verified"

    # A failed attempt gets a fresh code, so the one on the second terminal is
    # no longer the one to type.
    retry = submit_identifier(session, state.identifier or "", client, issue_otp)
    if retry.status is GateStatus.OTP_SENT:
        return OTP_RETRY, "otp_sent"
    return RETRY_ID, "id_prompt"
