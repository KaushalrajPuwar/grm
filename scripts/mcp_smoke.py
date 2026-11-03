"""MCP smoke test. Run against a live MCP server:

    uvicorn grm.mcp.server:app --port 8100
    python scripts/mcp_smoke.py

Speaks raw JSON-RPC, the same way the voice team's client will. No REST calls,
no direct imports of the harness: this tests the contract, not the internals.
"""

from __future__ import annotations

import argparse
import json
import re
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


def banner(text: str) -> None:
    print(f"\n{'-' * 70}\n{text}\n{'-' * 70}")


class McpClient:
    """Minimal MCP client: JSON-RPC over Streamable HTTP, one request per call."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self._id = 0

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{self.base}/mcp",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.load(response)

    def rpc(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        reply = self._post(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        )
        if "error" in reply:
            raise RuntimeError(f"{method} failed: {reply['error']}")
        return reply["result"]

    def call(self, name: str, **arguments) -> dict:
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            message = result.get("content", [{}])[0].get("text", "tool returned an error")
            raise RuntimeError(message)
        if "structuredContent" in result:
            return result["structuredContent"]
        return json.loads(result["content"][0]["text"])


def published_otp() -> str:
    if not ISSUED_OTP.exists():
        return ""
    return json.loads(ISSUED_OTP.read_text())["code"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8100")
    args = parser.parse_args()
    client = McpClient(args.base)

    banner("Discovery")
    init = client.rpc(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "grm-smoke", "version": "1.0"},
        },
    )
    check("server identifies itself", init["serverInfo"]["name"] == "grm-dialogue")
    check("protocol version negotiated", bool(init["protocolVersion"]))

    tools = client.rpc("tools/list")["tools"]
    names = {tool["name"] for tool in tools}
    check(
        "expected tools are exposed",
        names
        == {
            "route_turn",
            "check_connection",
            "session_status",
            "reset_session",
            "describe_contract",
        },
        f"got {sorted(names)}",
    )
    route_schema = next(tool for tool in tools if tool["name"] == "route_turn")
    props = route_schema["inputSchema"]["properties"]
    check("route_turn exposes session_id", props.get("session_id", {}).get("type") == "string")
    check("route_turn exposes text", props.get("text", {}).get("type") == "string")
    check("route_turn exposes channel", "channel" in props)

    probe = client.rpc(
        "tools/call",
        {
            "name": "check_connection",
            "arguments": {"session_id": "check", "text": "", "channel": "voice"},
        },
    )
    probe_text = probe["content"][0]["text"]
    check(
        "check tool returns the connectivity string",
        probe_text == "hi you are now connected to the MCP",
        probe_text,
    )

    contract = client.call("describe_contract")
    check("contract lists telephony as a channel", "telephony" in contract["channels"])
    check("contract names the three agents", set(contract["agents"]) >= {"chat", "reasoning", "qa"})
    check("contract lists the check tool", "check_connection" in contract["tools"])
    check("contract explains expects", "otp" in contract["expects"])
    check("contract reports evaluation state", contract["evaluation"] in {"enabled", "disabled"})
    check("contract declares FastMCP transport", "FastMCP" in contract["transport"])

    banner("Gate over MCP")
    session = f"voice-{uuid.uuid4().hex[:8]}"

    opened = client.call("route_turn", session_id=session, text="", channel="telephony")
    check("channel alias telephony accepted", opened["session_id"] == session)
    check("nothing authenticated on open", opened["authenticated"] is False)
    check("channel is told to ask for an identifier", opened["expects"] == "beneficiary_id")
    check("no name leaks pre-auth", "Lakshmi" not in opened["reply"])

    # Isolate this check from any code left behind by an earlier run.
    ISSUED_OTP.unlink(missing_ok=True)
    unknown = client.call("route_turn", session_id=session, text="FID-0000000000", channel="voice")
    check("unknown identifier reveals nothing", unknown["authenticated"] is False)
    check("unknown identifier issues no code", not published_otp())

    identified = client.call(
        "route_turn", session_id=session, text="FID-9988776655", channel="voice"
    )
    code = published_otp()
    check("code published for the issuer terminal", bool(code))
    check("channel is told to ask for the code", identified["expects"] == "otp")
    check("pending_otp flag set", identified["pending_otp"] is True)
    check("identifier alone does not authenticate", identified["authenticated"] is False)

    verified = client.call("route_turn", session_id=session, text=code, channel="voice")
    check("code authenticates over MCP", verified["authenticated"] is True)
    check("greeting opens from the record", "Lakshmi" in verified["reply"])
    check("channel is told to allow free speech", verified["expects"] == "message")
    check(
        "gate opening appears in handoffs",
        any(h["kind"] == "gate_open" for h in verified["handoffs"]),
    )

    banner("Route A over MCP: delivery already moving")
    lookup = client.call("route_turn", session_id=session, text="what is my LPG connection number?")
    check("reference lookup stays with the chat agent", lookup["owner"] == "chat")

    moving = client.call(
        "route_turn", session_id=session, text="when will my cylinder arrive?", channel="voice"
    )
    check("delivery question hands to reasoning", moving["owner"] == "reasoning")
    check("evaluation is disabled by configuration", moving["qa_verdict"] is None)
    # The agent may render 2026-10-24 or 24 October 2026; both are correct.
    check(
        "answer states the expected date",
        bool(re.search(r"2026-10-24|24 october|october 24", moving["reply"], re.IGNORECASE)),
        moving["reply"][:160],
    )
    check(
        "handoff is reported to the channel",
        any(h["kind"] == "to_reasoning" for h in moving["handoffs"]),
    )

    banner("Route B over MCP: blocked, with a way out")
    blocked = client.call(
        "route_turn", session_id=session, text="why was my gas subsidy blocked this month?"
    )
    check("blocked question hands to reasoning", blocked["owner"] == "reasoning")
    check("answer names the cause", "aadhaar" in blocked["reply"].lower())
    check("answer names the amount", "300" in blocked["reply"])
    # Phrasing varies; grievance, ticket and complaint all name the same route.
    check(
        "a route to resolution is offered",
        bool(re.search(r"grievance|ticket|complaint", blocked["reply"], re.IGNORECASE)),
        blocked["reply"][:160],
    )

    banner("Session lifecycle")
    status = client.call("session_status", session_id=session)
    check("status reports verified", status["authenticated"] is True)
    check(
        "status does not leak record contents",
        "reply" not in status and "Lakshmi" not in json.dumps(status),
    )

    reset = client.call("reset_session", session_id=session)
    check("reset acknowledged", reset["reset"] is True)

    after = client.call("session_status", session_id=session)
    check("reset drops verification", after["authenticated"] is False)

    resumed = client.call("route_turn", session_id=session, text="hello again", channel="voice")
    check("session after reset asks for an identifier", resumed["expects"] == "beneficiary_id")
    check("session after reset is unauthenticated", resumed["authenticated"] is False)

    banner("Error surface")
    try:
        client.call("route_turn", session_id=session, text="hi", channel="carrier-pigeon")
        check("unknown channel rejected", False)
    except (RuntimeError, urllib.error.HTTPError):
        check("unknown channel rejected", True)

    print()
    if failures:
        print(f"RESULT {len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("RESULT every MCP check passed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as exc:
        print(f"FAIL cannot reach MCP server: {exc}")
        print("Start it with: uvicorn grm.mcp.server:app --port 8100")
        sys.exit(1)
