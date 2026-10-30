# v0.5 source reliability audit and bounded v0.6 repairs

Audit date: October 30, 2026 (Asia/Baghdad). This audit used a separate host agent
context and synthetic local SQLite/filesystem tests. It is not evidence that any
Claude/OpenAI account, model API, publishing service or paid background process
was configured or invoked.

## Baseline classification

Classifications apply to the actual v0.5 implementation, not the intended role names.
The root audit preserves the released archive and complete baseline test evidence.

| Modules / feature | v0.5 classification | Actual behavior |
| --- | --- | --- |
| `core`, `legacy`, `roles`, `departments` | FULLY FUNCTIONAL local governance; model execution MISSING | Enforced plan/assignment/preflight/state transitions, explicit role allowlist, parent/dependency and artifact gates; dispatch/start record packets/intent, not a model invocation. |
| `memory`, `freshness`, `providers` | FULLY FUNCTIONAL local record/projection workflows, with concurrency repairs needed | Persistent namespaces/history, freshness and Markdown conflicts/retries work locally. Notion is an explicit MISSING implementation. Source verification and role identity are operator evidence, not an authentication service. |
| `usage` | FULLY FUNCTIONAL local ledger/gates; provider telemetry FUNCTIONAL WITH CONFIGURATION | Distinct unknown/measured/estimated values, reservations and six budget scopes. No automatic provider billing client; forecasts are not hard provider caps. |
| `skills`, `skill_finder` | FUNCTIONAL local inventory/lifecycle; execution PARTIALLY IMPLEMENTED | Fingerprint/scope checks and candidate quarantine work. Dependency metadata is recorded, not equivalent to installing or running a skill's tool. Finder needs a configured transport; auto-install is disabled. |
| `projects`, `social`, `design`, `ecommerce` | FULLY FUNCTIONAL bounded local helpers; broader AI production FUNCTIONAL WITH CONFIGURATION | Actual prototype files/API, SVG/calendar outputs, supplied-data arithmetic and archived CSV lookup. They do not perform autonomous software reasoning, render an MP4, publish or obtain private analytics. |
| `connectors` | PARTIALLY IMPLEMENTED integration layer | Callable adapter boundary, permission/argument/subject approval guards and durable external intents execute configured callbacks. No general authenticated provider SDK bridge is bundled. Test fixtures do not establish live connections. |
| `scheduler` | FULLY FUNCTIONAL fixed local scheduling; AI execution DOCUMENTATION / queued requests | Disabled defaults, claims/leases/retries/recovery for local handlers. AI jobs create tasks, not actual model calls. |
| `improvements` | FUNCTIONAL reviewed update controls, with a BROKEN staging data omission | Hashed proposals, exact QA links, authorization, backups and rollback exist. The old stage copy dropped reviewed UI CSV data. Copying a directory is not an OS execution sandbox. |
| `monitoring`, `dashboard`, `reporting` | FULLY FUNCTIONAL local read-only reporting | Observed records, partial health, workload and cost views. Actual agent invocation/process monitoring was MISSING before the runtime extension. |
| `migrations`, `intelligence_schema`, `expansion_schema` | FULLY FUNCTIONAL additive local storage | Consistent backup/integrity checks and conservative migration holds; no destructive downgrade. |
| `__main__`, `intelligence_cli`, `security`, `__init__` | FULLY FUNCTIONAL bounded CLI/input utilities | Explicit local actions, redaction and path guards. These are neither a credential manager nor an OS sandbox, and a role-name argument does not authenticate a model. |

## Confirmed failures repaired in this change

### Concurrent memory writes and history

The old MemoryVault.put read an existing record before acquiring its write
transaction, then performed an unconditional UPSERT. A controlled two-connection
reproduction against the unmodified release accepted both writers using
expected_revision=1. Both returned revision 2; the final body belonged to writer A
while revision-2 history contained writer B. This was a real local SQLite race,
not a model/provider simulation.

