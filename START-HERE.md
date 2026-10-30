# Start Master Agent System v0.6

For the programmatic execution engine, follow docs/RUNTIME-V06.md first.
The interactive workflow below remains supported and does not authenticate a CLI
for programmatic use automatically.

Extract the whole ZIP, including hidden .claude files. If upgrading operational
state, follow docs/MIGRATION-V06.md before opening an operational v0.4 database with v0.6.

```bash
cd master-agent-system-v0.6
python -m unittest discover -s tests -v
npm ci --prefix tools/claude --no-audit --no-fund
tools/claude/node_modules/.bin/claude auth login
bash scripts/start-master.sh
```

On Windows use `py -3` if needed, then launch
`tools\claude\node_modules\.bin\claude.cmd --agent master-agent` from the project
folder after installing and authenticating. Never paste credentials into chat.

Paste a focused mission into the authenticated Claude Code session:

> Act as my v0.6 master using CLAUDE.md. Ask Management to prepare a small local
> website prototype with an original launch-content draft. Scope the requirements
> first, inspect any existing project, choose the smallest qualified Web/Social team,
> and use scoped child tasks only where needed. Actually invoke the necessary
> workers, research current authoritative sources when available, label missing facts,
> read selected registered skills, recall memory, preflight and budget-gate starts.
> Produce real local files, a testable prototype and a draft calendar with audience
> timezone and hypotheses. Obtain separately invoked independent QA, resolve precise
> corrections and return reviewed artifacts, costs/UNKNOWN, limits and next decisions.
> This mission authorizes research/local implementation/drafts; external publishing,
> paid generation, advertising, messages and deployment need actual scoped authority.

A single caption can go directly through Management to social-copywriter-scriptwriter;
a focused bug fix can use web-frontend-engineer or web-backend-api-engineer. Do not
launch the full department for those tasks. Read docs/WEB-WORKFLOW-V05.md,
docs/SOCIAL-WORKFLOW-V05.md and docs/CONNECTORS-V05.md for CLI data and limits.

The initial real mission has not been run here: this workspace has no authenticated
Claude Code session. Closing your session does not leave an autonomous worker running.
