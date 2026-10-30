# Two integrated operational departments — v0.5

Organization: User → Master → Management → assigned department → independent QA →
Master → User. Web & Application Development and Social Media & Digital Presence
are peers of Income under Management. Income still owns Trading, Shorts/Content
Income and Iraq E-commerce. There are 70 root roles and 9 operational dashboard
panels (including the three Income subdepartments), with 176 catalogued skills.

This upgrade extends the existing Python standard-library hub, SQLite Vault,
read-only dashboard, memory, health/freshness, usage, scheduler and reviewed-update
modules. It does not install a second agent framework, paid daemon or competing DB.

## Roles and focused assignment

WD-01 through WD-13 cover direction, current technology research, UI/UX research,
product architecture, design systems, frontend, backend/API, database architecture,
mobile, testing/accessibility, security/performance, deployment and documentation.
SM-01 through SM-13 cover direction, trends, audience/competitors, strategy, copy,
brand, graphics/carousels, video/motion, calendars, analytics, community, integrations
and internal compliance. See ARCHITECTURE-V05.md and each .claude/agents profile.

Management confirms scope, chooses a registered owner and the smallest useful team,
sets measurable criteria and dependencies, then assigns. `route suggest` returns
transparent lexical hints; it invokes nobody and never overrides an explicit worker.
General Instagram/campaign requests suggest Social Media; website/API work suggests
Web. Commercial Iraq feasibility can involve E-commerce, while software is Web work.
Income Shorts is suggested for explicit income/monetization work, not all video posts.
Ambiguous work stays with Management. Examples and hints are not exhaustive NLP.

Use `projects decompose` for scoped child tasks. Management must first review the
parent. Each child has a stable scope name, department, owner, request and criteria.
Optional depends_on names form an acyclic graph. Retries are idempotent; invalid
batches roll back. Dependencies survive subsequent planning and gate dispatch.
Handoff acknowledgement records receipt, not assignment, invocation or completion.
The original parent/child/dependency QA checks remain authoritative.

## Real local support and runtime boundaries

`projects scaffold` produces actual responsive HTML/CSS or a loopback-only SQLite
JSON API prototype in ignored outputs/, after the assigned Web task is IN_PROGRESS.
The choice is explicit, not a universal framework recommendation. Local prototypes
have actual files/run instructions; the API has JSON validation and parameterized
SQLite writes. They still need project-specific engineering, testing and independent
QA. Production authentication, deployment, load/cross-browser/accessibility coverage
and native mobile builds are not provided by the small scaffold helper.

`social graphic` produces an actual escaped SVG draft. `social export` produces
versioned Markdown/CSV calendar files with timezone and timing basis. It schedules
nothing on a platform. Caption/script/design/video production beyond these helpers
is performed by actual authenticated runtime workers using selected reviewed skills.
A production brief is a useful fallback when a renderer, SDK or design connector is
absent. No MP4, Figma edit, iOS/Android build, social publication or website deployment
is claimed from descriptions, HTML, a skill or a mock adapter.

A separate authenticated Claude Code session must actually invoke workers and QA.
Python packets/state records cannot do that. This build used offline fixtures for
model/QA/provider references; no live business account was connected.

## Persistent records and memory

`projects` stores software/campaign briefs, requirements, constraints, milestones,
risks, technology decisions, research/design/implementation state, tests, defects,
deployment readiness, output paths, revisions and history. `kind=web` and `kind=social`
share the same service/table; a project UUID also groups cross-department tasks and
usage. Approved project links bind the current record and actual file hashes.
Edits invalidate project QA links. A separate follow-up/action task can reference a
project after its original parent closes; closed parents cannot gain new children.

Web roles can read/write web-development, web-design-research and application-architecture.
Social roles can read/write social-media, social-trends, brand-assets, content-calendar
and social-analytics. Existing namespaces remain. connector-capabilities is readable
by registered roles and writable only by Management/Master, Agent Development and
the two designated integration roles. Other department knowledge remains restricted;
collaboration does not grant unrestricted access. These are trusted-operator application
ACLs, not authenticated multi-user OS isolation.

New/edited knowledge is UNVERIFIED. Framework-version review defaults to 7 days,
social trends to 3 days, connector permissions to 1 day. Existing category defaults
remain configurable. Retrieval flags an expired FRESH record before reuse even if
the scheduled scan has not run. Supersession, content hashes, source dates and full
history still use the existing Knowledge Freshness Auditor and QA gates.

## QA, resources and maintenance

All new work retains the original eleven checks, precise rework and escalation.
Web QA additionally covers accessibility, responsiveness, performance, maintainability,
dependency compatibility, documentation and deployment readiness. Social QA adds
brand/audience alignment, readability/visual quality/platform suitability, rights,
disclosures, calendar correctness, connector authority and analytics integrity.
NOT_APPLICABLE needs a reason; acceptance criteria cannot be skipped. Internal testing
or content compliance review never grants independent approval.

Task/project/agent/department/daily/monthly AI budgets share the existing ledger and
reservation gates. Project budgets include all attached child and follow-up tasks,
including other departments. Actual costs, estimates, cache counters and UNKNOWN
remain distinct. Missing provider data is not zero. Successful connector receipts
record any supplied usage/cost evidence; simulated telemetry stays estimated/unknown.
Unusable telemetry cannot erase a verified external receipt. Provider-side hard billing
caps still require separate configuration and cannot be guaranteed by local Python.

The same Health Registry now covers both departments, stale knowledge and actual
QA-rework/cost observations. Local/upstream currency remains PARTIALLY_VERIFIED without
live authoritative research. Existing weekly/monthly/quarterly scheduler suggestions
apply through the same department allowlist; all jobs remain disabled by default.
AI maintenance queues requests for authenticated Claude, never a silent paid call.
Agent/skill changes still require isolated staging/tests, separate QA, actual scoped
activation, idle tasks, backup and rollback. No auto-update of active instructions.

## CLI entry points

All new service actions take JSON keyword arguments in `--data FILE`, as in v0.4.
Use ignored work/ for actual records, not checked-in templates containing private data.

| Command family | Actions |
| --- | --- |
| `projects` | create, get, list, update, decompose, accept_handoff, scaffold, approve, deployment_payload |
| `social` | create, get, list, update, internal_review, approve, archive, export, graphic, analytics, publication_payload |
| `connectors` | candidates, discover, discover_tools, get, list, plan, disable, authorize |
| `route` | suggest |
| `design-search` | search |

Read WEB-WORKFLOW-V05.md, SOCIAL-WORKFLOW-V05.md and CONNECTORS-V05.md for arguments,
review links and the configured-runtime adapter boundary. External execution is a
Python runtime-adapter API, not an arbitrary shell command or stored credential.

Project/content approval packets must belong to the same project/campaign and its
owning department, and record the actual subject authors; another department's
completed generic QA task cannot supply the specialized approval link.
