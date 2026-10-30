# Trading department v0.2

Reporting path: Human -> Master -> Income -> Trading.

The imported Day Trader package contains 11 skills and standard-library tools.
It can analyze data, build plans, simulate paths, calculate sizes, check limits
and record tickets. `ticket.py` does not call a broker. References in skill prose
to placing an order depend on a separately configured brokerage connector.

All 315 fixture tests passed in this environment. They do not verify live quote
access, account eligibility, fills, strategy profitability, current rules or broker
authorization. The package's claimed fixture provenance and regulatory statements
have not been independently verified. Treat them as unverified until checked.

This release enables research/paper preparation only. The project-local trader-*
skills link to preserved source directories. Run tools from a task work directory
so `trader/` state is isolated; do not run with another task's portfolio or limits.
Read the chosen SKILL.md and tool `--help` first. Tests use pinned historical clocks;
never use those clocks to validate a current proposed trade.

Do not create a personal config by copying `config.example.json` unchanged. It
contains an illustrative $5,000 balance, permissive concentration limits and other
example values. No personal account configuration is supplied in this release.

Before a later real-money integration, resolve:

- User's instructions: markets, broker, residency/eligibility, account type,
  capital, position limits, max loss per trade/day and instrument restrictions.
- Broker-verified current data, portfolio, open orders, eligibility and rules.
- Tested paper-account connector, idempotency, reconciliation, partial fills,
  rejection recovery and emergency stop procedures.
- Authenticated, expiring approval bound to the exact order/account/limits,
  followed by host tool approval. Local approval text is not authentication.

No money movement, live mode, leverage, shorting or brokerage credential is
authorized by a task packet or the request to create these agents. User-facing
reports should distinguish hypothetical risk at the stop from actual worst-case
loss, and simulation estimates from future performance.
