# Logging conventions

How this repo records history. Two files, two jobs. Do not mix them.

## Changelog vs ADR

| Question | CHANGELOG.rst | ADR.rst |
| --- | --- | --- |
| What happened? | Yes | No |
| What did we decide, and why? | No | Yes |
| Who decided it? | Contributors list only | Author field per ADR |
| When? | Version date | Date field per ADR |

Rule of thumb: if a teammate asks what changed in a release, point at the changelog. If they ask why the stack looks this way, point at the ADR.

## CHANGELOG.rst

One section per version, newest first.

```rst
Version 0.2.0 (2026-10-01)
--------------------------
- Short bullet per user visible change.
```

Rules:

* Bullets describe outcomes, not effort. Write "Add Redis session store", not "Worked on Redis".
* Every version section carries a date in `YYYY-MM-DD`.
* Never rewrite a released section. New changes go in a new section.
* The Contributors section lists people, not tasks. Add your name when you land your first change. Keep per person detail to one line.

## ADR.rst

Single file, appended records. New decisions go at the end as `ADR 0002`, `ADR 0003`, and so on. Never edit a decided record in place. A changed mind gets a new record that supersedes the old one.

Fields:

| Field | What to write |
| --- | --- |
| Title | `ADR NNNN: short decision name` |
| Status | One of the values below |
| Date | Decision date, `YYYY-MM-DD` |
| Author | Full name plus GitLab handle, for tracing ownership |
| Context | The problem and the constraints, two to four sentences. No solutions here. |
| Decision | What was chosen, stated plainly. Include the main alternatives rejected. |
| Consequences | What this choice forces on us later: seams, deferred work, migration paths. |

Status values:

| Value | Meaning |
| --- | --- |
| Proposed | Under discussion, not yet agreed |
| Accepted | Agreed and in force |
| Rejected | Considered and turned down, kept for the record |
| Deprecated | No longer recommended, not yet replaced |
| Superseded | Replaced by a newer ADR, which must name it |

Keep each section short. If Context needs more than a paragraph, the decision is probably two decisions. Split it.

## ARCHITECTURE.md

The header block is the file's own log. Every edit refreshes it, no exceptions.

| Field | What to write |
| --- | --- |
| Status | Current maturity, e.g. early scaffolding |
| Last reviewed | Date of your edit, `YYYY-MM-DD` |
| Change in | The ADR or change driving the edit, e.g. ADR-0001 |
| Last updated by | Your full name |

Rules:

* Update all three dated fields on every edit, even a small one.
* The header keeps only the latest edit. Full history lives in git log.
* An edit that implements a decision must name its ADR in Change in. An edit with no ADR behind it probably needs one.