The repair acquires the writer lock before reading, uses an exact revision/body
compare-and-swap for updates, inserts new IDs without a conflict-overwriting UPSERT,
and records body/history in the same transaction. A caller's existing transaction
is preserved via a savepoint. commit=False retains its explicit-commit behavior.
The returned record is the version written in that transaction. Existing namespace,
redaction, stable-ID, immutable supersession and optimistic-conflict APIs remain.
Existing historically inconsistent records are not silently rewritten; inspect and
reconcile such evidence explicitly if an older deployment experienced this race.

### Stale freshness decisions

Old freshness metadata updates targeted only the record ID. An earlier review could
therefore label concurrently edited knowledge FRESH or reuse a stale revision.
Updates now compare both revision and content_hash atomically and raise ConflictError
on a changed subject. Supersession also rechecks the replacement's revision/hash and
current fresh/non-superseded state inside the transaction before changing the old item.
History remains intact, and stale review evidence cannot freshen a new body.

### Upgrade staging and live workers

The old Improvements.stage excluded every directory named data, including the
reviewed vendor/supplementary/ui-ux-pro-max-skill/data source CSV directory. The real
project suite needs those files, so the stage was incomplete despite passing the
small fixture validator. Staging now keeps only that exact reviewed source-data
exception while still excluding operational data, outputs, Vaults and unrelated
vendor data directories.

The idle check now feature-detects agent_runs and agent_invocations, plus process
lifecycle tables. Queued/running/approval/QA/rework work and unfinished provider/tool
processes block instruction activation even when a parent task was cancelled.
A premature terminal flag with an unfinished live PID also blocks activation.
Actual terminal TIMED_OUT/OUTPUT_LIMIT outcomes do not create permanent false blocks;
workspace_checks PASS/FAIL outcomes are not treated as active processes. Unknown
runtime lifecycle schemas fail closed. PID inspection sends no terminating signal;
actual process identity/recovery belongs to the runtime/workspace process manager.

## Runtime insertion requirements found by the audit

- Preserve explicit user-selected owners, while allowing an unscoped Management
  intake to choose a specialist. v0.5 pinned the implicit default owner too.
- Make result/state/execution updates atomic. Legacy submit/dispatch previously
  committed a compatible status before the extended phase/event transaction.
- Runtime cancellation must stop/cancel actual processes and retain unresolved
  charges/external receipts; changing only the task phase is insufficient.
- Give Management, specialist, QA and tool/provider invocations distinct stable
  invocation/reservation keys. The existing ledger permits one cumulative provider
  invocation per reservation and requires the reservation's agent to match.
- Bind model-facing memory/tool actors to the invocation identity; never accept a
  role or namespace authority supplied by model tool arguments.
- Use actual separately invoked QA results linked to the producing invocation and
  exact output bytes. Retain the existing structured criterion/check validators,
  correction history and bounded escalation; add repeated-identical-failure handling.
- Never turn an ambiguous external result into an automatic retry. A verified
  external receipt must survive telemetry/post-processing failure. Reconciliation
  and provider idempotency are separate from model/task retry policies.
- Treat subprocess/workspace containment and provider authentication as observed
  capabilities. A folder copy, config, tool name or interactive session is not proof.
  Filter provider event streams explicitly; never persist hidden reasoning or raw
  credential-bearing requests/responses.

These integration items are owned by the v0.6 runtime/core implementation, not by
this bounded memory/freshness/staging patch. No vendor source was modified here.

## Verification

`tests/test_v06_reliability.py` adds 11 meaningful local scenarios: independent
SQLite writers, returned/history consistency, caller transaction visibility and
rollback, commit=False, failed FK write savepoints, stale body and metadata reviews,
reviewed source data versus private data staging, runtime/invocation idle detection,
live cancelled-process detection, terminal limits and unknown lifecycle rejection.
All 11 passed. The existing Memory/Freshness/Upgrade subset (34 cases) also passed
after the main fixes. The root integration must still run both required complete
commands after parallel changes settle:

```bash
python -m unittest discover -s tests -v
python scripts/validate_all.py
```

This evidence establishes local persistence/guard behavior. It does not establish
live model QA, remote connector operations or production sandbox availability.
