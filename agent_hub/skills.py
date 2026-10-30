"""Central skill inventory, guarded activation and task usage. No installers run here."""
import hashlib
import json
import re
from pathlib import Path

from .legacy import now, required
from .roles import ROLES, DOMAINS
from .security import canonical, safe_file, redact

ACTIVE = {'BASELINE_REVIEWED', 'VALIDATED'}


def skill_fingerprint(root, instruction):
    instruction = safe_file(root, instruction)
    files = {}
    for path in sorted(instruction.parent.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            if not path.resolve().is_relative_to(Path(root).resolve()):
                raise ValueError('Skill references an external symlink')
            files[path.relative_to(instruction.parent).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(canonical(files).encode()).hexdigest()


class SkillRegistry:
    def __init__(self, connection, root):
        self.db, self.root = connection, Path(root).resolve()
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS skill_registry (
          id TEXT PRIMARY KEY, record TEXT NOT NULL, fingerprint TEXT NOT NULL,
          security_status TEXT NOT NULL, validated_at TEXT);
        CREATE TABLE IF NOT EXISTS skill_usage (
          task_id INTEGER NOT NULL REFERENCES tasks(id), skill_id TEXT NOT NULL REFERENCES skill_registry(id),
          handoff_id INTEGER NOT NULL REFERENCES events(id), selected_at TEXT NOT NULL,
          used_at TEXT, PRIMARY KEY(task_id,skill_id,handoff_id));
        ''')
        seed = self.root / 'registry/skills.json'
        if seed.is_file():
            document = json.loads(seed.read_text())
            with self.db:
                for record in document['skills']:
                    self._validate_shape(record,allow_missing=True)
                    try:
                        current = skill_fingerprint(self.root, record['path'])
                        status = record['security_status'] if current == record['fingerprint'] else 'QUARANTINED'
                    except (ValueError,OSError):
                        current=record['fingerprint'];status='QUARANTINED'
                    self.db.execute('INSERT OR IGNORE INTO skill_registry VALUES(?,?,?,?,?)',
                        (record['id'], canonical(record), current, status, record.get('last_validation_date')))

    def _validate_shape(self, record, allow_missing=False):
        for key in ['id', 'name', 'version', 'description', 'path', 'source', 'fingerprint']:
            required(record.get(key), 'Skill ' + key)
        for key in ['supported_agents', 'supported_departments', 'dependencies', 'permissions', 'test_results']:
            if not isinstance(record.get(key), list):
                raise ValueError('Skill metadata list missing: ' + key)
        if not re.fullmatch(r'[a-z][a-z0-9-]{1,100}', record['id']):
            raise ValueError('Invalid skill ID')
        path=self.root/record['path']
        if Path(record['path']).is_absolute() or not path.resolve().is_relative_to(self.root):raise ValueError('Unsafe skill path')
        if not allow_missing or path.exists():safe_file(self.root, record['path'])

    def get(self, skill_id):
        row = self.db.execute('SELECT * FROM skill_registry WHERE id=?', (skill_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown registered skill: ' + skill_id)
        record = json.loads(row['record'])
        record.update(security_status=row['security_status'], fingerprint=row['fingerprint'],
                      last_validation_date=row['validated_at'])
        try:current = skill_fingerprint(self.root, record['path'])
        except (ValueError,OSError):
            record['security_status']='QUARANTINED';record['validation_error']='Skill files unavailable or unsafe'
            return record
        if current != row['fingerprint']:
            record['security_status'] = 'QUARANTINED'
            record['validation_error'] = 'Skill bytes changed since review'
        return record

    def list(self):
        return [self.get(row[0]) for row in self.db.execute('SELECT id FROM skill_registry ORDER BY id')]

    def search(self, query, department=None):
        required(query, 'Skill query')
        words = set(re.findall(r'[a-z0-9]+', query.lower()))
        candidates = []
        for record in self.list():
            if record['security_status'] not in ACTIVE:
                continue
            if department and department not in record['supported_departments']:
                continue
            tokens = set(re.findall(r'[a-z0-9]+', (record['name'] + ' ' + record['description']).lower()))
            score = len(words & tokens)
            if score:
                candidates.append(dict(record, relevance=score))
        return sorted(candidates, key=lambda r: (-r['relevance'], r['id']))

    def require(self, skill_ids, owner):
        if owner not in ROLES or not isinstance(skill_ids, list) or not skill_ids or any(not isinstance(s, str) for s in skill_ids) or len(set(skill_ids)) != len(skill_ids):
            raise ValueError('Select a nonempty unique list of registered skills for a known agent')
        records = []
        for skill_id in skill_ids:
            record = self.get(skill_id)
            if record['security_status'] not in ACTIVE:
                raise ValueError('Unvalidated or changed skill cannot execute: ' + skill_id)
            if ROLES[owner][0] not in record['supported_departments']:
                raise ValueError('Skill is not validated for this department')
            if record['supported_agents'] and owner not in record['supported_agents']:
                raise ValueError('Skill is not validated for this agent')
            records.append(record)
        return records

    def register_candidate(self, record, actor):
        if actor != 'agent-creator-researcher':
            raise PermissionError('Agent Development & Research must register candidates')
        self._validate_shape(record)
        if not record['path'].startswith('work/skill-candidates/'):
            raise ValueError('Stage unreviewed candidates under work/skill-candidates, outside native .claude discovery')
        # Caller-supplied popularity, security verdicts and test results are not activation.
        record = redact(dict(record, security_status='QUARANTINED', test_results=[], last_validation_date=None))
        fingerprint = skill_fingerprint(self.root, record['path'])
        record['fingerprint'] = fingerprint
        with self.db:
            self.db.execute('INSERT INTO skill_registry VALUES(?,?,?,?,?)',
                            (record['id'], canonical(record), fingerprint, 'QUARANTINED', None))
        return self.get(record['id'])

    def activate(self, skill_id, reviewer, author, authorization, tests, review_notes):
        record = self.get(skill_id)
        if reviewer != 'qa-auditor' or reviewer == author or author != 'agent-creator-researcher':
            raise ValueError('Independent QA of the Research candidate is required')
        required(authorization, 'Scoped activation authorization reference')
        required(review_notes, 'Compatibility, dependency, permission, license and security review notes')
        if not isinstance(tests, list) or not tests or any(not isinstance(t, dict) or t.get('result') != 'PASS' or not t.get('reference') for t in tests):
            raise ValueError('Passing candidate test evidence required')
        fingerprint = skill_fingerprint(self.root, record['path'])
        if fingerprint != record['fingerprint']:
            raise ValueError('Candidate changed after registration; register a new version for review')
        record.update(security_status='VALIDATED', last_validation_date=now(), test_results=tests,
                      activation=redact({'author': author, 'reviewer': reviewer, 'authorization_reference': authorization,
                                         'notes': review_notes, 'identity_authenticated': False}))
        with self.db:
            self.db.execute('UPDATE skill_registry SET record=?,security_status=?,validated_at=? WHERE id=?',
                            (canonical(record), 'VALIDATED', record['last_validation_date'], skill_id))
        return self.get(skill_id)

    def usage(self, skill_id):
        self.get(skill_id)
        return [dict(r) for r in self.db.execute('SELECT * FROM skill_usage WHERE skill_id=? ORDER BY task_id,handoff_id', (skill_id,))]


    def baseline_diff(self):
        document=json.loads((self.root/'registry/skills.json').read_text())
        changes=[]
        for seed in document['skills']:
            self._validate_shape(seed)
            if seed['path'].startswith('work/') or skill_fingerprint(self.root,seed['path'])!=seed['fingerprint']:raise ValueError('Reviewed baseline source is missing, changed or outside native baseline scope')
            row=self.db.execute('SELECT * FROM skill_registry WHERE id=?',(seed['id'],)).fetchone()
            if row is None:continue
            old=json.loads(row['record'])
            if old!=seed or row['fingerprint']!=seed['fingerprint'] or row['security_status']!=seed['security_status']:
                changes.append({'id':seed['id'],'old_record':old,'new_record':seed,
                    'old_fingerprint':row['fingerprint'],'new_fingerprint':seed['fingerprint'],
                    'capability_expansion':any(old.get(k)!=seed.get(k) for k in ['supported_agents','supported_departments','permissions','dependencies'])})
        return {'changes':changes,'diff_hash':hashlib.sha256(canonical(changes).encode()).hexdigest(),
            'source':'Current reviewed registry seed and matching on-disk bytes; raw/user candidates excluded.'}

    def reconcile_baseline(self,reviewer,author,review_reference,authorization_reference,tests,expected_diff_hash,allow_capability_expansion=False):
        import uuid
        from .usage import atomic
        if reviewer!='qa-auditor' or author!='agent-creator-researcher' or reviewer==author:raise ValueError('A separate Research author and independent QA reviewer are required')
        required(review_reference,'Actual independent baseline review reference');required(authorization_reference,'Actual scoped baseline authorization')
        if not isinstance(tests,list) or not tests or any(not isinstance(t,dict) or t.get('result')!='PASS' or not t.get('reference') for t in tests):raise ValueError('Actual passing compatibility/security test references are required')
        with atomic(self.db):
            if self.db.execute("SELECT 1 FROM tasks WHERE phase NOT IN ('COMPLETED','CANCELLED') AND migration_hold=0 LIMIT 1").fetchone():raise ValueError('Finish/cancel current work; only migration-held tasks may remain during baseline reconciliation')
            if self.db.execute("SELECT 1 FROM maintenance_runs WHERE status='RUNNING' LIMIT 1").fetchone():raise ValueError('Stop active maintenance first')
            diff=self.baseline_diff()
            if expected_diff_hash!=diff['diff_hash']:raise ValueError('Baseline diff changed after review; inspect it again')
            if any(c['capability_expansion'] for c in diff['changes']) and allow_capability_expansion is not True:raise PermissionError('Explicit scoped capability/dependency expansion authorization is required')
            for change in diff['changes']:
                seed=change['new_record']
                self.db.execute('INSERT INTO skill_baseline_revisions VALUES(?,?,?,?,?,?,?,?)',
                    (str(uuid.uuid4()),seed['id'],canonical(change['old_record']),canonical(seed),redact(review_reference),redact(authorization_reference),diff['diff_hash'],now()))
                self.db.execute('UPDATE skill_registry SET record=?,fingerprint=?,security_status=?,validated_at=? WHERE id=?',
                    (canonical(seed),seed['fingerprint'],seed['security_status'],now(),seed['id']))
        return {'updated':[c['id'] for c in diff['changes']],'diff_hash':diff['diff_hash'],'identity_authenticated':False,'candidate_activation':False}
