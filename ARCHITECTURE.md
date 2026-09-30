# GRM Architecture

Living draft. This file records current understanding of the OpenG2P Beneficiary Conversational Agent. It is not a frozen specification. Implementation and this document will move together. Where they disagree, record a decision rather than patching around it.

Status: early scaffolding, pre implementation.
Last reviewed: 2026-09-22.
Change in: ADR-0001
Last updated by: Kaushalraj Puwar.

## 1. Purpose

Provide a single beneficiary facing conversational service over voice and chat for government social benefit programmes. The service answers questions, checks eligibility, tracks benefit status, and handles grievance redressal. All beneficiary facing answers are grounded in authenticated structured records.

## 2. Goals

* Give beneficiaries a simple conversational path to concrete answers about schemes, payments, and complaints.
* Keep routine dialogue fast and low latency.
* Isolate deep structured data analysis in a larger reasoning component.
* Validate every candidate answer independently before delivery.
* Enforce identity as a hard programmatic gate.
* Keep every layer replaceable: models, storage, transport, and deployment target.

## 3. Non-goals

* No autonomous backend access from the reasoning path. Analysis runs on a pre-fetched blob.
* No user facing output that has skipped evaluation.
* No identity reasoning inside an agent prompt. Verification stays programmatic.
* No single irreversible implementation path. Thin modules with explicit seams take priority over early completeness.
* No licence or production hardening decisions in this draft.

## 4. Users and interaction modes

* Primary users: beneficiaries and citizens using government social benefit services.
* Modes: voice and chat. Both enter through the same session and flow control.
* Service goals: information seeking, eligibility checks, benefit status tracking, grievance redressal.
* Personal data boundary: protected records are accessed only after the authenticator gate succeeds.

## 5. Design principles

* Authenticated context first. Resolve identity before touching protected data.
* Structured evidence over improvisation. Reason from the blob, not from prior assumptions.
* Prompt controlled flow. Branching, clarification, satisfaction checks, and closure are harness state.
* Independent validation. The writer of a candidate is never its reviewer.
* Light front line. The assistant owns dialogue. The reasoning model is used only where analysis is needed.
* Swap, do not weld. Interfaces must survive a change of model vendor, store, or transport.

## 6. Tech stack (locked 2026-09-22)

Decided through grill, ratified in ADR.rst. Everything below it must be consistent with this table.

| Layer | Choice | Notes |
| --- | --- | --- |
| Language | Python 3.12 | Already pinned by `.python-version` |
| Harness | LangGraph | Stateful graph for handoffs, gates, bounded retries |
| Model clients | LangChain chat models, one fixed instance per agent | Handoff is graph edges, model calls are per node transport; no runtime model selection |
| API | FastAPI plus Pydantic v2 | Strict JSON blob contracts, CSV export only |
| Beneficiary 360 | Typed client behind an interface, mock now | Real spec exists, colleague owns it; swap mock for real without touching flow |
| Channels | Transport neutral turn connector, versioned REST JSON now | Chat scope only here; voice team integrates through the same turn contract; WebSockets later behind the same seam; no CLI as interface |
| Sessions | Redis | Live session and history pointers |
| Blob snapshots | SQLite file plus Redis pointer | Session keyed snapshot table with fetched at and cleanup; Postgres path kept open for deploy |
| Authenticator | Plain deterministic function plus thin FastAPI wrapper | Callable from graph, HTTP, and tests; zero LLM calls |
| Observability | LangSmith plus structlog JSON | OpenTelemetry, Prometheus, Grafana deferred |
| Packaging | uv plus ruff plus mypy | Lint, format, typed boundaries |
| Testing now | Minimal functional tests only | Full pytest async plus httpx, respx, model stubs deferred |
| Run now | Local machine, no containers | Docker and Kubernetes at deploy time only |

Replacement rules: REST to WebSockets behind the connector seam; SQLite to Postgres behind the store seam; structlog to OpenTelemetry without touching flow code.

## 7. System context

Actors:

* Beneficiary on voice or chat.
* Client and server entry point holding the session.
* Agent harness owning execution and state.
* Three model roles: assistant, reasoning, QA and evaluation.
* Programmatic authenticator gate.
* Backend: API layer with typed Beneficiary 360 client; SQLite snapshots plus Redis sessions for the local run; PostgreSQL and Kubernetes as deploy targets.

External context:

* OpenG2P ecosystem for registries and government to person delivery.
* Scheme rules and beneficiary records owned outside this service and read through controlled APIs.

## 8. Runtime and data path

Deploy target path:

```text
Server -> Kubernetes -> PostgreSQL -> API layer -> Data blob (JSON)
```

Locked for now: local machine run with SQLite plus Redis and no containers. Kubernetes and PostgreSQL enter at deploy time. See section 6.

Notes:

* The API layer is the only controlled read path for beneficiary and programme information in a session.
* The data blob is the reasoning substrate. Strict Pydantic JSON canonical; CSV export only.
* The reasoning agent does not choose endpoints. It receives the blob plus turn context.

## 9. Component catalogue

| Component | Kind | Responsibility |
| --- | --- | --- |
| Assistant agent | Low latency model | Dialogue turns, greeting, clarification, presentation, satisfaction, session interaction |
| Reasoning agent | Larger reasoning model | Blob filtering, structured analysis, candidate synthesis |
| QA and evaluation agent | Independent model | Retrieval validity, relevance, accuracy, completeness, safety |
| Authenticator gate | Programmatic, non agent | Identity verification, beneficiary record resolution |
| Agent harness | Infrastructure | Tool chain execution, flow control, chat and session state |

## 10. Agent harness

The harness is infrastructure, not a fourth agent. It owns:

* Tool chain execution. Invoke approved tools and backend calls in the order required by the active path. Pass structured outputs between stages.
* Prompt based flow control. Apply state transitions, branch conditions, clarification loops, satisfaction prompts, and closure behaviour.
* Chat history and session state. Persist conversation context, current service state, user feedback, and enough state to resume an incomplete path safely.

Boundaries:

* The harness does not make autonomous domain decisions.
* All flow transitions must be observable and testable without calling a model.
* Flow definitions should live as data or explicit state handlers, not buried inside prompts.

## 11. Assistant agent

Owns the beneficiary relationship for the turn.

Duties:

* Greeting and identifier request.
* Clarification when input is denied, off topic, or underspecified.
* Presentation of validated answers in a session appropriate form.
* Satisfaction prompts and continuation or closure handling.

Must not:

* Perform deep structured analysis.
* Bypass the authenticator.
* Deliver unvalidated candidates.

Latency target is qualitative at this stage: routine turns should feel conversational. Quantitative budgets are an open question.

## 12. Reasoning agent

High capacity analysis component. Receives the blob plus relevant turn context.

Stages:

1. Ingestion. Accept blob and turn scoped context.
2. Contextual filtering. Keep only fields and records relevant to the active request.
3. Structured reasoning. Interpret relations across beneficiary, enrolment, scheme, payment or disbursement, and grievance records present in the blob.
4. Candidate generation. Synthesise a structured answer grounded in retained evidence.
5. Threshold governance. Apply the configured confidence requirement before handoff. Design reference uses greater than 90 percent. Final value is undecided.
6. Evaluation handoff. Pass candidate plus supporting context to QA.

Must not own the conversation or replace the authenticator.

## 13. QA and evaluation agent

Independent check before anything reaches the beneficiary.

Checks:

* Retrieval validity. The answer is grounded in authorised context supplied to the reasoning path.
* Relevance. The answer addresses the actual request, not an adjacent topic.
* Accuracy and completeness. No unsupported claims, no missing material facts, no partial handling.
* Safety. Reject or revise output that should not be exposed in its current form.

Correction loop: on failure, return corrective context to the reasoning agent and require a revised candidate. No direct beneficiary output from this role.

## 14. Authenticator gate

Hard security boundary. Programmatic verification and identity resolution. Explicitly not an agent.

