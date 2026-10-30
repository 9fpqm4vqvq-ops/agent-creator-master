"""Age policy and evidence-linked knowledge review; historical records are never deleted."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from .legacy import now, required
from .memory import authorize
from .security import canonical
from .usage import instant, atomic

POLICIES = {
    'supplier_price':86400, 'market_price':86400, 'payment_service':604800,
    'framework_version':604800,'social_trend':259200,'connector_permission':86400,
    'assumption':2592000, 'procedure':15552000, 'research':2592000,
}


def policy_for(category,root=None):
    if category not in POLICIES:raise ValueError('Unknown knowledge category')
    ttl=POLICIES[category]
    if root is not None:
        from pathlib import Path
        path=Path(root)/'registry/freshness-policies.json'
        if path.is_file():
            config=json.loads(path.read_text());ttl=config.get('ttl_seconds',{}).get(category,ttl)
            if type(ttl) is not int or not 60<=ttl<=31536000:raise ValueError('Knowledge TTL must be 60 seconds to one year')
    return {'category':category,'ttl_seconds':ttl,'version':'0.4.0',
            'meaning':'maximum age after independent source verification; never proof of truth'}


def approved_task(hub, task_id, field, identity, required_author=None):
    task=hub.task(task_id)
    if task['phase']!='COMPLETED' or task['migration_hold']:raise ValueError('A completed independent QA task is required')
    hub.check_deliverables(task)
    result=json.loads(task['result'])
    if identity not in result.get(field,[]):raise ValueError('QA task did not assess this exact record/proposal')
    if required_author and required_author not in result.get('authors',[]):raise ValueError('QA task must include the responsible auditor as an author')
    records=[e for e in hub.history(task_id) if e['kind']=='QA_RECORD' and e['detail']['verdict']=='PASS']
    if not records:raise ValueError('Actual recorded independent QA PASS is required')
    return result, records[-1]


class FreshnessAuditor:
    actor='knowledge-freshness-auditor'
    def __init__(self,hub):self.hub=hub;self.db=hub.db

    def _metadata(self,record,updates,reason):
        self.hub.memory._history(record,self.actor,'before '+reason)
        values=dict(updates,revision=record['revision']+1,updated_at=now())
        self.db.execute('UPDATE memory_records SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),record['id']))
        updated=dict(self.db.execute('SELECT * FROM memory_records WHERE id=?',(record['id'],)).fetchone())
        self.hub.memory._history(updated,self.actor,reason)
        return updated

    def scan(self,at=None,queue=False):
        at=instant(at or now());findings=[];groups={}
        with atomic(self.db):
            for row in self.db.execute('SELECT * FROM memory_records ORDER BY id').fetchall():
                record=dict(row)
                if record['superseded_by']:continue
                due=instant(record['next_review_at']) if record['next_review_at'] else instant(record['date_collected'])+timedelta(seconds=policy_for(record['category'],self.hub.root)['ttl_seconds'])
                expired=due<=at
                if expired or record['verification_status'] not in {'FRESH'}:
                    findings.append({'record_id':record['id'],'revision':record['revision'],
                        'status':'STALE' if expired else 'REQUIRES_VERIFICATION','due_at':due.isoformat()})
                if expired and record['verification_status']!='REQUIRES_VERIFICATION':
                    record=self._metadata(record,{'verification_status':'REQUIRES_VERIFICATION','next_review_at':due.isoformat()},'age review due')
                key=(record['namespace'],record['title'].casefold())
                groups.setdefault(key,[]).append(record)
            for records in groups.values():
                if len(records)>1:
                    payloads={r['payload'] for r in records}
                    findings.append({'status':'POTENTIAL_CONFLICT' if len(payloads)>1 else 'POTENTIAL_DUPLICATE',
                                     'record_ids':[r['id'] for r in records], 'note':'Requires research; title similarity alone is not a factual contradiction.'})
            identity=str(uuid.uuid4())
            self.db.execute('INSERT INTO freshness_audits VALUES(?,?,?,?)',(identity,self.actor,at.isoformat(),canonical(findings)))
        if queue:
            for finding in findings:
                if 'record_id' in finding:finding['refresh_task_id']=self.queue(finding['record_id'])
        return {'id':identity,'at':at.isoformat(),'findings':findings,'deleted':0}

    def queue(self,record_id):
        record=self.hub.memory.get(record_id,self.actor)
        with atomic(self.db):
            prior=self.db.execute('SELECT task_id FROM freshness_requests WHERE record_id=? AND revision=?',(record_id,record['revision'])).fetchone()
            if prior:return prior[0]
            task=self.hub.create('Verify knowledge: '+record['title'],
                'Verify dated sources for memory '+record_id+' hash '+record['content_hash']+'; record limitations and obtain independent QA.',
                agent=self.actor,idempotency_key='freshness:'+record_id+':'+str(record['revision']))
            self.db.execute('INSERT INTO freshness_requests VALUES(?,?,?)',(record_id,record['revision'],task['id']))
            return task['id']

    def verify(self,record_id,qa_task_id):
        record=self.hub.memory.get(record_id,self.actor)
        result,qa=approved_task(self.hub,qa_task_id,'verified_memory_ids',record_id,self.actor)
        if result.get('memory_record_hashes',{}).get(record_id)!=record['content_hash']:raise ValueError('Reviewed knowledge bytes changed')
        if qa['detail']['evidence']['checks']['source_freshness']['verdict']!='PASS':raise ValueError('Source freshness must explicitly pass')
        dates=[instant(s['checked_at']) for s in result['sources'] if s['classification']=='VERIFIED']
        if not dates:raise ValueError('Verified dated source evidence is required')
        # Linking an old QA task cannot make old source checks fresh today.
        verified=min(instant(qa['at']),min(dates));policy=policy_for(record['category'],self.hub.root)
        due=verified+timedelta(seconds=policy['ttl_seconds'])
        state='FRESH' if due>instant(now()) else 'REQUIRES_VERIFICATION'
        with atomic(self.db):
            self._metadata(record,{'last_verified_at':verified.isoformat(),'next_review_at':due.isoformat(),
                'expiry_policy':canonical(policy),'verification_status':state},'independent verification task '+str(qa_task_id))
        return self.hub.memory.get(record_id,self.actor)

    def supersede(self,record_id,replacement_id,qa_task_id):
        if record_id==replacement_id:raise ValueError('A record cannot supersede itself')
        old=self.hub.memory.get(record_id,self.actor);replacement=self.hub.memory.get(replacement_id,self.actor)
        approved_task(self.hub,qa_task_id,'superseded_memory_ids',record_id,self.actor)
        result=json.loads(self.hub.task(qa_task_id)['result'])
        if result.get('supersession',{}).get(record_id)!=replacement_id:raise ValueError('QA did not approve this exact replacement')
        if old['superseded_by'] or old['namespace']!=replacement['namespace'] or replacement['superseded_by']:raise ValueError('Invalid namespace or supersession chain')
        if replacement['verification_status']!='FRESH' or instant(replacement['next_review_at'])<=instant(now()):raise ValueError('Replacement must have fresh independently verified evidence')
        if result.get('memory_record_hashes',{}).get(replacement_id)!=replacement['content_hash'] or result.get('memory_record_hashes',{}).get(record_id)!=old['content_hash']:raise ValueError('Reviewed memory bytes changed')
        with atomic(self.db):self._metadata(old,{'superseded_by':replacement_id,'verification_status':'SUPERSEDED'},'QA-approved supersession '+str(qa_task_id))
        return self.hub.memory.get(record_id,self.actor)


class ResearchCache:
    """Task-scoped source references, never substitute a cache hit for source verification."""
    def __init__(self,hub):self.hub=hub;self.db=hub.db
    def _key(self,query):
        required(query,'Research query')
        return hashlib.sha256(' '.join(query.casefold().split()).encode()).hexdigest()
    def record(self,task_id,query,source,references,ttl_seconds=3600):
        self.hub.task(task_id);required(source,'Search source')
        if type(ttl_seconds) is not int or not 1<=ttl_seconds<=86400:raise ValueError('Search TTL must be 1..86400 seconds')
        if not isinstance(references,list) or not references or any(not isinstance(r,str) or not r.strip() for r in references):raise ValueError('Dated research references are required')
        from .security import redact
        with self.db:self.db.execute('INSERT OR REPLACE INTO research_cache VALUES(?,?,?,?,?,?,?,?)',
            (task_id,self._key(query),source,redact(query),canonical(redact(references)),now(),
             (instant(now())+timedelta(seconds=ttl_seconds)).isoformat(),'UNVERIFIED_REFERENCES'))
        return self.lookup(task_id,query,source)
    def lookup(self,task_id,query,source):
        row=self.db.execute('SELECT * FROM research_cache WHERE task_id=? AND query_hash=? AND source=?',(task_id,self._key(query),source)).fetchone()
        return dict(row,usable=instant(row['expires_at'])>instant(now()),references=json.loads(row['references_json'])) if row else None
