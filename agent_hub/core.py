"""v0.4 management-led control plane with local intelligence and budget gates."""
import hashlib
import json
from pathlib import Path

from .legacy import Hub as LegacyHub, ROOT, now, required, validate_sources, digest
from .roles import ROLES, DOMAINS, DEPARTMENT_NAMESPACE
from .migrations import migrate, backup
from .memory import MemoryVault, initialize as initialize_memory
from .skills import SkillRegistry
from .security import redact, canonical

QA_CHECKS = ('completeness', 'functional_correctness', 'accuracy_evidence', 'output_quality',
             'user_instructions', 'security_permissions', 'skill_use', 'source_freshness',
             'reproducibility', 'missing_requirements', 'artifact_integrity')
PHASES = ('CREATED', 'MANAGEMENT_REVIEW', 'PLANNED', 'ASSIGNED', 'PREFLIGHT', 'IN_PROGRESS',
          'SUBMITTED', 'QA_REVIEW', 'COMPLETED', 'BLOCKED', 'ESCALATION', 'CANCELLED')
TRANSITIONS = {
    'CREATED': {'MANAGEMENT_REVIEW'}, 'MANAGEMENT_REVIEW': {'PLANNED'},
    'PLANNED': {'ASSIGNED'}, 'ASSIGNED': {'PREFLIGHT'}, 'PREFLIGHT': {'IN_PROGRESS'},
    'IN_PROGRESS': {'SUBMITTED'}, 'SUBMITTED': {'QA_REVIEW'},
    'QA_REVIEW': {'COMPLETED', 'ASSIGNED'}, 'BLOCKED': {'ESCALATION'},
    'ESCALATION': {'MANAGEMENT_REVIEW'}, 'COMPLETED': set(), 'CANCELLED': set(),
}


