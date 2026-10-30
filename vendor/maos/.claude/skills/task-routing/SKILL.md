---
name: task-routing
description: Route work to the smallest qualified team with explicit responsibility. Use when selecting existing agents or coordinating cross-department tasks.
---
# Task Routing

## When to use
Route work to the smallest qualified team with explicit responsibility. Use when selecting existing agents or coordinating cross-department tasks.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Match objective to registry capability tags using `python scripts/maos.py agents` and `route ID`.
2. Inspect permissions, evidence and dependencies.
3. Choose one lead, optional supporting roles, sequence, token estimate and QA reviewer.
4. Escalate missing capability without inventing an agent.

## Expected output
Routing decision with reasoning. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
