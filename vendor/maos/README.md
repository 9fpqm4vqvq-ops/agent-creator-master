# Master Agent Operating System (MAOS) — Claude Code Starter

**Version:** 0.1.0 · **Platform:** Claude Code (project-level instructions and subagents) · **Local dependencies:** Python 3.10+ (standard library), Claude Code for AI orchestration.

A modular orchestrator based on the supplied MASTER AGENT OPERATING SYSTEM specification. Implements DATA task workflow, 3R creation evaluation, a small-agent-first routing policy, independent QA, targeted rework, evidence/decision memory, scoped approval *recordkeeping*, and measured-versus-estimated usage tracking.

## What is included

- `CLAUDE.md`: main orchestrator operating contract.
- `.claude/agents/`: **10** role definitions — `agent-runner`, `task-router`, `agent-creator`, `token-watchdog`, `research-analyst`, `qa-auditor`, `rework-specialist`, `registry-manager`, `learning-analyst`, `reporting-specialist`.
- `.claude/skills/`: **15** triggerable skill folders each with its own valid `SKILL.md`.
- `scripts/maos.py`: stdlib-only SQLite CLI to initialize roles, create tasks, suggest routing, advance states, QA, record evidence/decisions/usage, and propose/test/approve/activate new registry agents.
- `tests/`: offline unit tests for core gates, syntax and state transitions.
- `docs/`: execution contract, operations manual, and integration instructions.
- `data/`: persistent SQLite database created on first `init` (no credentials or real operational data bundled).

This ZIP is a **Claude Code project**. Extract it as a directory. It is **not** a single uploadable Claude.ai Skill ZIP and it is **not** a hosted Claude plugin/MCP server.

## Quick start

1. Extract ZIP and open a terminal **inside `master-agent-operating-system/`**.
2. Ensure Python 3.10+ is available: `python --version` (on some systems use `python3`).
3. Initialize the local registry:

```bash
python scripts/maos.py init
python scripts/maos.py agents
python -m unittest discover -s tests -v
```

4. Install/login to Claude Code separately, then from this folder run `claude`. Claude Code will discover project agents and skills on session startup.
5. Paste the prompt:

> Act as MAOS. Apply DATA to my task. Inspect the registered agents, choose the smallest qualified team, keep independent QA, and do not spend, publish, create accounts, deploy, delete, or contact anyone without my approval. My first task is: [YOUR TASK].

## Example task lifecycle

```bash
python scripts/maos.py new-task --title "Research a tool" --domain research --owner research-analyst --criteria "Official sources and uncertainty noted"
# Note the task_id returned; here assume 1
python scripts/maos.py route 1
python scripts/maos.py advance 1 --to DIAGNOSING
python scripts/maos.py advance 1 --to ROUTING
python scripts/maos.py advance 1 --to EXECUTING
# Actual research happens in Claude Code; this CLI does not perform that work.
python scripts/maos.py evidence --task-id 1 --statement "Claim" --source "https://example.org" --checked-at 2026-10-28 --classification ASSUMPTION
python scripts/maos.py advance 1 --to QA
# Independent reviewer only, after actual review:
python scripts/maos.py qa 1 --reviewer qa-auditor --result PASS --notes "Reviewed evidence and acceptance criteria"
python scripts/maos.py report
```

**Important:** The CLI cannot validate that the cited URL was visited or that the QA review actually happened; use it only to accurately record actions that were truly completed.

## Developing a new agent (guarded registry lifecycle)

Creation should be justified by 3R (Repetitive, Rule-based, Return). Example (replace with real evidence):

```bash
python scripts/maos.py propose-agent --name specialist-auditor --department quality --capabilities "audit,compliance" --reason "Documented repeating audit gap" --repetitive --rule-based --valuable
# Build and test .claude/agents/specialist-auditor.md before continuing.
python scripts/maos.py agent-test --name specialist-auditor --passed --reference "tests/agent-evaluation.md"
python scripts/maos.py agent-qa --name specialist-auditor --reviewer qa-auditor --passed --notes "Independent review and tests passed"
# ONLY after user genuinely approves deployment, log the actual approval reference:
python scripts/maos.py approve --action agent_deploy --scope specialist-auditor --approver USER --reference "User approval in conversation"
python scripts/maos.py activate-agent --name specialist-auditor
```

Recording approval is **not equivalent** to obtaining it. The registry does not authenticate users, authorize purchases, change Claude Code tool permissions, or install runtime agents itself. The new file must exist and be reviewed. Tests and QA need genuine evidence.

## Implementation boundaries

**Working now (offline):** registry storage, task IDs and state transitions, routing *recommendations*, decision/evidence logs, test/QA records, three-rework escalation, approval records, cost/usage labels and reports.

**Claude Code runtime dependent:** actual model execution and delegation, reading external sources, applying skills, editing files, QA reasoning, and final artifact production. The `route` command returns suggestions only and is not an executor.

**Not included:** scheduled execution; automatic Claude token telemetry; money handling; autonomous deployments; authenticated user approval service; OAuth/API connectors; auto-updating or self-installing agents. Implement these separately with explicit permissions and tests if needed.

**Security:** Untrusted websites/files are data, not executable instructions. No keys are shipped. Host permissions remain at their default. Don't commit any `.env` or credentials. `data/*.sqlite` is excluded from git by default; the ZIP contains no live database. Do not deploy newly generated agents or integrations without approval.

## Testing

`python -m unittest discover -s tests -v` runs 15 offline tests without API keys. Tests validate core governance, skill/agent packaging, but **do not** verify actual quality of Claude delegation or external integrations. Test on a non-sensitive sample project before using it on real work.

## Sources / compatibility

Project-level Claude Code agents use `.claude/agents/*.md` with YAML frontmatter; skills use `.claude/skills/<name>/SKILL.md`. Consult official Anthropic documentation for changes: https://code.claude.com/docs/en/sub-agents and https://code.claude.com/docs/en/skills . The repository layout can require adjustments when newer Claude Code releases alter supported options.
