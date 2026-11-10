"""Pre-authentication gate conversation. No agent model is called.

Until the Authenticator Gate passes, there is no protected data and no reasoning
to do. A deterministic script handles the exchange so no model can leak anything
by improvising. The agent resumes only after verification.

The caller always speaks first. Their first turn is answered with the welcome,
once. Every later turn is an attempt at the registration number: a match moves
to name confirmation, and anything else gets the same request for the number.
There is no content sniffing, because a distressed caller may open anywhere.

The OTP is issued through `grm.auth.otp`, which publishes it for the standalone
issuer process to display. A human reads it on that terminal and types it into
the chat window. The server never enters its own code.

Every line here is written for speech: no symbols, no parentheses, no markdown.
"""

from __future__ import annotations

from grm.auth.gate import AuthSession, GateStatus, submit_identifier, submit_otp
from grm.auth.otp import clear_issued, issue_otp
from grm.beneficiary360.client import Beneficiary360Client

#: Opening line. Fixed, so the first thing a caller hears is always the same.
WELCOME = "Hello and welcome to OpenG2P support service. How can I help you today?"

#: Every turn after the welcome, until a registration number resolves.
LOOKING_INTO_IT = "Let me look into it. Could you please share your registration number?"

#: Used when a code fails, so the caller knows the attempt was rejected.
RETRY_ID = "That did not match any record. Please check the registration number and try again."

OTP_PROMPT = "Thank you. I have sent a four digit code to your registered mobile {masked}."

OTP_RETRY = (
    "That code does not match. Please enter the four digit code again, or share "
    "your registration number if you would rather start over."
)


def handle_gate_message(
    session: AuthSession, text: str, client: Beneficiary360Client
) -> tuple[str, str]:
    """Return (reply, stage) for one gate turn.

    The caller is past the welcome by the time this runs, so an empty turn is
    treated as another attempt at the number rather than a new greeting.
    """
    status = session.state.status
    cleaned = text.strip()

    if not cleaned:
        return LOOKING_INTO_IT, "id_prompt"

    if status is GateStatus.OTP_SENT:
        return _handle_code(session, cleaned, client)

    return _handle_identifier(session, cleaned, client)


def _handle_identifier(
    session: AuthSession, cleaned: str, client: Beneficiary360Client
) -> tuple[str, str]:
    # issue_otp runs only once a record matches, so an unknown identifier never
    # publishes a live code to the issuer process.
    state = submit_identifier(session, cleaned, client, issue_otp)

    # No reply text here: once identity resolves, the caller is asked to confirm
    # the name, and that line needs the record. The turn loop builds it.
    if state.status is GateStatus.VERIFIED:
        return "", "confirm_identity"

    if state.status is GateStatus.OTP_SENT:
        return OTP_PROMPT.format(masked=state.masked_mobile), "otp_sent"

    return LOOKING_INTO_IT, "id_prompt"


def _handle_code(
    session: AuthSession, cleaned: str, client: Beneficiary360Client
) -> tuple[str, str]:
    state = submit_otp(session, cleaned)

    if state.status is GateStatus.VERIFIED:
        clear_issued()
        return "", "confirm_identity"

    # A failed attempt gets a fresh code, so the one on the second terminal is
    # no longer the one to type.
    retry = submit_identifier(session, state.identifier or "", client, issue_otp)
    if retry.status is GateStatus.OTP_SENT:
        return OTP_RETRY, "otp_sent"
    return RETRY_ID, "id_prompt"
