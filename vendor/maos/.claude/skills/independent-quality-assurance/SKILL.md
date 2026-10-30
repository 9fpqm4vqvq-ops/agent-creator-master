---
name: independent-quality-assurance
description: Audit specialist deliverables for accuracy, security and acceptance. Use before closing meaningful tasks or activating agents.
---
# Independent Quality Assurance

## When to use
Audit specialist deliverables for accuracy, security and acceptance. Use before closing meaningful tasks or activating agents.

## Inputs
Task objective, constraints, supporting evidence, assigned owner, and available tools.

## Procedure
1. Use a reviewer different from task owner and artifact author.
2. Check requirements, citations, security boundaries and test outputs.
3. Return PASS, REWORK, BLOCKED or FAIL with severity and exact defects.
4. Do not approve unresolved critical issues or your own work.

## Expected output
Independent QA verdict. Include `TASK_ID`, evidence, uncertainty and next handoff when applicable.

## Failure and escalation
If information or permission is missing, mark BLOCKED and identify the dependency. Never invent a verification, token measurement, tool call or approval. Consult `CLAUDE.md` and `docs/CONTRACT.md`.
