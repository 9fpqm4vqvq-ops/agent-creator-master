# Intelligence, monitoring and safe maintenance — v0.4

This release extends the existing supervised hub. It adds no paid API, hosted
service, second operational database or brokerage connection. Python 3.10+ standard
library serves the dashboard and persists all records in `data/hub.sqlite`.

## Local dashboard

```bash
python -m agent_hub migrate
python -m agent_hub dashboard --port 8765
# Open http://127.0.0.1:8765 on the same computer.
```

The dashboard is interactive and read-only: nine views, task filtering, parent and
child references, owner, department, full task history, QA evidence/failed criteria,
usage, budgets, approvals, department health, knowledge age, agent scorecards and
maintenance/change histories. It polls every 15 seconds by default and has manual
refresh. Counts cover all tasks; displayed task list is capped at 500, QA records
at 200, health/runs/changes at 100 and freshness records at 200. Task detail includes
all events, invocations and current budget evaluation. Scorecards cover all records.

The HTTP server binds only to loopback. Each API response uses one read transaction
on a `mode=ro`, `query_only` connection; GET never initializes or migrates a Hub.
Only explicit static paths are served. Mutation methods are refused, Host/Origin
are checked, no CORS is enabled, and content is rendered with textContent under CSP.
It is for a trusted local operator; it has no public hosting, network identity or
multi-user login. Do not proxy it onto the public Internet.

## Command interface

Existing task commands are unchanged. New service operations accept a JSON object
of keyword arguments with `--data PATH`. Keep these files under ignored `work/`.
No file needs credentials. Empty argument operations may omit `--data`.

```bash
python -m agent_hub usage summary
python -m agent_hub health audit --data work/health.json
python -m agent_hub freshness scan
python -m agent_hub scorecards list
python -m agent_hub scheduler list
python -m agent_hub improvements get --data work/proposal-id.json
```

| Command / action | JSON fields |
| --- | --- |
| `usage record` | `entry` object below; optional `expected_revision` |
| `usage summary` | optional `task_id`, `agent`, `department` |
| `usage estimate` | `usage` token counts and `rates` with source, checked_at, currency, input_includes_cache and four FIELD_per_million rates |
| `budget configure` | `scope`, `key`, `limit_usd`, optional `alert_ratio` (default 0.8) |
| `budget evaluate` | `task_id`, `agent`, optional `projected_cost` |
| `budget approve` | `approval_id`, `reference`, optional `valid_minutes`, `maximum_usd` |
| `health audit` | `department`, optional `review_kind` daily/weekly/monthly/quarterly |
| `health get` / `health approve` | `identity`; approve also `qa_task_id` |
| `freshness scan` | optional `at` aware time, `queue` boolean |
| `freshness queue` | `record_id` |
| `freshness verify` | `record_id`, `qa_task_id` |
| `freshness supersede` | `record_id`, `replacement_id`, `qa_task_id` |
| `freshness history` | `record_id`, `actor` with namespace read access |
| `research-cache record` | `task_id`, `query`, `source`, `references` list, optional `ttl_seconds` (1–86400) |
| `research-cache lookup` | `task_id`, `query`, `source` |
| `scheduler configure` | fixed job `identity`, `enabled` boolean; optional `cadence`, `interval_seconds`, `departments` |
| `scheduler list/tick/history/recover` | no arguments |
| `scheduler run` | optional `poll_seconds` (1–60); explicit foreground loop, Ctrl-C stops |
| `improvements propose` | `department`, research-backed `reason`, `files` mapping relative paths to text, optional `health_review_id` |
| `improvements get/stage/test` | `identity` |
| `improvements qa` | `identity`, `task_id` of completed independent QA review packet |
| `improvements activate` | `identity`, `authorization_reference`, optional `allow_permission_expansion` boolean |
| `improvements rollback/recover` | `identity`, `authorization_reference` |

## Usage evidence and budget controls

The ledger is separate from trading capital. Each cumulative provider invocation
has one stable `(provider, invocation_id)` identity, its task, registered agent,
derived department, model, collection time/source, token evidence kind, optional
actual and estimated USD charges, cache read/write counts and duration. No provider
is polled automatically. Import real runtime/provider telemetry using, for example:

