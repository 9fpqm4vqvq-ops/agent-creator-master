#!/usr/bin/env python3
"""MAOS local registry and governance tool. Stdlib only; DOES NOT execute Claude agents."""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / 'data' / 'maos.sqlite'
AGENT_ROLES = {
    'agent-runner': ('operations', 'execute,coordinate,workflow,production,delivery', 'Read,Glob,Grep,Bash,Write,Edit'),
    'task-router': ('operations', 'route,assignment,planning,coordination,classification', 'Read,Glob,Grep,Bash'),
    'agent-creator': ('development', 'agent,create,skill,design,benchmark,test', 'Read,Glob,Grep,Bash,Write,Edit'),
    'token-watchdog': ('resources', 'budget,token,cost,efficiency,optimization', 'Read,Glob,Grep,Bash'),
    'research-analyst': ('research', 'research,investigation,fact,evidence,web,market', 'Read,Glob,Grep,WebSearch,WebFetch'),
    'qa-auditor': ('quality', 'qa,quality,review,security,validation,testing', 'Read,Glob,Grep,Bash'),
    'rework-specialist': ('quality', 'rework,repair,correction,root-cause,debugging', 'Read,Glob,Grep,Bash,Write,Edit'),
    'registry-manager': ('learning', 'registry,agent,lifecycle,versions,governance', 'Read,Glob,Grep,Bash'),
    'learning-analyst': ('learning', 'learning,memory,experiment,retrospective', 'Read,Glob,Grep,Bash'),
    'reporting-specialist': ('reporting', 'report,summary,dashboard,documentation', 'Read,Glob,Grep,Bash,Write'),
}
DB_SQL = '''
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS agents (
  name TEXT PRIMARY KEY, department TEXT NOT NULL, capabilities TEXT NOT NULL,
  tools TEXT NOT NULL, version TEXT NOT NULL DEFAULT '1.0.0',
  status TEXT NOT NULL, repetitive INTEGER NOT NULL DEFAULT 0,
  rule_based INTEGER NOT NULL DEFAULT 0, return_value INTEGER NOT NULL DEFAULT 0,
  creation_reason TEXT DEFAULT '', test_passed INTEGER NOT NULL DEFAULT 0,
  qa_passed INTEGER NOT NULL DEFAULT 0, qa_reviewer TEXT DEFAULT '', created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
  objective TEXT NOT NULL DEFAULT '', domain TEXT NOT NULL,
  owner TEXT NOT NULL REFERENCES agents(name),
  criteria TEXT NOT NULL, risk TEXT NOT NULL DEFAULT 'medium',
  status TEXT NOT NULL DEFAULT 'QUEUED', reworks INTEGER NOT NULL DEFAULT 0,
  last_qa TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER REFERENCES tasks(id),
  event_type TEXT NOT NULL, detail TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS qa_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id),
  reviewer TEXT NOT NULL REFERENCES agents(name), verdict TEXT NOT NULL,
  notes TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals (
  id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, scope TEXT NOT NULL,
  approver TEXT NOT NULL, reference TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id),
  statement TEXT NOT NULL, source TEXT NOT NULL, checked_at TEXT NOT NULL,
  classification TEXT NOT NULL, freshness_days INTEGER NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER REFERENCES tasks(id),
  kind TEXT NOT NULL, reason TEXT NOT NULL, outcome TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id),
  kind TEXT NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
  cost_usd REAL NOT NULL, reference TEXT NOT NULL, at TEXT NOT NULL);
'''
TRANSITIONS = {
 'QUEUED': {'DIAGNOSING', 'CANCELLED'},
 'DIAGNOSING': {'ROUTING','BLOCKED','CANCELLED'},
 'ROUTING': {'EXECUTING','BLOCKED','WAITING_APPROVAL','CANCELLED'},
 'EXECUTING': {'QA','BLOCKED','WAITING_APPROVAL','FAILED','CANCELLED'},
 'REWORK': {'EXECUTING','BLOCKED','CANCELLED'},
 'WAITING_APPROVAL': {'EXECUTING','BLOCKED','CANCELLED'},
 'BLOCKED': {'ROUTING','EXECUTING','CANCELLED'},
 'QA': {'BLOCKED','CANCELLED'},
 'COMPLETED': set(), 'FAILED': set(), 'CANCELLED': set()
}

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def connect(db):
    path=Path(db); path.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(path)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript(DB_SQL)
    return con

