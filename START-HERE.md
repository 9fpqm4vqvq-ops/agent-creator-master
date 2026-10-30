# Start v0.7

Follow README.md's installation, authentication and actual live check first. Use
Python 3.10+ and a supported authenticated provider. Never copy an operational
v0.6 database into new code without reading docs/MIGRATION-V07.md and backing up.

Create `work/request.json`:

```json
{"request":"Draft three original launch captions and a calendar as local files; do not publish","criteria":"Three original captions, clear audience/timezone, source limitations and separate QA"}
```

```bash
python -m agent_hub runtime intake --data work/request.json
```

Use the actual task ID returned to write `work/execute.json`:

```json
{"task_id":1}
```

```bash
python -m agent_hub runtime execute --config templates/runtime-claude.json --data work/execute.json
python -m agent_hub dashboard --port 8765
```

Inspect status/error, invocation evidence and QA result. Configured does not mean
live tested; a blocked run is never a completed task. Read docs/OPERATIONS-V07.md
for web checks, per-run ceilings, other budget scopes, capacity, recovery and
connector setup. Source and source-derived instructions cannot authorize account
writes. The interactive `scripts/start-master.sh` workflow remains available, but
it is a separate interface requiring its own authentication and real delegation.
