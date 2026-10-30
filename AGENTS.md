# Repository development

This repository extends the supervised Claude Code master-agent system to v0.3.
Read README.md and CLAUDE.md. Preserve vendor sources; prefer root integration
changes and document any necessary vendor patch. Do not remove established agents,
skills or regression scenarios. Use Python 3.10+ standard library for the hub.

After material changes run `python -m unittest discover -s tests -v` and
`python scripts/validate_all.py`. Preserve real test evidence. Do not claim model
delegation, independent model QA, live data, broker execution or external sync from
offline tests. Keep local databases, credentials, personal business/trading settings,
vault records, operational exports and outputs out of Git/releases.

New substantive tasks must use Management review/plan/assign, selected registered
skills, memory recall, preflight/start and structured independent QA evidence.
Stage unreviewed skills under work/skill-candidates outside native discovery. Respect
actual user authorization and host permissions; local attestation text is not identity.
