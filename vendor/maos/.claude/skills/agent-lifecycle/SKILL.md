---
name: agent-lifecycle
description: Control proposed, tested, QA-approved and active agent registry states. Use when promoting, updating or retiring agents.
---
# Agent Lifecycle

## When to use
Control proposed, tested, QA-approved and active agent registry states. Use when promoting, updating or retiring agents.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Check documented capability gap and recorded 3R decision.
2. Record tests and independent QA verdict in registry.
3. Seek explicit approval to deploy; validate host permissions separately.
4. Promote only after gates pass; monitor and retire stale agents.

## Expected output
Lifecycle record and audit trail. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