class Hub(LegacyHub):
    def __init__(self, db, root=ROOT):
        super().__init__(db, root)
        try:
            self.migration = migrate(self.db, db)
            initialize_memory(self.db)
            self.memory = MemoryVault(self.db,self.root)
            self.skills = SkillRegistry(self.db, self.root)
            from .usage import UsageLedger, BudgetService
            from .freshness import FreshnessAuditor, ResearchCache
            from .monitoring import HealthRegistry
            self.usage=UsageLedger(self.db);self.budgets=BudgetService(self.db)
            self.freshness=FreshnessAuditor(self);self.health=HealthRegistry(self);self.research_cache=ResearchCache(self)
            from .scheduler import Scheduler
            from .improvements import Improvements
            self.scheduler=Scheduler(self);self.scheduler.seed();self.improvements=Improvements(self)
        except Exception:
            self.db.close()
            raise

    def event(self, task, kind, detail, actor=None, refs=None):
        if actor is None:
            row = self.db.execute('SELECT owner FROM tasks WHERE id=?', (task,)).fetchone()
            actor = row['owner'] if row else 'master-agent'
        if actor not in ROLES and actor != 'USER':
            raise ValueError('Unknown event actor')
        if refs is None:
            refs = ['task://' + str(task)]
            if isinstance(detail, dict):
                refs += detail.get('artifacts', [])
                refs += [s['location'] for s in detail.get('sources', []) if isinstance(s, dict) and 'location' in s]
        self.db.execute('INSERT INTO events(task_id,kind,detail,at,actor,refs) VALUES(?,?,?,?,?,?)',
            (task, kind, canonical(redact(detail)), now(), actor, canonical(redact(refs))))

    def _move(self, task_id, destination, evidence, actor):
        required(evidence, 'Transition evidence')
        task = self.task(task_id)
        if destination not in PHASES:
            raise ValueError('Unknown task phase')
        allowed = TRANSITIONS[task['phase']] | ({'BLOCKED', 'CANCELLED'} if task['phase'] not in {'COMPLETED', 'CANCELLED', 'BLOCKED'} else set())
        if destination not in allowed:
            raise ValueError(f"Illegal task transition {task['phase']} -> {destination}")
        status = {'CREATED': 'QUEUED', 'MANAGEMENT_REVIEW': 'QUEUED', 'PLANNED': 'QUEUED',
                  'ASSIGNED': 'REWORK' if task['reworks'] else 'QUEUED', 'PREFLIGHT': 'DISPATCHED',
                  'IN_PROGRESS': 'DISPATCHED', 'SUBMITTED': 'QA', 'QA_REVIEW': 'QA',
                  'COMPLETED': 'COMPLETED', 'BLOCKED': 'BLOCKED', 'ESCALATION': 'BLOCKED',
                  'CANCELLED': 'CANCELLED'}[destination]
        self.db.execute('UPDATE tasks SET phase=?,status=?,updated_at=? WHERE id=?',
                        (destination, status, now(), task_id))
        self.event(task_id, 'TRANSITION', {'from': task['phase'], 'to': destination, 'evidence': evidence}, actor)

    def create(self, request, criteria, domain='management', agent=None, mode='research', parent=None,
               cycle_limit=3, idempotency_key=None):
        from .usage import atomic
        if type(cycle_limit) is not int or not 1<=cycle_limit<=20:raise ValueError('QA escalation threshold must be 1..20')
        required(request,'Request');required(criteria,'Acceptance criteria')
        if mode not in {'research','paper'} or domain not in DOMAINS:raise ValueError('Unknown department or unsupported execution mode')
        owner=agent or DOMAINS[domain]
        if owner not in ROLES:raise ValueError('Unknown agent')
        request,criteria=redact(request),redact(criteria)
        if idempotency_key is not None:required(idempotency_key,'Idempotency key')
        with atomic(self.db):
            if self.db.execute("SELECT 1 FROM change_proposals WHERE status IN ('ACTIVATING','ROLLING_BACK') LIMIT 1").fetchone():raise ValueError('Recover the interrupted instruction update before creating work')
            if idempotency_key is not None:
                existing=self.db.execute('SELECT * FROM tasks WHERE idempotency_key=?',(idempotency_key,)).fetchone()
                if existing:
                    if (existing['request'],existing['criteria'],existing['parent'],existing['mode'],existing['requested_owner'])!=(request,criteria,parent,mode,owner):raise ValueError('Idempotency key conflicts with a different request')
                    return dict(existing)
            if parent is not None and self.task(parent)['status'] in {'COMPLETED','CANCELLED','BLOCKED'}:raise ValueError('Cannot add work to a closed parent')
            department=ROLES[owner][0]
            cur=self.db.execute("""INSERT INTO tasks(request,criteria,owner,mode,parent,status,created_at,updated_at,
                department,requested_owner,cycle_limit,idempotency_key) VALUES(?,?,?,?,?,'QUEUED',?,?,?,?,?,?)""",
                (request,criteria,owner,mode,parent,now(),now(),department,owner,cycle_limit,idempotency_key))
            self.event(cur.lastrowid,'CREATED',{'owner':owner})
            self.event(cur.lastrowid,'MANAGEMENT_INTAKE',{'requested_owner':owner,'department':department,'criteria':criteria},'master-agent')
        return self.task(cur.lastrowid)

    def management_review(self, task_id, analysis, actor='management-director'):
        if actor != 'management-director':
            raise PermissionError('Management must analyze the task before planning')
        required(analysis, 'Management analysis')
        with self.db:
            self._move(task_id, 'MANAGEMENT_REVIEW', analysis, actor)
        return self.task(task_id)

    def _check_graph(self, task_id, dependencies):
        if not isinstance(dependencies, list) or any(type(i) is not int for i in dependencies) or len(set(dependencies)) != len(dependencies):
            raise ValueError('Dependencies must be unique task IDs')
        tasks = {r['id']: dict(r) for r in self.db.execute('SELECT * FROM tasks')}
        if any(i not in tasks or i == task_id for i in dependencies):
            raise ValueError('Dependencies must reference other existing tasks')
        graph = {i: json.loads(t['dependencies']) for i, t in tasks.items()}
        graph[task_id] = dependencies
        for i, task in tasks.items():
            if task['parent'] is not None:
                graph[task['parent']].append(i)
        visiting, finished = set(), set()
        def visit(i):
            if i in visiting:
                raise ValueError('Dependency/parent cycle detected')
            if i in finished:
                return
            visiting.add(i)
            for dependency in graph[i]:
                visit(dependency)
            visiting.remove(i); finished.add(i)
        for i in graph:
            visit(i)

    def plan(self, task_id, plan, actor='management-director'):
        task = self.task(task_id)
        if actor != 'management-director' or task['phase'] != 'MANAGEMENT_REVIEW':
            raise ValueError('A Management review must precede planning')
        if not isinstance(plan, dict):
            raise ValueError('Management plan must be an object')
        owner = plan.get('owner', task['requested_owner'])
        if task['requested_owner'] and owner != task['requested_owner']:
            raise ValueError('Honor the requested department/agent; create a scoped child task for other work')
        self.skills.require(plan.get('selected_skills'), owner)
        required(plan.get('rationale'), 'Management research and assignment rationale')
        criteria = plan.get('acceptance_criteria')
        if not isinstance(criteria, list) or not criteria or any(not isinstance(s, str) or not s.strip() for s in criteria):
            raise ValueError('Measurable acceptance criteria are required')
        plan = dict(plan, acceptance_criteria=list(dict.fromkeys([task['criteria']] + criteria)))
        priority = plan.get('priority', 'normal')
        if priority not in {'low', 'normal', 'high', 'urgent'}:
            raise ValueError('Unknown task priority')
        dependencies = plan.get('dependencies', [])
        self._check_graph(task_id, dependencies)
        resource=plan.get('resource_plan',{'complexity':'UNKNOWN','team':[owner], 'rationale':'Single assigned specialist; expand only for a documented capability gap.'})
        if not isinstance(resource,dict) or resource.get('complexity') not in {'UNKNOWN','simple','moderate','complex'} or resource.get('team')!=[owner]:
            raise ValueError('Plan one accountable specialist; use scoped child tasks for additional specialists')
        required(resource.get('rationale'),'Smallest qualified team rationale')
        plan.update(owner=owner, priority=priority, dependencies=dependencies,resource_plan=resource)
        with self.db:
            self.db.execute('''UPDATE tasks SET owner=?,department=?,selected_skills=?,dependencies=?,
                priority=?,management_plan=?,resource_plan=?,migration_hold=0 WHERE id=?''',
                (owner, ROLES[owner][0], canonical(plan['selected_skills']), canonical(dependencies),
                 priority, canonical(redact(plan)), canonical(redact(resource)), task_id))
            self._move(task_id, 'PLANNED', plan['rationale'], actor)
            self.event(task_id, 'MANAGEMENT_PLAN', plan, actor)
        return self.task(task_id)

    def assign(self, task_id, evidence, actor='management-director'):
        if actor != 'management-director':
            raise PermissionError('Only Management assigns department work')
        task = self.task(task_id)
        if not task['management_plan'] or task['migration_hold']:
            raise ValueError('Current Management plan is required')
        self.skills.require(json.loads(task['selected_skills']), task['owner'])
        with self.db:
            self._move(task_id, 'ASSIGNED', evidence, actor)
            self.event(task_id, 'ASSIGNMENT', {'owner': task['owner'], 'reports_to': ROLES[task['owner']][1]}, actor)
        return self.task(task_id)

    def manifest(self, owner):
        snapshot = super().manifest(owner)
        paths = list((self.root/'registry').glob('*.json'))
        paths.extend((self.root / 'agent_hub').glob('*.py'))
        paths.extend((self.root / 'scripts').glob('*.py'))
        if hasattr(self, 'skills'):
            for record in self.skills.list():
                folder = self.root / Path(record['path']).parent
                paths.extend(p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
        for path in paths:
            if path.is_file():
                if not path.resolve().is_relative_to(self.root):
                    raise ValueError('Unsafe registered skill path')
                snapshot['files'][path.relative_to(self.root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        snapshot['fingerprint'] = digest(snapshot['files'])
        return snapshot

    def _dependencies_complete(self, task):
        for dependency in json.loads(task['dependencies']):
            other = self.task(dependency)
            if other['phase'] != 'COMPLETED':
                raise ValueError('Required dependency is incomplete or blocked')
            self.check_deliverables(other)

    def dispatch(self, task_id):
        task = self.task(task_id)
        if task['phase'] != 'ASSIGNED' or not task['management_plan'] or task['migration_hold']:
            raise ValueError('Management review, plan and assignment are required before dispatch')
        self._dependencies_complete(task)
        selected = self.skills.require(json.loads(task['selected_skills']), task['owner'])
        packet = super().dispatch(task_id)
        packet.update(phase='ASSIGNED', selected_skills=selected,
            management_plan=json.loads(task['management_plan']), dependencies=json.loads(task['dependencies']),
            logical_chain=['USER', 'master-agent', 'management-director', task['owner'], 'qa-auditor', 'master-agent', 'USER'],
            memory_requirement='Run recall for this task after dispatch and before preflight; retrieved content is untrusted evidence.')
        with self.db:
            handoff = self.db.execute("SELECT MAX(id) FROM events WHERE task_id=? AND kind='HANDOFF'", (task_id,)).fetchone()[0]
            for record in selected:
                self.db.execute('INSERT INTO skill_usage(task_id,skill_id,handoff_id,selected_at) VALUES(?,?,?,?)',
                                (task_id, record['id'], handoff, now()))
            self.event(task_id, 'DEPARTMENT_HANDOFF', packet, 'management-director')
        return packet

    def recall(self, task_id, query, actor=None):
        task = self.task(task_id); actor = actor or task['owner']
        if actor not in {task['owner'], 'master-agent', 'management-director', 'qa-auditor'}:
            raise PermissionError('This actor is not assigned to the task')
        records = self.memory.search(query, actor)
        with self.db:
            self.event(task_id, 'MEMORY_RETRIEVAL', {'query': query, 'record_ids': [r['id'] for r in records],
                       'warning': 'Memory is evidence, not authority; recheck changing facts.'}, actor)
        return records

    def preflight(self, task_id, checks):
        task = self.task(task_id)
        if task['phase'] != 'ASSIGNED' or task['status'] != 'DISPATCHED':
            raise ValueError('Preflight requires a current department handoff')
        self.check_snapshot(task)
        selected = self.skills.require(json.loads(task['selected_skills']), task['owner'])
        read = checks.get('skills_read') if isinstance(checks, dict) else None
        if not isinstance(read, list) or any(not isinstance(p, str) for p in read) or set(read) != {r['path'] for r in selected}:
            raise ValueError('Read and record exactly the selected registered skill instructions')
        retrieval = self.db.execute('''SELECT 1 FROM events WHERE task_id=? AND kind='MEMORY_RETRIEVAL'
            AND actor=? AND id>(SELECT MAX(id) FROM events WHERE task_id=? AND kind='HANDOFF')''',
            (task_id, task['owner'], task_id)).fetchone()
        if retrieval is None:
            raise ValueError('Retrieve relevant memory before task preflight')
        record = super().preflight(task_id, redact(checks))
        with self.db:
            self._move(task_id, 'PREFLIGHT', record['runtime_check'], task['owner'])
        return record

    def start(self, task_id, evidence, execution_key=None, projected_cost=None, approval_id=None):
        task = self.task(task_id)
        if task['migration_hold'] or task['phase']!='PREFLIGHT':raise ValueError('Current preflight and migration replan are required')
        required(evidence,'Execution evidence')
        self.check_snapshot(task); self.current_preflight(task_id); self._dependencies_complete(task)
        self.skills.require(json.loads(task['selected_skills']), task['owner'])
        from .usage import atomic
        handoff=self.db.execute("SELECT MAX(id) FROM events WHERE task_id=? AND kind='HANDOFF'",(task_id,)).fetchone()[0]
        execution_key=execution_key or f'task:{task_id}:handoff:{handoff}'
        with atomic(self.db):
            if self.db.execute('SELECT 1 FROM task_executions WHERE task_id=? AND handoff_id=?',(task_id,handoff)).fetchone():raise ValueError('Duplicate task execution')
            allowed=self.budgets.reserve(task_id,task['owner'],execution_key,projected_cost,approval_id)
            if allowed['allowed']:
                self.db.execute('INSERT INTO task_executions VALUES(?,?,?,?,?,?,?)',(execution_key,task_id,handoff,task['owner'],'STARTED',now(),None))
                self._move(task_id, 'IN_PROGRESS', evidence, task['owner'])
                self.event(task_id,'RESOURCE_GATE',allowed,task['owner'])
        if not allowed['allowed']:raise ValueError('AI budget authorization required: '+allowed['approval_id'])
        return self.task(task_id)

    def submit(self, task_id, result):
        task = self.task(task_id)
        if task['migration_hold'] or task['phase'] != 'IN_PROGRESS':
            raise ValueError('Complete task preflight and start before submitting department artifacts')
        self.skills.require(json.loads(task['selected_skills']), task['owner'])
        if not isinstance(result, dict):
            raise ValueError('Result must be an object')
        result = dict(result)
        authors = result.get('authors', [task['owner']])
        if not isinstance(authors, list) or task['owner'] not in authors or any(a not in ROLES for a in authors):
            raise ValueError('Record the owner and all contributing authors')
        result['authors'] = authors
        used = result.get('skills_used', json.loads(task['selected_skills']))
        if not isinstance(used, list) or set(used) != set(json.loads(task['selected_skills'])):
            raise ValueError('Result must account for the selected skills used')
        result['skills_used'] = used
        super().submit(task_id, redact(result))
        with self.db:
            self.db.execute("UPDATE task_executions SET state='SUBMITTED',finished_at=? WHERE task_id=? AND state='STARTED'",(now(),task_id))
            self.db.execute("UPDATE usage_reservations SET state='AWAITING_TELEMETRY' WHERE task_id=? AND state='ACTIVE'",(task_id,))
            self._move(task_id, 'SUBMITTED', 'Existing artifacts and source evidence accepted for review', task['owner'])
            self._move(task_id, 'QA_REVIEW', 'Queued for separate independent QA; no review implied', 'management-director')
            self.db.execute('UPDATE skill_usage SET used_at=? WHERE task_id=? AND handoff_id=(SELECT MAX(id) FROM events WHERE task_id=? AND kind=?)',
                            (now(), task_id, task_id, 'HANDOFF'))
        return self.task(task_id)

    def _qa_evidence(self, task, verdict, evidence):
        if not isinstance(evidence, dict):
            raise ValueError('Structured QA evidence is required')
        required(evidence.get('review_reference'), 'Actual independent review invocation reference')
        expected = json.loads(task['management_plan'])['acceptance_criteria']
        criteria = evidence.get('criteria')
        if not isinstance(criteria, list) or any(not isinstance(r, dict) for r in criteria):
            raise ValueError('QA must assess each acceptance criterion')
        if len(criteria) != len(expected) or {r.get('criterion') for r in criteria} != set(expected):
            raise ValueError('QA omitted or duplicated an original acceptance criterion')
        checks = evidence.get('checks')
        if not isinstance(checks, dict) or set(checks) != set(QA_CHECKS):
            raise ValueError('QA must assess every required quality/security check')
        rows = criteria + list(checks.values())
        for row in rows:
            if not isinstance(row, dict) or row.get('verdict') not in {'PASS', 'FAIL', 'BLOCKED', 'NOT_APPLICABLE'}:
                raise ValueError('Malformed QA criterion verdict')
            if not isinstance(row.get('evidence'), list) or not row['evidence'] or any(not isinstance(x, str) or not x.strip() for x in row['evidence']):
                raise ValueError('Each QA assessment needs supporting evidence references')
            if row['verdict'] in {'FAIL', 'BLOCKED'}:
                required(row.get('correction'), 'Precise correction/blocker diagnosis')
            if row['verdict'] == 'NOT_APPLICABLE':
                required(row.get('reason'), 'Why the check is not applicable')
        if any(r['verdict'] == 'NOT_APPLICABLE' for r in criteria):
            raise ValueError('Acceptance criteria cannot be skipped')
        tests = evidence.get('tests')
        if not isinstance(tests, list):
            raise ValueError('QA tests must be a list')
        for test in tests:
            if not isinstance(test, dict) or test.get('result') not in {'PASS', 'FAIL'}:
                raise ValueError('Malformed QA test evidence')
            required(test.get('command'), 'Test/check performed'); required(test.get('reference'), 'Actual test result reference')
        if not tests:
            required(evidence.get('test_rationale'), 'Explain why executable tests do not apply')
        failed = [r for r in rows if r['verdict'] in {'FAIL', 'BLOCKED'}]
        if verdict == 'PASS' and (failed or any(t['result'] != 'PASS' for t in tests)):
            raise ValueError('QA cannot PASS failed checks or tests')
        if verdict != 'PASS' and not failed and not any(t['result'] == 'FAIL' for t in tests):
            raise ValueError('REWORK/BLOCKED must identify actual failed criteria, checks or tests')
        return evidence

    def review(self, task_id, reviewer, verdict, notes, evidence=None):
        task = self.task(task_id)
        if task['migration_hold'] or task['phase'] != 'QA_REVIEW' or reviewer != 'qa-auditor' or task['owner'] == reviewer:
            raise ValueError('Independent qa-auditor review of a QA task is required')
        result = json.loads(task['result'])
        if reviewer in result['authors']:
            raise ValueError('A contributing author cannot independently approve the output')
        if verdict not in {'PASS', 'REWORK', 'BLOCKED'}:
            raise ValueError('Unknown QA verdict')
        required(notes, 'Review evidence and notes')
        evidence = self._qa_evidence(task, verdict, evidence)
        if verdict == 'PASS':
            self.skills.require(json.loads(task['selected_skills']), task['owner'])
            self.check_deliverables(task); self._dependencies_complete(task)
        cycles = task['reworks'] + (verdict == 'REWORK')
        with self.db:
            self.db.execute('UPDATE tasks SET reworks=? WHERE id=?', (cycles, task_id))
            self.event(task_id, 'QA_RECORD', {'reviewer': reviewer, 'verdict': verdict, 'notes': notes,
                       'evidence': evidence, 'identity_authenticated': False}, reviewer)
            if verdict == 'PASS':
                self._move(task_id, 'COMPLETED', notes, reviewer)
                namespace = DEPARTMENT_NAMESPACE.get(task['department'], task['department'])
                stored = self.memory.put(namespace, 'approved-task-outcome', task['request'],
                    {'summary': result['summary'], 'artifacts': result['artifacts'],
                     'artifact_hashes': result['artifact_hashes'], 'limitations': result['limitations'],
                     'lessons': result.get('lessons', []), 'review_reference': evidence['review_reference']},
                    'master-agent', sources=result['sources'], task_id=task_id,
                    confidence='QA_APPROVED_OPERATOR', commit=False)
                self.event(task_id, 'MEMORY_STORED', {'record_id': stored['id'], 'namespace': namespace},
                           'master-agent', ['memory://' + stored['id']])
            elif verdict == 'BLOCKED' or cycles >= task['cycle_limit']:
                self._move(task_id, 'BLOCKED', notes, reviewer)
                self._move(task_id, 'ESCALATION', 'Unresolved issue requires diagnosis and scoped authorization', 'management-director')
            else:
                self._move(task_id, 'ASSIGNED', notes, 'management-director')
                self.event(task_id, 'REWORK_REQUEST', {'owner': task['owner'], 'corrections': evidence,
                           'cycle': cycles, 'threshold': task['cycle_limit']}, 'management-director')
        return self.task(task_id)

    def resume(self, task_id, diagnosis, authorization_reference, cycle_limit=None):
        task = self.task(task_id)
        if task['phase'] != 'ESCALATION':
            raise ValueError('Only escalated work can be resumed')
        required(diagnosis, 'Escalation diagnosis'); required(authorization_reference, 'Actual scoped user authorization reference')
        limit = cycle_limit if cycle_limit is not None else task['cycle_limit']
        if not isinstance(limit, int) or not task['reworks'] < limit <= 20:
            raise ValueError('Resumption threshold must exceed failures and be at most 20')
        with self.db:
            self.db.execute('UPDATE tasks SET cycle_limit=? WHERE id=?', (limit, task_id))
            self._move(task_id, 'MANAGEMENT_REVIEW', diagnosis, 'management-director')
            self.event(task_id, 'RESUME_AUTHORIZATION', {'diagnosis': diagnosis,
                'authorization_reference': authorization_reference, 'cycle_limit': limit,
                'identity_authenticated': False}, 'management-director')
        return self.task(task_id)

    def request_capability(self, task_id, capability, evidence):
        from .skill_finder import SkillFinderAdapter
        required(capability, 'Missing capability'); required(evidence, 'Capability gap evidence')
        with self.db:
            self._move(task_id, 'BLOCKED', evidence, 'management-director')
            self._move(task_id, 'ESCALATION', 'Agent Development & Research must validate a missing skill', 'management-director')
            self.event(task_id, 'CAPABILITY_REQUEST', {'capability': capability,
                'assigned_to': 'agent-creator-researcher', 'finder': SkillFinderAdapter().search(capability)}, 'management-director')
        return self.task(task_id)

    def record(self, task_id, actor, kind, summary, refs=None):
        task = self.task(task_id)
        if actor not in {task['owner'], 'master-agent', 'management-director', 'qa-auditor'}:
            raise PermissionError('Actor is not responsible for this task')
        if kind not in {'RESEARCH', 'DECISION', 'TEST', 'CORRECTION', 'ERROR', 'BLOCKER', 'AUTHORIZATION'}:
            raise ValueError('Unknown operational event type')
        required(summary, 'Action summary')
        if refs is not None and (not isinstance(refs, list) or any(not isinstance(r, str) for r in refs)):
            raise ValueError('Event references must be a list of strings')
        with self.db:
            self.event(task_id, kind, {'summary': summary}, actor, refs)

    def history(self, task_id):
        self.task(task_id)
        return [dict(r, detail=json.loads(r['detail']), refs=json.loads(r['refs']))
                for r in self.db.execute('SELECT * FROM events WHERE task_id=? ORDER BY id', (task_id,))]

    def cancel(self, task_id, reason):
        with self.db:
            self._move(task_id, 'CANCELLED', reason, 'management-director')
        return self.task(task_id)

    def report(self):
        report = super().report()
        report.update(version='0.4.0', phase_counts={p: sum(t['phase'] == p for t in report['tasks']) for p in PHASES},
                      management_required=True, memory_provider='local SQLite system of record',
                      external_memory_sync='Markdown adapter available; Notion unimplemented/unconfigured')
        from .monitoring import snapshot
        report['intelligence']=snapshot(self.db)
        return report

    def replan_migrated(self,task_id,evidence):
        required(evidence,'Migration replan rationale')
        task=self.task(task_id)
        if not task['migration_hold']:raise ValueError('Task has no migration hold')
        with self.db:
            self.db.execute("UPDATE tasks SET phase='MANAGEMENT_REVIEW',status='QUEUED',management_plan=NULL,updated_at=? WHERE id=?",(now(),task_id))
            self.event(task_id,'MIGRATION_REPLAN',{'from':task['phase'],'evidence':evidence},'management-director')
        return self.task(task_id)

    def verified_tool_failure(self,task_id,tool,diagnosis,reference):
        required(tool,'Failed tool');required(diagnosis,'Observed failure');required(reference,'Actual tool failure evidence')
        task=self.task(task_id)
        with self.db:self.event(task_id,'VERIFIED_TOOL_FAILURE',{'tool':tool,'diagnosis':diagnosis,'operator_attested':True},task['owner'],[reference])

    def backup(self, destination):
        return backup(self.db, destination)
