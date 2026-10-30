---
name: approval-gates
description: Enforce human authorization for consequential actions. Use for payments, registration, publishing, deployments or deletion.
---
# Approval Gates

## When to use
Enforce human authorization for consequential actions. Use for payments, registration, publishing, deployments or deletion.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Identify action, affected assets, scope and risk.
2. Obtain explicit approval before action; document reference.
3. Check Claude Code native permissions as a separate gate.
4. Do not claim an approval log is authentication or external execution.

## Expected output
Verified approval record or blocker. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
