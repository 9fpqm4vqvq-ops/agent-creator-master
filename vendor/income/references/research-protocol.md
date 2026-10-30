# Research protocol / evidence grading

- Separate EVIDENCE from ASSUMPTION. Do not invent source references, local banks, provider support or outcomes.
- Class A: official platform/merchant/payment provider and government docs, with relevant jurisdiction and checked date.
- Class B: reproducible public market listing, user reviews, independently published dataset; note sampling bias.
- Class C: anecdote, marketing claims, single unverified post; useful only to generate hypotheses.
- Where provider rules conflict with anecdotes, investigate product, account class, time and location differences; do not average contradictory facts.
- Record exact claim, URL, kind, access date, confidence and limitation using `evidence-add` CLI. Independently reopen critical sources during QA.
- Consider demand signals in order: paid customer proof, active buyer requests, conversion tests, intent surveys, trend search volume, mere social attention.
- Record false positives and negative results equally. Retry failed source fetches once, then mark unavailable; never claim success from a search result snippet alone.
