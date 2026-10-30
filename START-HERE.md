# Start your master agent in Claude Code

Extract the complete folder, including hidden `.claude` files. Requires Python
3.10+, Node.js/npm, internet access and your own authorized Claude Code account.

```bash
cd master-agent-system
python -m unittest discover -s tests -v
npm ci --prefix tools/claude --no-audit --no-fund
tools/claude/node_modules/.bin/claude auth login
bash scripts/start-master.sh
```

On Windows, use `py -3` if needed and launch
`tools\claude\node_modules\.bin\claude.cmd --agent master-agent` after installing
and authenticating. The folder must be the current working directory.

Paste this first mission into the running Claude Code session:

> Act as my master agent using CLAUDE.md. Receive my requests and delegate them
> through Management, Agent Development & Research, and Income. Trading reports
> through Income. First, create one parent readiness task and child tasks for
> Agent Development & Research and Income/Trading. Actually invoke the named
> native subagents. Have the creator inspect current roles and skills, verify
> version-sensitive claims against official documentation and return a tested
> improvement proposal. Have Income and Trading prepare the trading intake and
> a paper-validation plan using the supplied Day Trader skills. Record each
> task's preflight, preserve dated sources and disclose unverified facts. Obtain
> a separately invoked QA review of completed artifacts. Return one consolidated
> report with completed work, blocked items, evidence and the few decisions you
> need from me. No live orders or external publishing are part of this mission.

To assign a worker explicitly, say: “Give this task to agent-creator-researcher:
[request].” To address a department, say: “Ask Income / Trading to [request].”
Ask “Give me the management report” for the consolidated task status and evidence.

The local CLI prepares handoffs and records outcomes. Actual reasoning and
delegation happen inside your authenticated Claude Code session. No background
worker runs after you close the session. The first mission still needs to be run
with real subagents; offline tests do not establish independent QA or live access.
