# v0.5 → v0.6: implementation versus verified operation

2026-10-30. Classifications concern actual implementation and observed validation,
not profile counts. V06-BASELINE-AUDIT.json preserves the pre-change plan.

| Feature | v0.5 finding | v0.6 change | Classification and limit |
|---|---|---|---|
| Roles and skills | ALREADY IMPLEMENTED | Preserve 70 roles / 176 skills | FULLY FUNCTIONAL local registration/loading; tools need dependencies |
| Master/Management routing | Manual records, handoff only | IMPROVED: unlocked intake, real Management result application | FUNCTIONAL WITH CONFIGURATION; live inference blocked here |
| Model execution | MISSING | ADDED Claude Code, Codex CLI, Responses adapters | FUNCTIONAL WITH CONFIGURATION; no successful live inference here |
| Specialist production | Local scaffolds/manual work | IMPROVED structured responses become guarded files | PARTIALLY IMPLEMENTED; fixture flow passes, live acceptance pending |
| Independent QA | Structured local attestations | IMPROVED separate invocation, actual artifact bytes and test binding | FUNCTIONAL WITH CONFIGURATION; live model QA unverified |
| Corrections | Local rework records | IMPROVED reinvoke responsible specialist with findings | SIMULATED model scenarios pass; live cycle unverified |
| Memory CAS | BROKEN under concurrent writers | FIXED serialized revision check/write/history | FULLY FUNCTIONAL tests using independent SQLite connections |
| Freshness supersession | Race window | FIXED content/revision CAS | FULLY FUNCTIONAL local provenance, not automatic factual verification |
| Public research | Cache/record framework | ADDED fetches, dates, excerpts, provenance, TTL and comparison | FUNCTIONAL WITH CONFIGURATION; direct DNS blocked here; actual host GitHub read recorded separately |
| General web search | MISSING | ADDED explicit injectable search interface | PARTIALLY IMPLEMENTED; no general search provider configured |
| GitHub/Notion reads | Candidate capabilities | ADDED documented GET adapters | FUNCTIONAL WITH CONFIGURATION; direct REST unavailable here, Notion unconnected |
| Native tools | Host discovery | IMPROVED trusted host read bridge | FUNCTIONAL WITH CONFIGURATION; host credentials do not transfer to Claude Code |
| Figma/Drive/media/social providers | Candidates and approval guards | ALREADY IMPLEMENTED controls retained | PARTIALLY IMPLEMENTED or DOCUMENTATION ONLY per candidate; no invented live integrations |
| Workspaces | Local scaffolds | ADDED isolated execution and checks | FULLY FUNCTIONAL guarded files; actual Docker check passed; browser/dependency image setup needed |
| Dependency installation | Manual setup | Explicit gate; network installs disabled | PARTIALLY IMPLEMENTED; separately reviewed images required |
| Browser checks | Host-dependent | Approved argv in compatible image | FUNCTIONAL WITH CONFIGURATION; no runtime browser acceptance claimed |
| Social assets | Real local graphics/draft services | IMPROVED runtime text/SVG files and QA input | FUNCTIONAL WITH CONFIGURATION; live model campaign unverified, video needs renderer |
| Publishing/deployment/trading | Scoped approval required | ALREADY IMPLEMENTED gates retained | No new write capability enabled; unavailable without verified provider bridge |
| Telemetry | Manual records | IMPROVED per-stage receipts and provider token fields | ACTUAL/ESTIMATED/UNKNOWN separate; USD often UNKNOWN |
| Budgets | Local enforcement | IMPROVED each invocation reserves separately | FULLY FUNCTIONAL deterministic policy; provider billing caps remain external |
| Cancellation/timeouts | No running model process | ADDED process-group termination and bounded output | FULLY FUNCTIONAL local tests; remote cancellation/rollback not guaranteed |
| Recovery | Maintenance/action recovery | ADDED durable runs/dead-worker detection/no blind replay | PARTIALLY IMPLEMENTED; safe checkpoints resume, uncertain calls need reconciliation/replacement |
| Dashboard | 13 local read-only views | IMPROVED execution view | FULLY FUNCTIONAL local HTTP regression checks |
| Skill staging | Reviewed UI CSV omitted | FIXED preserve design source data | FULLY FUNCTIONAL local staging/activation; not automatic upstream trust |
| Migration/release | Schema 5/source ZIP | IMPROVED schema 6, backup/rollback and manifest | FULLY FUNCTIONAL local migration checks; operational data excluded |
| Unattended production | Not certified | No certification added | PARTIALLY IMPLEMENTED; live acceptance and deployment security remain prerequisites |

SIMULATED denotes model/remote fixtures, not actual local filesystem/SQLite/HTTP
operations exercised alongside them. Host-plugin access is evidence of that host
operation, not proof the downloadable project inherits those credentials.
