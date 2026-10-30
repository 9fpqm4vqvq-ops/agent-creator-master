# Master Agent System v0.7

A supervised Claude Code agent system with **70 registered roles and 176 reviewed
skills**, one SQLite Memory Vault, Management routing, separate QA, guarded local
execution and explicit authorization for consequential external actions.

v0.7 preserves v0.6 and improves functional acceptance, provider receipts, supervised
recovery, shared concurrency, run budgets, research provenance, GitHub reads and
execution reporting. **It is not certified for unattended production.**

Read [the readiness report](docs/V07-READINESS-REPORT.md) for exact live/local/blocked
results, and [operations](docs/OPERATIONS-V07.md) for architecture and controls.
Older versioned documents are historical; use this v0.7 setup and START-HERE.md.

## Quick start

Python 3.10+, Node/npm for the optional pinned Claude Code launcher, and a working
provider account/CLI or explicit API credentials. Account subscriptions do not
automatically grant API access. Docker with a reviewed dependency image is required
for generated-code checks; actual isolation probes must succeed.

```bash
python -m unittest discover -s tests -v
python -m agent_hub migrate
npm ci --prefix tools/claude --no-audit --no-fund
tools/claude/node_modules/.bin/claude auth login
python -m agent_hub runtime probe --config templates/runtime-claude.json
python scripts/live_model_check.py --config templates/runtime-claude.json --out work/first-live-check.json
```

Use the correct Windows CLI executable path if applicable. Authenticate locally;
never paste credentials into requests or JSON. A readiness probe is not inference.
The live check must return an actual completed provider receipt before continuing.
This environment's CLI inference was blocked by a read-only initialization error.
The readiness report separately identifies actual supervised host Agent-tool calls;
that interface does not become an unattended subscription API in this download.

Create a focused request as JSON (examples in START-HERE.md), then:

```bash
python -m agent_hub runtime intake --data work/request.json
python -m agent_hub runtime execute --config templates/runtime-claude.json --data work/execute.json
python -m agent_hub dashboard --port 8765
```

`work/execute.json` contains `{"task_id": ACTUAL_RETURNED_ID}`. Management chooses the
smallest qualified team unless the request locks a domain/agent. Each worker reads
current role/selected skills and recalls memory. Separate QA assesses the original
criteria and real artifacts. BLOCKED or WAITING_FOR_APPROVAL is not completion.

For web acceptance, configure exact approved commands and reviewed verifier hashes.
Trivial command exits and syntax-only checks do not establish functionality.
See [the task-page fixture](examples/task-manager/README.md) and
[acceptance templates](templates/acceptance-v07.json). Social scripts and publishing
plans remain drafts; rendered-media and real analytics require actual evidence.
No deployment or publishing happens automatically.

## Operations

- [Runtime, budgets, connectors and recovery](docs/OPERATIONS-V07.md)
- [Migration and rollback](docs/MIGRATION-V07.md)
- [Baseline audit](docs/V07-BASELINE-AUDIT.md)
- [Readiness, security and remaining work](docs/V07-READINESS-REPORT.md)
- [Historical v0.6 provider interfaces](docs/V06-PROVIDER-INTERFACES.md)

SQLite is local-first. Namespace ACLs, history and freshness checks remain enforced.
Markdown export is explicit; Notion needs its own authenticated integration.
The dashboard binds loopback and is read-only. Shared runtime capacity defaults to
one claimed worker. Unknown billing is retained as unknown, with held reservations.

The v0.7 upgrade is delivered on `upgrade/v0.7-live-acceptance` for PR review.
Existing release archives remain unchanged. Do not merge or deploy without approval.
