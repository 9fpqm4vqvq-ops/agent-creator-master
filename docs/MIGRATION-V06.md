# v0.5 → v0.6 migration and rollback

Stop workers, schedulers and dashboard first. Preserve the original ZIP, application
source, operational databases, memory projection and any execution workspaces.
Never publish operational state or credentials.

Run `python -m agent_hub backup --out /your/backup/hub-v05.sqlite` with the old code
first. Extract v0.6 in a separate directory. Copy operational state only deliberately,
preserving ownership and restrictive permissions. Then run
`python -m agent_hub --db /your/state/hub.sqlite migrate` from the v0.6 directory.

Schema 6 adds run/invocation/event/tool/research/check records and owner_locked.
Existing active v3/v4/v5 tasks receive migration_hold and need fresh Management
replanning with `replan`, then fresh instructions/preflight. Existing requested
owners remain locked. Current source changes invalidate old instruction snapshots.
The migrator creates a timestamped `.pre-v06-...` SQLite backup before changing an
existing schema; verify reported backup and integrity. Closed task history is retained.
The read-only dashboard requires the matching migrated schema and never migrates it.

Rollback: stop all new processes, archive v0.6 operational state for investigation,
restore the verified pre-v6 database to a **new** destination with `restore` and use
the preserved v0.5 source with that restored database. Do not open a schema-6
operational database with old code or downgrade it in place. Reconcile external
operations and unknown provider costs before replacement work; rollback cannot undo
provider calls, deployment, publication or financial actions.
