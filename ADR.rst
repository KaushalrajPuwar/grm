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
