"""Optional local runner: fixed deterministic handlers or queued Claude Code review requests."""
import calendar
import json
import uuid
from datetime import timedelta

from .legacy import now, required
from .usage import atomic, instant
from .security import canonical, redact
from .roles import DOMAINS

PRINCIPAL='SERVICE:local-maintenance'
KINDS={'health':'LOCAL_CHECK','freshness':'LOCAL_CHECK','scorecards':'LOCAL_CHECK','capability-review':'AI_REQUEST','architecture-review':'AI_REQUEST'}
DEFAULTS=[('daily-health','health','daily'),('weekly-health','health','weekly'),
          ('monthly-capability','capability-review','monthly'),('quarterly-architecture','architecture-review','quarterly'),
          ('daily-freshness','freshness','daily'),('weekly-scorecards','scorecards','weekly')]


def next_due(at,cadence,interval_seconds=None):
    at=instant(at)
    if cadence=='interval':return at+timedelta(seconds=interval_seconds)
    if cadence in {'daily','weekly'}:return at+timedelta(days=1 if cadence=='daily' else 7)
    months=1 if cadence=='monthly' else 3
    month=at.month-1+months;year=at.year+month//12;month=month%12+1
    return at.replace(year=year,month=month,day=min(at.day,calendar.monthrange(year,month)[1]))


