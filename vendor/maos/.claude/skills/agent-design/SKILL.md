---
name: agent-design
description: Specify agent interfaces, tools, skills, limits and acceptance criteria. Use when designing or refining a Claude Code subagent.
---
# Agent Design

## When to use
Specify agent interfaces, tools, skills, limits and acceptance criteria. Use when designing or refining a Claude Code subagent.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Write unique name, domain, version, scope, exclusions, inputs and outputs.
2. Choose minimum required tool allowlist; do not use bypassPermissions.
3. Create representative test cases and a QA plan.
4. Require human deployment authorization.

## Expected output
Testable agent specification. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
