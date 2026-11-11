"""Live trace of the MCP boundary.

Writes one JSON line per inbound turn and one per reply, so a terminal can show
exactly what the service received from the channel. Disabled unless MCP_TRACE is
true. The file contains raw beneficiary text and is demo-only.

The writer must never break a turn. Any failure is swallowed after a single log
line, because tracing is a diagnostic, not part of the request path.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from grm.config import TRACE_LOG_PATH, get_settings
from grm.observability.logging import get_logger


def _write(direction: str, session_id: str, **fields: Any) -> None:
    if not get_settings().mcp_trace:
        return

    record = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "direction": direction,
        "session": session_id,
        **fields,
    }

    try:
        TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        get_logger().warning(
            "trace write failed",
            stage="trace",
            error=type(exc).__name__,
        )


def trace_inbound(session_id: str, channel: str, text: str) -> None:
    _write("in", session_id, channel=channel, text=text, length=len(text))


def trace_outbound(session_id: str, owner: str, reply: str) -> None:
    _write("out", session_id, owner=owner, text=reply, length=len(reply))


def trace_error(session_id: str, error: str) -> None:
    _write("error", session_id, error=error)
