"""Deterministic local observations and unranked evidence-based scorecards."""
import json
import platform
import shutil
import uuid
from datetime import timedelta
from pathlib import Path

from .roles import ROLES, DOMAINS
from .skills import skill_fingerprint
from .legacy import now
from .freshness import approved_task
from .usage import UsageLedger, BudgetService, instant
from .security import canonical

CADENCES={'daily':1,'weekly':7,'monthly':30,'quarterly':90}


class HealthRegistry:
    def __init__(self,hub):self.hub=hub;self.db=hub.db
    def audit(self,department,review_kind='weekly'):
        if department not in DOMAINS or review_kind not in CADENCES:raise ValueError('Unknown department/cadence')
        findings=[];evidence=[];versions={'python_observed':platform.python_version(),
            'project_declared':'0.5.0','external_currency':'NOT_VERIFIED_OFFLINE'}
        for name,(dept,parent,bundle) in ROLES.items():
            if dept!=department:continue
            path=self.hub.root/f'.claude/agents/{name}.md'
            if not path.is_file():findings.append({'kind':'MISSING_ROLE','agent':name,'reference':str(path.relative_to(self.hub.root))})
            else:
                text=path.read_text()
                if not text.startswith('---\n') or '\nname: '+name+'\n' not in text:findings.append({'kind':'PROFILE_METADATA','agent':name})
                evidence.append({'path':str(path.relative_to(self.hub.root)),'observation':'local profile present; existence is not proof of current guidance'})
        for skill in self.hub.skills.list():
            if department not in skill['supported_departments']:continue
            try:
                observed=skill_fingerprint(self.hub.root,skill['path'])
                if observed!=skill['fingerprint']:findings.append({'kind':'SKILL_DRIFT','skill_id':skill['id']})
            except (OSError,ValueError) as exc:findings.append({'kind':'SKILL_UNAVAILABLE','skill_id':skill['id'],'error':str(exc)})
            evidence.append({'skill_id':skill['id'],'declared_version':skill['version'],
                'last_validation_date':skill['last_validation_date'],'current_upstream_version':'UNKNOWN'})
        for tool in ['python3','git','claude']:
            executable=shutil.which(tool)
            versions[tool+'_available']=bool(executable)
            if tool=='claude' and not executable:findings.append({'kind':'RUNTIME_UNAVAILABLE','tool':tool})
        from .departments import NAMESPACE_OWNERS
        stale=[r['id'] for r in self.db.execute('SELECT * FROM memory_records') if NAMESPACE_OWNERS.get(r['namespace'],r['responsible_department'])==department and not r['superseded_by'] and (r['verification_status']!='FRESH' or not r['next_review_at'] or instant(r['next_review_at'])<=instant(now()))]
        if stale:findings.append({'kind':'KNOWLEDGE_REQUIRES_REVIEW','record_ids':stale})
        reworks=self.db.execute('SELECT COALESCE(SUM(reworks),0) FROM tasks WHERE department=?',(department,)).fetchone()[0]
        if reworks:findings.append({'kind':'QA_REWORK_HISTORY','cycles':reworks,'note':'Inspect difficulty and failure evidence before proposing an improvement.'})
        evidence.append({'department_usage':UsageLedger(self.db).summary(department=department),'research_freshness_unverified_records':len(stale),'qa_rework_cycles':reworks})
        identity=str(uuid.uuid4());at=instant(now());next_due=at+timedelta(days=CADENCES[review_kind])
        actions=[{'action':'Research and independently validate '+f['kind'],'finding':f} for f in findings]
        with self.db:self.db.execute('INSERT INTO department_health VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (identity,department,review_kind,at.isoformat(),'PARTIALLY_VERIFIED',canonical(versions),canonical(findings),
             canonical(evidence),canonical(actions),'[]','OBSERVED_UNREVIEWED',next_due.isoformat(),None))
        return self.get(identity)
    def get(self,identity):
        row=self.db.execute('SELECT * FROM department_health WHERE id=?',(identity,)).fetchone()
        if row is None:raise ValueError('Unknown health review')
        result=dict(row)
        for key in ['verified_versions','findings','evidence','corrective_actions','proposed_updates']:result[key]=json.loads(result[key])
        return result
    def approve(self,identity,qa_task_id):
        self.get(identity);approved_task(self.hub,qa_task_id,'health_review_ids',identity,'department-health-auditor')
        with self.db:self.db.execute("UPDATE department_health SET review_status='QA_REVIEWED',qa_task_id=? WHERE id=?",(qa_task_id,identity))
        return self.get(identity) # Offline evidence stays PARTIALLY_VERIFIED even after structural QA.


