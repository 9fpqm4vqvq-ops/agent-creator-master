# v0.5 baseline audit and implementation gap analysis

Baseline: released v0.4 ZIP, 371 verified file hashes, 473 passing checks
(126 root; 15 MAOS; 12 Income; 5 Shorts; 315 Trader). Raw baseline results
will remain in docs/evidence/v05-baseline-validation.log.

Existing strengths: explicit 44-role allowlist, 65-skill catalogue, Management-led
plan/assignment/preflight, byte-bound artifacts, independent QA/rework, one SQLite
Vault, freshness/health audits, read-only dashboard, five AI budget scopes,
optional disabled scheduler, immutable update staging/backups/rollback.

Gaps to fill: two independent operational departments (13 roles each); explicit
Management routing suggestions; department-scoped skills and namespace families;
persistent software project/campaign/content records and cross-department handoffs;
project budgets; honest connector discovery/test states and exact action approvals;
local useful software/content deliverables; specialized independent QA checks;
new dashboard views; additive migration and regression coverage.

Design choices: reuse the current Hub, SQLite Vault, usage ledger, audits, scheduler
and dashboard. No second orchestration service or background paid runtime. Keep
Income Shorts and E-commerce ownership unchanged. Scope child tasks rather than
launching all specialists. Stage third-party source outside native discovery.
Activate only reviewed local wrappers with provenance and constrained permissions.
No external publication/deployment/messages without actual scoped authorization
and a tested runtime adapter. Existing public GitHub release authorization applies
to publishing this project update, not to future business account actions.

Package review: 12 accessible uploaded ZIPs contain 417 SKILL.md entries including
CLI copies, test fixtures and unrelated business domains. Each receives an inventory
record, hash, risk flags and disposition. Two archives contain symlinks; their link
entries are not executed or copied as active instructions. Hyperframes and Headroom
were too large for the 32 MiB transfer tool, so user-supplied upstream URLs are used
as pinned source subsets and are not asserted identical to the uploaded ZIPs.

Risks: raw automatic-hook/installation/paid-model guidance conflicts with supervised
execution; overlapping session observers and memory proxies must not replace Vault;
UI/design preferences are not universal evidence; named connectors and API lists do
not establish actual access or free quotas. Unknown licenses/rates/current versions
stay explicit. Raw archived code is not executed just because it is available.

Implementation order: roles/routing/schema; reviewed skills; connector/action gates;
projects/campaign/calendar/local outputs; namespaces/freshness/health/usage; dashboard;
targeted and regression tests; source/package evidence; docs; portable release.
