"""Execution records extend the canonical task workflow, not a second task database."""
SCHEMA='''
CREATE TABLE IF NOT EXISTS agent_runs (
 id TEXT PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id), status TEXT NOT NULL,
 provider TEXT NOT NULL, model TEXT, stage TEXT NOT NULL, workspace TEXT,
 worker_id TEXT, worker_pid INTEGER, worker_host TEXT, lease_until TEXT,
 cancel_requested INTEGER NOT NULL DEFAULT 0, attempt INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 3, input_hash TEXT NOT NULL, config TEXT NOT NULL,
 last_step TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 started_at TEXT, finished_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS agent_one_active_run ON agent_runs(task_id)
 WHERE status IN ('QUEUED','RUNNING','WAITING_FOR_TOOL','WAITING_FOR_APPROVAL','WAITING_FOR_QA','REWORK','CANCELLING');
CREATE TABLE IF NOT EXISTS agent_invocations (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES agent_runs(id), task_id INTEGER NOT NULL REFERENCES tasks(id),
 agent TEXT NOT NULL, department TEXT NOT NULL, stage TEXT NOT NULL, cycle INTEGER NOT NULL,
 status TEXT NOT NULL, reservation_key TEXT NOT NULL UNIQUE, input_hash TEXT NOT NULL,
 instruction_hash TEXT NOT NULL, provider TEXT NOT NULL, model TEXT, provider_invocation_id TEXT,
 reference TEXT, evidence_kind TEXT NOT NULL, output TEXT, error TEXT, approval_id TEXT,
 started_at TEXT, finished_at TEXT, duration_seconds TEXT, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS agent_invocation_active_stage ON agent_invocations(run_id,stage,cycle)
 WHERE status IN ('PREPARED','WAITING_FOR_APPROVAL','RUNNING','WAITING_FOR_TOOL');
CREATE TABLE IF NOT EXISTS agent_run_events (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES agent_runs(id), invocation_id TEXT REFERENCES agent_invocations(id),
 kind TEXT NOT NULL, actor TEXT NOT NULL, detail TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runtime_tool_calls (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES agent_runs(id), invocation_id TEXT NOT NULL REFERENCES agent_invocations(id),
 agent TEXT NOT NULL, name TEXT NOT NULL, arguments_hash TEXT NOT NULL, status TEXT NOT NULL,
 result TEXT, error TEXT, started_at TEXT NOT NULL, finished_at TEXT);
CREATE TABLE IF NOT EXISTS runtime_host_requests (
 id TEXT PRIMARY KEY REFERENCES agent_invocations(id), run_id TEXT NOT NULL REFERENCES agent_runs(id),
 challenge TEXT NOT NULL UNIQUE, status TEXT NOT NULL, request_path TEXT NOT NULL, response_path TEXT,
 reference TEXT, evidence_kind TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT);
'''
