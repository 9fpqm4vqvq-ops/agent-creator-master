# v0.3 → v0.4 comparison and readiness

Review date: October 30, 2026 (Asia/Baghdad).

The released v0.3 archive's 345 file hashes were checked before editing, and all
414 baseline tests passed (hub 67; MAOS 15; Income 12; Shorts 5; Trader 315).
This is offline implementation evidence. It does not certify production autonomy.

| Area | Retained from v0.3 | v0.4 change | Actual readiness / configuration |
| --- | --- | --- | --- |
| Organization | Master → Management → department → separate QA → Master | 2 auditor profiles under Agent Development; 44 total roles across 7 departments | Native Claude invocations still require signed-in Claude Code and actual permission/tool checks |
| Task control | Plan/assign, snapshots, recall/preflight/start, parent/dependency gates, precise rework/escalation | Idempotent intake, one execution per handoff, smallest-team rationale, migration replan | Supported local workflow tested; invocation references remain operator attestations |
| Skills | 65 reviewed catalogue entries, quarantined candidates, guarded Skill Finder | Health drift/missing-file observations, reviewed instruction/registry updates and rollback | No auto installer; live Skill Finder endpoint and upstream currency unverified |
| Visibility | JSON/Markdown reports and event history | Read-only interactive local dashboard, 9 views, full per-task history and budget detail | Real local HTTP and Chromium tested; no public dashboard hosting or remote login |
| Resources | Structural token-watchdog profile | Central invocation ledger, distinct measured/estimated/unknown tokens/costs/cache/duration, five budget scopes, reservations/approvals | No live provider telemetry adapter; operator imports actual evidence; provider hard caps configured externally |
| Health | Manual maintenance guidance | Persistent observations, versions, problems/actions, due dates, separate QA linking | Local reviews are PARTIALLY_VERIFIED for current upstream knowledge |
| Knowledge | SQLite namespaces, revisions, stable IDs, source provenance, Markdown projection | Category TTLs, verification metadata/history, stale/conflict/duplicate signals, refresh requests, QA-linked supersession | No deletion; imports are locally unverified; official sources require live research |
| Performance | Task/QA/skill history | Per-agent counts/rates, durations, cost evidence, skills, failures, weaknesses, sample/difficulty caveats | Objective recorded observations; no rankings or automatic removal |
| Maintenance | No scheduler implementation | Optional fixed local checks and queued AI requests, disabled defaults, leases/history/retry/recovery | Explicit tick/foreground loop only; no OS daemon or autonomous model execution |
| Updates | Staging guidance and guarded skill candidate review | Hashed immutable proposals, isolated test execution, completed QA links, scoped activation, backups/rollback, memory history | Trusted local operator workflow; diff/security review required for new code/dependencies |
| Storage | One SQLite Vault, ACL/redaction, backup/restore, provider protocol | Additive schema 4 and persistent intelligence records, existing IDs/phases preserved | Existing v0.3 unfinished tasks held for replan; file/vault backups still operator responsibility |
| Business | Iraq e-commerce research templates, Income/Shorts/Trading packages | Monitoring applies to all 7 departments | Supplier/payment eligibility, live prices, brokerage, YouTube publishing/analytics remain unconnected/unverified |

Repairs include explicit memory INSERT columns for additive schemas, exact-rate/cache
estimate semantics, duplicate cumulative-invocation protection, missing-skill reporting
without breaking the catalogue, atomic intake/execution reservations, and skill metadata
rollback that preserves existing usage references. v0.3 future-version regression now
checks schema 5 because version 4 is the supported schema; its rejection scenario remains.

No live model delegation, independently invoked model QA, Notion sync, live Skill Finder
transport, brokerage orders or revenue was tested. Markdown projection is a working
local file adapter; Obsidian the application is not connected. Python controls are not
an OS sandbox. Provider billing, actual authenticated Claude execution and source access
remain required before claiming real-world autonomous operation.
