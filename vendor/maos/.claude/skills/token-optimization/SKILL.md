---
name: token-optimization
description: Reduce redundant model calls and context without losing quality. Use when token budgets, latency or tool costs are relevant.
---
# Token Optimization

## When to use
Reduce redundant model calls and context without losing quality. Use when token budgets, latency or tool costs are relevant.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Estimate complexity and risk; set proportional budget.
2. Reuse current evidence and provide short agent contracts.
3. Detect duplicate research and excessive handoffs.
4. Label measurements and estimates distinctly; do not eliminate critical QA.

## Expected output
Efficiency advice and usage record. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
