# v0.4 → v0.5 migration and rollback

Stop all hub writers, foreground maintenance loops and Claude workers. Keep the v0.4
source and a consistent database/file backup. No operational DB, credentials, outputs,
vault or personal configuration belongs in GitHub or the release ZIP.

1. From v0.4, run `python -m agent_hub backup --out /SAFE/PATH/pre-v05.sqlite`.
   Also back up runtime configuration, actual artifacts, local Markdown and custom
   source changes. SQLite backup verifies integrity; filesystem backup is separate.
2. Extract v0.5 in a separate folder including hidden .claude files. Merge your
   custom source changes explicitly; do not overwrite reviewed v0.5 profiles with
   older ones. Original vendor packages are preserved. New package sources/wrappers
   are documented in SKILLS-V05.md; no third-party installer is run by extraction.
3. With every writer stopped, copy the old Vault and needed artifacts to the new
   folder at the same relative paths, or use --db to point at the actual existing DB.
4. Run `python -m agent_hub --db /PATH/hub.sqlite migrate`. Schema 5 adds project,
   content, connector/action/handoff records and task project linkage to the same DB.
   Existing task/memory content triggers a verified `.pre-v05-TIMESTAMP.sqlite` backup
   before transactional DDL. Future schema versions are refused.
5. Existing IDs, task phases/status, history, usage, reservations, budgets, namespace
   data, freshness, scheduler settings and provider queues remain. Active v0.4 tasks
   gain migration_hold=1; completed/cancelled work stays historical. New role/skill
   seeds are imported as reviewed built-ins, not unreviewed raw packages. Existing
   database skill records are not silently overwritten: inspect stale fingerprints
   after a version change and revalidate via the approved registry/update workflow.
6. For each held task, run `replan ID --evidence 'Actual migration diagnosis'`, then
   replan/assign/dispatch/recall/preflight/start under the current instructions.
   Reconcile prior invocations/reservations; never charge/replay them just because
   the new version can start. Current task/skill/instruction snapshots must match.
7. New Web/Social namespace families are explicit; existing department ACLs remain.
   Run health/freshness scans. Framework/social/permission TTLs are review suggestions,
   not current external verification. Preserve historical findings/supersession.
8. Newly seeded maintenance remains disabled. Existing user-selected scheduler
   enablement/department lists are preserved. If an old enabled job explicitly named
   only the old departments, add the new departments deliberately before expecting
   it to audit them. Nothing launches a paid model or installs an OS daemon.
9. Configure project budgets if useful. Discover actual tools in the authenticated
   target runtime and test harmless read/auth/permissions before consequential use.
   No old plugin configuration or build-session access becomes a live connection.

## Existing reviewed skill metadata

v0.4 correctly used INSERT OR IGNORE for operational skill records, so a new source
seed cannot silently widen an existing runtime skill's permissions. Consequently,
old master-workflow/memory-vault records may show drift or lack the new departments.
Use the v0.5 reviewed-baseline synchronization command after migration:

```bash
python -m agent_hub skills reconcile-baseline --review work/baseline-review.json
```

The review object needs reviewer qa-auditor, author agent-creator-researcher,
actual review_reference, actual authorization_reference, expected_diff_hash from skills baseline-diff, and passing tests with
real references. The operation shows changed old/new metadata, verifies current
source fingerprints and requires allow_capability_expansion=true when departments,
permissions or dependencies change. It refuses active tasks unless they are held
for migration, retains old/new skill revisions and never revalidates user candidates.
These are operator attestations, not authenticated model identities. Complete the
real review; do not copy fixture approvals or manufacture evidence. Replan held work
only after its skills are valid. This migration exception does not allow edits to
active source instructions or arbitrary unreviewed native skill installation.

## Nondestructive rollback

Stop v0.5 and retain its current DB/artifacts/history separately. With the v0.5 restore
helper, restore the pre-upgrade snapshot to a NEW destination:

```bash
python -m agent_hub restore --source /SAFE/PATH/pre-v05.sqlite --out /SAFE/PATH/restored-v04.sqlite
```

Start the preserved v0.4 code against that restored v0.4 DB. Never open the schema-5
Vault with old code, change PRAGMA user_version to disguise it, or delete tables.
Post-upgrade projects/content/usage remain in the saved v0.5 DB and must be explicitly
reconciled before any future migration/merge. No destructive down-migration is supplied.

For individual instructions/skill updates use the existing improvements rollback or
recover workflow with actual scoped authorization/incident references and verified
file/Vault backups. Later manual edits are conflicts, not permission to overwrite.
For ambiguous external actions, use read-only provider reconciliation; database or
source rollback cannot undo a real publication, deployment or provider charge.
