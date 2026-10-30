"""AI resource evidence and conservative budget reservations; never trading capital."""
import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from .legacy import now, required
from .roles import ROLES, DOMAINS
from .security import canonical, redact

BAGHDAD = timezone(timedelta(hours=3), 'Asia/Baghdad')
TOKEN_FIELDS = ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens')


def instant(value):
    value = datetime.fromisoformat(value) if isinstance(value,str) else value
    if not isinstance(value,datetime) or value.tzinfo is None:
        raise ValueError('A timezone-aware timestamp is required')
    return value.astimezone(timezone.utc)


def amount(value, label='USD amount', allow_none=False):
    if value is None and allow_none:return None
    if isinstance(value,bool):raise ValueError(label+' must be numeric')
    try: value=Decimal(str(value))
    except (InvalidOperation,ValueError):raise ValueError('Invalid '+label) from None
    if not value.is_finite() or value<0:raise ValueError(label+' must be finite and nonnegative')
    return value


@contextmanager
def atomic(db):
    if db.in_transaction:
        yield
    else:
        with db:
            db.execute('BEGIN IMMEDIATE')
            yield


def estimate_cost(usage, rates):
    if not isinstance(usage,dict) or not isinstance(rates,dict) or type(rates.get('input_includes_cache')) is not bool:
        raise ValueError('Explicit provider cache-accounting semantics are required')
    required(rates.get('source'),'Rate-card provenance')
    if instant(rates.get('checked_at'))>datetime.now(timezone.utc):raise ValueError('Rate verification cannot be in the future')
    if rates.get('currency','USD')!='USD':raise ValueError('Rate estimates must explicitly use USD')
    for field in TOKEN_FIELDS:
        if type(usage.get(field)) is not int or usage[field]<0:
            raise ValueError('Every token count must be explicitly supplied for a pricing estimate')
    counts=dict(usage)
    if rates['input_includes_cache']:
        counts['input_tokens']-=counts['cache_read_tokens']+counts['cache_write_tokens']
        if counts['input_tokens']<0:raise ValueError('Cached tokens exceed inclusive input tokens')
    total=sum(Decimal(counts[f])*amount(rates.get(f+'_per_million'),'rate')/Decimal(1_000_000) for f in TOKEN_FIELDS)
    return {'estimated_cost':str(total),'currency':'USD','classification':'ESTIMATED',
            'rate_source':rates['source'],'rate_checked_at':rates['checked_at'],
            'note':'Not a provider charge; rate freshness and cache semantics require independent verification.'}


