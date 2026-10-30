# Migration, interruption recovery and rollback

Keep v0.2 source and its operational data separately. The delivered ZIP contains
source only; it does not include your existing task DB, credentials or memory.

## Upgrade existing operational state

1. Stop all writers/Claude workers using the old DB. Save a consistent backup using
   SQLite's backup API. Do not copy a busy SQLite/WAL file as an ad hoc backup.
2. Use a copy of the operational database for the first migration. Keep the original
   protected. From v0.3, run `python -m agent_hub --db PATH_TO_COPY migrate`.
3. A nonempty v0.2 database automatically gets a timestamped `.pre-v03-...sqlite`
   backup before schema migration. Keep that returned path private and outside Git.
4. The migration transaction adds task phase, department, requested owner, priority,
   selected skills, dependencies, Management plan, cycle threshold and migration hold,
   plus event actor/references. It then initializes memory/skill tables and sets
   PRAGMA user_version=3. Existing task IDs, requests, result/event bytes and historic
   approvals are retained. Schema migration is additive, transactional and idempotent.
5. In-flight v0.2 tasks enter MANAGEMENT_REVIEW with migration_hold=1. Do not dispatch
   stale packets. Inspect original history, record a current plan and assign before
   a fresh handoff/preflight/start. Existing COMPLETED/CANCELLED tasks remain historical.
   Old snapshots are not recertified by migrating the DB.
6. Confirm counts, histories, registry and backup integrity before choosing the new
   DB as the active local store. Reconnect actual Claude authentication/tools separately.

The v0.2 `status` field is retained as a compatibility projection; `phase` is the
new enforced lifecycle. Old direct `new -> dispatch` scripts must add Management
review/plan/assignment and explicit start. Old review scripts must supply criterion
-level evidence. This intentional behavior change closes the previous routing gaps.
The original 24 regression scenarios remain, with setup helpers/CLI steps adapted
for these required gates. All imported package tests remain unchanged.

## Backup and restore

```bash
python -m agent_hub --db data/hub.sqlite backup --out work/manual-backup.sqlite
python -m agent_hub restore --source work/manual-backup.sqlite --out work/restored.sqlite
```

Existing destinations are refused. Restoring writes a new DB and validates source
integrity; point the intended version of the code at that restored DB only after
stopping other writers. A newer unsupported database version is rejected.

## Rollback to v0.2

Stop v0.3, retain its DB for investigation, restore the pre-v0.3 backup into a new
path, then run the original v0.2 code against that restored copy. v0.2 cannot read
v0.3 task phases/QA semantics safely. There is no destructive in-place downgrade
or silent merge of post-upgrade operations. Export/reconcile any desired new
knowledge explicitly. Vendor databases remain separate and are not migrated.

Test evidence covers v0.2 migration, replan holds, backup/restore, repeated migration,
future-version refusal and rollback after injected DDL failure. Live concurrent
multi-process operation, process-kill-at-every-instruction testing, external service
recovery and production backup retention have not been established.