```json
{
  "entry": {
    "task_id": 1,
    "agent": "management-director",
    "provider": "REPLACE_WITH_ACTUAL_PROVIDER",
    "model": "REPLACE_WITH_ACTUAL_MODEL",
    "invocation_id": "REPLACE_WITH_ACTUAL_INVOCATION_ID",
    "source": "REPLACE_WITH_ACTUAL_TELEMETRY_REFERENCE",
    "token_kind": "UNKNOWN"
  }
}
```

Missing values remain null/UNKNOWN, never measured zero. Use `MEASURED` only for
observed counters, `ESTIMATED` for estimated counters. Preserve cumulative counters:
identical replays do nothing; changed telemetry requires the current expected_revision.
Use explicit collected_at timestamps for auditable cumulative exports; identical replays without a timestamp retain the original collection time. Actual and estimated costs are displayed separately. Budget charging uses actual
where available, otherwise explicit estimate, without adding both. Inclusive input
and cache counts are not summed twice. Pricing estimates require explicit cache
semantics and dated rate provenance; bundled code contains no claim of current prices.

Set TASK (key = task ID as string), AGENT, DEPARTMENT, DAILY or MONTHLY (key = global)
budgets. Calendar boundaries use Asia/Baghdad. For example `work/budget.json`:

```json
{"scope":"DAILY","key":"global","limit_usd":"5.00","alert_ratio":"0.8"}
```

Before an actual invocation, use `start ID --evidence ACTUAL_REFERENCE
--projected-cost AMOUNT`. `start` checks budgets, records warnings and atomically
reserves the forecast for one task/handoff. An exceeded budget or unknown cost
under a configured budget creates a persistent PENDING authorization and leaves
the task at PREFLIGHT. Inspect it, obtain actual scoped authorization, then use
`budget approve` and retry the same start with `--approval-id ID`. Unknown estimates
require an explicit maximum_usd ceiling. Authorization is bound to task/agent,
execution key, estimate and budget configuration, expires, and is consumed once.

Supply the resulting execution_key when recording telemetry to reconcile its
reservation. Submitted/cancelled work retains unresolved holds until telemetry
arrives; unknown spend must not disappear. Reservations carry across calendar
periods conservatively. Budget evaluations expose negative remaining funds and
unknown costs. A charge above its forecast can exceed a budget; the recorded cost
is retained rather than falsified to fit the cap.

These gates control the supported hub start path. They cannot physically interrupt
an already-running external Claude session, observe unreported charges, or implement
a provider billing hard cap. Configure provider-side limits separately. With no
configured limits, UNKNOWN telemetry does not block start. Identity/reference text
is operator attestation, not a signed billing or authorization identity.

Use a single qualified owner per task; document complexity and team rationale in
resource_plan. Create scoped child tasks for additional specialists. Optional
idempotency keys on `new` reject conflicting replays; they do not merge distinct
requests automatically. Before repeating a search, use research-cache lookup and
recall. Cache hits are source references marked UNVERIFIED_REFERENCES, expire after
their TTL and never replace verification. No live search executor is installed.

## Department health and agent scorecards

The Health Registry records department, review kind, observed versions, local
instruction/profile integrity, skill fingerprint drift, missing tools, findings,
evidence, corrective actions, proposed updates, next due time and separate QA status.
Python version is observed; project/skill versions are declared. Availability of
python3/git/claude is checked without executing untrusted packages. The pinned CLI
version in tools/claude is not evidence that it is installed or the latest release.
Every local health observation remains PARTIALLY_VERIFIED for upstream currency.

A completed QA task authored by department-health-auditor must list `health_review_ids`
in its submitted result before `health approve` can link it. QA_REVIEWED describes
that review, and does not upgrade offline evidence into current external facts.
Auditors report to agent-creator-researcher. Their cross-department memory access
is read-only; metadata mutations use narrow freshness operations, not arbitrary
knowledge-body writes.

Scorecards include assignment/completion counts and rates, QA attempts/pass/fail,
rework, blocks, intake-to-completion duration (includes waiting), separately reported
execution duration/costs, skills and evidence of weaknesses. A generic ERROR is not
counted as a verified tool failure. `Hub.verified_tool_failure` requires the tool,
observed diagnosis and actual evidence reference; it remains an operator attestation.
No rankings, automatic removals or conclusions from untested sample sizes are made.

## Knowledge freshness

Every record has collection time, last_verified_at, next_review_at, category,
expiry_policy, confidence, verification_status, superseded_by and responsible_department.
Category TTLs in registry/freshness-policies.json are configurable from 60 seconds to
one year. Defaults: supplier/market prices 1 day, payment-service rules 7 days,
research/assumptions 30 days, procedures 180 days. These are review suggestions,
not factual guarantees. Policy edits invalidate active task snapshots.