Locked shape: plain deterministic function plus thin FastAPI wrapper, callable from graph, HTTP, and tests. Zero LLM calls.

Rules:

* No planning, no intent reasoning, no answer generation.
* No bypass path. Protected data access requires success here.
* Behaviour on no record found: register or create the required record, then continue to enrolment confirmation.
* Behaviour on denial or off topic input: clarify and loop back to the identifier check.

Exact identifier type and verification flow are undecided and depend on backend contracts.

## 15. Data blob contract

Intent: a single turn scoped, authenticated snapshot that the reasoning agent can analyse without further backend roaming.

Locked: strict Pydantic JSON canonical; CSV export only.

Proposed shape, subject to change:

```text
blob = {
  beneficiary: {...},
  enrolments: [...],
  schemes: [...],
  disbursements: [...],
  grievances: [...],
  meta: { session_id, fetched_at, source_refs }
}
```

Open points:

* Field level allow list per scenario.
* Size limits and filtering policy before model handoff.
* Provenance refs so QA can trace each claim to a record.

## 16. Conversation lifecycle and state machine

Phases: initiation and identity, intent execution and routing, feedback and wrap up.

Control points:

| Control point | System action | Next state |
| --- | --- | --- |
| Identity gate | Confirm identity, register if new | Enrolment confirmation |
| Enrolment state | Associated scheme or seeking new | Existing scheme, new scheme, general query |
| General query confidence | Answer only when context is relevant, else clarify | Answer plus satisfaction check, or clarification |
| Session continuation | Use explicit satisfaction signal | Next request, closing message, auto close |

State sketch:

```text
init -> greeting_id_check -> {confirmed | new_user_registered | clarify_loop}
  -> enrolment_confirmed -> {existing_scheme | new_scheme | general_query}
  -> answer_candidate -> evaluation -> {deliver | revise}
  -> satisfaction_check -> {continue | close}
```

Clarification loops are harness controlled with bounded retries. Unbounded free form retry is out of scope.

## 17. Scenario flows

### 17.1 Existing scheme

For a user already enrolled. Extract relevant status and details. Present a structured summary. Typical data: enrolment, disbursement cycle, payment status, blocker flags.

### 17.2 New scheme

For a user seeking a new scheme. Retrieve profile and scheme rule context. Compare attributes to eligibility conditions. Distinguish supported matches from missing or failing evidence. Present recommendations with a concise basis.

### 17.3 General query

For open information requests. Decide relevance and answerability from available context. Relevant path: answer from evidence, then satisfaction check. Low confidence or irrelevant path: fallback clarification, request better context, re enter only when context improves.

### 17.4 Non receipt or delayed benefit

Retrieve disbursement and payment status through the API layer. Identify the blocker or status for delayed, partial, or missing benefit. Use profile data only as needed to interpret status. Present a structured summary with next action, correction path, timeline, or escalation route where data supports it.

### 17.5 Scheme eligibility and recommendation

Same engine as new scheme, with emphasis on correct matching and refusal to infer beyond evidence.

### 17.6 General grievance redressal

Complaint style turns needing acknowledgement, status, and next step or escalation guidance. Capture and clarify the grievance when needed. Hold grievance context in session state until satisfaction or closure.

## 18. Confidence, evaluation, and correction loops

Gates:

| Gate | Pass | Fail action |
| --- | --- | --- |
| Reasoning confidence | Meets threshold and is evidence grounded | Do not commit the candidate |
| QA and evaluation | Accuracy, relevance, safety, completeness acceptable | Re prompt reasoning with corrective context |
| Assistant presentation | Validated answer fits session and format | Return to harness for correction before display |

Retry policy is undecided. Needs bounds on revision rounds, backoff, and what the beneficiary sees during a retry.

## 19. Session and chat history

Locked store: Redis for live session and history pointers; blob snapshots in SQLite keyed by session with cleanup.

Harness persists:

* Turn history for continuity.
* Current service state and active scenario.
* Grievance context while an issue is open.
* User feedback signals.
* Enough state to resume after interruption.

