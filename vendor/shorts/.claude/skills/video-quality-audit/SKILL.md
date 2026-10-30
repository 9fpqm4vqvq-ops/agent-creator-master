---
name: video-quality-audit
description: Inspect 9:16 resolution, streams, audio, captions and visual consistency before publishing. Use for final video QA.
---
# Video Quality Audit

## Procedure
Run scripts/video_tools.py qa, then human visual/audio review. Validate caption sync and clarity, black frames, clipping and pacing; fix high-severity failures and rerun.

## Evidence and safety
Never invent access, API responses, metrics, sources, or licenses. Label estimates and confidence. Follow approval gates in `CLAUDE.md` and produce an explicit result plus next test.
