=============================
Architecture Decision Records
=============================

ADR 0001: Base tech stack
=========================

:Status: Proposed
:Date: 2026-09-22
:Author: Kaushalraj Puwar

Context
=======

Early scaffolding of the GRM repository. The team needed a locked base stack before implementation so harness, API, storage, and channel work can proceed in parallel without blocking on the Beneficiary 360 real contract or deploy infrastructure.

Decision
========

Adopt the following base stack, decided 2026-09-22:

* Language: Python 3.12.
* Harness: LangGraph for stateful assistant to reasoning to QA handoffs with gated retries.
* Model clients: LangChain chat models, one fixed instance per agent. Handoff is graph edges; model calls are per node transport.
* API: FastAPI plus Pydantic v2 with strict JSON blob contracts.
* Beneficiary 360: typed client behind an interface, mock now against the existing spec, real client later without touching flow.
* Channels: transport neutral turn connector, versioned REST JSON now, WebSockets later behind the same seam. Chat scope here; voice integrates through the same contract.
* Sessions: Redis for live session and history pointers.
* Blob snapshots: SQLite file plus Redis pointer, session keyed with cleanup; Postgres path kept open for deploy.
* Authenticator: plain deterministic function plus thin FastAPI wrapper, zero LLM calls.
* Observability: LangSmith plus structlog JSON now; OpenTelemetry, Prometheus, Grafana deferred.
* Packaging: uv plus ruff plus mypy.
* Testing: minimal functional tests now; full pytest async plus httpx, respx, model stubs deferred.
* Run: local machine with no containers; Docker and Kubernetes at deploy time only.

Consequences
============

* REST to WebSockets swaps behind the connector seam.
* SQLite to Postgres swaps behind the store seam.
* Structlog to OpenTelemetry swaps without touching flow code.
* Model rebinding stays a configuration change, not a flow rewrite.

New records append below as ADR 0002, ADR 0003, and so on. See logging.md.

==============================
ADR 0002: MCP as the channel contract
==============================

:Status: Accepted
:Date: 2026-10-27
:Author: Kaushalraj Puwar

Context
=======

The voice stack is built by another team and already speaks MCP. They run on
the same VM and need to call our dialogue service without an HTTP client, a
bespoke schema, or knowledge of our internal routing. The REST endpoint worked
for the web demo but made every new channel a code change on our side.

Decision
========

Expose the dialogue service over MCP using FastMCP, callable at `/mcp` on a
dedicated server (`grm.mcp.server:app`), and mount the same router on the main
application for convenience.

* Tools: `route_turn`, `check_connection`, `session_status`, `reset_session`,
  `describe_contract`.
* Tool arguments are scalars: the caller sends a transcript, a session id and
  a channel. Structured internal models stay inside our service.
* Transport is MCP Streamable HTTP with `json_response=True` and
  `stateless_http=True`, so a deterministic client gets one JSON reply and
  keeps no protocol session.
* `DialogueService` holds the single implementation of a turn. The MCP tools are
  a thin adapter over it.
* The REST surface and its web demo wiring are removed. MCP is the only channel
  contract; a second channel, if it ever exists, integrates through MCP.
* `TurnResponse` gains `expects`, so a telephony client can drive prompts
  without parsing reply text.

Consequences
============

* A new channel integrates by speaking MCP, not by editing our code.
* One service sits behind the tool layer, so there is no second implementation to diverge from.
* The transport is stateless, so a restart loses verification for every call.
  That is correct: a restarted process no longer holds the snapshot either.
* Streaming and barge-in are not covered. If the voice team needs partial
  transcripts or mid-turn ownership events, that is a new transport decision,
  recorded separately.
