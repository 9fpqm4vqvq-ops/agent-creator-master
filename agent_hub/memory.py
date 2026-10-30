"""Local system-of-record memory, explicit namespace access and durable sync queues."""
import hashlib
import json
import sqlite3
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .legacy import now, required, validate_sources
from .roles import ROLES, NAMESPACES, DEPARTMENT_NAMESPACE
from .departments import NAMESPACE_OWNERS
from .security import redact, canonical


class ConflictError(ValueError):
    pass


def authorize(actor, namespace, write=False):
    if namespace not in NAMESPACES or actor not in ROLES:
        raise PermissionError('Unknown principal or memory namespace')
    department = DEPARTMENT_NAMESPACE.get(ROLES[actor][0], ROLES[actor][0])
    if actor in {'master-agent', 'management-director'}:
        return
    if actor in {'qa-auditor','department-health-auditor','knowledge-freshness-auditor'} and not write:
        return
    if namespace=='connector-capabilities':
        if not write or actor in {'agent-creator-researcher','social-platform-integration-specialist','web-devops-deployment-engineer'}:return
    if namespace == department or NAMESPACE_OWNERS.get(namespace)==ROLES[actor][0] or namespace == 'shared' and not write:
        return
    raise PermissionError('Memory namespace access denied')


MEMORY_SCHEMA = '''
    CREATE TABLE IF NOT EXISTS memory_records (
      id TEXT PRIMARY KEY, namespace TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
      payload TEXT NOT NULL, sources TEXT NOT NULL, task_id INTEGER REFERENCES tasks(id),
      owner TEXT NOT NULL, confidence TEXT NOT NULL, revision INTEGER NOT NULL,
      content_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS memory_sync_queue (
      id INTEGER PRIMARY KEY, provider TEXT NOT NULL, record_id TEXT NOT NULL REFERENCES memory_records(id),
      revision INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0,
      next_at TEXT NOT NULL, error TEXT, UNIQUE(provider,record_id,revision));
    CREATE TABLE IF NOT EXISTS memory_sync_state (
      provider TEXT NOT NULL, record_id TEXT NOT NULL, remote_hash TEXT NOT NULL,
      revision INTEGER NOT NULL, PRIMARY KEY(provider,record_id));
    CREATE TABLE IF NOT EXISTS memory_metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS memory_sync_resolutions (
      id INTEGER PRIMARY KEY, queue_id INTEGER NOT NULL REFERENCES memory_sync_queue(id),
      actor TEXT NOT NULL, evidence TEXT NOT NULL, acknowledged_remote_hash TEXT NOT NULL,
      local_revision INTEGER NOT NULL, at TEXT NOT NULL);
    '''


def initialize(connection):
    connection.executescript(MEMORY_SCHEMA)
    with connection:
        connection.execute("INSERT OR IGNORE INTO memory_metadata VALUES('source_instance',?)", (str(uuid.uuid4()),))


