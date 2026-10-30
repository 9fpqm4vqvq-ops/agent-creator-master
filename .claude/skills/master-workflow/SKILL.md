---
name: master-workflow
description: Receive a user request, route it through the master agent departments, track evidence and handoffs, and return a reviewed report.
---

Read the root CLAUDE.md. Use `python -m agent_hub agents` to inspect departments.
Create a task with explicit acceptance criteria. Dispatch a packet and actually invoke
the designated Claude Code profile. The dispatch command itself performs no AI work.
Record instruction/skill/runtime/freshness checks with `preflight ID --checks PATH`
before execution. Repeat after each rework handoff. Report inaccessible current sources.
Submit real artifacts and dated evidence. Obtain independent QA and report results.
Use creator/researcher for agent maintenance; use Income -> Trading for trading.
Any live action remains outside this research/paper-only release.