class UsageLedger:
    def __init__(self,db):self.db=db

    def record(self,entry,expected_revision=None):
        if not isinstance(entry,dict):raise ValueError('Usage record must be an object')
        entry=dict(entry)
        if type(entry.get('task_id')) is not int:raise ValueError('Usage task ID must be an integer')
        task=self.db.execute('SELECT * FROM tasks WHERE id=?',(entry.get('task_id'),)).fetchone()
        if task is None or entry.get('agent') not in ROLES:raise ValueError('Usage needs a known task and registered agent')
        for key in ['provider','model','invocation_id','source']:required(entry.get(key),'Usage '+key)
        if entry.get('currency','USD')!='USD':raise ValueError('AI execution ledger is USD only; investment balances are separate')
        kind=entry.get('token_kind','UNKNOWN')
        if kind not in {'MEASURED','ESTIMATED','UNKNOWN'}:raise ValueError('Unknown token evidence kind')
        for field in TOKEN_FIELDS:
            value=entry.get(field)
            if value is not None and (type(value) is not int or not 0<=value<2**63):raise ValueError('Token counts must be nonnegative integers or null')
            if kind=='UNKNOWN' and value is not None:raise ValueError('UNKNOWN token telemetry cannot contain claimed token counts')
            entry[field]=value
        if kind!='UNKNOWN' and all(entry[f] is None for f in TOKEN_FIELDS):raise ValueError('Measured/estimated token records need at least one count')
        for field in ['actual_cost','estimated_cost','duration_seconds']:
            value=amount(entry.get(field),field,allow_none=True);entry[field]=str(value) if value is not None else None
        existing=self.db.execute('SELECT collected_at FROM usage_events WHERE provider=? AND invocation_id=?',(entry['provider'],entry['invocation_id'])).fetchone()
        collected=instant(entry.get('collected_at',existing[0] if existing and expected_revision is None else now()))
        if collected>datetime.now(timezone.utc):raise ValueError('Usage collection cannot be in the future')
        entry.update(department=ROLES[entry['agent']][0],token_kind=kind,collected_at=collected.isoformat())
        # Persist only declared fields, not arbitrary provider raw payloads or secrets.
        fields=['task_id','agent','department','provider','model','invocation_id','execution_key','token_kind',*TOKEN_FIELDS,
                'actual_cost','estimated_cost','duration_seconds','collected_at','source']
        clean=redact({key:entry.get(key) for key in fields});fingerprint=hashlib.sha256(canonical(clean).encode()).hexdigest()
        with atomic(self.db):
            prior=self.db.execute('SELECT * FROM usage_events WHERE provider=? AND invocation_id=?',(entry['provider'],entry['invocation_id'])).fetchone()
            if prior and (prior['task_id']!=entry['task_id'] or prior['agent']!=entry['agent']):raise ValueError('An invocation cannot move to another task or agent')
            if prior and prior['payload_hash']==fingerprint:return dict(prior)
            if prior and prior['revision']!=expected_revision:raise ValueError('Usage revision conflict; reload cumulative telemetry before updating')
            key=entry.get('execution_key')
            if key:
                reservation=self.db.execute('SELECT * FROM usage_reservations WHERE execution_key=?',(key,)).fetchone()
                if reservation is None or reservation['task_id']!=entry['task_id'] or reservation['agent']!=entry['agent']:
                    raise ValueError('Usage execution key does not match its task/agent reservation')
                duplicate=self.db.execute('SELECT id FROM usage_events WHERE execution_key=? AND NOT(provider=? AND invocation_id=?)',
                                          (key,entry['provider'],entry['invocation_id'])).fetchone()
                if duplicate:raise ValueError('An execution reservation may reconcile only one cumulative invocation')
            record_id=prior['id'] if prior else str(uuid.uuid4());revision=prior['revision']+1 if prior else 1
            columns=['id',*fields,'revision','payload_hash']
            values=[record_id,*[clean[k] for k in fields],revision,fingerprint]
            updates=','.join(k+'=excluded.'+k for k in columns if k!='id')
            self.db.execute('INSERT INTO usage_events('+','.join(columns)+') VALUES('+','.join('?' for _ in values)+') ON CONFLICT(provider,invocation_id) DO UPDATE SET '+updates,values)
            if key and (entry['actual_cost'] is not None or entry['estimated_cost'] is not None):
                self.db.execute("UPDATE usage_reservations SET state='RECONCILED' WHERE execution_key=?",(key,))
        return dict(self.db.execute('SELECT * FROM usage_events WHERE id=?',(record_id,)).fetchone())

    def summary(self,task_id=None,agent=None,department=None):
        rows=[dict(r) for r in self.db.execute('SELECT * FROM usage_events')
              if (task_id is None or r['task_id']==task_id) and (agent is None or r['agent']==agent)
              and (department is None or r['department']==department)]
        def total(field,kind=None):
            values=[r[field] for r in rows if r[field] is not None and (kind is None or r['token_kind']==kind)]
            if not values:return None
            return sum(values) if field in TOKEN_FIELDS else str(sum(Decimal(v) for v in values))
        return {'availability':'UNKNOWN' if not rows else 'PARTIAL' if any(r['token_kind']!='MEASURED' or r['actual_cost'] is None or any(r[f] is None for f in TOKEN_FIELDS) for r in rows) else 'MEASURED',
            'invocations':len(rows),'actual_cost_usd':total('actual_cost'),'estimated_cost_usd':total('estimated_cost'),
            'duration_seconds':total('duration_seconds'),
            'measured_tokens':{f:total(f,'MEASURED') for f in TOKEN_FIELDS},
            'estimated_tokens':{f:total(f,'ESTIMATED') for f in TOKEN_FIELDS},
            'unpriced_invocations':sum(r['actual_cost'] is None and r['estimated_cost'] is None for r in rows),
            'unknown_token_invocations':sum(r['token_kind']=='UNKNOWN' for r in rows),
            'note':'Measured and estimated values stay separate; cache counts are not added again to inclusive input totals.'}


