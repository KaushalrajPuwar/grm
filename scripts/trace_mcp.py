"""Watch exactly what the MCP service receives and returns.

Terminal 1:
    sudo journalctl -u grm-mcp -f        # optional, for server logs

Terminal 2:
    sudo systemctl restart grm-mcp
    python scripts/trace_mcp.py

Terminal 3, or the voice client:
    send a turn

The service writes one JSON line per inbound turn and per reply to
var/mcp_trace.log when MCP_TRACE=true. This script tails that file and prints it
as a readable conversation.

    python scripts/trace_mcp.py              follow live
    python scripts/trace_mcp.py --once       print what is there and exit
    python scripts/trace_mcp.py --from-start print from the beginning, then follow
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG = REPO_ROOT / "var" / "mcp_trace.log"


def format_record(record: dict[str, Any]) -> str:
    stamp = str(record.get("ts", ""))
    clock = stamp[11:19] if len(stamp) >= 19 else stamp

    direction = str(record.get("direction", "?"))
    label = {"in": "IN ", "out": "OUT", "error": "ERR"}.get(direction, direction.upper())
    session = str(record.get("session", ""))
    detail = []

    for key in ("channel", "owner", "length"):
        if key in record:
            detail.append(f"{key}={record[key]}")

    head = f"[{clock}] {label} session={session} {' '.join(detail)}".rstrip()
    text = record.get("text", record.get("error", ""))
    body = json.dumps(text, ensure_ascii=False)

    return f"{head}\n    {body}"


def follow(path: Path, from_start: bool, once: bool) -> int:
    if not path.exists():
        print(f"Waiting for {path}")
        print("Is MCP_TRACE=true in .env, and has the service been restarted?")
        if once:
            return 1

    position = 0 if from_start else (path.stat().st_size if path.exists() else 0)
    inode = path.stat().st_ino if path.exists() else None

    print(f"Tracing {path}")
    print("Send a turn now. Ctrl+C to stop.\n")

    while True:
        if path.exists():
            stat = path.stat()
            if inode is not None and stat.st_ino != inode:
                position = 0
            inode = stat.st_ino

            if stat.st_size < position:
                position = 0

            if stat.st_size > position:
                with path.open(encoding="utf-8") as handle:
                    handle.seek(position)
                    while True:
                        line = handle.readline()
                        if not line:
                            break
                        position = handle.tell()
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        print(format_record(record))
                        print()

        if once:
            return 0
        time.sleep(0.4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--once", action="store_true", help="print existing entries and exit")
    parser.add_argument(
        "--from-start",
        action="store_true",
        help="print everything already in the file before following",
    )
    args = parser.parse_args()

    try:
        return follow(args.file, args.from_start, args.once)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
