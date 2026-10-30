# Integrating existing specialist projects

To reuse another Claude Code project, do not blindly merge overlapping CLAUDE.md instructions. Audit its agents and skills, identify unique capability tags, confirm its permissions, then either:
- Register a compatible agent capability using `propose-agent` / test / independent QA / approve / activate, with a corresponding tested agent definition in `.claude/agents`.
- Link to a separate project as a handoff artifact and perform delegation manually in Claude Code.

An entry in the registry does not enable cross-project process spawning, live tool execution, or autonomous background monitoring. Integrations with n8n, databases, or external APIs require separate credentials, host permission review and implementation.
