"""v0.4 extensions in the existing task/Memory Vault database."""
SCHEMA = '''
CREATE TABLE IF NOT EXISTS usage_events (
 id TEXT PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id), agent TEXT NOT NULL,
 department TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, invocation_id TEXT NOT NULL,
 execution_key TEXT, token_kind TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER,
 cache_read_tokens INTEGER, cache_write_tokens INTEGER, actual_cost TEXT, estimated_cost TEXT,
 duration_seconds TEXT, collected_at TEXT NOT NULL, source TEXT NOT NULL, revision INTEGER NOT NULL,
 payload_hash TEXT NOT NULL, UNIQUE(provider,invocation_id));
CREATE TABLE IF NOT EXISTS ai_budgets (
 id TEXT PRIMARY KEY, scope TEXT NOT NULL, scope_key TEXT NOT NULL, limit_usd TEXT NOT NULL,
 alert_ratio TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL,
 UNIQUE(scope,scope_key));
CREATE TABLE IF NOT EXISTS budget_approvals (
 id TEXT PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id), execution_key TEXT NOT NULL,
 fingerprint TEXT NOT NULL, status TEXT NOT NULL, maximum_usd TEXT, reference TEXT,
 expires_at TEXT, created_at TEXT NOT NULL, consumed_at TEXT);
CREATE TABLE IF NOT EXISTS usage_reservations (
 execution_key TEXT PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id), agent TEXT NOT NULL,
 department TEXT NOT NULL, amount_usd TEXT, state TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS task_executions (
 execution_key TEXT PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id), handoff_id INTEGER NOT NULL REFERENCES events(id),
 agent TEXT NOT NULL, state TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
 UNIQUE(task_id,handoff_id));
CREATE TABLE IF NOT EXISTS memory_history (
 record_id TEXT NOT NULL REFERENCES memory_records(id), revision INTEGER NOT NULL,
 snapshot TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL,
 PRIMARY KEY(record_id,revision));
CREATE TABLE IF NOT EXISTS freshness_audits (
 id TEXT PRIMARY KEY, actor TEXT NOT NULL, at TEXT NOT NULL, findings TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS freshness_requests (
 record_id TEXT NOT NULL REFERENCES memory_records(id), revision INTEGER NOT NULL,
 task_id INTEGER NOT NULL REFERENCES tasks(id), PRIMARY KEY(record_id,revision));
CREATE TABLE IF NOT EXISTS department_health (
 id TEXT PRIMARY KEY, department TEXT NOT NULL, review_kind TEXT NOT NULL,
 reviewed_at TEXT NOT NULL, outcome TEXT NOT NULL, verified_versions TEXT NOT NULL,
 findings TEXT NOT NULL, evidence TEXT NOT NULL, corrective_actions TEXT NOT NULL,
 proposed_updates TEXT NOT NULL, review_status TEXT NOT NULL, next_due_at TEXT NOT NULL,
 qa_task_id INTEGER REFERENCES tasks(id));
CREATE TABLE IF NOT EXISTS maintenance_jobs (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, cadence TEXT NOT NULL, interval_seconds INTEGER,
 enabled INTEGER NOT NULL DEFAULT 0, due_at TEXT NOT NULL, principal TEXT NOT NULL,
 failures INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3, config TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS maintenance_runs (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES maintenance_jobs(id), due_at TEXT NOT NULL,
 worker_id TEXT NOT NULL, principal TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
 started_at TEXT NOT NULL, lease_until TEXT NOT NULL, finished_at TEXT, outcome TEXT, error TEXT,
 UNIQUE(job_id,due_at));
CREATE UNIQUE INDEX IF NOT EXISTS maintenance_one_running ON maintenance_runs(job_id) WHERE status='RUNNING';
CREATE TABLE IF NOT EXISTS change_proposals (
 id TEXT PRIMARY KEY, department TEXT NOT NULL, reason TEXT NOT NULL, health_review_id TEXT,
 files TEXT NOT NULL, manifest_hash TEXT NOT NULL, status TEXT NOT NULL, tests TEXT NOT NULL,
 qa_task_id INTEGER REFERENCES tasks(id), authorization_reference TEXT, backup_path TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, history TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_cache (
 task_id INTEGER NOT NULL REFERENCES tasks(id), query_hash TEXT NOT NULL, source TEXT NOT NULL,
 query TEXT NOT NULL, references_json TEXT NOT NULL, checked_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 classification TEXT NOT NULL, PRIMARY KEY(task_id,query_hash,source));
CREATE UNIQUE INDEX IF NOT EXISTS task_idempotency_key ON tasks(idempotency_key) WHERE idempotency_key IS NOT NULL;
'''

FRESHNESS_COLUMNS = {
 'date_collected': 'TEXT', 'last_verified_at': 'TEXT', 'next_review_at': 'TEXT',
 'expiry_policy': "TEXT NOT NULL DEFAULT '{}'", 'verification_status': "TEXT NOT NULL DEFAULT 'UNVERIFIED'",
 'superseded_by': 'TEXT', 'responsible_department': 'TEXT', 'category': "TEXT NOT NULL DEFAULT 'research'",
}
