# Independent QA and bounded rework

## Gate 1 — Evidence
- Demand and key platform claims have dated sources; source assertions agree with citations.
- Fee, legal, KYC, tax and residency claims supported or appropriately marked unknown.
- Net-income projections labeled hypothetical unless actual ledger records.

## Gate 2 — Payment feasibility (HARD BLOCK)
- Six route stages from payment-route.md independently validated; all VERIFIED with specific current primary evidence, not just a pasted URL.
- No unresolved account eligibility, currency, withdrawal or local account concerns.

## Gate 3 — Fraud/compliance (HARD BLOCK)
- No suspicious credential sharing, upfront release fee, fake identity/residence, copyright abuse, prohibited automation/spam or material regulatory risk.

## Gate 4 — Experiment readiness
- Experiment has a hypothesis, objective metric, budget cap, time cap, stop conditions, and true baseline.
- User explicitly approves any outreach, account registration, paid signup, spending or financial commitment.

QA provides PASS, FAIL, or NEEDS_EVIDENCE with finding IDs and owners. Rework agent cannot mark its own work PASS. Max 3 loops. The database tool `qa-check` applies minimal *structural* gates only; `qa-attest` records an independent human/QA-agent judgment with no identity authentication — don't confuse it with automatic proof of compliance.
