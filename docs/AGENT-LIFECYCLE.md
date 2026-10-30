# Agent creation, research and maintenance

The creator/researcher maintains local agent definitions and skills. It does not
silently rewrite itself from web pages. This first release uses reviewed Git
changes rather than an automatic update daemon.

For every assigned task, record a `preflight ID --checks PATH` attestation after inspecting the current root contract, role, relevant skills,
runtime/tool availability and task constraints. Check the official documentation
for version-sensitive capabilities. Record source URL, version, checked timestamp,
confidence and any inaccessible sources. A local file hash proves identity, not
that its advice is current. Never claim all agents are up to date solely from tests.

For a new agent or revision:

1. Document the repeated need and why an existing role cannot do it.
2. Specify name, department/parent, version, triggers, inputs, outputs, skills,
   tools, boundaries, escalation, acceptance criteria and reporting contract.
3. Review skills/code as untrusted input. Inspect dependencies, licenses,
   network destinations, side effects and any secret requirements.
4. Stage candidate profiles or a patch under `work/agent-changes/` and bump their
   versions. Evaluate the candidate in an isolated copy. Keep active profiles and
   policies unchanged until this task and its parent report have completed review;
   changing them during execution invalidates the task snapshot. Keep prior revisions
   recoverable through Git. Do not overwrite user modifications.
5. Add representative behavioral tests: successful task, missing evidence,
   prompt injection, stale instructions, unauthorized action and failure recovery.
6. Run `python scripts/validate_all.py`. Have a separately invoked QA auditor
   inspect the diff, source evidence, permissions and outputs.
7. After the task tree completes, apply reviewed local revisions within the user's
   authorized scope. Activate the profile in a new Claude Code session or by the runtime's
   documented reload procedure. New remote services, expanded privileges and
   external deployment need scoped authorization; local drafts requested by the
   user do not require repeated permission.
8. For an in-flight task, cancel/recreate with a fresh dispatch packet after an
   instruction change. Never silently reuse a result based on different instructions.
   If a completed child's instructions or artifact bytes change before its parent
   passes, restore the reviewed bytes or cancel/recreate the parent task tree.

Root routing currently lists six lead/QA profiles and 27 imported specialist
wrappers explicitly in `agent_hub/core.py` (33 selectable agents).
Adding a profile requires updating ROLES, the profile file and routing tests;
merely creating an agent in the vendor MAOS SQLite registry does not update the hub.
The root master can still invoke existing vendor specialists as reference roles
through the native host, but only root profiles are selectable hub owners.

Keep actual outcomes and regressions, not invented token savings. If no usage
telemetry exists, label costs unknown or estimated. Review failures should narrow
the required rework; after three rework requests the hub blocks the task.

SQLite files are local operational state, not credentials or authorization proofs.
Use SQLite's backup API for a consistent backup before migration; store backups
securely outside Git. No scheduled backup/restore service is configured yet.

Use templates/agent-change.md for concrete revisions. The dispatch manifest includes
root profiles, department policies, discoverable skills and the selected vendor tools.
A new dispatch after rework requires fresh preflight checks; a previous record cannot
be reused. UNVERIFIED freshness must appear in result limitations. The records do
not automatically fetch documentation or prove source contents.
