---
name: targeted-rework
description: Repair failed deliverables without restarting valid work. Use following a specific independent QA failure.
---
# Targeted Rework

## When to use
Repair failed deliverables without restarting valid work. Use following a specific independent QA failure.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Map failure to affected artifact and root cause.
2. Retain previously accepted work.
3. Make constrained edits and run relevant regression tests.
4. Return to independent QA; stop after three correction cycles.

## Expected output
Root-cause record and corrected artifact. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
