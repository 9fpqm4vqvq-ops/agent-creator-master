# v0.5 test results and actual readiness

Validation date: October 30, 2026 (Asia/Baghdad).

| Validation | Result |
| --- | --- |
| Released v0.4 source manifest | 371 SHA-256 entries verified before editing |
| Released v0.4 baseline | 473 passed: root 126 + MAOS 15 + Income 12 + Shorts 5 + Trader 315 |
| Final root suite | **179 passed**, no skips/failures |
| Preserved vendor suites | **347 passed**: 15 + 12 + 5 + 315 |
| Full final validation | **526 passed**, no skips/failures |
| Chromium local UI | PASS: 13 views, 9 department panels, consistent totals, project/campaign fields, connector states, filtering/history, escaped content, desktop/mobile and no mobile page overflow/JavaScript errors |
| Python / JavaScript | compileall and node --check passed |
| Original vendor integrity | Tracked original vendor source bytes preserved; receipt in evidence/v05-vendor-integrity.json |

Commands:

```bash
python -m unittest discover -s tests -v
python scripts/validate_all.py
node --check dashboard/app.js
```

HTTP checks require local loopback socket permission; final runs actually bound/read
local HTTP rather than skipping/mocking the server. Raw logs are in
[evidence/v05-baseline-validation.log](evidence/v05-baseline-validation.log),
[evidence/v05-hub-tests.log](evidence/v05-hub-tests.log),
[evidence/v05-validation.log](evidence/v05-validation.log) and
[evidence/v05-browser.json](evidence/v05-browser.json). v0.3/v0.4 logs remain historical.

## New coverage

The 53 new scenarios cover the exact 13 roles per new department and retained Income
hierarchy, routing suggestions, Management gates, scoped skill selection, specialized
QA omissions/rework/author independence, missing capability escalation and Health.
They exercise new namespace families/ACLs and stale-on-recall evidence without a scan.

Project checks cover persisted briefs/revision conflicts, Web/Social decomposition,
idempotent scopes, cross-department dependencies, invalid-batch rollback, restricted
handoff acknowledgement, actual site/API files, a running generated SQLite API with
HTTP validation/persistence, exact same-project/owning-department approval (including rejected borrowed review packets), project budget aggregation and
dated technology-claim requirements.

Social checks cover draft calendars versus actual schedules, timezone/hypothesis
validation, internal versus independent review, edit invalidation, actual escaped SVG
output, supplied analytics/missing counts/defined rates, simulated publication and
refusal of unreviewed substitute copy. Connector checks cover actual adapter invocation
boundaries with fixtures, config-only/disconnected states, read versus write grants,
cross-runtime restrictions, no write-based connection tests, exact destination/argument/
cost authority, replay/ambiguous failure, secret rejection, disabled tools, unreviewed
deployment refusal, immutable simulation evidence, read reconciliation and runtime
refresh invalidation.

Supply checks hash all 417 preserved uploaded skill entries, verify individual
dispositions, native-wrapper provenance/scopes/fingerprints/no hooks, required specific
profiles, real supplied CSV search and honest pinned-source substitutions. Reporting
checks use real local HTTP/read-only behavior and CLI input/routing behavior.

Migration checks use an actual synthetic dump produced by the released v0.4 code,
including IN_PROGRESS work, history, knowledge and reservations; schema 5 preserves
them and conservatively holds old work. Baseline metadata reconciliation requires an
exact previewed diff, actual independent-review/authorization/test references, explicit
capability expansion scope, idle/migration-held tasks and persistent old/new revisions.
All previous 126 root and 347 vendor scenarios remain; the old future-version guard
now checks schema 6, and department-count assertions retain all original departments
while allowing the two additions.

## Fixture boundaries and unverified integrations

Model/independent-QA/provider/cost/analytics references in unit tests are explicitly
synthetic. Browser data is synthetic local data. The generated API, local HTTP,
filesystem artifacts, SQLite operations, source hashes and subprocesses were actually
executed. Neither these checks nor a simulated connector establish real model review,
account authentication, design editing, MP4 output, native mobile compilation,
publication, application deployment, private analytics, token savings or profitability.

No authenticated Claude mission, Figma editor, Higgsfield, Hyperframes render/FFmpeg
pipeline, social account, mobile SDK build, deployment provider, live Skill Finder,
Notion, paid-provider billing hard cap or unattended paid runtime was validated.
The build did read the user-supplied upstream GitHub repositories and pins their
source commits; this is source inspection, not live creative/account integration.
Markdown remains a working local projection; Obsidian the application is not connected.

The ZIP additionally must pass source-manifest/extraction checks and the same suites
before publication. RELEASE-MANIFEST.json records packaged bytes. Public release
metadata/SHA256SUMS identifies the archive externally; operational DBs, credentials,
private Vaults, outputs, node_modules and Git history are excluded. The bundled UI/UX
CSV directory is explicitly reviewed source data, not operational user data.
