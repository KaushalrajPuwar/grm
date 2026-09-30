"""Turn logging, so a live turn can be watched from the terminal.

Emits to stdout as one readable line per event. Every model call is timed and
every stage transition is announced, so it is always possible to say which part
of a turn is currently in flight and how long the earlier parts took.

Events:

    turn received      a turn arrived at the transport layer
    turn finished      the reply is on its way back, with the total
    turn failed        something raised, with where it raised
    gate               identity progress, never the code itself
    routing decided    which agent owns this turn, and why
    model call         one line on entry, one on exit, with the duration
    handoff            ownership moved between agents
    qa verdict         pass or fail, and the reason when it fails
    revision           a candidate was sent back for correction

Identifiers, mobile numbers and codes are redacted, not merely omitted.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

#: Never let identifiers or codes reach a log body.
REDACT_KEYS = frozenset(
    {
        "beneficiary_id",
        "identifier",
        "registered_mobile",
        "mobile",
        "expected_otp",
        "otp",
        "code",
        "aadhaar_last4",
    }
)

#: Fixed-width stage so a running turn reads as a column in the terminal.
STAGE_WIDTH = 22


def redact(
    _logger: object, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in REDACT_KEYS & event_dict.keys():
        event_dict[key] = "<redacted>"
    return event_dict


def _console_renderer(_logger: object, _name: str, event_dict: MutableMapping[str, Any]) -> str:
    """One line, human order, stage first so a running turn reads as a column."""
    event = str(event_dict.pop("event", ""))
    level = str(event_dict.pop("level", "info"))
    event_dict.pop("timestamp", None)

    stage = str(event_dict.pop("stage", "")).ljust(STAGE_WIDTH)
    detail = "  ".join(f"{k}={v}" for k, v in event_dict.items())
    marker = {"info": " ", "warning": "!", "error": "x", "debug": "."}.get(level, " ")
    return f"[{marker}] {stage} {event}{'  ' + detail if detail else ''}"


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            redact,
            structlog.processors.TimeStamper(fmt="iso"),
            _console_renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger() -> Any:
    """Bound logger. Cheap, so call sites need not cache it."""
    return structlog.get_logger("grm")
