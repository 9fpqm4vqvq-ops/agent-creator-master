# Shorts Growth Lab — Claude Code Starter (v0.1)

A seven-subagent, seventeen-skill **Claude Code project** for original YouTube Shorts research, experimentation, production support and audit-gated decisions. Approval mode: **human approval before publishing or consequential actions**.

## Quick start
1. Extract the entire ZIP to a folder (do not upload the entire ZIP as a single Claude skill).
2. Install **Claude Code** and open a terminal in the extracted project directory. Run `claude` from that directory. Claude Code detects `CLAUDE.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`.
3. Run `python scripts/shortslab.py init` to initialize SQLite.
4. Run `python -m unittest discover -s tests -v` to check the starter.
5. Ask Claude: `Use niche-market-researcher and competitor-intelligence-analyst to propose 5 original Shorts niches with evidence and next experiments; do not make publishing decisions yet.`
6. For optional public YouTube search, obtain a YouTube Data API key; set `YOUTUBE_API_KEY` in your shell and run `python scripts/shortslab.py research --query 'science shorts' --max-results 5`. The API key is not bundled and `.env` is not automatically loaded.
7. For a basic local video prototype, install FFmpeg (`ffmpeg` and `ffprobe` on PATH); run `python scripts/video_tools.py render --script examples/demo-script.txt --output outputs/demo.mp4`. This prototype displays script lines as caption cards and contains **no narration by default**. It is NOT publication-ready.

## Architecture
- `CLAUDE.md`: Lead orchestrator, approval contract, stage gates.
- `.claude/agents/`: Seven independently prompted specialist subagents.
- `.claude/skills/`: Seventeen lean, auto-discoverable workflow skills.
- `scripts/shortslab.py`: sqlite memory, niche scoring, experiment tracking, sample CSV import, public YouTube search.
- `scripts/video_tools.py`: simple local vertical test render + ffprobe verification.
- `templates/`: research, experiment, QA and human approval handoffs.
- `examples/`: **DEMO/FAKE** niche assumptions, generic script, simulated analytics. Never report these as live results.

## Integration availability / honest boundaries
| Integration | Starter state | Required setup |
|---|---|---|
| YouTube Data API | **Implemented** minimal public video search | API key / quota |
| YouTube Analytics API | Not wired | OAuth consent, permissions, owned channel; export CSV into starter meanwhile |
| Google Trends | Manual research only | Use browser, record dated sources; no assumed official free endpoint |
| yt-dlp | Not wired | Install separately; use only for authorized retrieval |
| FFmpeg/ffprobe | Implemented optional render and basic technical QA | Local executable on PATH |
| Whisper | Not wired | Install separately for transcription/subtitles |
| Piper TTS | Not wired | Install separately and obtain licensed/appropriate voice model |
| Remotion | Not wired | Node.js, project scaffolding, compatible license |
| SQLite | Implemented | Python standard library |
| n8n | Not wired | Self-host + configured credentials, approvals and triggers |

The basic rendering prototype can fail if your FFmpeg build lacks drawtext/libfreetype. It also does not perform line wrapping, audio normalization, subtitle alignment, full artistic production, rights verification, or publishing. The QA CLI performs technical checks only; final QA needs independent human/editorial review and rights inspection. YouTube Shorts classification and monetization eligibility depend on current YouTube rules, not just dimensions/duration.

## Example usage
```bash
python scripts/shortslab.py score --input examples/niches.json
python scripts/shortslab.py decision --title 'Pilot science niche' --rationale 'Low-cost test' --evidence 'Source URLs + uncertainty'
python scripts/shortslab.py experiment --name 'Hook A vs B' --hypothesis 'Question hook increases hold' --metric 'viewed rate' --target 'Improvement over baseline'
python scripts/shortslab.py analytics-import --csv examples/analytics_sample.csv --source demo_only
python scripts/shortslab.py summary
python scripts/video_tools.py qa --video outputs/demo.mp4
```
For local use, do not import demo analytics into a production database. Use a distinct database file for simulations or delete demo rows explicitly after testing.

## Governance and accuracy
- Never auto-publish, bypass copyright/factual BLOCKER/HIGH QA failures, buy resources, or mutate channel settings without approval.
- Rely on observed channel measurements for claims of performance; track sample size, age and metric definitions.
- Avoid copyright infringement, prohibited scraping and fake engagement tactics; respect API terms and privacy.
- Financial viability is a hypothesis until actual measured revenue and expenses exist.
- Decisions persist in local `data/shortslab.db`, which is excluded from git by default. Back it up securely.

## Development roadmap
P1: Google OAuth for owned YouTube Analytics API + date-window metric dictionary; privacy-safe credentials storage.
P2: stronger video production (Piper TTS, Whisper SRT, Remotion brand templates, aspect-safe text).
P3: n8n scheduled research with rate limits and human publish approval; separate QA signoff state.
P4: experiment dashboards with cohort comparisons, actual costs, uncertainty and statistical caution.

## Sources / references
- Claude Skills: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Claude Code agents: https://code.claude.com/docs/en/sub-agents
- YouTube Data API search: https://developers.google.com/youtube/v3/docs/search/list
- YouTube Analytics API: https://developers.google.com/youtube/analytics
- YouTube creator policy center: https://support.google.com/youtube/topic/2803176
