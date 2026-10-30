# Package manifest — MAOS 0.1.0

- Target: Claude Code, project-level package
- Main orchestrator: `CLAUDE.md`
- Subagents: 10 YAML-frontmatter Markdown files under `.claude/agents/`
- Skills: 15 folders under `.claude/skills/`, each with exactly one `SKILL.md`
- Local engine: `scripts/maos.py` (SQLite, Python stdlib)
- Tests: `tests/test_maos.py` (15 offline tests)
- Docs: `README.md`, `docs/CONTRACT.md`, `docs/OPERATIONS.md`, `docs/INTEGRATION.md`
- Example: `examples/task-contract.md`

No installed API connectors, credentials, schedules, third-party runtime dependencies, or actual work histories are bundled. Agent registry initialization only creates local metadata; delegation must occur inside Claude Code. Explicit human authorization and host tool permissions are required for consequential actions.
