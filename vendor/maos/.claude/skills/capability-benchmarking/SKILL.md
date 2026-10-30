---
name: capability-benchmarking
description: Compare a new or modified specialist against baseline results. Use before agent promotion or redesign.
---
# Capability Benchmarking

## When to use
Compare a new or modified specialist against baseline results. Use before agent promotion or redesign.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Define baseline output and measurable success criteria.
2. Run representative happy-path, edge and adversarial tests.
3. Compare reliability, cost and correctness; avoid invented numbers.
4. Submit comparative findings to independent QA.

## Expected output
Benchmark result and recommendation. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
