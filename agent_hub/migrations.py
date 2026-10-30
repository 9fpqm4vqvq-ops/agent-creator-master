"""Additive v0.2/v0.3 -> v0.5 migration with verified pre-migration SQLite backup."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

VERSION = 6
TASK_COLUMNS = {
    'phase': "TEXT NOT NULL DEFAULT 'CREATED'",
    'department': "TEXT NOT NULL DEFAULT 'management'",
    'requested_owner': 'TEXT',
    'priority': "TEXT NOT NULL DEFAULT 'normal'",
    'selected_skills': "TEXT NOT NULL DEFAULT '[]'",
    'dependencies': "TEXT NOT NULL DEFAULT '[]'",
    'management_plan': 'TEXT',
    'cycle_limit': 'INTEGER NOT NULL DEFAULT 3',
    'migration_hold': 'INTEGER NOT NULL DEFAULT 0',
    'idempotency_key': 'TEXT',
    'resource_plan': 'TEXT',
    'project_id':'TEXT REFERENCES projects(id)',
    'owner_locked':'INTEGER NOT NULL DEFAULT 1',
}


def backup(connection, destination):
    path = Path(destination)
    if path.exists():
        raise ValueError('Backup destination already exists')
    path.parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(path)
    try:
        connection.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Created backup failed SQLite integrity verification')
    finally:
        target.close()
    return str(path)


def restore(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_file() or destination.exists():
        raise ValueError('Restore needs an existing backup and a new destination')
    connection = sqlite3.connect(f'{source.resolve().as_uri()}?mode=ro', uri=True)
    try:
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Backup integrity check failed')
        return backup(connection, destination)
    finally:
        connection.close()


def migrate(connection, db_path):
    version = connection.execute('PRAGMA user_version').fetchone()[0]
    if version > VERSION:
        raise ValueError('Database is newer than this application; use matching code')
    columns = {r[1] for r in connection.execute('PRAGMA table_info(tasks)')}
    legacy = 'phase' not in columns
    existing = connection.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    saved = None
    memory_exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_records'").fetchone()
    memory_count = connection.execute('SELECT COUNT(*) FROM memory_records').fetchone()[0] if memory_exists else 0
    if version < VERSION and (existing or memory_count):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        saved = backup(connection, str(db_path) + f'.pre-v06-{stamp}.sqlite')
    # DDL is transactional; a failed migration leaves the original schema usable.
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        for name, declaration in TASK_COLUMNS.items():
            if name not in columns:
                connection.execute(f'ALTER TABLE tasks ADD COLUMN {name} {declaration}')
        event_columns = {r[1] for r in connection.execute('PRAGMA table_info(events)')}
        if 'actor' not in event_columns:
            connection.execute("ALTER TABLE events ADD COLUMN actor TEXT NOT NULL DEFAULT 'legacy-operator'")
        if 'refs' not in event_columns:
            connection.execute("ALTER TABLE events ADD COLUMN refs TEXT NOT NULL DEFAULT '[]'")
        if legacy and existing:
            # Historical completions stay historical. In-flight work must be replanned.
            connection.execute("""UPDATE tasks SET phase=CASE
                WHEN status='COMPLETED' THEN 'COMPLETED'
                WHEN status='CANCELLED' THEN 'CANCELLED'
                ELSE 'MANAGEMENT_REVIEW' END,
                requested_owner=owner, migration_hold=CASE
                WHEN status IN ('COMPLETED','CANCELLED') THEN 0 ELSE 1 END""")
        from .memory import MEMORY_SCHEMA
        from .intelligence_schema import SCHEMA, FRESHNESS_COLUMNS
        import uuid
        for statement in MEMORY_SCHEMA.split(';'):
            if statement.strip(): connection.execute(statement)
        connection.execute("INSERT OR IGNORE INTO memory_metadata VALUES('source_instance',?)", (str(uuid.uuid4()),))
        present = {r[1] for r in connection.execute('PRAGMA table_info(memory_records)')}
        for name, declaration in FRESHNESS_COLUMNS.items():
            if name not in present:
                connection.execute(f'ALTER TABLE memory_records ADD COLUMN {name} {declaration}')
        connection.execute("UPDATE memory_records SET date_collected=created_at WHERE date_collected IS NULL")
        connection.execute("UPDATE memory_records SET responsible_department=CASE WHEN namespace='research' THEN 'agent-development' ELSE namespace END WHERE responsible_department IS NULL")
        for statement in SCHEMA.split(';'):
            if statement.strip(): connection.execute(statement)
        from .expansion_schema import SCHEMA as EXPANSION_SCHEMA
        for statement in EXPANSION_SCHEMA.split(';'):
            if statement.strip():connection.execute(statement)
        from .runtime_schema import SCHEMA as RUNTIME_SCHEMA
        from .research import RESEARCH_SCHEMA
        from .workspaces import WORKSPACE_SCHEMA
        for schema in [RUNTIME_SCHEMA,RESEARCH_SCHEMA,WORKSPACE_SCHEMA]:
            for statement in schema.split(';'):
                if statement.strip():connection.execute(statement)
        if version in {3,4,5}:
            connection.execute("UPDATE tasks SET migration_hold=1 WHERE phase NOT IN ('COMPLETED','CANCELLED')")
        connection.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT, backup_path TEXT)')
        connection.execute('INSERT OR IGNORE INTO schema_migrations VALUES(?,?,?)',
                           (VERSION, datetime.now(timezone.utc).isoformat(), saved))
        connection.execute(f'PRAGMA user_version={VERSION}')
    return {'version': VERSION, 'backup': saved, 'legacy_tasks': existing if legacy else 0}
