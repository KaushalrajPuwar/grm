# Greivance Redressal Mechanism

**OpenG2P Beneficiary Conversational Agent**

A citizen-facing conversational service for government social-benefit programmes. Beneficiaries can ask questions, check eligibility, track benefit status, and raise grievances over voice or chat. Answers are grounded in authenticated programme data, not unsupported model inference.

[![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-early%20scaffolding-yellow)](#project-status)
[![OpenG2P](https://img.shields.io/badge/ecosystem-OpenG2P-1B4F72)](https://openg2p.org)
[![GitHub](https://img.shields.io/badge/github-KaushalrajPuwar%2Fgrm-181717?logo=github&logoColor=white)](https://github.com/KaushalrajPuwar/grm)

---

GRM is being built as one cohesive service, not a collection of loosely related apps. Dialogue stays lightweight and low-latency. Deeper analysis is delegated to a larger reasoning model. Independent evaluation sits in front of anything a beneficiary sees. Identity is a hard programmatic gate, not an agent.

The current system design is a north star, not a frozen contract. Components are written so they can be swapped, split, or replaced without collapsing the rest of the system.

## Why this exists

People enrolled in social-protection programmes often need a simple answer to a concrete question: whether they qualify, whether a payment has gone out, why a benefit is delayed, or how to escalate a complaint. Those answers live in structured programme records. They should not be improvised.

This service is the beneficiary-facing conversational layer for that problem. It is intended to sit in the [OpenG2P](https://openg2p.org) ecosystem, which provides registries and delivery systems for government-to-person transfers.

## What it does

| Capability | What the beneficiary gets |
| --- | --- |
| Information seeking | Grounded answers from authorised programme context |
| Scheme eligibility | Profile compared against scheme rules, with supported matches only |
| Benefit-status tracking | Current disbursement state, identified blockers, and next steps |
| Grievance redressal | Acknowledgement, contextual status, and escalation guidance |

Protected beneficiary and programme data is accessed only after the Authenticator Gate succeeds.

## Architecture

Three model roles, one programmatic security gate, and a harness that owns execution. No component is allowed to do another component's job.

```mermaid
flowchart LR
  B["Beneficiary<br/>voice / chat"] --> C["Client / server"]
  C --> H["Agent harness"]

  H --> A["Assistant agent<br/>low latency"]
  H --> G["Authenticator gate<br/>programmatic"]
  H --> R["Reasoning agent<br/>structured analysis"]
  H --> Q["QA / evaluation agent<br/>independent check"]

  G --> API["API layer"]
  API --> PG["PostgreSQL"]
  API --> D["Data blob<br/>JSON / CSV"]
  D --> R
  R --> Q
  Q --> A
  A --> B
```

### Runtime path

Server → Kubernetes → PostgreSQL → APIs → Data blob (JSON or CSV)

The data blob is the reasoning substrate. The reasoning agent analyses pre-fetched structured records. It does not roam the backend choosing arbitrary endpoints.

### Component boundaries

| Component | Kind | Owns | Must not |
| --- | --- | --- | --- |
| **Assistant agent** | Low-latency model | Greeting, clarification, presentation, satisfaction checks, session turns | Deep structured-data analysis |
| **Reasoning agent** | Larger reasoning model | Filtering the blob, interpreting records, synthesising a candidate answer | Owning the conversation or bypassing auth |
| **QA / evaluation agent** | Independent model | Retrieval validity, relevance, accuracy, completeness, safety | Talking to the beneficiary directly |
| **Authenticator gate** | Programmatic, non-agent | Identity verification and beneficiary-record resolution | Planning, intent reasoning, or answer generation |
| **Agent harness** | Infrastructure | Tool-chain execution, prompt-controlled flow, chat and session state | Becoming a fourth autonomous agent |

### Conversation lifecycle

1. **Session and identity.** Open a voice or chat turn. Resolve identity. Register a new record if none exists. Stay in the identity loop until verification succeeds.
2. **Routing.** Establish enrolment state, then take one of three paths: existing scheme, new scheme, or general query.
3. **Evidence.** Fetch authorised records and assemble the data blob.
4. **Reasoning.** Filter, analyse, and produce a candidate only when confidence clears the configured threshold.
5. **Evaluation.** An independent agent scores the candidate. Failures are sent back for revision. Unvalidated answers are not delivered.
6. **Close.** Ask whether the answer satisfied the query. Continue or auto-close from that explicit signal.

### In-scope scenarios

- **Non-receipt or delayed benefit** — disbursement status, likely blocker, correction path or escalation.
- **Scheme eligibility and recommendation** — profile matched to scheme rules; unsupported inference is rejected.
- **General grievance redressal** — complaint capture, status, next step; grievance context is held until the user is satisfied or the session closes.

## Agent modes

Two modes, one flag. `SINGLE_AGENT=false` is the default and keeps the two-agent flow: a chat model reads the enrollment picture and either answers or hands to the reasoning agent, which sees the full record.

`SINGLE_AGENT=true` gives every authenticated turn to one agent, bound to `MODELID_1`, with the full snapshot and `prompts/single_agent.md`. There is no routing call, no discarded draft, and no handoff. The two-agent code path stays intact, so flipping the flag back restores it.

Both modes share the same gate, session, QA switch, tools and response contract.

## Tech stack

Locked 2026-09-22. Full rationale lives in [ARCHITECTURE.md](ARCHITECTURE.md) and [ADR.rst](ADR.rst).

| Layer | Choice |
| --- | --- |
| Language | Python 3.12 |
| Harness | Plain async turn loop, two-agent or single-agent behind a flag |
| Model clients | LangChain chat models, one fixed instance per agent |
| API | FastAPI plus Pydantic v2, one dialogue service behind the MCP tool layer |
| Beneficiary 360 | Typed client behind an interface, one JSON file per person under `data/beneficiaries/` |
| Channels | MCP Streamable HTTP (FastMCP), MCP only |
| Sessions | In-process registry, single process (Redis deferred) |
| Blob snapshots | Held in memory on the session, dropped on reset (SQLite deferred) |
| Authenticator | Plain deterministic function, callable from the tool layer and tests |
| Observability | structlog console logs with redaction |
| Packaging | uv plus ruff plus mypy |
| Run | Local machine, containers at deploy time only |

## Design principles

**Authenticated context first.** No protected data before the gate succeeds.

**Structured evidence over improvisation.** Reasoning runs on the pre-fetched blob.

**Prompt-controlled flow.** Branching, clarification, satisfaction, and closure are harness state, not free-form model whim.

**Independent validation.** The model that writes a candidate is not the model that signs it off.

**Keep the front line light.** Routine dialogue stays on the assistant. The larger model is used where analysis actually needs it.

**Swap, do not weld.** Agents, models, storage, and transport are replaceable modules. Interfaces should survive a change of vendor, model, or deployment target.

## Project status

This repository is in **early scaffolding**. The design document in `docs/` describes the intended system. Implementation has not caught up, and the design itself is expected to move.

Treat the following as living, not final:

- agent topology and model assignment
- flow-control details
- backend contracts and the shape of the data blob
- voice and chat transport
- evaluation thresholds and retry policy

Build in thin, replaceable pieces. Do not collapse the system into a single irreversible path.

## Repository layout

```text
grm/
├── ARCHITECTURE.md       # living architecture and locked tech stack
├── ADR.rst               # architecture decision records
├── CHANGELOG.rst         # releases and contributors
├── docs/                 # design material (local; not a frozen spec)
├── pyproject.toml        # project metadata and dependencies
├── .python-version       # 3.12
├── .env.example          # required runtime configuration
└── README.md
```

Application packages, harness code, agent adapters, API clients, and tests will land as separate modules. Prefer a new module over growing a catch-all file.

## Prerequisites

- Python 3.12
- A virtual environment (the repo ships `.python-version` for that)
- Credentials for the model endpoints you intend to use

## Getting started

```bash
git clone https://github.com/KaushalrajPuwar/grm.git
cd grm
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Fill in `.env` before running anything that talks to a model or a backend.

## Running the service

One contract: MCP. The voice stack is the only client.

```bash
uvicorn grm.mcp.server:app --host 0.0.0.0 --port 8100
```

MCP lives at `POST /mcp`, Streamable HTTP, JSON responses, stateless. Discover the tools with:

```bash
curl -s -X POST http://127.0.0.1:8100/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

| Tool | Purpose |
| --- | --- |
| `route_turn` | One utterance in, one reply out, with `expects` telling the channel what to ask next |
| `check_connection` | Fixed connectivity string, same call shape, no model and no session |
| `session_status` | Whether the call is verified and where it has reached |
| `reset_session` | Hangup: drop verification and the snapshot together |
| `describe_contract` | Integration notes, in the protocol, so the voice team never reads our source |

Verify the contract end to end while the MCP server is running:

```bash
python scripts/mcp_smoke.py --base http://127.0.0.1:8100
```

Read a full conversation in order, with every reply printed:

```bash
python scripts/mcp_walkthrough.py --base http://127.0.0.1:8100
```

## Configuration

| Variable | Purpose |
| --- | --- |
| `API_KEY` | Credential for the configured model or API host |
| `BASE_URL` | Endpoint base for model access |
| `MODELID_1` | Model bound to one agent role |
| `MODELID_2` | Model bound to one agent role |
| `MODELID_3` | Model bound to the QA role (unused while QA is disabled) |
| `QA_ENABLED` | `false` ships the reasoning answer directly; `true` re-enables the QA gate |
| `DEMO_AUTO_VERIFY` | `true` skips the OTP for a matched identifier. Temporary demo bypass; set `false` and restart to restore the gate |
| `SINGLE_AGENT` | `false` keeps chat routing plus reasoning. `true` gives every turn to one agent using the full snapshot and `single_agent.md` |

Model identifiers are configuration, not architecture. Bind them at the adapter boundary so a role can change model without a rewrite of flow control.

## Development

Work as if every piece will be replaced.

- Keep the harness, the three agent roles, and the authenticator behind explicit interfaces.
- Do not let conversation state leak into the reasoning path, or reasoning output skip evaluation.
- Do not fold the authenticator into an agent prompt.
- Prefer typed boundaries and small modules over a shared utility pile.
- When in doubt, add a seam.

Testing strategy, service contracts, and ownership across the team will be documented as they are decided. Leave room for those decisions rather than encoding them early in the wrong layer.

## Contributing

This is an OpenG2P / jan-ai project, hosted on GitHub at [KaushalrajPuwar/grm](https://github.com/KaushalrajPuwar/grm).

1. Branch from the active development line.
2. Keep changes scoped to one module or one contract.
3. Open a pull request on [GitHub](https://github.com/KaushalrajPuwar/grm).
4. Say what you changed, what you deliberately left open, and what another teammate should not have to rediscover.

## Related

- [OpenG2P](https://openg2p.org) — open-source platform for registries and G2P delivery
- [OpenG2P documentation](https://docs.openg2p.org)
- [OpenG2P on GitLab](https://gitlab.com/openg2p)

## Licence

Licence to be confirmed with the OpenG2P project. Do not assume a licence until one is added to this repository.