class MemoryVault:
    def __init__(self, connection, root=None):
        self.db = connection
        self.root = root

    def get(self, record_id, actor):
        row = self.db.execute('SELECT * FROM memory_records WHERE id=?', (record_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown memory record')
        record = dict(row)
        authorize(actor, record['namespace'])
        record['payload'] = json.loads(record['payload'])
        record['sources'] = json.loads(record['sources'])
        from .usage import instant
        record['effective_verification_status']='REQUIRES_VERIFICATION' if record['verification_status']=='FRESH' and record['next_review_at'] and instant(record['next_review_at'])<=instant(now()) else record['verification_status']
        record['source_instance'] = self.db.execute("SELECT value FROM memory_metadata WHERE key='source_instance'").fetchone()[0]
        return record

    def put(self, namespace, kind, title, payload, actor, sources=None, task_id=None,
            confidence='UNVERIFIED', record_id=None, expected_revision=None, commit=True, category='research'):
        authorize(actor, namespace, write=True)
        from .freshness import policy_for
        policy = policy_for(category,self.root)
        required(kind, 'Memory kind'); required(title, 'Memory title')
        if confidence not in {'UNVERIFIED', 'VERIFIED', 'ESTIMATE', 'ASSUMPTION', 'QA_APPROVED_OPERATOR'}:
            raise ValueError('Unknown memory confidence')
        sources = sources if sources is not None else []
        validate_sources(sources)
        if confidence == 'VERIFIED' and not any(s['classification'] == 'VERIFIED' for s in sources):
            raise ValueError('Verified memory requires dated verified source evidence')
        record_id = record_id or str(uuid.uuid4())
        try:
            uuid.UUID(record_id)
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Memory IDs must be UUIDs') from None
        clean = redact({'kind': kind, 'title': title, 'payload': payload, 'sources': sources})
        content = dict(clean, namespace=namespace, task_id=task_id, confidence=confidence)
        content_hash = hashlib.sha256(canonical(content).encode()).hexdigest()
        prior = self.db.execute('SELECT * FROM memory_records WHERE id=?', (record_id,)).fetchone()
        if prior:
            authorize(actor, prior['namespace'], write=True)
            if prior['namespace'] != namespace:
                raise ConflictError('A record cannot change namespace')
            if prior['content_hash'] == content_hash and prior['category']==category:
                return self.get(record_id, actor)
            if prior['superseded_by']:raise ConflictError('Superseded knowledge is immutable; create a new record for a new claim')
            if expected_revision != prior['revision']:
                raise ConflictError('Memory revision conflict; reload before updating')
        revision = prior['revision'] + 1 if prior else 1
        created = prior['created_at'] if prior else now()
        with self.db if commit else nullcontext():
            if prior:self._history(dict(prior), actor, 'before content update')
            self.db.execute('''INSERT INTO memory_records
                (id,namespace,kind,title,payload,sources,task_id,owner,confidence,revision,content_hash,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,title=excluded.title,
                payload=excluded.payload,sources=excluded.sources,task_id=excluded.task_id,
                confidence=excluded.confidence,revision=excluded.revision,
                content_hash=excluded.content_hash,updated_at=excluded.updated_at''',
                (record_id, namespace, clean['kind'], clean['title'], canonical(clean['payload']),
                 canonical(clean['sources']), task_id, actor, confidence, revision, content_hash, created, now()))
            self.db.execute("UPDATE memory_records SET category=?,date_collected=?,expiry_policy=?,responsible_department=?,verification_status='UNVERIFIED',last_verified_at=NULL,next_review_at=?,superseded_by=NULL WHERE id=?",
                (category, now(), canonical(policy), NAMESPACE_OWNERS.get(namespace,'agent-development' if namespace=='research' else namespace),
                 (datetime.now(timezone.utc)+timedelta(seconds=policy['ttl_seconds'])).isoformat(),record_id))
            self._history(dict(self.db.execute('SELECT * FROM memory_records WHERE id=?',(record_id,)).fetchone()),actor,'content recorded; verification required')
        return self.get(record_id, actor)

    def _history(self, record, actor, reason):
        self.db.execute('INSERT OR IGNORE INTO memory_history VALUES(?,?,?,?,?,?)',
            (record['id'],record['revision'],canonical(record),actor,reason,now()))

    def history(self, record_id, actor):
        self.get(record_id,actor)
        return [dict(r,snapshot=json.loads(r['snapshot'])) for r in self.db.execute('SELECT * FROM memory_history WHERE record_id=? ORDER BY revision',(record_id,))]

    def search(self, query, actor, namespace=None, limit=20, include_superseded=False):
        required(query, 'Memory query')
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError('Memory result limit must be 1..100')
        if namespace:
            authorize(actor, namespace)
        records = []
        for row in self.db.execute('SELECT * FROM memory_records ORDER BY updated_at DESC,id'):
            if row['superseded_by'] and not include_superseded:continue
            if namespace and row['namespace'] != namespace:
                continue
            try:
                authorize(actor, row['namespace'])
            except PermissionError:
                continue
            words = query.lower().split()
            if any(word in (row['title'] + ' ' + row['payload']).lower() for word in words):
                records.append(self.get(row['id'], actor))
            if len(records) >= limit:
                break
        return records

    def export(self, actor, namespaces=None):
        selected = set(namespaces) if namespaces is not None else NAMESPACES
        records = []
        accessible = set()
        for namespace in selected:
            try:
                authorize(actor, namespace)
            except PermissionError:
                if namespaces is not None:
                    raise
                continue
            accessible.add(namespace)
        for row in self.db.execute('SELECT id,namespace FROM memory_records ORDER BY id'):
            if row['namespace'] in accessible:
                records.append(self.get(row['id'], actor))
        return {'format': 'memory-vault-v1', 'exported_at': now(),
                'source_instance': self.db.execute("SELECT value FROM memory_metadata WHERE key='source_instance'").fetchone()[0],
                'records': redact(records)}

    def import_records(self, document, actor):
        if not isinstance(document, dict) or document.get('format') != 'memory-vault-v1' or not isinstance(document.get('records'), list):
            raise ValueError('Unsupported memory import format')
        results = []
        with self.db:
            for record in document['records']:
                if not isinstance(record, dict):
                    raise ValueError('Malformed memory import record')
                task_id = record.get('task_id')
                payload = record['payload']
                source_instance = record.get('source_instance', document.get('source_instance'))
                local_instance = self.db.execute("SELECT value FROM memory_metadata WHERE key='source_instance'").fetchone()[0]
                if task_id is not None and (source_instance != local_instance or not self.db.execute('SELECT 1 FROM tasks WHERE id=?', (task_id,)).fetchone()):
                    payload = {'imported_payload': payload, 'import_provenance': {
                        'origin_task_id': task_id, 'origin_instance': source_instance}}
                    task_id = None
                results.append(self.put(record['namespace'], record['kind'], record['title'],
                    payload, actor, sources=record['sources'], task_id=task_id,
                    confidence=record['confidence'], record_id=record['id'], commit=False,category=record.get('category','research')))
        return results

    def enqueue(self, record_id, provider, actor):
        record = self.get(record_id, actor)
        required(provider, 'Provider name')
        with self.db:
            self.db.execute('''INSERT OR IGNORE INTO memory_sync_queue
                (provider,record_id,revision,status,next_at) VALUES(?,?,?,'PENDING',?)''',
                (provider, record_id, record['revision'], now()))
        return {'record_id': record_id, 'provider': provider, 'revision': record['revision']}

    def sync(self, provider, actor, limit=20):
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError('Sync limit must be 1..100')
        rows = self.db.execute('''SELECT * FROM memory_sync_queue WHERE provider=?
            AND status IN ('PENDING','RETRY') AND next_at<=? ORDER BY id LIMIT ?''',
            (provider.name, now(), limit)).fetchall()
        outcomes = []
        for row in rows:
            # Authorization failures do not consume or modify another namespace's queue.
            record = self.get(row['record_id'], actor)
            if record['revision'] != row['revision']:
                with self.db:
                    self.db.execute("UPDATE memory_sync_queue SET status='SUPERSEDED' WHERE id=?", (row['id'],))
                self.enqueue(record['id'], provider.name, actor)
                continue
            state = self.db.execute('SELECT * FROM memory_sync_state WHERE provider=? AND record_id=?',
                                    (provider.name, record['id'])).fetchone()
            try:
                remote_hash = provider.write(record, state['remote_hash'] if state else None)
                with self.db:
                    self.db.execute('INSERT OR REPLACE INTO memory_sync_state VALUES(?,?,?,?)',
                                    (provider.name, record['id'], remote_hash, record['revision']))
                    self.db.execute("UPDATE memory_sync_queue SET status='DONE',error=NULL WHERE id=?", (row['id'],))
                outcomes.append({'id': record['id'], 'status': 'DONE'})
            except (OSError, ValueError, RuntimeError) as exc:
                attempts = row['attempts'] + 1
                status = 'CONFLICT' if isinstance(exc, ConflictError) else 'FAILED' if attempts >= 5 else 'RETRY'
                next_at = (datetime.now(timezone.utc) + timedelta(seconds=min(300, 2 ** attempts))).isoformat()
                with self.db:
                    self.db.execute('UPDATE memory_sync_queue SET status=?,attempts=?,next_at=?,error=? WHERE id=?',
                        (status, attempts, next_at, str(redact(str(exc)))[:500], row['id']))
                outcomes.append({'id': record['id'], 'status': status})
        return outcomes

    def retry(self, queue_id, actor, resolution):
        required(resolution, 'Retry diagnosis/resolution')
        row = self.db.execute('SELECT * FROM memory_sync_queue WHERE id=?', (queue_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown sync queue item')
        self.get(row['record_id'], actor)
        if row['status'] not in {'RETRY', 'FAILED', 'CONFLICT'}:
            raise ValueError('Only failed, retry or conflict items can be retried')
        # Keep the old remote hash: retry never silently overwrites an external edit.
        with self.db:
            self.db.execute("UPDATE memory_sync_queue SET status='PENDING',attempts=0,next_at=?,error=? WHERE id=?",
                            (now(), redact(resolution), queue_id))

    def resolve_conflict(self, queue_id, provider, actor, expected_remote_hash, evidence):
        """Explicitly acknowledge inspected remote bytes before a keep-local overwrite.

        To keep remote content, first review it and update SQLite through put with
        expected_revision. This operation never imports notes as trusted authority.
        """
        required(evidence, 'Conflict diagnosis and explicit keep-local resolution')
        required(expected_remote_hash, 'Observed remote hash, or MISSING')
        row = self.db.execute('SELECT * FROM memory_sync_queue WHERE id=?', (queue_id,)).fetchone()
        if row is None or row['status'] != 'CONFLICT' or row['provider'] != provider.name:
            raise ValueError('Expected a matching conflicted queue item')
        record = self.get(row['record_id'], actor)
        authorize(actor, record['namespace'], write=True)
        current = provider.current_hash(record) or 'MISSING'
        if current != expected_remote_hash:
            raise ConflictError('Remote bytes changed since inspection; inspect again')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO memory_sync_state VALUES(?,?,?,?)',
                            (provider.name, record['id'], current, record['revision']))
            self.db.execute('INSERT INTO memory_sync_resolutions(queue_id,actor,evidence,acknowledged_remote_hash,local_revision,at) VALUES(?,?,?,?,?,?)',
                (queue_id, actor, redact(evidence), current, record['revision'], now()))
            if record['revision'] == row['revision']:
                self.db.execute("UPDATE memory_sync_queue SET status='PENDING',attempts=0,next_at=?,error=NULL WHERE id=?", (now(), queue_id))
            else:
                self.db.execute("UPDATE memory_sync_queue SET status='SUPERSEDED' WHERE id=?", (queue_id,))
                self.db.execute('''INSERT OR IGNORE INTO memory_sync_queue
                    (provider,record_id,revision,status,next_at) VALUES(?,?,?,'PENDING',?)''',
                    (provider.name, record['id'], record['revision'], now()))
        return {'resolved_queue_id': queue_id, 'record_id': record['id'], 'strategy': 'explicit-keep-local', 'next_status': 'PENDING'}
