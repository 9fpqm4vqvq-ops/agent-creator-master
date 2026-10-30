---
name: registry-management
description: Maintain persistent local agent and task capabilities. Use when checking ownership, role coverage or lifecycle records.
---
# Registry Management

## When to use
Maintain persistent local agent and task capabilities. Use when checking ownership, role coverage or lifecycle records.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Inspect seeded agents and known skill tags.
2. Record versions and state transitions with the CLI.
3. Never interpret registration as actual execution.
4. Preserve provenance of outcomes and changes.

## Expected output
Auditable local registry. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