def scorecards(db):
    cards=[];ledger=UsageLedger(db)
    tasks=[dict(r) for r in db.execute('SELECT * FROM tasks')]
    events=[dict(r,detail=json.loads(r['detail'])) for r in db.execute('SELECT * FROM events ORDER BY id')]
    for name,(department,parent,bundle) in ROLES.items():
        owned=[t for t in tasks if t['owner']==name];ids={t['id'] for t in owned}
        reviews=[e for e in events if e['task_id'] in ids and e['kind']=='QA_RECORD']
        passed=sum(e['detail']['verdict']=='PASS' for e in reviews)
        complete=[t for t in owned if t['phase']=='COMPLETED'];durations=[]
        for task in complete:
            end=[e for e in events if e['task_id']==task['id'] and e['kind']=='TRANSITION' and e['detail'].get('to')=='COMPLETED']
            if end:durations.append((instant(end[-1]['at'])-instant(task['created_at'])).total_seconds())
        failures=[e for e in events if e['task_id'] in ids and e['kind']=='VERIFIED_TOOL_FAILURE']
        skills=sorted({r[0] for r in db.execute('SELECT DISTINCT skill_id FROM skill_usage WHERE task_id IN (SELECT id FROM tasks WHERE owner=?)',(name,))})
        cards.append({'agent':name,'department':department,'assigned':len(owned),'completed':len(complete),
            'completion_rate':len(complete)/len(owned) if owned else None,'qa_reviews':len(reviews),
            'qa_passes':passed,'qa_failures':len(reviews)-passed,'qa_pass_rate':passed/len(reviews) if reviews else None,
            'rework_cycles':sum(t['reworks'] for t in owned),'blocked':sum(t['phase'] in {'BLOCKED','ESCALATION'} for t in owned),
            'mean_completion_elapsed_seconds':sum(durations)/len(durations) if durations else None,
            'duration_basis':'intake to completion includes waiting; execution duration is separately reported in usage',
            'verified_tool_failures':len(failures),'failure_evidence':[json.loads(e['refs']) for e in failures],
            'usage':ledger.summary(agent=name),'skills_used':skills,
            'strengths':['Recorded independent QA passes'] if passed else [],
            'weaknesses':['Review corrections recorded; inspect task difficulty and evidence'] if len(reviews)>passed else [],
            'sample_caution':'Small or differently scoped samples are not comparable. No ranking or automatic role removal.',
            'difficulty_context':[json.loads(t['resource_plan']) if t['resource_plan'] else {'complexity':'UNKNOWN'} for t in owned]})
    return cards


