"""SQLite backend for IOI. No network access; no payment or outbound actions."""
import json, os, sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGES=('customer_payment','platform_receipt','withdrawable_balance','payout_provider','iraqi_account','usable_funds')
WEIGHTS={'iraq_access':25,'demand':20,'net_potential':20,'low_cost':10,'time_fit':10,'scalability':10,'differentiation':5}
STATUS={'VERIFIED','UNVERIFIED','BLOCKED'}
DECISIONS={'HOLD','REWORK','MONITOR','REJECT','PROCEED_TO_PLAN','REQUEST_APPROVAL','TEST','SCALE'}

class IOIError(Exception): pass

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

def location(db=None):
    raw=db or os.getenv('IOI_DB_PATH')
    return Path(raw).expanduser().resolve() if raw else ROOT/'data'/'ioi.db'

def connect(db=None):
    p=location(db)
    if not p.parent.exists(): p.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(p))
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=3000')
    return conn

def init(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS opportunities(
      id INTEGER PRIMARY KEY, title TEXT NOT NULL, model TEXT NOT NULL DEFAULT '',
      buyer TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL DEFAULT 'main-agent',
      status TEXT NOT NULL DEFAULT 'RESEARCH', revision INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS evidence(
      id INTEGER PRIMARY KEY, opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
      claim TEXT NOT NULL, url TEXT NOT NULL, classification TEXT NOT NULL,
      confidence TEXT NOT NULL, checked_at TEXT NOT NULL, caveats TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS payout_checks(
      opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
      stage TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'UNVERIFIED',
      provider TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
      checked_at TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
      PRIMARY KEY(opportunity_id,stage));
    CREATE TABLE IF NOT EXISTS ratings(
      opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
      criterion TEXT NOT NULL, rating REAL NOT NULL CHECK(rating>=0 AND rating<=10),
      rationale TEXT NOT NULL, updated_at TEXT NOT NULL,
      PRIMARY KEY(opportunity_id,criterion));
    CREATE TABLE IF NOT EXISTS risk_flags(
      id INTEGER PRIMARY KEY, opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
      severity TEXT NOT NULL, summary TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN',
      created_at TEXT NOT NULL, resolved_at TEXT);
    CREATE TABLE IF NOT EXISTS qa_attestations(
      id INTEGER PRIMARY KEY, opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
      revision INTEGER NOT NULL, reviewer TEXT NOT NULL, verdict TEXT NOT NULL,
      findings TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS rework(
      id INTEGER PRIMARY KEY, opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
      attempt INTEGER NOT NULL, cause TEXT NOT NULL, correction TEXT NOT NULL,
      owner TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS decisions(
      id INTEGER PRIMARY KEY, opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
      decision TEXT NOT NULL, rationale TEXT NOT NULL, alternatives TEXT NOT NULL DEFAULT '',
      trigger TEXT NOT NULL DEFAULT '', author TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS experiments(
      id INTEGER PRIMARY KEY, opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
      hypothesis TEXT NOT NULL, metric TEXT NOT NULL, target REAL NOT NULL,
      max_cost REAL NOT NULL CHECK(max_cost>=0), max_hours REAL NOT NULL CHECK(max_hours>0),
      status TEXT NOT NULL DEFAULT 'PLANNED', result_notes TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS approvals(
      id INTEGER PRIMARY KEY, opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
      action TEXT NOT NULL, max_cost REAL NOT NULL DEFAULT 0, approved_by TEXT NOT NULL,
      scope TEXT NOT NULL, experiment_id INTEGER REFERENCES experiments(id), created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS experiment_events(
      id INTEGER PRIMARY KEY, experiment_id INTEGER NOT NULL REFERENCES experiments(id),
      metric_value REAL, revenue REAL NOT NULL DEFAULT 0,
      cost REAL NOT NULL DEFAULT 0, hours REAL NOT NULL DEFAULT 0,
      note TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS monitoring(
      id INTEGER PRIMARY KEY, opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
      trigger TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'OPEN',
      created_at TEXT NOT NULL, resolved_at TEXT);
    CREATE INDEX IF NOT EXISTS idx_evidence_op ON evidence(opportunity_id);
    CREATE INDEX IF NOT EXISTS idx_decisions_op ON decisions(opportunity_id);
    """)
    conn.commit()

def get(conn,oid):
    row=conn.execute('SELECT * FROM opportunities WHERE id=?',(oid,)).fetchone()
    if row is None: raise IOIError(f'Opportunity {oid} does not exist')
    return row

def create(conn,title,model='',buyer='',created_by='main-agent'):
    if not title.strip(): raise IOIError('Title cannot be blank')
    with conn:
        cur=conn.execute('INSERT INTO opportunities(title,model,buyer,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?)',(title,model,buyer,created_by,now(),now()))
        oid=cur.lastrowid
        conn.executemany('INSERT INTO payout_checks(opportunity_id,stage,checked_at) VALUES(?,?,?)',[(oid,s,now()) for s in STAGES])
    return oid

def revision(conn,oid):
    get(conn,oid)
    conn.execute('UPDATE opportunities SET revision=revision+1,updated_at=? WHERE id=?',(now(),oid))

def evidence_add(conn,oid,claim,url,classification='B',confidence='MEDIUM',caveats=''):
    get(conn,oid)
    if not claim.strip():raise IOIError('Evidence claim must not be blank')
    if not url.startswith(('https://','http://')):raise IOIError('Evidence requires a real http(s) URL; do not invent one')
    if classification not in ('A','B','C'):raise IOIError('Evidence classification must be A, B or C')
    if confidence not in ('LOW','MEDIUM','HIGH'):raise IOIError('Confidence must be LOW, MEDIUM, HIGH')
    with conn:
        conn.execute('INSERT INTO evidence(opportunity_id,claim,url,classification,confidence,checked_at,caveats,created_at) VALUES(?,?,?,?,?,?,?,?)',(oid,claim,url,classification,confidence,now(),caveats,now()))
        revision(conn,oid)

def payout_set(conn,oid,stage,status,provider='',url='',details=''):
    get(conn,oid)
    if stage not in STAGES:raise IOIError('Invalid stage: '+stage)
    if status not in STATUS:raise IOIError('Invalid status: '+status)
    if status=='VERIFIED' and (not provider.strip() or not url.startswith('https://') or not details.strip()):
        raise IOIError('VERIFIED requires provider, HTTPS evidence URL, and specific details (source contents must be checked independently)')
    with conn:
        conn.execute('UPDATE payout_checks SET status=?,provider=?,url=?,checked_at=?,details=? WHERE opportunity_id=? AND stage=?',(status,provider,url,now(),details,oid,stage))
        revision(conn,oid)

def rating_set(conn,oid,criterion,rating,rationale):
    get(conn,oid)
    if criterion not in WEIGHTS:raise IOIError('Unknown criterion: '+criterion)
    if not 0<=rating<=10:raise IOIError('Rating must be between 0 and 10')
    if not rationale.strip():raise IOIError('Rating rationale is mandatory')
    with conn:
        conn.execute('INSERT INTO ratings(opportunity_id,criterion,rating,rationale,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(opportunity_id,criterion) DO UPDATE SET rating=excluded.rating,rationale=excluded.rationale,updated_at=excluded.updated_at',(oid,criterion,rating,rationale,now()))
        revision(conn,oid)

def score(conn,oid):
    get(conn,oid)
    rows=conn.execute('SELECT criterion,rating,rationale FROM ratings WHERE opportunity_id=?',(oid,)).fetchall()
    values={r['criterion']:r['rating'] for r in rows}
    present=sum(WEIGHTS[k] for k in values)
    # Missing criteria count as zero, and score is marked incomplete; avoid cherry-picking normalizations.
    val=sum(WEIGHTS[k]*v/10 for k,v in values.items())
    return {'score':round(val,2),'complete':len(values)==len(WEIGHTS), 'coverage_pct':present,'ratings':values,'unrated':[k for k in WEIGHTS if k not in values]}

def flag_add(conn,oid,severity,summary):
    get(conn,oid)
    if severity not in ('BLOCKER','MAJOR','MINOR'):raise IOIError('Severity must be BLOCKER, MAJOR, MINOR')
    if not summary.strip():raise IOIError('Flag summary required')
    with conn:
        cur=conn.execute('INSERT INTO risk_flags(opportunity_id,severity,summary,created_at) VALUES(?,?,?,?)',(oid,severity,summary,now()))
        revision(conn,oid)
    return cur.lastrowid

def flag_close(conn,flagid,note):
    r=conn.execute('SELECT * FROM risk_flags WHERE id=?',(flagid,)).fetchone()
    if not r:raise IOIError('No such risk flag')
    if not note.strip():raise IOIError('A resolution note is required')
    with conn:
        conn.execute('UPDATE risk_flags SET status=?,resolved_at=?,summary=? WHERE id=?',('CLOSED',now(),r['summary']+' [Resolution: '+note+']',flagid))
        revision(conn,r['opportunity_id'])

def qa_check(conn,oid):
    candidate=get(conn,oid)
    stages={r['stage']:dict(r) for r in conn.execute('SELECT * FROM payout_checks WHERE opportunity_id=?',(oid,))}
    missing=[s for s in STAGES if stages[s]['status']!='VERIFIED']
    # Structural proof: URL, details, provider required; not a semantic validation of the pages.
    incomplete=[s for s in STAGES if stages[s]['status']=='VERIFIED' and (not stages[s]['url'].startswith('https://') or not stages[s]['details'] or not stages[s]['provider'])]
    counts=conn.execute('SELECT COUNT(*) FROM evidence WHERE opportunity_id=?',(oid,)).fetchone()[0]
    blockers=[dict(r) for r in conn.execute("SELECT * FROM risk_flags WHERE opportunity_id=? AND status='OPEN' AND severity IN ('BLOCKER','MAJOR')",(oid,))]
    gaps=[]
    if missing: gaps.append('Payout stages not verified: '+', '.join(missing))
    if incomplete:gaps.append('Insufficient payout documentation: '+', '.join(incomplete))
    if counts==0:gaps.append('No source evidence records')
    if blockers:gaps.append(str(len(blockers))+' open major/blocker risk flags')
    verdict='READY_FOR_INDEPENDENT_REVIEW' if not gaps else 'NEEDS_EVIDENCE'
    return {'opportunity':oid,'revision':candidate['revision'],'structural_verdict':verdict,'missing':gaps,'verified_stages':len(STAGES)-len(missing),'evidence_count':counts,'risk_flags':blockers,
            'warning':'Structural checks do not confirm that linked pages support claims. Only genuinely independent source review may attest PASS.'}

def qa_attest(conn,oid,reviewer,verdict,findings):
    candidate=get(conn,oid)
    if not reviewer.strip() or reviewer.casefold()==candidate['created_by'].casefold():
        raise IOIError('QA reviewer must be named and different from opportunity creator; actual identity is not authenticated')
    if verdict not in ('PASS','FAIL','NEEDS_EVIDENCE'):raise IOIError('Invalid verdict')
    if not findings.strip(): raise IOIError('QA findings required; describe actual source review, not just structural CLI pass')
    status=qa_check(conn,oid)
    if verdict=='PASS' and status['structural_verdict']!='READY_FOR_INDEPENDENT_REVIEW':
        raise IOIError('Cannot PASS: '+ '; '.join(status['missing']))
    with conn:
        conn.execute('INSERT INTO qa_attestations(opportunity_id,revision,reviewer,verdict,findings,created_at) VALUES(?,?,?,?,?,?)',(oid,candidate['revision'],reviewer,verdict,findings,now()))
    return verdict

def qa_current(conn,oid):
    op=get(conn,oid)
    r=conn.execute('SELECT * FROM qa_attestations WHERE opportunity_id=? ORDER BY id DESC LIMIT 1',(oid,)).fetchone()
    if r is None:return {'verdict':'MISSING','valid':False}
    isvalid=(r['revision']==op['revision'])
    return {'verdict':r['verdict'] if isvalid else 'STALE','valid':isvalid and r['verdict']=='PASS','reviewer':r['reviewer'],'revision':r['revision']}

def gate(conn,oid):
    s=qa_check(conn,oid); qa=qa_current(conn,oid)
    allowed=not s['missing'] and qa['valid']
    return {'allowed':allowed,'reason': 'Independent QA PASS at current revision and all structural checks clear' if allowed else '; '.join(s['missing'] or [f'Independent QA: {qa["verdict"]}']), 'qa':qa}

def rework_add(conn,oid,cause,correction,owner):
    get(conn,oid)
    if not all(x.strip() for x in [cause,correction,owner]):raise IOIError('Rework cause/correction/owner required')
    n=conn.execute('SELECT COUNT(*) FROM rework WHERE opportunity_id=?',(oid,)).fetchone()[0]
    if n>=3:raise IOIError('Three reworks already used; escalate to main agent for HOLD/REJECT')
    with conn:
        conn.execute('INSERT INTO rework(opportunity_id,attempt,cause,correction,owner,created_at) VALUES(?,?,?,?,?,?)',(oid,n+1,cause,correction,owner,now()))
        revision(conn,oid)
    return n+1

def decision_add(conn,oid,decision,rationale,author='income-strategy-director',alternatives='',trigger=''):
    get(conn,oid)
    if decision not in DECISIONS:raise IOIError('Invalid decision')
    if not rationale.strip():raise IOIError('Decision needs rationale')
    if decision in {'TEST','SCALE','PROCEED_TO_PLAN','REQUEST_APPROVAL'} and not gate(conn,oid)['allowed']:
        raise IOIError('Decision blocked by independent QA / payment gate: '+gate(conn,oid)['reason'])
    with conn:
        conn.execute('INSERT INTO decisions(opportunity_id,decision,rationale,alternatives,trigger,author,created_at) VALUES(?,?,?,?,?,?,?)',(oid,decision,rationale,alternatives,trigger,author,now()))
        conn.execute('UPDATE opportunities SET status=?,updated_at=? WHERE id=?',(decision,now(),oid))

def experiment_create(conn,oid,hypothesis,metric,target,max_cost,max_hours):
    get(conn,oid)
    if not hypothesis.strip() or not metric.strip():raise IOIError('Hypothesis/metric required')
    if max_cost<0 or max_hours<=0:raise IOIError('Invalid experiment cap')
    with conn:
        cur=conn.execute('INSERT INTO experiments(opportunity_id,hypothesis,metric,target,max_cost,max_hours,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(oid,hypothesis,metric,target,max_cost,max_hours,now(),now()))
    return cur.lastrowid

def approve(conn,oid,action,max_cost,approved_by,scope,experiment_id=None):
    get(conn,oid)
    if action not in ('EXPERIMENT','OUTREACH','ACCOUNT','PURCHASE','PUBLICATION'):
        raise IOIError('Invalid approval scope action')
    if max_cost<0 or not approved_by.strip() or not scope.strip():raise IOIError('Approval needs name, scope and nonnegative cap')
    if action=='EXPERIMENT':
        exp=conn.execute('SELECT * FROM experiments WHERE id=?',(experiment_id,)).fetchone()
        if not exp or exp['opportunity_id']!=oid:raise IOIError('EXPERIMENT approval must be bound to a valid experiment ID for this opportunity')
    elif experiment_id is not None:raise IOIError('Experiment ID is allowed only for EXPERIMENT approvals')
    with conn:
        cur=conn.execute('INSERT INTO approvals(opportunity_id,action,max_cost,approved_by,scope,experiment_id,created_at) VALUES(?,?,?,?,?,?,?)',(oid,action,max_cost,approved_by,scope,experiment_id,now()))
    return cur.lastrowid

def experiment_activate(conn,eid,approval_id):
    exp=conn.execute('SELECT * FROM experiments WHERE id=?',(eid,)).fetchone()
    if not exp:raise IOIError('No experiment '+str(eid))
    if exp['status']!='PLANNED':raise IOIError('Experiment already activated/completed')
    if not gate(conn,exp['opportunity_id'])['allowed']:
        raise IOIError('Cannot activate without current independent QA PASS and verified payment path')
    app=conn.execute('SELECT * FROM approvals WHERE id=?',(approval_id,)).fetchone()
    if not app or app['opportunity_id']!=exp['opportunity_id'] or app['action']!='EXPERIMENT' or app['experiment_id']!=eid or app['max_cost']<exp['max_cost']:
        raise IOIError('Specific experiment approval for this opportunity and sufficient cost cap required')
    with conn:
        conn.execute('UPDATE experiments SET status=?,updated_at=? WHERE id=?',('ACTIVE',now(),eid))
    return True

def event_add(conn,eid,metric_value,revenue,cost,hours,note):
    exp=conn.execute('SELECT * FROM experiments WHERE id=?',(eid,)).fetchone()
    if not exp:raise IOIError('No experiment')
    if exp['status']!='ACTIVE':raise IOIError('Only active experiments accept actual events')
    if any(x<0 for x in (revenue,cost,hours)) or not note.strip():raise IOIError('Revenue/cost/hours must be nonnegative and note required')
    spent=conn.execute('SELECT COALESCE(SUM(cost),0),COALESCE(SUM(hours),0) FROM experiment_events WHERE experiment_id=?',(eid,)).fetchone()
    if spent[0]+cost >exp['max_cost']+1e-8 or spent[1]+hours>exp['max_hours']+1e-8:
        raise IOIError('Event would exceed experiment authorized cost/hour caps')
    with conn:
        conn.execute('INSERT INTO experiment_events(experiment_id,metric_value,revenue,cost,hours,note,created_at) VALUES(?,?,?,?,?,?,?)',(eid,metric_value,revenue,cost,hours,note,now()))

def experiment_close(conn,eid,notes):
    exp=conn.execute('SELECT * FROM experiments WHERE id=?',(eid,)).fetchone()
    if not exp:raise IOIError('No experiment')
    if exp['status']!='ACTIVE':raise IOIError('Only active experiments may complete')
    if not notes.strip():raise IOIError('Actual outcome summary required')
    with conn:
        conn.execute('UPDATE experiments SET status=?,result_notes=?,updated_at=? WHERE id=?',('COMPLETED',notes,now(),eid))

def monitoring_add(conn,oid,trigger):
    get(conn,oid)
    if not trigger.strip():raise IOIError('Monitoring requires specific change trigger')
    with conn:
        return conn.execute('INSERT INTO monitoring(opportunity_id,trigger,created_at) VALUES(?,?,?)',(oid,trigger,now())).lastrowid

def finance(price,low,base,high,unit_cost,fee_pct,monthly_fixed,hours):
    if any(x<0 for x in [price,low,base,high,unit_cost,fee_pct,monthly_fixed,hours]):raise IOIError('Amounts may not be negative')
    if fee_pct>=100 or low>base or base>high:raise IOIError('Require fee % under 100 and low <= base <= high')
    contribution=price*(1-fee_pct/100)-unit_cost
    scenarios=[]
    for name,units in [('low',low),('base',base),('high',high)]:
        revenue=price*units; variable=unit_cost*units+revenue*fee_pct/100
        net=revenue-variable-monthly_fixed
        scenarios.append({'case':name,'units':units,'revenue':round(revenue,2),'total_cost':round(variable+monthly_fixed,2),'net':round(net,2),'hourly_net':round(net/hours,2) if hours else None})
    import math
    break_even=math.ceil(monthly_fixed/contribution) if contribution>0 else None
    return {'currency':'USD (illustrative inputs; not market estimates)','unit_contribution':round(contribution,2),'break_even_units':break_even,'scenarios':scenarios}

def dashboard(conn):
    out=['# Income Opportunity Intelligence — Actual Local Records','',f'Generated (UTC): {now()}','','*Only saved database records appear below. No external research or earnings are implied.*','']
    ops=conn.execute('SELECT * FROM opportunities ORDER BY id').fetchall()
    out += [f'Opportunities: **{len(ops)}**','']
    if not ops:out+=['No opportunities researched yet. Start with `python scripts/ioi.py add --title "..."`.','']
    for r in ops:
        oid=r['id']; score_info=score(conn,oid); check=gate(conn,oid)
        out += [f'## #{oid} — {r["title"]}',f'- Research status: {r["status"]}',f'- Model: {r["model"] or "not entered"}',f'- Buyer: {r["buyer"] or "not entered"}',f'- Provisional weighted score: {score_info["score"]}/100 (criteria coverage: {score_info["coverage_pct"]}%; {"complete" if score_info["complete"] else "incomplete"})',f'- Gate: {"PASS" if check["allowed"] else "HOLD"} — {check["reason"]}',f'- Current QA: {check["qa"]["verdict"]}']
        latest=conn.execute('SELECT * FROM decisions WHERE opportunity_id=? ORDER BY id DESC LIMIT 1',(oid,)).fetchone()
        if latest: out += [f'- Main decision: {latest["decision"]} — {latest["rationale"]}']
        out += ['']
    exp=conn.execute("SELECT COUNT(*),COALESCE(SUM(revenue),0),COALESCE(SUM(cost),0),COALESCE(SUM(hours),0) FROM experiment_events").fetchone()
    out+=['## Experiment actuals', f'- Logged events: {exp[0]}',f'- Revenue logged: ${exp[1]:,.2f}',f'- Costs logged: ${exp[2]:,.2f}',f'- Net before other business costs: ${exp[1]-exp[2]:,.2f}',f'- Hours logged: {exp[3]:,.2f}','', '## Monitoring queue']
    mon=conn.execute("SELECT m.*,o.title FROM monitoring m JOIN opportunities o ON o.id=m.opportunity_id WHERE m.state='OPEN' ORDER BY m.id DESC LIMIT 30").fetchall()
    out += [f'- #{m["opportunity_id"]}: {m["trigger"]}' for m in mon] or ['- No open triggers']
    out += ['','## Evidence and claims','Each opportunity requires dated, independently checked sources. URLs stored in SQLite are user/agent-reported and not verified by the CLI.']
    return '\n'.join(out)+'\n'
