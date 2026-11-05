GRM Changelog
=============

.. _changelog:

This file tracks changes and releases for the OpenG2P Beneficiary Conversational Agent project. Decisions live in ADR.rst.

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
