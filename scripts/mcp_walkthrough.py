"""One-file walkthrough against a running MCP server.

Terminal 1:
    uvicorn grm.mcp.server:app --host 127.0.0.1 --port 8100

Terminal 2:
    python scripts/mcp_walkthrough.py

It speaks raw JSON-RPC, the same way the voice team's client will. The demo OTP
is read from the shared store the server writes, so the human step is automated
for testing only. The server itself is unchanged: it still requires a correct
code before it releases any record.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OTP_FILE = REPO_ROOT / "var" / "demo_otp_issued.json"
BENEFICIARY_ID = "FID-9988776655"

failures: list[str] = []
STEP = 0


def step(title: str) -> None:
    global STEP
    STEP += 1
    print(f"\n[{STEP}] {title}")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(
        f"    {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else "")
    )
    if not ok:
        failures.append(name)


def show(label: str, text: str) -> None:
    body = " ".join(str(text).split())
    print(f"    {label}: {body}")


class McpClient:
    def __init__(self, base: str) -> None:
        self.url = base.rstrip("/") + "/mcp"
        self._id = 0

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        body = json.dumps(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        ).encode()
        request = urllib.request.Request(
            self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.load(response)
        if "error" in payload:
            raise RuntimeError(payload["error"])
        return payload["result"]

    def call(self, name: str, **arguments) -> dict:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise RuntimeError(result["content"][0]["text"])
        if "structuredContent" in result:
            return result["structuredContent"]
        return json.loads(result["content"][0]["text"])

    def call_text(self, name: str, **arguments) -> str:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise RuntimeError(result["content"][0]["text"])
        return result["content"][0]["text"]


def read_otp() -> str:
    """Read the code the server just published, the way a human would."""
    for _ in range(40):
        if OTP_FILE.exists():
            try:
                code = json.loads(OTP_FILE.read_text()).get("code", "")
            except (OSError, json.JSONDecodeError):
                code = ""
            if code:
                return str(code)
        time.sleep(0.25)
    return ""


def say(who: str, reply: str) -> None:
    print(f"    {who}: {' '.join(reply.split())}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8100")
    # Unique per run: the server keeps sessions in memory, so a fixed id would
    # resume an earlier run and skip the greeting.
    parser.add_argument("--session", default=f"walkthrough-{uuid.uuid4().hex[:8]}")
    args = parser.parse_args()
    client = McpClient(args.base)
    session = args.session

    print("MCP walkthrough")
    print(f"server: {args.base}   session: {session}")

    contract = client.call("describe_contract")
    single = contract.get("architecture") == "single_agent"
    lookup_owner = "single" if single else "chat"
    analysis_owner = "single" if single else "reasoning"
    print(f"architecture: {contract.get('architecture')}   qa: {contract.get('evaluation')}")

    # A stale code from an earlier run must not be mistaken for this one.
    OTP_FILE.unlink(missing_ok=True)

    step("connect to the server")
    greeting = client.call_text("check_connection", session_id=session, text="", channel="voice")
    show("check_connection", greeting)
    check("server replies with the connectivity string", greeting.startswith("hi you are now"))

    step("the caller speaks first")
    opened = client.call("route_turn", session_id=session, text="Hello", channel="voice")
    say("agent", opened["reply"])
    check("not authenticated yet", opened["authenticated"] is False)
    check("channel is told to ask for an identifier", opened["expects"] == "beneficiary_id")
    check("opening is the fixed welcome", "OpenG2P support service" in opened["reply"])
    check("no beneficiary data in the opening", "Lakshmi" not in opened["reply"])

    step("greeting again does not repeat the welcome")
    again = client.call("route_turn", session_id=session, text="hello", channel="voice")
    say("agent", again["reply"])
    check("welcome is said once", "OpenG2P support service" not in again["reply"])
    check("asks for the registration number", "registration number" in again["reply"])

    step("state a problem before identifying")
    complaint = client.call(
        "route_turn", session_id=session, text="I have a complaint", channel="voice"
    )
    say("agent", complaint["reply"])
    check("asks for the registration number", "registration number" in complaint["reply"])
    check("still unauthenticated", complaint["authenticated"] is False)

    step("send the registration number")
    identified = client.call("route_turn", session_id=session, text=BENEFICIARY_ID, channel="voice")
    say("agent", identified["reply"])

    if identified["authenticated"]:
        check("asks the caller to confirm the name", identified["expects"] == "confirmation")
        check("no OTP is pending", identified["pending_otp"] is False)
    else:
        check("identifier alone does not authenticate", identified["authenticated"] is False)
        check("channel is told to ask for the code", identified["expects"] == "otp")
        check("pending_otp is set", identified["pending_otp"] is True)

    if identified["authenticated"]:
        print("    OTP bypass active: the identifier authenticated directly")
        verified = identified
        check("identifier auto-verifies in demo mode", verified["authenticated"] is True)
    else:
        step("submit the demo code (read from the shared store)")
        code = read_otp()
        if not code:
            print("    FAIL  no code found. Is the server running from the repo root?")
            print(f"    looked in: {OTP_FILE}")
            return 1
        print(f"    read code: {'*' * max(0, len(code) - 2) + code[-2:]}")
        verified = client.call("route_turn", session_id=session, text=code, channel="voice")
        say("agent", verified["reply"])
        check("code authenticates", verified["authenticated"] is True)
    check("confirmation names the caller", "Lakshmi Narayan" in verified["reply"])
    check("channel asks for confirmation", verified["expects"] == "confirmation")

    step("confirm the name")
    confirmed = client.call(
        "route_turn", session_id=session, text="yes, that's me", channel="voice"
    )
    say("agent", confirmed["reply"])
    check("record opening names the benefits", "Domestic LPG Subsidy" in confirmed["reply"])
    check("record opening is speech ready", "(" not in confirmed["reply"])
    check("channel is told to allow free speech", confirmed["expects"] == "message")

    step("ask a reference question")
    lookup = client.call("route_turn", session_id=session, text="what is my LPG connection number?")
    say(f"agent({lookup['owner']})", lookup["reply"])
    check(f"answered by {lookup_owner}", lookup["owner"] == lookup_owner)
    # The agent may read the number in groups for speech: "T G 4471 9920".
    check(
        "answers with the connection number",
        "4471" in lookup["reply"] and "9920" in lookup["reply"],
        lookup["reply"][:120],
    )

    step("ask when the cylinder will arrive")
    delivery = client.call(
        "route_turn",
        session_id=session,
        text="You said my cylinder is on the way. When will I actually receive it?",
        channel="voice",
    )
    say(f"agent({delivery['owner']})", delivery["reply"])
    check(f"answered by {analysis_owner}", delivery["owner"] == analysis_owner)
    check(
        "states the expected delivery date",
        bool(re.search(r"2026-10-24|24 october|october 24", delivery["reply"], re.IGNORECASE)),
    )
    check("QA is disabled in this build", delivery["qa_verdict"] is None)
    check(
        "delivery answer is speech ready",
        "**" not in delivery["reply"] and "(" not in delivery["reply"],
    )

    step("ask why the subsidy was blocked")
    blocked = client.call(
        "route_turn",
        session_id=session,
        text="I did not get my gas subsidy this month. Why was it blocked?",
        channel="voice",
    )
    say(f"agent({blocked['owner']})", blocked["reply"])
    check(f"answered by {analysis_owner}", blocked["owner"] == analysis_owner)
    check("names the Aadhaar mismatch", "aadhaar" in blocked["reply"].lower())
    check("names the amount held", "300" in blocked["reply"])
    check(
        "offers a way to resolve it",
        bool(re.search(r"grievance|ticket|complaint|bank", blocked["reply"], re.IGNORECASE)),
    )

    step("hang up")
    reset = client.call("reset_session", session_id=session)
    check("reset acknowledged", reset["reset"] is True)
    status = client.call("session_status", session_id=session)
    check("reset drops verification", status["authenticated"] is False)

    step("a new utterance starts unverified")
    resumed = client.call("route_turn", session_id=session, text="hello again", channel="voice")
    say("agent", resumed["reply"])
    check("asks for an identifier again", resumed["expects"] == "beneficiary_id")
    check(
        "greets a fresh call instead of rejecting the speech",
        "OpenG2P support service" in resumed["reply"],
        resumed["reply"][:120],
    )

    print()
    if failures:
        print(f"RESULT {len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print(f"RESULT all {STEP} steps passed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as exc:
        print(f"\nCannot reach the MCP server at the given base URL: {exc}")
        print("Start it first: uvicorn grm.mcp.server:app --port 8100")
        sys.exit(1)
