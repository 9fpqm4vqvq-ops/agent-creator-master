# v0.3 validation results

Baseline v0.2 validation was executed before changes: 24 hub tests plus 347 imported
package tests, all passing (371 total). All 24 original hub regression scenario names
and assertions remain; their fixtures/CLI sequence now satisfy the mandatory v0.3 gates.
Imported test files and vendor sources remain unchanged.

Final executed commands:

```bash
python -m unittest discover -s tests -v
python scripts/validate_all.py
```

| Suite | Tests executed | Result |
| --- | ---: | --- |
| v0.3 hub, CLI, memory, registry, migration and economics | 67 | PASS |
| Preserved MAOS | 15 | PASS |
| Preserved Income | 12 | PASS |
| Preserved Shorts | 5 | PASS |
| Preserved Day Trader | 315 | PASS |
| Total isolated validation suites | 414 | PASS |

The standalone hub command also passed all 67 checks. It is the same hub suite
run within validate_all.py and is not counted twice in the 414 total. No skipped
or zero-test suite appears in these outputs. Raw logs: v03-validation.log and
v03-integration-tests.log. The v0.2 logs remain historical artifacts.

## Behavioral coverage

Management review/plan/assignment and requested-agent preservation; department and
all eight e-commerce registrations; dependencies and parent cycles; incomplete child
blocking; actual instruction/tool/skill/artifact drift checks; local discovery and
usage; missing-capability escalation; quarantined candidate rejection; separate
activation review; no automatic Skill Finder installation; all original QA gates;
structured criteria/checks/test evidence; contributor self-review rejection; multiple
reworks, configurable escalation and scoped resumption; event actors/references and
secret redaction; namespace ACLs; memory retrieval and restart persistence; stable-ID
idempotency and revision conflicts; transactional export/import with origin provenance;
SQLite provider protocol; real temporary Markdown writes/roundtrips; external-edit
conflicts, explicit inspected-hash resolution and stale-hash refusal; persistent retry
queues, superseded revisions, exhaustion and diagnosed retry; Notion stub failure;
consistent backups, restore refusal on existing targets, v0.2 migration/replan holds,
idempotent migration, future-version refusal and injected DDL rollback; deterministic
per-order economics, failed deliveries, nonpositive contribution and invalid inputs;
CLI workflow, Markdown report, memory export/sync/backup and offline Finder status.

Fixtures are explicitly simulations. They do not represent independent live-model
reviews, real trade fills, actual market observations or user business settings.

## Verification limits

No authenticated Claude Code mission or genuinely separate model QA was executed.
No live Skill Finder endpoint/installer, Notion API, Obsidian application, brokerage,
owned-channel analytics, social platform, payment provider, supplier, carrier or
Iraqi regulatory source was exercised. Markdown file projection is tested locally;
Notion remains an explicit unimplemented/unconfigured stub. Source popularity and
old example financial/regulatory assertions were not promoted to verified facts.
No production concurrency, background worker, multiuser identity/authentication,
end-to-end external transaction or business profitability is established.