New or edited knowledge starts UNVERIFIED. Scan marks overdue records
REQUIRES_VERIFICATION, flags same-title duplicates/potential conflicts and optionally
queues one unstarted research request per record/revision. It never deletes or
silently replaces claims. History snapshots retain each revision. Search returns
stale records visibly labeled and excludes superseded records by default; direct
get, history and the Python search include_superseded option retain access.

A verification QA task must be authored by knowledge-freshness-auditor, list
`verified_memory_ids` and exact `memory_record_hashes`, include dated VERIFIED sources,
and PASS the source_freshness check. The oldest supplied source check or actual QA
PASS time sets last_verified_at. Linking an old review cannot freshen stale facts.
Supersession requires a fresh verified replacement in the same namespace, a completed
QA task listing `superseded_memory_ids`, an exact `supersession` old→new mapping and
both content hashes. Old records stay immutable and explicitly retrievable.
Imported knowledge is UNVERIFIED locally; foreign task IDs retain provenance.

## Optional maintenance

All six seeded jobs start disabled. Daily health and freshness, weekly health and
scorecards, monthly capability and quarterly architecture reviews are suggestions.
Configure/enable each explicitly, then use one-shot `scheduler tick` or the explicit
foreground `scheduler run`. No OS service, cron job or background process is installed.
Monthly and quarterly jobs create CREATED tasks for authenticated Claude Code;
they do not invoke a model or spend on an API. Deterministic observations remain
OBSERVED_UNREVIEWED until the normal Management and independent QA path is completed.

Fixed handlers and the SERVICE:local-maintenance principal are the only allowed
scheduler execution scope. Arbitrary commands/models are not configurable. SQLite
claims/unique constraints prevent overlap of the same job across local workers.
Run identity, worker, due/start/end/lease, mode, result/error and retries persist.
Expired five-minute leases become INTERRUPTED; retries use bounded exponential
backoff and disable after three failures. `recover` records interruption; `tick`
then honors the new due time. Unfinished AI requests are reused after interruption.
Use one runner per Vault and stop it before applying instructions. Fixed local
checks are short; no lease heartbeat for long external operations is implemented.

## Reviewed improvements and rollback

1. Audit health and research the actual gap/current official sources. Reuse roles.
2. Propose immutable candidate text and baseline hashes, linked health evidence
   where applicable. Candidates live outside native discovery under work/agent-changes.
3. `stage` copies an isolated tree, omitting operational records/secrets/dependencies.
   It performs no installation or candidate execution. `test` explicitly runs the
   fixed `python scripts/validate_all.py` in that copy, retaining hashed output.
4. Agent Development authors a normal Management-led review task with the exact
   change manifest and actual test artifacts. A separate qa-auditor must review it.
   The result includes change_proposal_ids and change_manifest_hashes. Then `qa`
   links the completed review; it cannot approve unfinished/self-reviewed work.
5. Management checks the reviewed scope and actual authorization. `activate` requires
   all local tasks closed and maintenance stopped, unchanged baselines/candidates/
   tests/QA bytes, and separate explicit scope for declared tool/registry expansions.
   Textual permissions and code side effects still require human/QA diff inspection.
6. Back up the Vault and files, persist ACTIVATING intent, write reviewed bytes,
   update validated skill metadata, and store the result/history in memory. Reload
   Claude Code after instruction changes. No running task receives silent edits.
7. Failed writes restore originals; interrupted ACTIVATING/ROLLING_BACK states block
   new work until `improvements recover`. Rollback checks for later edits, verifies
   backups, restores files/skill metadata and preserves task/usage/knowledge history.

Allowed targets are root contracts, docs, agent profiles, standalone native skills,
agent_hub, dashboard and the reviewed skills/freshness registry JSON. Path traversal,
external links and symlink targets are rejected. Vendor source updates require a
separate reviewed vendoring change; imported skill links are not overwritten.
Skill edits must include registry/skills.json with exact new fingerprints; all
changed dependencies/permissions/capability scopes require explicit authorization.
Existing usage references survive metadata rollback; new reverted skill entries
stay quarantined if retained. This is a trusted local workflow, not an OS sandbox
or cryptographic multi-user approval system. Do not run untrusted staged code just
because its tests pass. No automatic skill install or permission expansion is enabled.
