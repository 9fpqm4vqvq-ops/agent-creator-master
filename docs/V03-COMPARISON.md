# v0.2 -> v0.3 architecture gap analysis and comparison

Scope: the existing project, its four preserved imports, both earlier README
attachments and the actual instruction-only Skill Finder ZIP. The requested audit
preceded source edits. v0.2 remains in a separate workspace folder; v0.3 extends its
control-plane validators rather than rebuilding the specialist tools.

| Requirement | v0.2 audit classification | v0.3 disposition |
| --- | --- | --- |
| Existing roles, skills and tools | ALREADY IMPLEMENTED | All original 33 root profiles, 28 vendor profiles and 60 vendor skills preserved; new roles/skills added |
| Master/department structure | PARTIALLY IMPLEMENTED | Explicit Management lead and mandatory logical chain |
| Management before dispatch | MISSING | Review, researched plan and assignment gates in the supported Hub/CLI |
| Acceptance criteria and artifacts | ALREADY IMPLEMENTED | Original artifact/path/hash checks retained and extended |
| Independent QA and bounded rework | PARTIALLY IMPLEMENTED | Criterion-level evidence, all eleven checks, test references, author exclusion and configurable escalation/resumption |
| Central skill metadata and usage | MISSING | Reviewed seed catalog plus persistent registry, discovery, source drift rejection and per-handoff usage |
| Automatic discovery and installs | MISSING | Guarded adapter and staged candidate lifecycle; automatic installs intentionally disabled |
| Skill Finder executable API | REQUIRES CONFIGURATION | Actual ZIP has instructions only; live documented endpoint/installer unverified; injectable discovery adapter provided |
| Iraq e-commerce subdepartment | MISSING | Eight specialist profiles under Income and explicit opportunity/economics contracts |
| Local event storage | PARTIALLY IMPLEMENTED | Existing events retained; actor/references, decisions, research, tests, corrections and retrieval trail added |
| Shared knowledge/department memory | MISSING | UUID/revision/hash SQLite records, namespace ACLs and recall/approved-outcome storage |
| Markdown/Obsidian vault files | MISSING | Local file projection and roundtrip implemented/tested; actual Obsidian application not connected |
| Notion service synchronization | REQUIRES CONFIGURATION | Explicit unimplemented stub; requires authorized API implementation and live tests |
| Incremental sync/retries/conflicts | MISSING | Durable revision-keyed queues, idempotency, bounded backoff, external-edit conflicts and reconciliation |
| Detailed lifecycle | PARTIALLY IMPLEMENTED | Full phase machine with v0.2 status projection |
| Migration/rollback | MISSING | Consistent pre-upgrade backup, additive transaction, replan hold, new-target restore and rollback procedure |
| Runtime identity/authentication | REQUIRES CONFIGURATION | Host/Claude authentication remains necessary; local attestations are not identity proofs |
| Broker/publishing/background execution | REQUIRES CONFIGURATION | Existing research/paper boundaries retained; no live broker or unattended worker added |
| Conflicting root reporting instructions | BROKEN | Root wrapper parent references aligned with explicit Management hierarchy |
| Raw Skill Finder auto-install policy | BROKEN for requested controls | Preserved as reference; safe wrapper prevents its guidance from authorizing installation |

## Responsibility review

Management owns task analysis, routing, priorities, dependencies and corrections.
Agent Development & Research owns capability evaluation/maintenance; its existing
agent-creator worker prepares drafts. Registry Manager maintains metadata, not
independent QA. Income owns opportunity research and its Trading/Shorts/E-commerce
subdepartments. The e-commerce Business Validation Analyst prepares a business
assessment; only separate QA reviews that departmental deliverable. Similar roles
are retained with distinct reporting/scope rather than deleted as duplicates.

## Preserved and repaired

Preserved: vendor source bytes and licenses, existing specialist definitions/tools,
standard-library hub approach, artifact and instruction hashing, source timestamp
validation, parent completion gates, the original 24 regression scenarios, and
credential/financial-action limits. Changes are concentrated in root integration,
new modular memory/skill providers, profiles, templates, documentation and tests.

Repaired: bypassable direct department dispatch, coarse/inflexible QA records,
missing instruction/code coverage in snapshots, inconsistent parent references,
native-discovery exposure for unreviewed candidates, and absent migration/recovery.

Added: Management role, eight e-commerce roles, four task-focused skills, central
65-skill inventory, full phase machine, structured QA/corrections, guarded discovery,
persistent knowledge/namespace memory, provider protocol, Markdown projection,
Notion stub, sync queues, migration tooling and complete CLI/documentation.

## Verification and remaining configuration

See V03-TEST-RESULTS.md for executed results. Tests exercise deterministic local
behavior, migration and offline transport/provider failures. They do not establish
real Claude delegation, independently invoked model QA, current Iraqi market data,
supplier shipping, payment/merchant eligibility, current legal rules, the live
Skill Finder service, Notion, Obsidian application sync or strategy profitability.

Actual Claude authentication/tools, authorized research access and any external
sync/side effects require configuration. Spending, purchases, inventory orders,
ads, outreach, new accounts, storefront/content publication and live trading
require the user's applicable scoped authorization and host permissions. No such
business action was performed by this upgrade. Local ACLs and redaction are not
an authenticated multiuser security service or an OS sandbox.
