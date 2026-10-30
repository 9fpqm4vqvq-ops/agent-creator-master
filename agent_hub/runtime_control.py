"""Operator-only recovery, capacity and run budget controls in the existing Vault."""
import json,uuid
from decimal import Decimal
from .legacy import now,required
from .security import canonical,redact
from .usage import atomic,amount

CONTROL_SCHEMA='''
CREATE TABLE IF NOT EXISTS runtime_policies (id TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
INSERT OR IGNORE INTO runtime_policies VALUES('concurrency_limit','1',CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS runtime_policy_history (id TEXT PRIMARY KEY,policy TEXT NOT NULL,value TEXT NOT NULL,reference TEXT NOT NULL,at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS execution_reconciliations (
 id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES agent_runs(id),invocation_id TEXT REFERENCES agent_invocations(id),
 outcome TEXT NOT NULL,reference TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);
'''

class CapacityPause(RuntimeError):pass

class RuntimeControl:
 def __init__(self,runtime):self.runtime=runtime;self.hub=runtime.hub;self.db=runtime.db
 def capacity(self,limit=None,authorization_reference=None):
  if limit is not None:
   if type(limit) is not int or not 1<=limit<=16:raise ValueError('Concurrency limit must be 1..16')
   required(authorization_reference,'Actual operator capacity authorization')
   with atomic(self.db):
    self.db.execute("UPDATE runtime_policies SET value=?,updated_at=? WHERE id='concurrency_limit'",(str(limit),now()))
    self.db.execute('INSERT INTO runtime_policy_history VALUES(?,?,?,?,?)',(str(uuid.uuid4()),'concurrency_limit',str(limit),redact(authorization_reference),now()))
  value=int(self.db.execute("SELECT value FROM runtime_policies WHERE id='concurrency_limit'").fetchone()[0])
  return {'limit':value,'claimed':self.db.execute('SELECT COUNT(*) FROM agent_runs WHERE worker_id IS NOT NULL').fetchone()[0],
    'policy':'Atomic shared writer claim; no lease-based stealing of live/remote owners'}
 def inspect(self,run_id):
  run=self.runtime.get(run_id);keys=[i['reservation_key'] for i in run['invocations']]
  holds=[dict(r) for r in self.db.execute('SELECT * FROM usage_reservations') if r['execution_key'] in keys]
  actions=[dict(r) for r in self.db.execute("SELECT * FROM external_actions WHERE task_id=? AND status IN ('STARTED','UNKNOWN_NEEDS_RECONCILIATION')",(run['task_id'],))]
  last=next(({'invocation_id':i['id'],'stage':i['stage'],'reference':i['reference'],'evidence_kind':i['evidence_kind']} for i in reversed(run['invocations']) if i['output'] is not None and i['reference']),None)
  return redact({'run':run,'last_verified_provider_receipt':last,'cost_reservations':holds,'uncertain_external_actions':actions,
   'reconciliations':[dict(r) for r in self.db.execute('SELECT * FROM execution_reconciliations WHERE run_id=? ORDER BY created_at',(run_id,))],
   'capacity':self.capacity(),'run_budget':self.run_budget(run_id)})
 def run_budget(self,run_id,projected_cost=None):
  run=self.runtime.get(run_id);config=json.loads(run['config']);limit=config.get('run_budget_usd')
  keys=[i['reservation_key'] for i in run['invocations']]
  usage=[dict(r) for r in self.db.execute('SELECT * FROM usage_events') if r['execution_key'] in keys]
  holds=[dict(r) for r in self.db.execute("SELECT * FROM usage_reservations WHERE state IN ('ACTIVE','AWAITING_TELEMETRY')") if r['execution_key'] in keys]
  spent=sum((Decimal(r['actual_cost'] if r['actual_cost'] is not None else r['estimated_cost']) for r in usage if r['actual_cost'] is not None or r['estimated_cost'] is not None),Decimal(0))
  # A priced event and its unresolved hold represent one invocation, not two charges.
  priced={r['execution_key'] for r in usage if r['actual_cost'] is not None or r['estimated_cost'] is not None}
  holds=[r for r in holds if r['execution_key'] not in priced]
  held=sum((Decimal(r['amount_usd']) for r in holds if r['amount_usd'] is not None),Decimal(0))
  unknown=any(r['actual_cost'] is None and r['estimated_cost'] is None for r in usage) or any(r['amount_usd'] is None for r in holds)
  projected=amount(projected_cost,allow_none=True)
  status='UNCONFIGURED' if limit is None else 'UNKNOWN' if unknown or projected is None else 'EXCEEDED' if spent+held+projected>amount(limit) else 'WITHIN_LIMIT'
  return {'limit_usd':limit,'recorded_usd':str(spent),'held_usd':str(held),'projected_usd':str(projected) if projected is not None else None,
   'status':status,'allowed':limit is None or status=='WITHIN_LIMIT','actual_billing':'UNKNOWN unless separately reported'}
 def set_run_budget(self,run_id,limit_usd,authorization_reference):
  required(authorization_reference,'Actual run budget authorization');limit=amount(limit_usd)
  run=self.runtime.get(run_id);config=json.loads(run['config']);config['run_budget_usd']=str(limit)
  with atomic(self.db):
   self.db.execute('UPDATE agent_runs SET config=?,updated_at=? WHERE id=?',(canonical(config),now(),run_id))
   self.runtime._event(run_id,'RUN_BUDGET_CHANGED',{'limit_usd':str(limit),'reference':authorization_reference})
  return self.run_budget(run_id)
 def reconcile(self,run_id,invocation_id,outcome,reference,detail):
  required(reference,'Actual provider receipt/cost reconciliation reference');required(detail,'Diagnosis and remaining uncertainty')
  run=self.runtime.get(run_id)
  if run['worker_id']:raise ValueError('Stop/recover the worker before reconciliation')
  inv=next((i for i in run['invocations'] if i['id']==invocation_id),None)
  if inv is None:raise ValueError('Invocation does not belong to the run')
  if outcome not in {'CONFIRMED_NO_RESULT','RECEIPT_RECORDED','COST_UNKNOWN'}:raise ValueError('Unsupported reconciliation outcome')
  if outcome=='CONFIRMED_NO_RESULT' and inv['output'] is not None:raise ValueError('Saved output contradicts no-result diagnosis; preserve the receipt')
  if outcome=='RECEIPT_RECORDED' and (not inv['reference'] or inv['output'] is None):raise ValueError('No saved provider receipt exists; operator text cannot fabricate one')
  identity=str(uuid.uuid4())
  with atomic(self.db):
   self.db.execute('INSERT INTO execution_reconciliations VALUES(?,?,?,?,?,?,?)',(identity,run_id,invocation_id,outcome,redact(reference),redact(detail),now()))
   self.runtime._event(run_id,'RECONCILIATION',{'id':identity,'outcome':outcome,'cost_holds':'retained'})
  return {'id':identity,'outcome':outcome,'cost_holds_released':False,'automatic_replay':False}
 def replacement(self,run_id,authorization_reference,diagnosis):
  required(authorization_reference,'Actual replacement task authorization');required(diagnosis,'Reconciliation diagnosis')
  # Eligibility, intent creation and permanent supersession share one writer lock.
  with atomic(self.db):
   report=self.inspect(run_id);run=report['run']
   if run['status']=='REPLACED':
    existing=self.db.execute('SELECT id FROM tasks WHERE idempotency_key=?',('replacement:'+run_id,)).fetchone()
    if existing:return self.hub.task(existing['id'])
    raise ValueError('Replacement linkage needs operator reconciliation')
   if run['worker_id'] or run['status'] not in {'BLOCKED','FAILED','CANCELLED'}:raise ValueError('Replacement requires a stopped run with no owner')
   if run['task']['phase']=='COMPLETED':raise ValueError('Completed work does not need a replacement execution')
   if report['uncertain_external_actions']:raise ValueError('Reconcile uncertain external actions through connector controls first')
   if self.db.execute("SELECT 1 FROM tool_processes WHERE run_id=? AND status IN ('RUNNING','CLEANUP_REQUIRED')",(run_id,)).fetchone():raise ValueError('Process/container cleanup is unresolved')
   unresolved=[i for i in run['invocations'] if i['status'] in {'FAILED','INTERRUPTED','RUNNING','WAITING_FOR_TOOL'}]
   for inv in unresolved:
    if not self.db.execute('SELECT 1 FROM execution_reconciliations WHERE run_id=? AND invocation_id=?',(run_id,inv['id'])).fetchone():raise ValueError('Reconcile every uncertain provider invocation before replacement')
   task=run['task']
   replacement=self.hub.create(task['request'],task['criteria'],agent=task['requested_owner'],project_id=task['project_id'],
    owner_locked=bool(task['requested_owner']),idempotency_key='replacement:'+run_id)
   if task['phase']!='CANCELLED':self.hub.cancel(task['id'],'Superseded by authorized replacement task '+str(replacement['id']))
   self.db.execute("UPDATE agent_runs SET status='REPLACED',last_step=?,updated_at=? WHERE id=?",('Replacement task '+str(replacement['id']),now(),run_id))
   self.runtime._event(run_id,'REPLACEMENT_CREATED',{'task_id':replacement['id'],'authorization_reference':authorization_reference,'diagnosis':diagnosis,'old_cost_holds':'retained'})
   return replacement
