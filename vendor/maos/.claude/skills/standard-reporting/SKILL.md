---
name: standard-reporting
description: Deliver concise, traceable completed-task reports. Use for user progress updates, QA summaries or final results.
---
# Standard Reporting

## When to use
Deliver concise, traceable completed-task reports. Use for user progress updates, QA summaries or final results.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Show actual finished artifact and verified outcome.
2. Cite key evidence and unresolved uncertainty.
3. Include QA decision and measured vs estimated costs.
4. Avoid verbose agent transcripts and unsupported claims.

## Expected output
Clear decision report. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
