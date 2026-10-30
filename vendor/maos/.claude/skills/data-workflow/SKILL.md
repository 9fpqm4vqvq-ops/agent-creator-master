---
name: data-workflow
description: Diagnose-Assemble-Take Action-Assess for meaningful task orchestration. Use when a task requires several steps or specialist coordination.
---
# Data Workflow

## When to use
Diagnose-Assemble-Take Action-Assess for meaningful task orchestration. Use when a task requires several steps or specialist coordination.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Define objective, risks, acceptance criteria, approval requirements and initial task state.
2. Find an existing owner and smallest team; create a local task ID.
3. Execute or delegate only necessary work with structured handoffs.
4. Seek independent QA; report actual outcome and limitations.

## Expected output
Execution record with outcomes and evidence. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
