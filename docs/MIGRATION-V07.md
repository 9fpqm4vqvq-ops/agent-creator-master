# v0.6 → v0.7 migration and rollback

Preserved baseline: main commit e1e94d17ed29c6de3514021098c742f9ea4c01c9.
Stop all workers, schedulers, bridge drivers and dashboards. Back up the existing
Vault with v0.6's `backup` command and retain its source and all workspaces/outputs.
Extract v0.7 into a separate directory. Operational state must never enter Git/ZIP.

Run `python -m agent_hub --db /your/state/hub.sqlite migrate` from v0.7.
Schema 7 adds shared runtime policy/history and reconciliation records to the same
Vault. Existing task, invocation, memory and cost histories remain. The migrator
creates a timestamped `.pre-v07-...` SQLite backup when existing records need an
upgrade. Confirm integrity and reported backup. Source changes invalidate older
instruction fingerprints; do not silently accept stale dispatch packets. Stop and
replan affected work, or create explicitly authorized replacement tasks after
reconciling external actions and costs.

Rollback: stop v0.7, preserve its operational state for diagnosis, restore the
verified pre-v7 backup into a NEW destination using `restore`, and reopen only that
schema-6 copy with preserved v0.6 code. Do not downgrade the operational database
in place or feed schema 7 to old code. Database rollback does not undo provider
charges, external actions or file edits. Preserve and reconcile those receipts.
The v0.6 archive is retained unchanged; v0.7 builds refuse archive overwrites.