def snapshot(db,root=None):
    tasks=[dict(r) for r in db.execute('SELECT * FROM tasks ORDER BY id DESC')]
    counts={}
    for t in tasks:counts[t['phase']]=counts.get(t['phase'],0)+1
    reviews=[dict(r,detail=json.loads(r['detail'])) for r in db.execute("SELECT * FROM events WHERE kind='QA_RECORD' ORDER BY id DESC")]
    failures={}
    for review in reviews:
        evidence=review['detail']['evidence']
        for assessment in evidence.get('criteria',[])+[dict(v,criterion=k) for k,v in evidence.get('checks',{}).items()]:
            if assessment['verdict'] in {'FAIL','BLOCKED'}:
                key=assessment['criterion'];failures[key]=failures.get(key,0)+1
    budget_rows=[]
    for row in db.execute('SELECT * FROM ai_budgets WHERE enabled=1'):
        task_id=int(row['scope_key']) if row['scope']=='TASK' else next((t['id'] for t in tasks if t['project_id']==row['scope_key']),None) if row['scope']=='PROJECT' else tasks[0]['id'] if tasks else None
        agent=row['scope_key'] if row['scope']=='AGENT' else DOMAINS[row['scope_key']] if row['scope']=='DEPARTMENT' else 'management-director'
        budget_rows.extend(b for b in BudgetService(db).evaluate(task_id,agent,'0')['budgets'] if b['id']==row['id'])
    return {'version':'0.7.0','collected_at':now(),'task_total':len(tasks),'phase_counts':counts,
        'active':sum(t['phase'] not in {'COMPLETED','CANCELLED','BLOCKED','ESCALATION'} for t in tasks),
        'completed':counts.get('COMPLETED',0),'blocked':counts.get('BLOCKED',0)+counts.get('ESCALATION',0),
        'rework_cycles':sum(t['reworks'] for t in tasks),'tasks':tasks[:500],'tasks_display_limit':500,
        'departments':[{'department':dept,'lead':lead,'tasks':sum(t['department']==dept for t in tasks),
             'active':sum(t['department']==dept and t['phase'] not in {'COMPLETED','CANCELLED','BLOCKED','ESCALATION'} for t in tasks),
             'blocked':sum(t['department']==dept and t['phase'] in {'BLOCKED','ESCALATION'} for t in tasks),
             'awaiting_qa':sum(t['department']==dept and t['phase'] in {'SUBMITTED','QA_REVIEW'} for t in tasks),
             'completed':sum(t['department']==dept and t['phase']=='COMPLETED' for t in tasks)} for dept,lead in DOMAINS.items()],
        'activity':[dict(r,detail=json.loads(r['detail'])) for r in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 50')],
        'qa':{'queue':[t['id'] for t in tasks if t['phase'] in {'SUBMITTED','QA_REVIEW'}],'reviews':reviews[:200],'review_display_limit':200,'failed_criteria_recurrences':failures},
        'usage':UsageLedger(db).summary(),'budgets':budget_rows,
        'usage_by_department':{d:UsageLedger(db).summary(department=d) for d in DOMAINS},
        'pending_budget_approvals':[dict(r) for r in db.execute("SELECT * FROM budget_approvals WHERE status='PENDING'")],
        'escalations':[t['id'] for t in tasks if t['phase']=='ESCALATION'],
        'health':[dict(r) for r in db.execute('SELECT * FROM department_health ORDER BY reviewed_at DESC LIMIT 100')],
        'freshness':[dict(r) for r in db.execute('SELECT id,title,namespace,category,verification_status,last_verified_at,next_review_at,superseded_by FROM memory_records ORDER BY updated_at DESC LIMIT 200')],
        'scheduler':{'jobs':[dict(r) for r in db.execute('SELECT * FROM maintenance_jobs')],
            'runs':[dict(r) for r in db.execute('SELECT * FROM maintenance_runs ORDER BY started_at DESC LIMIT 100')],
            'runtime':'Explicit local tick/loop required; no daemon installed. AI work is queued for authenticated Claude Code.'},
        'scorecards':scorecards(db),'changes':[dict(r) for r in db.execute('SELECT * FROM change_proposals ORDER BY created_at DESC LIMIT 100')],
        'execution':{'evidence_legend':['SIMULATED','LOCAL_TESTED','LIVE_TESTED','BLOCKED','UNVERIFIED'],
            'cost_reservations':[dict(r) for r in db.execute("SELECT * FROM usage_reservations WHERE state IN ('ACTIVE','AWAITING_TELEMETRY')")],
            'reconciliations':[dict(r) for r in db.execute('SELECT * FROM execution_reconciliations ORDER BY created_at DESC LIMIT 100')],
            'capacity':dict(db.execute("SELECT value AS concurrency_limit,updated_at FROM runtime_policies WHERE id='concurrency_limit'").fetchone()),
            'runs':[dict(r) for r in db.execute('SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT 100')],
            'invocations':[dict(r,evidence_status='SIMULATED' if r['evidence_kind']=='SIMULATED' else 'LIVE_TESTED' if r['status']=='COMPLETED' and r['reference'] else 'BLOCKED' if r['status'] in {'FAILED','INTERRUPTED'} else 'UNVERIFIED') for r in db.execute('SELECT id,run_id,task_id,agent,department,stage,cycle,status,provider,model,reference,evidence_kind,error,started_at,finished_at,duration_seconds FROM agent_invocations ORDER BY created_at DESC LIMIT 200')],
            'tools':[dict(r) for r in db.execute('SELECT * FROM runtime_tool_calls ORDER BY started_at DESC LIMIT 100')],
            'checks':[dict(r,evidence_status='LOCAL_TESTED' if r['status'] in {'PASS','FAIL'} else 'BLOCKED') for r in db.execute('SELECT * FROM workspace_checks ORDER BY started_at DESC LIMIT 100')]},
        'expansion':expansion_snapshot(db,root),
        'limitations':['Periodic local snapshot, not a live provider feed.','Operator attestations do not authenticate model identity.',
            'Unrecorded provider charges are UNKNOWN. Provider billing limits must also be configured externally.']}


def expansion_snapshot(db,root=None):
    from .connectors import CANDIDATES
    projects=[]
    for row in db.execute('SELECT * FROM projects ORDER BY created_at DESC'):
        item=dict(row,record=json.loads(row['record']))
        root_task=dict(db.execute('SELECT * FROM tasks WHERE id=?',(row['task_id'],)).fetchone())
        assigned=[dict(t) for t in db.execute('SELECT id,parent,owner,department,phase,reworks,dependencies FROM tasks WHERE project_id=?',(row['id'],))]
        item.update(phase=root_task['phase'],assigned_tasks=assigned,assigned_agents=sorted({t['owner'] for t in assigned}),
            qa_status='QA_LINKED' if row['qa_task_id'] else 'AWAITING_QA' if root_task['phase'] in {'SUBMITTED','QA_REVIEW'} else 'TASK_QA_PASSED_PROJECT_UNLINKED' if root_task['phase']=='COMPLETED' else 'NOT_SUBMITTED',usage=UsageLedger(db).summary(project_id=row['id']))
        projects.append(item)
    content=[dict(r,payload=json.loads(r['payload'])) for r in db.execute('SELECT * FROM content_items ORDER BY scheduled_at,created_at')]
    analytics=[dict(r,dataset=json.loads(r['dataset'])) for r in db.execute('SELECT * FROM analytics_observations ORDER BY collected_at DESC')]
    connectors=[dict(r,operations=json.loads(r['operations']),limitations=json.loads(r['limitations'])) for r in db.execute('SELECT * FROM connector_capabilities ORDER BY provider,runtime_id')]
    for project in projects:
        if project['kind']=='social':
            items=[i for i in content if i['project_id']==project['id']]
            project['calendar']=items;project['content_states']={state:sum(i['status']==state for i in items) for state in ['DRAFT','REVIEWED','APPROVED','SCHEDULED','PUBLISHED','FAILED','ARCHIVED']}
            project['approval_queue']=[i['id'] for i in items if i['status']=='REVIEWED']
            project['analytics']=[r for r in analytics if r['project_id']==project['id']]
            project['publishing_ready']=[i['id'] for i in items if i['status']=='APPROVED']
    handoffs=[dict(r) for r in db.execute('SELECT * FROM department_handoffs ORDER BY created_at DESC')]
    return {'web_projects':[p for p in projects if p['kind']=='web'],'social_campaigns':[p for p in projects if p['kind']=='social'],
        'content_calendar':content,'connectors':connectors,'connector_candidates':[{'provider':p,'status':'NOT_DISCOVERED'} for p in CANDIDATES if p not in {c['provider'] for c in connectors}],
        'handoffs':handoffs,'pending_handoffs':[h for h in handoffs if not h['accepted_at']],
        'action_approvals':[dict(r) for r in db.execute("SELECT * FROM action_approvals WHERE status='APPROVED'")],
        'external_actions':[dict(r) for r in db.execute('SELECT * FROM external_actions ORDER BY started_at DESC')],
        'note':'Local records and supplied data do not establish live platform publication, design edits, deployment or account analytics. Connector evidence is scoped to its recorded runtime.'}