def require(value,what):
    if value is None: raise ValueError(f'Missing {what}')
    return value

def get_agent(c,name):
    row=c.execute('SELECT * FROM agents WHERE name=?',(name,)).fetchone()
    if not row: raise ValueError(f'Unknown agent: {name}')
    return row

def get_task(c,task_id):
    row=c.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()
    if not row: raise ValueError(f'Unknown task: {task_id}')
    return row

def event(c,task_id,typ,detail):
    c.execute('INSERT INTO events(task_id,event_type,detail,at) VALUES(?,?,?,?)',
              (task_id,typ,detail,now()))

def init(c,args):
    for name,(dept,cap,tools) in AGENT_ROLES.items():
        c.execute('''INSERT OR IGNORE INTO agents
            (name,department,capabilities,tools,version,status,repetitive,rule_based,return_value,
             creation_reason,test_passed,qa_passed,qa_reviewer,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name,dept,cap,tools,'1.0.0','ACTIVE',1,1,1,'Built-in seeded role; source files reviewed during installation',1,1,
             'baseline_package',now(),now()))
    c.commit()
    return {'status':'initialized','agents':len(AGENT_ROLES),'database':str(args.db)}

def agents(c,args):
    return [dict(x) for x in c.execute('SELECT name,department,capabilities,tools,version,status FROM agents ORDER BY department,name')]

def new_task(c,args):
    agent=get_agent(c,args.owner)
    if agent['status'] not in ('ACTIVE','MONITORED'): raise ValueError('Owner must be active')
    if not args.title.strip() or not args.criteria.strip(): raise ValueError('Title and acceptance criteria required')
    cur=c.execute('''INSERT INTO tasks(title,objective,domain,owner,criteria,risk,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?)''',
                  (args.title,args.objective or '',args.domain,args.owner,args.criteria,args.risk,now(),now()))
    event(c,cur.lastrowid,'CREATED',args.title)
    c.commit()
    return {'task_id':cur.lastrowid,'status':'QUEUED','owner':args.owner}

def advance(c,args):
    task=get_task(c,args.task_id); dest=args.to.upper()
    if dest not in TRANSITIONS[task['status']]: raise ValueError(f'Illegal task transition {task["status"]} -> {dest}')
    if dest=='QA' and task['status']!='EXECUTING': raise ValueError('QA must follow execution')
    c.execute('UPDATE tasks SET status=?,updated_at=? WHERE id=?',(dest,now(),args.task_id))
    event(c,args.task_id,'STATE',f'{task["status"]} -> {dest}')
    c.commit(); return {'task_id':args.task_id,'status':dest}

def qa(c,args):
    task=get_task(c,args.task_id); reviewer=get_agent(c,args.reviewer)
    if task['status']!='QA':raise ValueError('Task must be in QA state')
    if args.reviewer==task['owner']:raise ValueError('Independent QA: reviewer cannot be task owner')
    if reviewer['department']!='quality' or args.reviewer!='qa-auditor' or reviewer['status'] not in ('ACTIVE','MONITORED'):
        raise ValueError('Reviewer must be active independent qa-auditor')
    if not args.notes.strip():raise ValueError('QA notes required')
    verdict=args.result
    c.execute('INSERT INTO qa_reviews(task_id,reviewer,verdict,notes,at) VALUES(?,?,?,?,?)',
              (args.task_id,args.reviewer,verdict,args.notes,now()))
    count=task['reworks']; new_status={'PASS':'COMPLETED','FAIL':'FAILED','BLOCKED':'BLOCKED','REWORK':'REWORK'}[verdict]
    if verdict=='REWORK':
        count+=1
        if count>=3:new_status='BLOCKED'
    c.execute('UPDATE tasks SET status=?,last_qa=?,reworks=?,updated_at=? WHERE id=?',
              (new_status,verdict,count,now(),args.task_id))
    event(c,args.task_id,'QA',f'{verdict} by {args.reviewer}: {args.notes[:120]}')
    c.commit();return {'task_id':args.task_id,'qa':verdict,'status':new_status,'reworks':count,
                       'escalated':verdict=='REWORK' and count>=3}

def route(c,args):
    task=get_task(c,args.task_id)
    query=set(re.findall(r'[a-z0-9]+',f'{task["domain"]} {task["title"]}'.lower()))
    results=[]
    for agent in c.execute("SELECT * FROM agents WHERE status IN ('ACTIVE','MONITORED')"):
        tokens=set(agent['capabilities'].split(','))|set(agent['department'].split(','))
        hits=sorted(query & tokens)
        # task owner receives small tie boost; prevents unrelated roles winning on no evidence
        score=3*len(hits)+(1 if agent['name']==task['owner'] else 0)
        results.append({'name':agent['name'],'score':score,'matched':hits,'capabilities':agent['capabilities'].split(',')})
    results.sort(key=lambda x:(-x['score'],x['name']))
    risk_factor={'low':1,'medium':2,'high':3}[task['risk']]
    return {'task_id':task['id'],'domain':task['domain'],'lead_suggestion':results[0]['name'] if results else None,
            'alternatives':results[:4],'token_budget_estimate':risk_factor*1500,
            'estimate_only':True,'qa_required':True,'does_not_execute_agent':True,
            'note':'A capability-based suggestion, NOT delegation or a guaranteed competence benchmark.'}

def propose_agent(c,args):
    if not re.fullmatch('[a-z][a-z0-9-]{2,63}',args.name):raise ValueError('Use kebab-case agent name 3-64 chars')
    if args.name in AGENT_ROLES:raise ValueError('Core role already exists; reuse it')
    if not (args.repetitive and args.rule_based and args.valuable):
        raise ValueError('Permanent agent requires all 3R checks; use a temporary workflow/script otherwise')
    if not args.reason.strip():raise ValueError('3R return justification required')
    if c.execute('SELECT 1 FROM agents WHERE name=?',(args.name,)).fetchone():raise ValueError('Agent already exists')
    c.execute('''INSERT INTO agents(name,department,capabilities,tools,version,status,repetitive,rule_based,return_value,
       creation_reason,test_passed,qa_passed,qa_reviewer,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
       (args.name,args.department,args.capabilities,args.tools,args.version,'PROPOSED',1,1,1,args.reason,0,0,'',now(),now()))
    c.commit();return {'agent':args.name,'status':'PROPOSED','requires':'agent definition, representative tests, independent QA and approval'}

def agent_test(c,args):
    a=get_agent(c,args.name)
    if a['status'] not in ('PROPOSED','DESIGNED','TESTING','NEEDS_UPDATE'):
        raise ValueError('Agent not in design/testing state')
    if not args.reference.strip():raise ValueError('Test evidence reference required')
    c.execute('UPDATE agents SET status=?,test_passed=?,qa_passed=0,qa_reviewer="",updated_at=? WHERE name=?',
              ('TESTING',int(args.passed),now(),args.name))
    c.execute('INSERT INTO decisions(task_id,kind,reason,outcome,at) VALUES(NULL,?,?,?,?)',
              ('AGENT_TEST',args.reference,'PASS' if args.passed else 'FAIL',now()))
    c.commit();return {'agent':args.name,'status':'TESTING','test_passed':args.passed}

def agent_qa(c,args):
    a=get_agent(c,args.name); reviewer=get_agent(c,args.reviewer)
    if a['status']!='TESTING' or not a['test_passed']:raise ValueError('Representative tests must pass first')
    if args.name==args.reviewer or args.reviewer!='qa-auditor' or reviewer['status']!='ACTIVE':
        raise ValueError('Independent qa-auditor required')
    if not args.notes.strip():raise ValueError('QA notes required')
    status='QA_APPROVED' if args.passed else 'TESTING'
    c.execute('UPDATE agents SET status=?,qa_passed=?,qa_reviewer=?,updated_at=? WHERE name=?',
              (status,int(args.passed),args.reviewer,now(),args.name))
    c.execute('INSERT INTO decisions(task_id,kind,reason,outcome,at) VALUES(NULL,?,?,?,?)',
              ('AGENT_QA',args.notes,'PASS' if args.passed else 'REWORK',now()))
    c.commit();return {'agent':args.name,'status':status,'qa_passed':args.passed}

def approve(c,args):
    if not args.reference.strip() or args.approver.strip().lower() not in ('user','owner'):
        raise ValueError('Approval must cite actual user decision; approver USER/OWNER only')
    if args.action=='agent_deploy':get_agent(c,args.scope)
    c.execute('INSERT INTO approvals(action,scope,approver,reference,at) VALUES(?,?,?,?,?)',
              (args.action,args.scope,args.approver,args.reference,now()))
    c.commit();return {'logged':True,'action':args.action,'scope':args.scope,
                       'warning':'Recordkeeping only; verify actual user approval and host permissions separately'}

def activate_agent(c,args):
    a=get_agent(c,args.name)
    if a['status']!='QA_APPROVED' or not a['test_passed'] or not a['qa_passed'] or a['qa_reviewer']==args.name:
        raise ValueError('Activation blocked: agent must pass tests and independent QA')
    app=c.execute("SELECT 1 FROM approvals WHERE action='agent_deploy' AND scope=? ORDER BY id DESC LIMIT 1",(args.name,)).fetchone()
    if not app:raise ValueError('Activation blocked: explicit scoped deployment approval not recorded')
    agent_file=Path(__file__).resolve().parents[1]/'.claude'/'agents'/f'{args.name}.md'
    if not agent_file.is_file():raise ValueError('Activation blocked: install/test project agent definition first')
    c.execute('UPDATE agents SET status="ACTIVE",updated_at=? WHERE name=?',(now(),args.name))
    c.commit();return {'agent':args.name,'status':'ACTIVE',
                       'warning':'Registry active only: Claude Code discovers agent file on session startup; validate native permissions'}

def evidence(c,args):
    get_task(c,args.task_id)
    if not args.statement.strip() or not args.source.strip():raise ValueError('Evidence needs claim and source')
    datetime.fromisoformat(args.checked_at)
    c.execute('INSERT INTO evidence(task_id,statement,source,checked_at,classification,freshness_days,at) VALUES(?,?,?,?,?,?,?)',
              (args.task_id,args.statement,args.source,args.checked_at,args.classification,args.freshness_days,now()))
    c.commit();return {'recorded':True,'classification':args.classification,'source_not_automatically_verified':True}

def decision(c,args):
    if args.task_id is not None:get_task(c,args.task_id)
    c.execute('INSERT INTO decisions(task_id,kind,reason,outcome,at) VALUES(?,?,?,?,?)',
              (args.task_id,args.kind,args.reason,args.outcome,now()))
    c.commit();return {'recorded':True,'kind':args.kind}

def usage(c,args):
    get_task(c,args.task_id)
    if args.kind=='measured' and not args.reference.strip():
        raise ValueError('Measured usage requires external telemetry reference')
    c.execute('INSERT INTO usage(task_id,kind,input_tokens,output_tokens,cost_usd,reference,at) VALUES(?,?,?,?,?,?,?)',
              (args.task_id,args.kind,args.input_tokens,args.output_tokens,args.cost_usd,args.reference or 'heuristic estimate',now()))
    c.commit();return {'recorded':True,'kind':args.kind,'tokens':args.input_tokens+args.output_tokens}

def report(c,args):
    tasks=[dict(x) for x in c.execute('SELECT id,title,owner,status,last_qa,reworks FROM tasks ORDER BY id DESC LIMIT 30')]
    counts={r['status']:r['n'] for r in c.execute('SELECT status,COUNT(*) n FROM tasks GROUP BY status')}
    usage_rows=[dict(r) for r in c.execute('SELECT kind,SUM(input_tokens) in_tok,SUM(output_tokens) out_tok,SUM(cost_usd) costs FROM usage GROUP BY kind')]
    return {'tasks_by_status':counts,'recent_tasks':tasks,'usage_by_kind':usage_rows,
            'warning':'No automatic Claude usage telemetry or live agent dispatch; all usage entries are user-provided.'}

def build_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default=str(DEFAULT_DB),help='SQLite path; override for tests')
    sub=parser.add_subparsers(dest='command',required=True)
    def command(name):return sub.add_parser(name)
    command('init'); command('agents')
    t=command('new-task');t.add_argument('--title',required=True);t.add_argument('--objective',default='');t.add_argument('--domain',required=True);t.add_argument('--owner',required=True);t.add_argument('--criteria',required=True);t.add_argument('--risk',choices=['low','medium','high'],default='medium')
    a=command('advance');a.add_argument('task_id',type=int);a.add_argument('--to',required=True,choices=list(TRANSITIONS.keys()))
    a=command('route');a.add_argument('task_id',type=int)
    q=command('qa');q.add_argument('task_id',type=int);q.add_argument('--reviewer',required=True);q.add_argument('--result',choices=['PASS','REWORK','BLOCKED','FAIL'],required=True);q.add_argument('--notes',required=True)
    a=command('propose-agent');a.add_argument('--name',required=True);a.add_argument('--department',required=True);a.add_argument('--capabilities',required=True);a.add_argument('--tools',default='Read,Glob,Grep');a.add_argument('--version',default='0.1.0');a.add_argument('--reason',required=True);a.add_argument('--repetitive',action='store_true');a.add_argument('--rule-based',action='store_true');a.add_argument('--valuable',action='store_true')
    a=command('agent-test');a.add_argument('--name',required=True);a.add_argument('--passed',action='store_true');a.add_argument('--reference',required=True)
    a=command('agent-qa');a.add_argument('--name',required=True);a.add_argument('--reviewer',default='qa-auditor');a.add_argument('--passed',action='store_true');a.add_argument('--notes',required=True)
    a=command('approve');a.add_argument('--action',choices=['agent_deploy','spending','external_contact','publishing','registration','deletion','privileged_access'],required=True);a.add_argument('--scope',required=True);a.add_argument('--approver',required=True);a.add_argument('--reference',required=True)
    a=command('activate-agent');a.add_argument('--name',required=True)
    a=command('evidence');a.add_argument('--task-id',type=int,required=True);a.add_argument('--statement',required=True);a.add_argument('--source',required=True);a.add_argument('--checked-at',required=True);a.add_argument('--classification',choices=['VERIFIED','ASSUMPTION','HYPOTHESIS','REJECTED','HISTORICAL'],required=True);a.add_argument('--freshness-days',type=int,default=30)
    a=command('decision');a.add_argument('--task-id',type=int);a.add_argument('--kind',required=True);a.add_argument('--reason',required=True);a.add_argument('--outcome',required=True)
    a=command('usage');a.add_argument('--task-id',type=int,required=True);a.add_argument('--kind',choices=['estimated','measured'],required=True);a.add_argument('--input-tokens',type=int,required=True);a.add_argument('--output-tokens',type=int,required=True);a.add_argument('--cost-usd',type=float,default=0.);a.add_argument('--reference',default='')
    command('report')
    return parser

def run(command,args,conn):
    operations={'init':init,'agents':agents,'new-task':new_task,'advance':advance,'route':route,'qa':qa,
                'propose-agent':propose_agent,'agent-test':agent_test,'agent-qa':agent_qa,'approve':approve,
                'activate-agent':activate_agent,'evidence':evidence,'decision':decision,'usage':usage,'report':report}
    return operations[command](conn,args)

def main(argv=None):
    parser=build_parser();args=parser.parse_args(argv)
    if args.command=='usage' and (args.input_tokens<0 or args.output_tokens<0 or args.cost_usd<0):
        parser.error('Usage and cost values cannot be negative')
    if args.command=='evidence' and args.freshness_days<0:parser.error('Freshness days cannot be negative')
    try:
        with connect(args.db) as c: result=run(args.command,args,c)
    except (ValueError,sqlite3.IntegrityError) as e:
        print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False),file=sys.stderr);return 2
    print(json.dumps({'ok':True,'data':result},ensure_ascii=False,indent=2));return 0

if __name__=='__main__':sys.exit(main())
