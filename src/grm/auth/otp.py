"""Demo OTP issuance. Standalone process, shared store with the server.

Phase 1 demo only. In production another team sends the code to the registered
mobile and returns the token; the server then verifies it. Nothing about the
verification path changes.

The point of this module is that a human reads the code. It runs as its own
process:

    python -m grm.auth.otp

When a verification starts, the server writes the pending code here. The
standalone process reads it and prints it. A person reads it on screen and types
it into the chat window. The server compares what was typed against what it
issued. There is no path where the server accepts its own code without a human
submitting it.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

from grm.config import OTP_ISSUE_PATH

OTP_LENGTH = 4
OTP_ALPHABET = "0123456789"
#: Codes older than this are ignored, so a stale terminal cannot authorise.
OTP_TTL_SECONDS = 300


def generate_otp(length: int = OTP_LENGTH) -> str:
    """Return a random numeric code of the given length."""
    return "".join(random.choice(OTP_ALPHABET) for _ in range(length))


def issue_otp(identifier: str = "", path: Path | None = None) -> str:
    """Generate a code and publish it for the standalone issuer to read.

    Argument order matches the callable the gate invokes on a record match.
    """
    target = path or OTP_ISSUE_PATH
    code = generate_otp()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"code": code, "issued_at": time.time(), "identifier": identifier}),
        encoding="utf-8",
    )
    return code


def peek_issued(path: Path | None = None) -> dict[str, object] | None:
    """Read the pending code without consuming it."""
    target = path or OTP_ISSUE_PATH
    if not target.exists():
        return None
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict):
        return None
    return record


def clear_issued(path: Path | None = None) -> None:
    """Consume the pending code. Called once verification completes."""
    target = path or OTP_ISSUE_PATH
    target.unlink(missing_ok=True)


def _fmt_age(issued_at: object) -> str:
    try:
        seconds = time.time() - float(issued_at)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "unknown age"
    if seconds < 60:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)}m"


def main() -> None:  # pragma: no cover - manual demo entry point
    print("Demo OTP issuer. Reads codes the server publishes, prints them.")
    print(f"Watching: {OTP_ISSUE_PATH}")
    print("Read the code here, then type it into the chat window.\n")
    last = ""
    try:
        while True:
            record = peek_issued()
            if record is None:
                time.sleep(1)
                continue
            code = str(record.get("code", ""))
            if code and code != last:
                last = code
                identifier = record.get("identifier") or ""
                age = _fmt_age(record.get("issued_at"))
                print(f"OTP for {identifier}: {code}  (issued {age} ago)")
                print("Type it into the chat window to verify.\n", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":  # pragma: no cover
    main()
