"""Phase 3 integration walkthrough.

Drives the whole stack the way the browser does: requests go to the front-end
origin and are proxied to the backend, so this exercises the exact transport the
chat app uses rather than a shortcut into the harness.

Covers both demo routes end to end, plus the gate and the channel boundary.

    python scripts/integration_walkthrough.py [--base http://127.0.0.1:5173]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ISSUED_OTP = Path("var/demo_otp_issued.json")

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" :: {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def turn(base: str, session: str, text: str) -> dict:
    body = json.dumps({"session_id": session, "text": text, "channel": "chat"}).encode()
    request = urllib.request.Request(
        f"{base}/v1/turns", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=240) as response:
        return json.load(response)


def published_otp() -> str:
    """What a human reads off the second terminal."""
    if not ISSUED_OTP.exists():
        return ""
    return json.loads(ISSUED_OTP.read_text())["code"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    from grm.beneficiary360.file_backed import get_client

    client = get_client()
    fid = client.foundational_id

    banner("Transport: the front end reaches the backend only through the turn contract")
    # The front end proxies /v1 only, which is all it is allowed to use.
    direct = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=30).read()
    check("backend healthy", json.loads(direct)["status"] == "ok")
    proxied = turn(base, "phase3-probe", "")
    check("turn contract reachable through the front-end origin", proxied["reply"] != "")

    # Unique per run: the registry lives in the running server, so a fixed id
    # would resume an already-verified session and skip the gate.
    session = f"phase3-{uuid.uuid4().hex[:8]}"
    banner("Gate: identity before any record is opened")
    first = turn(base, session, "")
    check("chat is available before verification", first["reply"] != "")
    check("nothing authenticated on open", first["authenticated"] is False)
    check("beneficiary name withheld pre-auth", "Lakshmi" not in first["reply"])
    check("blocked status withheld pre-auth", "blocked" not in first["reply"].lower())

    unknown = turn(base, session, "FID-0000000000")
    check("unknown identifier reveals nothing", unknown["authenticated"] is False)

    issued = turn(base, session, fid)
    check("identifier alone does not authenticate", issued["authenticated"] is False)
    check("code published for the second terminal", bool(published_otp()))
    check("contact masked to last three", "*******345" in issued["reply"])

    verified = turn(base, session, published_otp())
    check("code from the second terminal authenticates", verified["authenticated"] is True)
    check("greeting opens from the enrolment picture", "Lakshmi" in verified["reply"])
    check(
        "handoff trail reports the gate opening",
        any(h["kind"] == "gate_open" for h in verified["handoffs"]),
    )
    check("issued code consumed after use", not ISSUED_OTP.exists())

    banner("Route A: the happy path, a delivery already in motion")
    reference = turn(base, session, "what is my LPG connection number?")
    check("reference lookup stays with the front line", reference["owner"] == "chat")

    moving = turn(base, session, "when will my cylinder arrive?")
    check("delivery question hands off to analysis", moving["owner"] == "reasoning")
    check("handoff recorded", any(h["kind"] == "to_reasoning" for h in moving["handoffs"]))
    check("answer states a dispatch date", "august" in moving["reply"].lower())
    check("candidate passed evaluation", moving["qa_verdict"] == "pass")

    followup = turn(base, session, "will I definitely get it this week?")
    check("follow-up keeps its context", followup["reply"] != "")
    check("follow-up stays with analysis on the same thread", followup["owner"] == "reasoning")

    banner("Route B: nothing further will move it, a ticket is offered")
    blocked = turn(base, session, "why was my gas subsidy blocked this month?")
    check("blocked question hands off to analysis", blocked["owner"] == "reasoning")
    check("answer names the reason", "aadhaar" in blocked["reply"].lower())
    check("answer names the amount", "300" in blocked["reply"])
    check("candidate passed evaluation", blocked["qa_verdict"] == "pass")
    offers_ticket = "ticket" in blocked["reply"].lower() or "complaint" in blocked["reply"].lower()
    check("a route to resolution is offered", offers_ticket)
    check(
        "the citizen is asked whether this answered the question",
        "?" in blocked["reply"].split("The records")[-1][-160:],
    )

    banner("Ownership returns to the front line on a new topic")
    newtopic = turn(base, session, "what other schemes am I on?")
    check("new topic returns to the front line", newtopic["owner"] == "chat")
    fresh = turn(base, "phase3-other", "")
    check("a new session starts unverified", fresh["authenticated"] is False)
    check("a new session sees no prior conversation", "Lakshmi" not in fresh["reply"])

    banner("Channel boundary: the contract carries no agent internals")
    payload = json.dumps(verified)
    for leak in ("constitution", "system prompt", "ROUTE:", "api_key", "MODELID"):
        check(f"response does not expose {leak}", leak not in payload)

    print()
    if failures:
        print(f"RESULT {len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("RESULT every Phase 3 integration check passed")
    return 0


def banner(text: str) -> None:
    print(f"\n{'-' * 70}\n{text}\n{'-' * 70}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.HTTPError as exc:
        print(f"FAIL transport error: {exc}")
        sys.exit(1)
