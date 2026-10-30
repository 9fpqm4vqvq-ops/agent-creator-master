# Master Agent System v0.4

[Download the v0.4 project ZIP](https://github.com/9fpqm4vqvq-ops/agent-creator-master/raw/refs/heads/main/releases/master-agent-system-v0.4.zip).

A supervised Claude Code system with Management-led task routing, independently
reviewed outputs, a central skill registry, Iraq e-commerce specialists and local
persistent memory. It extends v0.3 and preserves the four imported source packages.

The organization is USER -> Master -> Management -> department -> independent QA
-> Master -> USER. Income owns Trading, Shorts and Iraq E-commerce. See the
[complete architecture and agent hierarchy](docs/ARCHITECTURE-V04.md).

The v0.4 upgrade adds a loopback dashboard, usage/budget ledger, department health
and knowledge freshness audits, unranked scorecards, and optional local maintenance.
All new records extend the same SQLite Vault. Read the [v0.4 guide](docs/INTELLIGENCE-V04.md)
and [v0.3 → v0.4 comparison](docs/V04-COMPARISON.md).

```bash
python -m agent_hub migrate
python -m agent_hub dashboard --port 8765
# Open http://127.0.0.1:8765; Ctrl-C stops the local dashboard.
```

The two auditors bring the root inventory to **44 roles / 65 skills**. Maintenance
jobs start disabled. Live usage/provider data remains UNKNOWN until imported.

## Start

Python 3.10+, Node.js/npm and your own authorized Claude Code account are required.
The hub itself uses only Python's standard library. No credentials are bundled.

```bash
cd master-agent-system-v0.4
python -m unittest discover -s tests -v
python scripts/validate_all.py
npm ci --prefix tools/claude --no-audit --no-fund
tools/claude/node_modules/.bin/claude auth login
bash scripts/start-master.sh
```

For a Git clone, use:

```bash
git clone https://github.com/9fpqm4vqvq-ops/agent-creator-master.git master-agent-system-v0.4
```

The pinned CLI is preserved from v0.2; it is not a claim of the newest release.
Read [START-HERE.md](START-HERE.md) for the first supervised mission. Actual model
delegation and web access depend on your authenticated runtime and permissions.

## Local task workflow

These commands record a supervised workflow; they do not invoke a model.
Replace ID with the task ID returned by `new`. Fill templates with actual work,
never placeholders or invented tests/reviews.

```bash
python -m agent_hub agents
python -m agent_hub skills search 'Iraq ecommerce research' --department ecommerce
python -m agent_hub new 'Prepare an Iraq e-commerce research plan' --department ecommerce --criteria 'List scope, required evidence, assumptions and missing inputs'
python -m agent_hub management-review ID --analysis 'Actual Management analysis and available capabilities'
python -m agent_hub plan ID --plan templates/management-plan.json
python -m agent_hub assign ID --evidence 'Actual Management assignment rationale'
python -m agent_hub dispatch ID
python -m agent_hub recall ID --query 'Iraq ecommerce prior decisions failures'
# Read selected skills and fill a fresh work/preflight.json using the packet fingerprint.
python -m agent_hub preflight ID --checks work/preflight.json
python -m agent_hub start ID --evidence 'Actual runtime invocation reference'
# Perform the work in Claude Code and write real deliverables and result JSON.
python -m agent_hub submit ID --result work/result.json
# After an actual independent reviewer invocation, fill work/qa-review.json.
python -m agent_hub review ID --reviewer qa-auditor --verdict PASS --notes 'Checks actually performed' --evidence work/qa-review.json
python -m agent_hub history ID
python -m agent_hub report --format markdown
```

Use `--agent NAME` for an explicit worker and `--parent ID` for child work. Record
cross-task dependencies in the Management plan. The canonical lifecycle is in
`phase`; `status` remains a v0.2-compatible projection. There is no direct
`complete` or arbitrary state-changing CLI command. See [workflow](docs/WORKFLOW-V03.md).

## Skills

`registry/skills.json` is the reviewed built-in inventory; operational validation
and usage history persist in SQLite. New or changed candidates cannot be selected
until reviewed. Stage candidates under `work/skill-candidates/`, outside native
`.claude/skills` discovery. `skills register`, `skills activate` and `skills usage`
provide the guarded lifecycle. Activation authorizes hub selection of the reviewed
staged files; it does not run an installer or silently create native slash commands.
A native installation is a separate reviewed local source change.

The actual supplied Skill Finder ZIP contains only SKILL.md. Its source is preserved
in vendor/skill-finder; the safe root wrapper and adapter disable automatic installs.
An injected authorized transport is supported and tested with fixtures. The live
registry endpoint and npx installer are unverified and disabled by default.
Read [the integration report](docs/SKILL-FINDER-V03.md).

## Local Memory Vault

SQLite stores events, task history, knowledge, department namespaces, skill usage
and sync queues. QA-approved outcomes are recorded automatically. Explicit knowledge
writes and retrieval use `memory put/get/search`; export/import keeps stable IDs
and rejects conflicting changes. Namespace checks are application-level controls
for trusted local operators, not authenticated user isolation.

```bash
python -m agent_hub memory export --actor master-agent --out work/memory-export.json
python -m agent_hub memory enqueue --actor master-agent --id RECORD_UUID --provider markdown
python -m agent_hub memory sync --actor master-agent --provider markdown --directory memory
python -m agent_hub memory queue --actor master-agent
python -m agent_hub backup --out work/hub-backup.sqlite
```

Markdown sync is local file projection compatible with Obsidian. External edits
cause conflicts rather than silent overwrites. Failures retry with bounded backoff;
Notion deliberately queues an unconfigured failure. No Notion account or Obsidian
application integration was authenticated. See [memory](docs/MEMORY-VAULT.md).

## Iraq e-commerce

Eight profiles cover direction, market research, products, suppliers/dropshipping,
logistics, finance/payments, marketing and validation. Initial scope is Kurdistan
Region and wider Iraq. Templates require dated evidence, supplier/fulfillment
feasibility, explicit costs and margins, payment-stage distinctions and a bounded
experiment. `ecommerce-finance --assumptions PATH` computes estimates only.
No current supplier, market demand, merchant eligibility, shipping route or legal
requirement was verified during this software upgrade.

## Upgrade, checks and delivery

[Migrations and rollback](docs/MIGRATION-V04.md), [comparison/gap analysis](docs/V04-COMPARISON.md),
[test results](docs/V04-TEST-RESULTS.md), and [change log](CHANGELOG.md) describe the
actual implementation and remaining configuration. Build a portable ZIP using:

```bash
python scripts/build_release.py /absolute/path/master-agent-system-v0.4.zip
```

Databases, vault records, operational outputs, credentials and dependencies are
excluded. Vendor code remains byte-for-byte preserved. Offline checks do not prove
real model delegation, authenticated independent QA, live research, publication,
external sync or profitability. No live broker or background worker is enabled.
