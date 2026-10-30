# Repository development

This repository implements a supervised Claude Code master-agent system. Read
README.md and CLAUDE.md for the intended organization and operating contract.
Source packages in vendor/ are preserved imports. Prefer changes in agent_hub/,
root profiles, docs and tests; document any necessary vendor patch separately.

Use Python 3.10+ standard library for the hub. Run `python -m unittest discover -s tests -v`
and `python scripts/validate_all.py` after material changes. Do not claim model
delegation, independent QA, live data, broker execution or publishing from offline tests.
Do not commit databases, credentials, personal trading settings or operational outputs.