class Scheduler:
    def __init__(self,hub,clock=None):
        self.hub=hub;self.db=hub.db;self.clock=clock or (lambda:instant(now()))
    def seed(self):
        with self.db:
            for identity,kind,cadence in DEFAULTS:
                self.db.execute('INSERT OR IGNORE INTO maintenance_jobs VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (identity,kind,cadence,None,0,self.clock().isoformat(),PRINCIPAL,0,3,'{}'))
        return self.jobs()
    def jobs(self):return [dict(r) for r in self.db.execute('SELECT * FROM maintenance_jobs ORDER BY id')]
    def configure(self,identity,enabled=False,cadence=None,interval_seconds=None,departments=None,principal=PRINCIPAL):
        if principal!=PRINCIPAL:raise PermissionError('Only the fixed local maintenance service identity is allowed')
        row=self.db.execute('SELECT * FROM maintenance_jobs WHERE id=?',(identity,)).fetchone()
        if row is None:raise ValueError('Unknown fixed maintenance job')
        if type(enabled) is not bool:raise ValueError('enabled must be boolean')
        cadence=cadence or row['cadence']
        if cadence not in {'daily','weekly','monthly','quarterly','interval'}:raise ValueError('Unknown cadence')
        if cadence=='interval' and (type(interval_seconds) is not int or interval_seconds<60):raise ValueError('Maintenance intervals must be at least 60 seconds')
        departments=list(DOMAINS) if departments is None else departments
        if not isinstance(departments,list) or any(d not in DOMAINS for d in departments):raise ValueError('Unknown maintenance department')
        with self.db:self.db.execute('UPDATE maintenance_jobs SET enabled=?,cadence=?,interval_seconds=?,principal=?,failures=0,config=? WHERE id=?',
            (int(enabled),cadence,interval_seconds,principal,canonical({'departments':departments}),identity))
        return dict(self.db.execute('SELECT * FROM maintenance_jobs WHERE id=?',(identity,)).fetchone())
    def recover(self):
        recovered=[];at=self.clock()
        with atomic(self.db):
            for row in self.db.execute("SELECT * FROM maintenance_runs WHERE status='RUNNING' AND lease_until<=?",(at.isoformat(),)).fetchall():
                job=self.db.execute('SELECT * FROM maintenance_jobs WHERE id=?',(row['job_id'],)).fetchone()
                failures=job['failures']+1
                self.db.execute("UPDATE maintenance_runs SET status='INTERRUPTED',finished_at=?,error=? WHERE id=?",(at.isoformat(),'Lease expired; process completion unknown. Idempotent request keys prevent duplicate AI requests.',row['id']))
                self.db.execute('UPDATE maintenance_jobs SET failures=?,enabled=?,due_at=? WHERE id=?',
                    (failures,job['enabled'] if failures<job['max_attempts'] else 0,(at+timedelta(seconds=min(3600,60*2**failures))).isoformat(),job['id']))
                recovered.append(row['id'])
        return recovered
    def claim(self,identity,worker_id):
        required(worker_id,'Worker identity');at=self.clock()
        with atomic(self.db):
            if self.db.execute("SELECT 1 FROM change_proposals WHERE status IN ('ACTIVATING','ROLLING_BACK') LIMIT 1").fetchone():return None
            row=self.db.execute('SELECT * FROM maintenance_jobs WHERE id=?',(identity,)).fetchone()
            if row is None or not row['enabled'] or instant(row['due_at'])>at:return None
            if row['principal']!=PRINCIPAL or row['kind'] not in KINDS:raise PermissionError('Unrecognized scheduler principal/handler')
            if self.db.execute("SELECT 1 FROM maintenance_runs WHERE job_id=? AND status='RUNNING'",(identity,)).fetchone():return None
            identity_run=str(uuid.uuid4())
            self.db.execute('INSERT INTO maintenance_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (identity_run,identity,row['due_at'],worker_id,PRINCIPAL,KINDS[row['kind']],'RUNNING',at.isoformat(),
                 (at+timedelta(minutes=5)).isoformat(),None,None,None))
            return dict(row,run_id=identity_run)
    def handle(self,job):
        kind=job['kind'];config=json.loads(job['config'])
        if kind=='health':return [self.hub.health.audit(d,job['cadence'] if job['cadence']!='interval' else 'daily') for d in config.get('departments',list(DOMAINS))]
        if kind=='freshness':return self.hub.freshness.scan()
        if kind=='scorecards':
            from .monitoring import scorecards
            cards=scorecards(self.db)
            # Persist the observed cards in the run outcome; no model evaluation implied.
            return cards
        if kind in {'capability-review','architecture-review'}:
            # Run identity derives from job+original due slot. Recovery reuses request identity via unfinished run's key.
            key='maintenance:'+job['id']+':'+job['due_at']
            interrupted=self.db.execute("SELECT outcome FROM maintenance_runs WHERE job_id=? AND status='INTERRUPTED' ORDER BY started_at DESC LIMIT 1",(job['id'],)).fetchone()
            # A task is persisted atomically with its key, so a crashed handler can find its existing review request.
            pending=self.db.execute("SELECT * FROM tasks WHERE idempotency_key LIKE ? AND phase NOT IN ('COMPLETED','CANCELLED') ORDER BY id DESC LIMIT 1",('maintenance:'+job['id']+':%',)).fetchone()
            task=dict(pending) if pending else self.hub.create('Scheduled '+kind,
                'Research current evidence, scope candidate improvements, test in isolation and obtain independent QA before requesting activation.',
                agent='department-health-auditor',idempotency_key=key)
            return {'status':'QUEUED_FOR_AUTHENTICATED_RUNTIME','task_id':task['id'],'model_invoked':False,'paid_api_called':False}
        raise ValueError('No arbitrary scheduler commands are allowed')
    def tick(self):
        self.recover();results=[];worker='local-'+str(uuid.uuid4())
        for job in self.jobs():
            claim=self.claim(job['id'],worker)
            if claim is None:continue
            try:
                outcome=self.handle(claim);error=None;status='SUCCEEDED';failures=0
                due=next_due(self.clock(),claim['cadence'],claim['interval_seconds'])
            except Exception as exc:
                outcome=None;error=str(redact(str(exc)))[:1000];status='FAILED';failures=claim['failures']+1
                due=self.clock()+timedelta(seconds=min(3600,60*2**failures))
            with atomic(self.db):
                # A reclaimed lease cannot be completed by the old worker.
                current=self.db.execute('SELECT * FROM maintenance_runs WHERE id=?',(claim['run_id'],)).fetchone()
                if current['status']!='RUNNING' or current['worker_id']!=worker:continue
                self.db.execute('UPDATE maintenance_runs SET status=?,finished_at=?,outcome=?,error=? WHERE id=?',
                    (status,self.clock().isoformat(),canonical(redact(outcome)),error,claim['run_id']))
                self.db.execute('UPDATE maintenance_jobs SET failures=?,due_at=?,enabled=CASE WHEN ? >= max_attempts THEN 0 ELSE enabled END WHERE id=?',
                    (failures,due.isoformat(),failures,claim['id']))
            results.append({'run_id':claim['run_id'],'job_id':claim['id'],'status':status,'outcome':outcome,'error':error})
        return results
