# Income Opportunity Intelligence (IOI) v0.1 — Claude Code starter

**Purpose:** A project-level Claude Code multi-agent framework to research and develop legitimate second-income opportunities executable by a person residing in Iraq. Includes the Income Strategy Director, 11 specialist subagents, 17 skills, independent QA, capped rework, six-stage payout verification, SQLite memory, local scoring and financial tools, experiment approval gates, and tests.

The agent system is designed to find credible businesses, **not** promise earnings or bypass platform geographical requirements. Live third-party integrations and continuous scheduling are not activated.

## Requirements

- Claude Code CLI installed and signed in.
- Python 3.10 or later (local scripts use standard library only).
- Internet and authorized Claude Code browsing tools for live research.
- Optional external services need configuration; see `connectors/README.md`.

## Install and start

1. Extract this ZIP to a folder, retaining all hidden `.claude` files.
2. Open a terminal *inside* `income-opportunity-intelligence`.
3. Run `python scripts/ioi.py init` (Windows may use `py -3 scripts/ioi.py init`).
4. Run `python -m unittest discover -s tests -v` to check the local tools.
5. Run `claude` from that same folder. The main `CLAUDE.md`, `.claude/agents/*.md`, and `.claude/skills/*/SKILL.md` configure the system.
6. Ask Claude to start the research mission using the first prompt below.

## First prompt for Claude Code

> Act as the Income Strategy Director. Coordinate the Global Opportunity Researcher, Iraq Feasibility & Payment Researcher, Market Intelligence Analyst, and Creative Opportunity Generator to investigate eight diverse second-income opportunities. Verify that any shortlisted opportunity has credible demand evidence and a lawful, usable six-stage payout route for Iraq. Delegate independent QA and bounded rework. Record research, decisions and uncertainties in SQLite. Provide a ranked dashboard with missing evidence and proposed inexpensive experiments. Do not register accounts, contact customers, spend, publish, or start external experiments without my explicit approval.

You can check available agent definitions using Claude Code's `/agents` command. Claude Code project-level skills become available through its skills functionality; `/skill-name` can invoke an individual skill.

## Quick command examples

```bash
python scripts/ioi.py --help
python scripts/ioi.py init
python scripts/ioi.py doctor
python scripts/ioi.py add --title "Spreadsheet cleanup service" --model "Remote data cleaning" --buyer "Small businesses"
python scripts/ioi.py list
python scripts/ioi.py show --id 1
python scripts/ioi.py qa-check --id 1
python scripts/ioi.py score --id 1
python scripts/ioi.py finance --price 30 --low 0 --base 5 --high 10 --unit-cost 4 --fee-pct 8 --monthly-fixed 20 --hours 12
python scripts/ioi.py report --out reports/dashboard.md
```

The example business name above is **not** a researched recommendation. `examples/illustrative-opportunity.json` contains fictional sample data and is **not** loaded by the database.

For further CLI steps, run `python scripts/ioi.py COMMAND --help` for `evidence-add`, `payout-set`, `risk-add`, `qa-attest`, `rework-add`, `decision`, `experiment-create`, `approve`, `experiment-start`, `event`, `experiment-close`, and `monitor-add`.

## Project structure

```text
income-opportunity-intelligence/
  CLAUDE.md                    Main orchestrator instructions
  .claude/agents/              11 distinct specialist subagents
  .claude/skills/*/SKILL.md    17 reusable skills
  references/                  Research protocol, payout chain, QA SOP, scoring
  ioi/core.py                  SQLite and validation rules
  ioi/cli.py                   Executable command interface
  scripts/ioi.py               Launcher
  connectors/                  Optional YouTube public metadata tool and notes
  templates/                   Research, QA, lean test, and 30/60/90 roadmap
  tests/                       Unit tests and packaging checks
  examples/                    Clearly fictional layout only
  data/                        Local DB created after `init`
```

## Core policies and limitations

1. **Six payout stages:** buyer payment → platform receives → cleared withdrawable balance → approved payout provider → accessible legitimate Iraqi account → spendable/withdrawable usable money. Each stage starts `UNVERIFIED`. A source URL alone does not prove eligibility; independent QA must read the source and assess account/residency applicability.
2. **QA is independent:** proposal author/rework agent may not sign their own work as independently reviewed. The `qa-attest` command records a reviewer identity but does not cryptographically authenticate the person's identity or fact-check web pages. No claim of genuine review should be made without one.
3. **Rework capped at three attempts** per opportunity, then escalate to Main Agent for hold/reject.
4. **Opportunity score is descriptive, not a QA pass** and cannot override serious risks or missing payout proof.
5. **Experiments require current QA PASS and explicit human approval** plus caps; `approve --action EXPERIMENT` also requires `--experiment-id`. Creating an experiment plan does not execute anything; recording approval locally does not itself contact a person or spend money.
6. **Actual earnings** are separate from hypothetical low/base/high finance scenarios. Neither simulated results nor sample fixtures are presented as observations.
7. **No continuous monitoring is active:** the monitoring queue works, but n8n/background services require separate setup. Claude Code subagents run when invoked within a live session. They can consume API/subscription usage.
8. **No service is automatically installed:** optional Google Search/Trends/Alerts, Crawl4AI, LangGraph, n8n, Metabase and YouTube metadata access need external configuration. Public YouTube search can use `YOUTUBE_API_KEY`; it cannot verify income or payout policies.
9. **Safety:** never use fake residency, borrowed payout accounts, invented customers, phishing, misleading marketing, unlicensed finance activities, or automated spam; do not store secrets in source control. `.gitignore` excludes `.env` and `data/*.db`.
10. **Tax and legal topics:** verify current primary sources; ask for professional guidance as needed; do not present speculative regulations as legal advice.

## Suggested rollout

Phase 1: find 8–12 distinct opportunities and gather dated demand evidence. Phase 2: verify Iraq payout route and independent QA, with targeted rework. Phase 3: obtain consent for minimum viable paid or unpaid tests with bounded budget/hours. Phase 4: log actual buyers, income, expenses, and lessons. Phase 5: connect optional integrations with permission-reviewed schedules and reports.

## Reference documentation

- Claude Code subagents: https://code.claude.com/docs/en/sub-agents
- Claude Code skills: https://code.claude.com/docs/en/skills
