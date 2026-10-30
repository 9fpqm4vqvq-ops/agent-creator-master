# Migration and rollback — v0.3 to v0.4

Keep the original source folder and stop all operators/scheduler loops first.
Do not open a v0.4 database with old code. v0.3 and v0.4 share one Vault schema;
opening the new code automatically applies the additive migration.

1. With v0.3, `python -m agent_hub backup --out /SAFE/PATH/pre-v04.sqlite`.
   Keep a separate file backup of operational artifacts, local Markdown vault,
   runtime config and uncommitted source changes. Git/ZIPs intentionally omit them.
2. Extract v0.4 to a new folder, including hidden .claude files. Keep its reviewed
   root integration and vendor packages; migrate your own custom changes as explicit
   proposals. Do not copy old profiles over new ones without comparing them.
3. Copy the old database and operational files while all writers are stopped, or
   point `--db` at the existing Vault. Keep path-sensitive task artifacts at the
   same relative paths. Do not put either DB or operational data in GitHub.
4. Run `python -m agent_hub --db /PATH/hub.sqlite migrate`. Existing tasks or memory
   trigger a consistent `.pre-v04-TIMESTAMP.sqlite` automatic backup before DDL.
   Schema DDL is transactional; future schema versions are refused. Empty new
   databases need no pre-migration state backup.
5. Inspect IDs, history, namespaces and `PRAGMA integrity_check` using SQLite.
   Migration preserves task phases/status, knowledge bodies and existing IDs.
   Nonclosed v0.3 tasks have migration_hold=1 because code/instruction snapshots
   changed. Completed outcomes remain completed; no model work is fabricated.
6. For each held task, use `replan ID --evidence 'Actual migration/recovery diagnosis'`.
   This records the prior phase and returns it to MANAGEMENT_REVIEW. Record a fresh
   plan and assign, read current skills, redispatch, recall, preflight and start.
   Do not replay old provider invocations. Inspect old artifacts before reusing work.
7. Existing knowledge starts UNVERIFIED with original created_at as date_collected.
   No old record acquires a fabricated verification date. Run freshness scan and
   review outdated evidence. New maintenance jobs are disabled. Configure budgets
   and real usage sources before beginning paid work.

## Application/database rollback

Stop v0.4 and keep its current DB, audit logs and artifact folders as a separate
backup. Restore the pre-v0.4 snapshot to a NEW path with:

```bash
python -m agent_hub restore --source /SAFE/PATH/pre-v04.sqlite --out /SAFE/PATH/restored-v03.sqlite
```

`restore` checks SQLite integrity and refuses overwrite. Start the preserved v0.3
code against that restored v0.3 DB. Do not change PRAGMA user_version to pretend a
new schema is old, or delete v0.4 tables. Post-upgrade task/usage/knowledge writes
are in the retained v0.4 backup; reconcile them explicitly before any future merge.
No destructive down-migration or automatic cross-version data merge is provided.

For an individual agent/skill change, use `improvements rollback`; for an interrupted
activation use `improvements recover`, with a real incident/authorization reference.
Later human edits are a conflict and must be reviewed manually, never overwritten.
The proposal's file and SQLite backups plus chronological change history support
recovery. Global user authorization and host tool permissions remain authoritative.
