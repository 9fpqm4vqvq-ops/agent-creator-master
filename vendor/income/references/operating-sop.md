# Operating SOP: Research → QA → Rework → Experiment → Learn

1. Main agent asks for/records constraints only as needed (country assumed Iraq; time, budget, language, experience and banking unknown until provided).
2. Global and creative research produce candidate records, full evidence URLs, dates, competitor gaps.
3. Iraq feasibility checks all six payout stages independently of proposal author; outcome default UNVERIFIED.
4. Financial analysis produces low/base/high scenarios with assumptions, time, fees, and variance.
5. QA independently checks source contents and country restrictions. CLI `qa-check` gives structural checklist; `qa-attest --reviewer ... --verdict pass` records real reviewed conclusions. Do NOT simply attest pass to unblock a candidate.
6. If failed: Rework creates root-cause task and correction request, never approves own work. Up to three retries; otherwise HOLD/REJECT.
7. Main agent decides and records reasons. On PASS, design a bounded experiment (plan is free). Any real-world test requires explicit consent, and the CLI only records that consent; obey Claude Code tool permissions too.
8. Results: record actual costs, revenue, conversion, hours and learning. Compare to original threshold, update decision and monitor triggers.
9. Reporting: use actual database records, never examples or hypothetical financial models as observed performance.

`IOI` is a local, operator-in-the-loop framework. It does not run scheduled research on its own. Optional n8n schedulers, Metabase and LangGraph adapters are future connections; wire them only after opt-in, security review, and test.
