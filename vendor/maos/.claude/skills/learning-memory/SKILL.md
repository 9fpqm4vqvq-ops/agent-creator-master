---
name: learning-memory
description: Record lessons, rejected hypotheses and routing outcomes. Use after experiments, failures or major decisions.
---
# Learning Memory

## When to use
Record lessons, rejected hypotheses and routing outcomes. Use after experiments, failures or major decisions.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Log what was tried, evidence and context.
2. Separate facts, assumptions and speculative hypotheses.
3. Track source date and freshness threshold.
4. Recommend future action only from supported results.

## Expected output
Structured decision or lesson entry. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