class BudgetService:
    def __init__(self,db,clock=None):self.db=db;self.clock=clock or (lambda:datetime.now(timezone.utc))

    def configure(self,scope,key,limit_usd,alert_ratio='0.8'):
        if scope not in {'TASK','AGENT','DEPARTMENT','DAILY','MONTHLY'}:raise ValueError('Unknown AI budget scope')
        if scope=='TASK' and not self.db.execute('SELECT 1 FROM tasks WHERE id=?',(key,)).fetchone():raise ValueError('Unknown task budget')
        if scope=='AGENT' and key not in ROLES:raise ValueError('Unknown agent budget')
        if scope=='DEPARTMENT' and key not in DOMAINS:raise ValueError('Unknown department budget')
        if scope in {'DAILY','MONTHLY'} and key!='global':raise ValueError('Calendar budgets use global scope key')
        limit=amount(limit_usd);ratio=amount(alert_ratio,'alert ratio')
        if not 0<ratio<=1:raise ValueError('Alert ratio must be within (0,1]')
        with self.db:
            existing=self.db.execute('SELECT id FROM ai_budgets WHERE scope=? AND scope_key=?',(scope,str(key))).fetchone()
            identity=existing[0] if existing else str(uuid.uuid4())
            self.db.execute('INSERT INTO ai_budgets VALUES(?,?,?,?,?,1,?) ON CONFLICT(scope,scope_key) DO UPDATE SET limit_usd=excluded.limit_usd,alert_ratio=excluded.alert_ratio,enabled=1,updated_at=excluded.updated_at',
                            (identity,scope,str(key),str(limit),str(ratio),now()))
        return identity

    def _matches(self,row,budget):
        scope,key=budget['scope'],budget['scope_key']
        if scope=='TASK':return str(row['task_id'])==key
        if scope=='AGENT':return row['agent']==key
        if scope=='DEPARTMENT':return row['department']==key
        date=instant(row['collected_at']).astimezone(BAGHDAD);today=instant(self.clock()).astimezone(BAGHDAD)
        return date.date()==today.date() if scope=='DAILY' else (date.year,date.month)==(today.year,today.month)

    def evaluate(self,task_id,agent,projected_cost=None):
        if agent not in ROLES:raise ValueError('Unknown budget principal')
        projected=amount(projected_cost,allow_none=True)
        usage=[dict(r) for r in self.db.execute('SELECT * FROM usage_events')]
        holds=[dict(r) for r in self.db.execute("SELECT * FROM usage_reservations WHERE state IN ('ACTIVE','AWAITING_TELEMETRY')")]
        budgets=[]
        for row in self.db.execute('SELECT * FROM ai_budgets WHERE enabled=1 ORDER BY scope,scope_key'):
            budget=dict(row)
            if budget['scope']=='TASK' and budget['scope_key']!=str(task_id):continue
            if budget['scope']=='AGENT' and budget['scope_key']!=agent:continue
            if budget['scope']=='DEPARTMENT' and budget['scope_key']!=ROLES[agent][0]:continue
            selected=[u for u in usage if self._matches(u,budget)]
            # Unsettled reservations carry forward across calendar periods conservatively.
            reserved=[u for u in holds if budget['scope'] in {'DAILY','MONTHLY'} or
                      budget['scope']=='TASK' and str(u['task_id'])==budget['scope_key'] or
                      budget['scope']=='AGENT' and u['agent']==budget['scope_key'] or
                      budget['scope']=='DEPARTMENT' and u['department']==budget['scope_key']]
            spent=sum((Decimal(u['actual_cost'] if u['actual_cost'] is not None else u['estimated_cost'])
                       for u in selected if u['actual_cost'] is not None or u['estimated_cost'] is not None),Decimal(0))
            held=sum((Decimal(u['amount_usd']) for u in reserved if u['amount_usd'] is not None),Decimal(0))
            unknown=any(u['actual_cost'] is None and u['estimated_cost'] is None for u in selected) or any(u['amount_usd'] is None for u in reserved)
            limit=Decimal(budget['limit_usd']);forecast=spent+held+(projected or 0)
            status='UNKNOWN_COST' if projected is None or unknown else 'EXCEEDED' if forecast>limit else 'WARNING' if forecast>=limit*Decimal(budget['alert_ratio']) else 'WITHIN_LIMIT'
            budgets.append(dict(budget,recorded_charge_usd=str(spent),reserved_usd=str(held),
                remaining_usd=str(limit-spent-held),projected_total_usd=str(forecast),status=status,
                cost_basis='actual where supplied, otherwise explicitly estimated; reservations are forecasts'))
        return {'task_id':task_id,'agent':agent,'projected_cost_usd':str(projected) if projected is not None else None,
            'budgets':budgets,'requires_authorization':any(b['status'] in {'EXCEEDED','UNKNOWN_COST'} for b in budgets),
            'warnings':[b['id'] for b in budgets if b['status']=='WARNING'],
            'policy':'AI execution USD only; not trading investment capital. Missing telemetry is not a zero charge.'}

    def _fingerprint(self,evaluation,execution_key):
        binding={'task':evaluation['task_id'],'agent':evaluation['agent'],'key':execution_key,
                 'projected_cost':evaluation['projected_cost_usd'],
                 'budgets':[{k:b[k] for k in ['id','scope','scope_key','limit_usd','updated_at']} for b in evaluation['budgets']]}
        return hashlib.sha256(canonical(binding).encode()).hexdigest()

    def reserve(self,task_id,agent,execution_key,projected_cost=None,approval_id=None):
        required(execution_key,'Unique execution key')
        with atomic(self.db):
            if self.db.execute('SELECT 1 FROM usage_reservations WHERE execution_key=?',(execution_key,)).fetchone():
                raise ValueError('Duplicate execution reservation; do not replay a task invocation')
            evaluation=self.evaluate(task_id,agent,projected_cost);binding=self._fingerprint(evaluation,execution_key)
            held_amount=evaluation['projected_cost_usd']
            if evaluation['requires_authorization']:
                approval=self.db.execute('SELECT * FROM budget_approvals WHERE id=?',(approval_id,)).fetchone() if approval_id else None
                valid=approval and approval['status']=='APPROVED' and approval['task_id']==task_id and approval['execution_key']==execution_key and approval['fingerprint']==binding and instant(approval['expires_at'])>instant(self.clock())
                if not valid:
                    prior=self.db.execute("SELECT id FROM budget_approvals WHERE fingerprint=? AND status='PENDING'",(binding,)).fetchone()
                    identity=prior[0] if prior else str(uuid.uuid4())
                    if not prior:self.db.execute("INSERT INTO budget_approvals VALUES(?,?,?,?,?,?,?,?,?,?)",(identity,task_id,execution_key,binding,'PENDING',evaluation['projected_cost_usd'],None,None,now(),None))
                    return {'allowed':False,'approval_id':identity,'evaluation':evaluation}
                held_amount=approval['maximum_usd']
                self.db.execute("UPDATE budget_approvals SET status='CONSUMED',consumed_at=? WHERE id=?",(now(),approval['id']))
            self.db.execute('INSERT INTO usage_reservations VALUES(?,?,?,?,?,?,?)',
                            (execution_key,task_id,agent,ROLES[agent][0],held_amount,'ACTIVE',now()))
            return {'allowed':True,'evaluation':evaluation,'execution_key':execution_key}

    def approve(self,approval_id,reference,valid_minutes=60,maximum_usd=None):
        required(reference,'Actual scoped user authorization reference')
        if type(valid_minutes) is not int or not 1<=valid_minutes<=1440:raise ValueError('Approval lifetime must be 1..1440 minutes')
        approval=self.db.execute('SELECT * FROM budget_approvals WHERE id=?',(approval_id,)).fetchone()
        if approval is None or approval['status']!='PENDING':raise ValueError('Expected a pending budget authorization')
        ceiling=amount(maximum_usd if maximum_usd is not None else approval['maximum_usd'], 'Explicit authorization ceiling')
        if approval['maximum_usd'] is not None and ceiling<Decimal(approval['maximum_usd']):raise ValueError('Ceiling is below the planned invocation estimate')
        expires=instant(self.clock())+timedelta(minutes=valid_minutes)
        with self.db:self.db.execute("UPDATE budget_approvals SET status='APPROVED',reference=?,expires_at=?,maximum_usd=? WHERE id=?",(redact(reference),expires.isoformat(),str(ceiling),approval_id))
        return {'id':approval_id,'expires_at':expires.isoformat(),'identity_authenticated':False}