Retention, redaction, and audit policy are open. No raw secrets in history. No protected data in logs by default.

## 20. Backend API surface

Locked: typed Beneficiary 360 client behind an interface, mock now against the existing spec, real client later without touching flow.

Assumed reads, to be confirmed against the real contracts:

* Beneficiary record lookup and registration.
* Enrolment and scheme association reads.
* Scheme rules or programme metadata reads.
* Disbursement and payment status reads.
* Grievance record read and write.

All reads for a turn feed the blob assembly step. Direct model to backend calls are out of scope.

## 21. Storage

Locked: SQLite file for per session blob snapshots plus Redis for session pointers. Postgres path kept open for deploy. Schema, migration strategy, and retention policy still to be defined.

## 22. Deployment

Locked: local machine with no containers for now. Docker and Kubernetes enter at deploy time. Image layout, service topology, scaling policy, and environment promotion are undecided.

## 23. Configuration and model binding

Environment provides endpoint base, credentials, and one model identifier per agent role. See `.env.example`.

Rules:

* Bind models at the adapter boundary.
* A role changes model by configuration, not by flow rewrite.
* No model identifier hard coded in flow logic.
* No credential committed to the repo.

## 24. Security and privacy

* Authenticator success is required before protected data access.
* Least privilege reads per scenario.
* Redact identifiers in logs and traces by default.
* Separate secrets from code and from session state.
* Threat model, audit trail, and data retention policy are open.

## 25. Observability

Locked: LangSmith plus structlog JSON. OpenTelemetry, Prometheus, and Grafana are deferred.

Minimum intent, not yet implemented:

* Structured logs for state transitions, tool calls, gate outcomes, and evaluation verdicts.
* Trace per turn from entry to delivery or revision.
* Metrics for latency by role, evaluation pass rate, revision rounds, clarification rate, and closure reasons.
* No beneficiary data in log bodies without explicit allow listing.

## 26. Failure modes and fallback behaviour

* Identity not verified: stay in clarification. Expose no protected data.
* Context insufficient: ask a targeted clarification question. Re enter the reasoning path only after context improves.
* Candidate fails evaluation: do not deliver. Re prompt with corrective context within bounded retries.
* Backend unavailable: fail closed with a safe message. Do not invent status.
* Model unavailable or slow: degrade to a safe holding response. Keep session state intact.
* User dissatisfied: route to clarification or escalation, preserve grievance context.

Exact copy for safe responses is undecided.

## 27. Testing strategy

Locked: minimal functional tests now so breakage is visible. Full layers deferred: unit tests for flow transitions, gate logic, blob assembly, and redaction with no model calls; contract tests for backend APIs and blob schema; golden path tests per scenario with fixed blobs and stubbed models; adversarial and evaluation tests; load checks once the runtime exists.

## 28. Modularity seams and replacement rules

* Harness exposes flow, tool chain, and state interfaces. Agents plug in behind them.
* Each agent role has an adapter. Model change stays inside the adapter.
* Authenticator is a function or service call, never a prompt.
* Blob assembly is a separate module with schema validation.
* Session store is behind an interface. Swap without touching flow code.
* Channel connector is behind an interface. REST to WebSockets swaps there.
* Prefer a new module over growth of a shared utility file.

## 29. Open questions

* Identifier type and verification flow.
* Confidence threshold final value and calibration method.
* Revision retry bounds and user visible behaviour during retries.
* Real Beneficiary 360 contract binding and field allow lists.
* Session affinity and retention policy.
* Latency budgets per role.
* Evaluation metric definitions and who owns them.
* Team ownership per module and testing responsibilities.

## 30. Glossary

* GRM: grievance redressal mechanism, the complaint handling scope of this service.
* Harness: infrastructure wrapper owning tools, flow, and state.
* Blob: authenticated structured snapshot supplied to reasoning.
* Gate: a pass or fail checkpoint. Authenticator, confidence, QA, and presentation are all gates.
* Turn: one beneficiary input plus system handling through to response or clarification.
