---
name: cost-estimation
description: Forecast approximate cost and token needs. Use when scoping complex workflows or comparing agent options.
---
# Cost Estimation

## When to use
Forecast approximate cost and token needs. Use when scoping complex workflows or comparing agent options.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Estimate stages, retrieval/tool overhead and outputs.
2. Describe assumptions and explicitly mark estimates.
3. Record measured telemetry only if supplied by genuine provider logs.
4. Escalate before user spending thresholds.

## Expected output
Budget with uncertainty. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
