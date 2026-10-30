# Start Master Agent System v0.4

Extract the whole ZIP, including hidden .claude files. If upgrading operational
state, follow docs/MIGRATION-V04.md before opening an operational v0.3 database with v0.4.

```bash
cd master-agent-system-v0.4
python -m unittest discover -s tests -v
npm ci --prefix tools/claude --no-audit --no-fund
tools/claude/node_modules/.bin/claude auth login
bash scripts/start-master.sh
```

On Windows use `py -3` if needed, then launch
`tools\claude\node_modules\.bin\claude.cmd --agent master-agent` from the project
folder after installing and authenticating. Never paste credentials into chat.

Paste this first mission into the authenticated Claude Code session:

> Act as my v0.4 master using CLAUDE.md. Route the request through Management.
> Prepare an Iraq e-commerce research plan focused initially on Kurdistan Region,
> with acceptance criteria covering scope, evidence needed, assumptions and missing
> inputs. Have Management discover current roles and skills, create scoped Income
> and e-commerce child tasks, and assign owners. Actually invoke the required
> native workers; preserve the logical department path if nested delegation is
> unavailable. Retrieve prior memory, record preflight and start for each task.
> Ask the e-commerce specialists to define the market, supplier, logistics,
> payment-stage, unit-economics and validation evidence needed. Do not invent current
> market findings. Obtain a separately invoked QA review of actual outputs and
> tests; return precise corrections for rework. Consolidate only reviewed work,
> store the approved outcome and return one report with evidence and open inputs.
> This mission authorizes research and drafts, not spending, outreach, account
> creation, ads, storefront publication or broker orders.

For a specific worker: “Route this through Management to iraq-market-researcher:
[request].” For agent maintenance: “Ask Management and Agent Development & Research
to investigate this missing capability: [need].” Ask “Give me the management report”
for consolidated phases, sources, QA results and blockers.

The initial real mission has not been run here: this workspace has no authenticated
Claude Code session. Closing your session does not leave an autonomous worker running.
