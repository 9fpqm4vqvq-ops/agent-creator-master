---
name: persistent-agent-memory
description: Maintain SQLite-backed evidence, decisions, payout checks, scenarios, experiments and learning outcomes.
---
# Persistent Agent Memory

## When to use
Use when the task requires maintain SQLite-backed evidence, decisions, payout checks, scenarios, experiments and learning outcomes.

## Procedure
Use `python scripts/ioi.py --help`; initialize before writes, record what was tested, author, supporting URLs, QA judgment, user-approved activities, actual outcomes and lessons. Do not overwrite historical evidence; append new records and flag stale claims.

## Mandatory handoff
Return: input/assumptions, steps completed, dated evidence or local record IDs, confidence, blockers, quality checks, next action. If required evidence or permission is missing, stop and mark UNVERIFIED or BLOCKED rather than guessing.

## Safety
No financial commitment, account registration, external outreach, false identity, geographic restriction bypass, or publication without explicit user approval. Avoid leaking credentials or private data.
