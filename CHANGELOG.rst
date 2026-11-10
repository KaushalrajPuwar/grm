GRM Changelog
=============

.. _changelog:

This file tracks changes and releases for the OpenG2P Beneficiary Conversational Agent project. Decisions live in ADR.rst.

Version 0.4.0 (2026-11-10)
--------------------------
- Add a deterministic opening: the caller speaks first, the welcome is said
  once, every later turn asks for the registration number, and the name is
  confirmed before the record opens.
- Remove the greeting detector. A distressed caller may open anywhere, so the
  gate no longer guesses whether an utterance is a greeting.
- Add the confirm_identity stage and the confirmation value to expects.
- Denying the name drops verification and the snapshot, then asks for the number
  again.
- Rewrite the single-agent constitution around the call flow: holding line
  before analysis, finding, meaning, next step, offer of further help.
- Add speech-first rules to all agent constitutions: no markdown, parentheses,
  symbols, abbreviations or status codes; full dates and spoken amounts.
- Add channels/speech.py, a conservative normaliser applied to every reply.

Version 0.3.0 (2026-11-05)
--------------------------
- Add SINGLE_AGENT, default false. When true, MODELID_1 handles every turn with
  the full snapshot and prompts/single_agent.md, removing the routing call and
  the discarded draft. The two-agent path remains for rollback.
- Add architecture to describe_contract and report owner single in this mode.
- Keep QA independent and disabled by default.
- Flatten conversation history into the system prompt so reasoning models no
  longer reject synthetic assistant turns without reasoning content.
- Tool failures now return one fixed, beneficiary-safe sentence with isError
  true. The real exception and provider detail stay in our logs.

Version 0.2.0 (2026-11-03)
--------------------------
- MCP is the only channel contract. The REST adapter and its web demo wiring
  are removed.
- MCP server built with FastMCP, Streamable HTTP, JSON responses, stateless.
  Tools: route_turn, check_connection, session_status, reset_session,
  describe_contract.
- QA is disabled by default behind QA_ENABLED. The agent, its prompt and the
  revision loop remain in place, so one environment change re-enables the gate.
- The reasoning candidate ships directly while QA is off.
- Demo record dates moved to October 2026 so "this month" is backed by data.
- .env is now authoritative for local runs, so a stale API_KEY exported in the
  shell cannot shadow a renewed one.
- Add DEMO_AUTO_VERIFY, a temporary switch that auto-verifies a matched
  identifier without an OTP. Set false and restart to restore the gate.
- Reasoning now states the amount held whenever money is blocked or unreleased.

Version 0.1.0 (2026-09-22) [Unreleased]
--------------------------
- Initial repository scaffolding.
- Professional README.md rewrite.
- Established project structure and version control baseline.

.. _contributors:

Contributors
------------

The following individuals have contributed to this project:

- **Kaushalraj Puwar**
- **Sidhanth Prabhu**
- **Shrey Modi**
- **Parth Samanta**

For full contribution records, see the Git history and commit messages.
