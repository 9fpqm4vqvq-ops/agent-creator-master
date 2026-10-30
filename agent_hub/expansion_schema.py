"""Additive v0.5 records in the existing SQLite Vault."""
SCHEMA='''
CREATE TABLE IF NOT EXISTS skill_baseline_revisions (
 id TEXT PRIMARY KEY, skill_id TEXT NOT NULL REFERENCES skill_registry(id), old_record TEXT NOT NULL,
 new_record TEXT NOT NULL, review_reference TEXT NOT NULL, authorization_reference TEXT NOT NULL,
 diff_hash TEXT NOT NULL, at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id), kind TEXT NOT NULL,
 title TEXT NOT NULL, brief TEXT NOT NULL, record TEXT NOT NULL, revision INTEGER NOT NULL,
 qa_task_id INTEGER REFERENCES tasks(id),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS project_history (
 project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL, record TEXT NOT NULL,
 actor TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY(project_id,revision));
CREATE TABLE IF NOT EXISTS department_handoffs (
 id TEXT PRIMARY KEY, parent_task_id INTEGER NOT NULL REFERENCES tasks(id), child_task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id),
 from_department TEXT NOT NULL, to_department TEXT NOT NULL, brief TEXT NOT NULL, accepted_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS content_items (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), task_id INTEGER NOT NULL REFERENCES tasks(id),
 platform TEXT NOT NULL, title TEXT NOT NULL, payload TEXT NOT NULL, content_hash TEXT NOT NULL,
 revision INTEGER NOT NULL, status TEXT NOT NULL, scheduled_at TEXT, timezone TEXT NOT NULL,
 timing_basis TEXT NOT NULL, qa_task_id INTEGER REFERENCES tasks(id), remote_reference TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS content_history (
 item_id TEXT NOT NULL REFERENCES content_items(id), revision INTEGER NOT NULL, snapshot TEXT NOT NULL,
 actor TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY(item_id,revision));
CREATE TABLE IF NOT EXISTS analytics_observations (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), platform TEXT NOT NULL,
 dataset TEXT NOT NULL, classification TEXT NOT NULL, source TEXT NOT NULL, collected_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS connector_capabilities (
 runtime_id TEXT NOT NULL, provider TEXT NOT NULL, connector_type TEXT NOT NULL, status TEXT NOT NULL,
 operations TEXT NOT NULL, authentication_status TEXT NOT NULL, approvals TEXT NOT NULL,
 rate_limits TEXT, cost_limits TEXT, last_successful_test TEXT, limitations TEXT NOT NULL,
 evidence_kind TEXT NOT NULL, discovered_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(runtime_id,provider));
CREATE TABLE IF NOT EXISTS connector_tests (
 id TEXT PRIMARY KEY, runtime_id TEXT NOT NULL, provider TEXT NOT NULL, operation TEXT NOT NULL,
 result TEXT NOT NULL, evidence_kind TEXT NOT NULL, reference TEXT NOT NULL, at TEXT NOT NULL,
 FOREIGN KEY(runtime_id,provider) REFERENCES connector_capabilities(runtime_id,provider));
CREATE TABLE IF NOT EXISTS action_approvals (
 id TEXT PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id), runtime_id TEXT NOT NULL,
 provider TEXT NOT NULL, operation TEXT NOT NULL, subject_hash TEXT NOT NULL, destination TEXT NOT NULL,
 request_hash TEXT NOT NULL, reference TEXT NOT NULL, maximum_usd TEXT NOT NULL,
 expires_at TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS external_actions (
 id TEXT PRIMARY KEY, approval_id TEXT NOT NULL UNIQUE REFERENCES action_approvals(id),
 task_id INTEGER NOT NULL REFERENCES tasks(id), runtime_id TEXT NOT NULL, provider TEXT NOT NULL,
 operation TEXT NOT NULL, subject_hash TEXT NOT NULL, destination TEXT NOT NULL,
 execution_key TEXT NOT NULL UNIQUE REFERENCES task_executions(execution_key),
 evidence_kind TEXT NOT NULL,
 status TEXT NOT NULL, result TEXT, error TEXT, started_at TEXT NOT NULL, finished_at TEXT);
'''
