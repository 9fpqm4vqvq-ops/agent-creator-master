# Actual Skill Finder integration

The provided skill-finder.zip was inspected before integration. It contains one
file, skill-finder/SKILL.md (8,105 bytes), and no Python/JavaScript package, executable
API implementation, test suite or bundled dependency lock. SHA-256 and provenance
are recorded in registry/skill-finder-source.json. The raw document is preserved
unchanged under vendor/skill-finder and is not a native active skill.

It describes GET https://claude-plugins.dev/api/skills?q=... and
`npx claude-plugins skills install <namespace> --local`, with popularity heuristics
and automatic installation. Those are document claims, not verified capabilities.
No live endpoint or installer execution was performed. The auto-install guidance
conflicts with the v0.3 security request and is deliberately disabled.

The root skill-finder wrapper and SkillFinderAdapter search locally first and
return discovery-only candidates. An authorized host can inject a WebFetch/HTTP
transport. The adapter validates the documented response shape and HTTPS source
URLs, marks every result QUARANTINED and never fetches/executes candidate code or
runs a package manager. Offline schema, transport-failure and no-install checks
were executed. Without a transport, it returns REQUIRES_CONFIGURATION and a query
hint while the system's local inventory remains usable.

Management escalates a missing capability to Agent Development & Research. Stage
candidate files under work/skill-candidates, outside native .claude discovery.
Inspect dependencies, code, referenced files, provenance/license, permissions and
compatibility; adapt an existing reviewed skill when possible. Register metadata,
then conduct representative tests and separate QA. Activation needs passing test
references, review notes, a separate QA actor and a real scoped authorization
reference. Source drift invalidates review. Popularity and a GitHub URL are never
security validation. Registry attestations do not authenticate a human/model.

Activation permits hub selection of the reviewed staged instructions. It does not
silently install a native slash command. A requested native installation must be a
separately reviewed local source revision after current task trees complete.
Metadata includes name/version, description, agent/department compatibility,
dependencies, source/provenance, permissions, security status, test evidence,
validation date and durable per-handoff selection/use history.
