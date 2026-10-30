"""Runtime-scoped capability observations and exact, one-use external action gates.
No installed provider client, paid call, credentials, or shell execution is implicit.
"""
import hashlib
import json
import uuid
from datetime import timedelta

from .legacy import now,required
from .security import canonical,redact
from .usage import atomic,instant,amount
from .freshness import approved_task

STATES={'NOT_DISCOVERED','AVAILABLE_NOT_CONNECTED','CONNECTED','TESTED_READ','TESTED_WRITE','READ_ONLY','FAILED','DISABLED'}
KINDS={'read','write','publish','deploy','message','delete','paid-generation'}
CANDIDATES=['Figma','Higgsfield','Hyperframes','GitHub','Google Drive','Notion','Instagram','Facebook','TikTok','YouTube','LinkedIn','X','Pinterest','Image generation','Deployment']


def request_hash(arguments):
    if not isinstance(arguments,dict) or redact(arguments)!=arguments:raise ValueError('Use runtime credentials, never secrets in recorded action arguments')
    return hashlib.sha256(canonical(arguments).encode()).hexdigest()


class CapabilityRegistry:
    def __init__(self,hub):self.hub=hub;self.db=hub.db
    def candidates(self):return [{'provider':p,'status':'NOT_DISCOVERED'} for p in CANDIDATES]
    def get(self,runtime_id,provider):
        row=self.db.execute('SELECT * FROM connector_capabilities WHERE runtime_id=? AND provider=?',(runtime_id,provider)).fetchone()
        if row is None:raise ValueError('Connector has not been discovered in this runtime')
        result=dict(row)
        for key in ['operations','approvals','limitations']:result[key]=json.loads(result[key])
        return result
    def list(self,runtime_id=None):
        return [self.get(r['runtime_id'],r['provider']) for r in self.db.execute('SELECT runtime_id,provider FROM connector_capabilities ORDER BY runtime_id,provider') if runtime_id is None or r['runtime_id']==runtime_id]
    def discover(self,runtime_id,provider,connector_type,operations,evidence_reference,rate_limits=None,cost_limits=None,limitations=None,evidence_kind='RUNTIME_OBSERVATION'):
        for value,label in [(runtime_id,'Current runtime identity'),(provider,'Provider'),(connector_type,'Connector type'),(evidence_reference,'Actual runtime tool discovery reference')]:required(value,label)
        if evidence_kind not in {'RUNTIME_OBSERVATION','SIMULATED'}:raise ValueError('Unknown connector evidence kind')
        if not isinstance(operations,list) or not operations:raise ValueError('Discover actual available operations, not hypothetical names')
        clean=[]
        for op in operations:
            if not isinstance(op,dict) or op.get('kind') not in KINDS:raise ValueError('Each operation needs an explicit capability kind')
            required(op.get('name'),'Actual tool/operation name')
            clean.append({'name':op['name'],'kind':op['kind'],'permission':'UNKNOWN'})
        if len({o['name'] for o in clean})!=len(clean):raise ValueError('Duplicate connector operations')
        if limitations is not None and (not isinstance(limitations,list) or any(not isinstance(x,str) for x in limitations)):raise ValueError('Connector limitations must be a list of strings')
        rate_limits=canonical(rate_limits) if isinstance(rate_limits,(dict,list)) else rate_limits
        cost_limits=canonical(cost_limits) if isinstance(cost_limits,(dict,list)) else cost_limits
        notes=list(limitations or [])+['Tool names/configuration are not authentication or successful execution evidence.','Discovery reference: '+evidence_reference]
        with atomic(self.db):self.db.execute('''INSERT INTO connector_capabilities VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(runtime_id,provider) DO UPDATE SET connector_type=excluded.connector_type,status=excluded.status,
            operations=excluded.operations,authentication_status=excluded.authentication_status,approvals=excluded.approvals,
            rate_limits=excluded.rate_limits,cost_limits=excluded.cost_limits,last_successful_test=NULL,
            limitations=excluded.limitations,evidence_kind=excluded.evidence_kind,updated_at=excluded.updated_at''',
            (runtime_id,provider,connector_type,'AVAILABLE_NOT_CONNECTED',canonical(clean),'UNKNOWN',
             canonical(['Exact task/subject/arguments/destination/cost-scoped authorization for every consequential action']),
             redact(rate_limits),redact(cost_limits),None,canonical(redact(notes)),evidence_kind,now(),now()))
        return self.get(runtime_id,provider)
    def discover_tools(self,runtime_id,descriptors,evidence_reference,evidence_kind='RUNTIME_OBSERVATION'):
        required(runtime_id,'Actual current runtime identity');required(evidence_reference,'Actual runtime tool listing reference')
        if not isinstance(descriptors,list):raise ValueError('Runtime tool descriptors must be a list')
        groups={}
        for tool in descriptors:
            if not isinstance(tool,dict):raise ValueError('Malformed runtime tool descriptor')
            required(tool.get('provider'),'Observed tool provider');required(tool.get('connector_type'),'Connector type')
            groups.setdefault((tool['provider'],tool['connector_type']),[]).append({'name':tool.get('name'),'kind':tool.get('kind')})
        if len({provider for provider,_ in groups})!=len(groups):raise ValueError('A provider needs one explicit connector type per runtime observation')
        results=[]
        with atomic(self.db):
            for provider,connector_type in groups:
                results.append(self.discover(runtime_id,provider,connector_type,groups[(provider,connector_type)],evidence_reference,evidence_kind=evidence_kind))
            observed={provider for provider,_ in groups}
            for row in self.db.execute('SELECT provider FROM connector_capabilities WHERE runtime_id=?',(runtime_id,)).fetchall():
                if row['provider'] not in observed:self.db.execute("UPDATE connector_capabilities SET status='NOT_DISCOVERED',authentication_status='UNKNOWN',last_successful_test=NULL,updated_at=? WHERE runtime_id=? AND provider=?",(now(),runtime_id,row['provider']))
        return results

    def disable(self,runtime_id,provider):
        self.get(runtime_id,provider)
        with self.db:self.db.execute("UPDATE connector_capabilities SET status='DISABLED',updated_at=? WHERE runtime_id=? AND provider=?",(now(),runtime_id,provider))
        return self.get(runtime_id,provider)
    def _operation(self,record,operation):
        match=next((o for o in record['operations'] if o['name']==operation),None)
        if match is None:raise PermissionError('Operation was not discovered in this runtime')
        return match
    def test_read(self,runtime_id,provider,operation,arguments,adapter):
        record=self.get(runtime_id,provider);op=self._operation(record,operation)
        if record['status']=='DISABLED' or op['kind']!='read':raise PermissionError('Connection tests must be nonconsequential read operations')
        request_hash(arguments)
        if not callable(adapter):raise ValueError('Supply the actual authorized runtime tool adapter')
        try:
            result=adapter(operation,arguments,{'purpose':'connection-test','runtime_id':runtime_id,'provider':provider})
            if not isinstance(result,dict) or result.get('ok') is not True or result.get('authenticated') is not True:raise ValueError('Authenticated successful tool response required; config is insufficient')
            required(result.get('reference'),'Actual invocation/result reference')
            grants=result.get('granted_operations',[operation])
            if not isinstance(grants,list) or any(g not in {o['name'] for o in record['operations']} for g in grants):raise ValueError('Permission evidence exceeds discovered operations')
            for operation_record in record['operations']:operation_record['permission']='GRANTED' if operation_record['name'] in grants else 'UNKNOWN'
            status='TESTED_READ' if any(o['kind']!='read' for o in record['operations']) else 'READ_ONLY'
            with self.db:
                self.db.execute('UPDATE connector_capabilities SET status=?,operations=?,authentication_status=?,last_successful_test=?,updated_at=? WHERE runtime_id=? AND provider=?',
                    (status,canonical(record['operations']),'AUTHENTICATED_OBSERVATION',now(),now(),runtime_id,provider))
                self.db.execute('INSERT INTO connector_tests VALUES(?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),runtime_id,provider,operation,'PASS',record['evidence_kind'],redact(result['reference']),now()))
        except Exception as exc:
            with self.db:
                self.db.execute("UPDATE connector_capabilities SET status='FAILED',authentication_status='UNKNOWN',updated_at=? WHERE runtime_id=? AND provider=?",(now(),runtime_id,provider))
                self.db.execute('INSERT INTO connector_tests VALUES(?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),runtime_id,provider,operation,'FAIL',record['evidence_kind'],str(redact(str(exc)))[:1000],now()))
            raise
        return self.get(runtime_id,provider)
    def plan(self,runtime_id,provider,operation):
        try:
            record=self.get(runtime_id,provider);op=self._operation(record,operation)
        except (ValueError,PermissionError) as exc:return {'available':False,'fallback':'Prepare a local artifact or production/deployment brief','reason':str(exc)}
        ready=record['status'] in {'TESTED_READ','TESTED_WRITE','READ_ONLY'} and op['permission']=='GRANTED' and record['last_successful_test'] and instant(record['last_successful_test'])>instant(now())-timedelta(hours=1)
        return {'available':bool(ready),'evidence_kind':record['evidence_kind'],'operation':op,'status':record['status'],
                'fallback':None if ready else 'Prepare a local artifact or production/deployment brief','authentication_is_operator_observation':True}
    def authorize(self,task_id,runtime_id,provider,operation,subject_hash,destination,arguments,reference,maximum_usd,valid_minutes=60):
        task=self.hub.task(task_id)
        if task['phase']!='IN_PROGRESS' or task['migration_hold']:raise ValueError('Start a separate scoped action task through Management/preflight/budget gates first')
        for value,label in [(reference,'Actual scoped user authorization'),(destination,'Exact destination'),(subject_hash,'QA-approved subject hash')]:required(value,label)
        if len(subject_hash)!=64 or any(c not in '0123456789abcdef' for c in subject_hash):raise ValueError('Subject must be an exact SHA-256 hash')
        record=self.get(runtime_id,provider);op=self._operation(record,operation)
        if op['kind']=='read':raise ValueError('This authorization is for consequential operations')
        if not self.plan(runtime_id,provider,operation)['available']:raise PermissionError('Test connection and actual permission grants before authorizing the action')
        if type(valid_minutes) is not int or not 1<=valid_minutes<=1440:raise ValueError('Authorization lifetime must be 1..1440 minutes')
        ceiling=amount(maximum_usd);binding=request_hash(arguments);identity=str(uuid.uuid4())
        with self.db:self.db.execute('INSERT INTO action_approvals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (identity,task_id,runtime_id,provider,operation,subject_hash,redact(destination),binding,redact(reference),str(ceiling),
             (instant(now())+timedelta(minutes=valid_minutes)).isoformat(),'APPROVED',now()))
        return {'id':identity,'identity_authenticated':False,'note':'Operator attestation, not a provider billing hard cap.'}
    def execute(self,approval_id,subject_hash,destination,arguments,projected_cost,adapter):
        if not callable(adapter):raise ValueError('No configured runtime adapter; create a local deliverable instead')
        projected=amount(projected_cost);binding=request_hash(arguments)
        with atomic(self.db):
            approval=self.db.execute('SELECT * FROM action_approvals WHERE id=?',(approval_id,)).fetchone()
            if approval is None or approval['status']!='APPROVED' or instant(approval['expires_at'])<=instant(now()):raise PermissionError('A current unused scoped action authorization is required')
            if (approval['subject_hash'],approval['destination'],approval['request_hash'])!=(subject_hash,destination,binding) or projected>amount(approval['maximum_usd']):raise PermissionError('Action content, arguments, destination or cost changed since authorization')
            task=self.hub.task(approval['task_id'])
            if task['phase']!='IN_PROGRESS' or task['migration_hold']:raise ValueError('Action task must still be IN_PROGRESS')
            self.hub.check_snapshot(task)
            ready=self.plan(approval['runtime_id'],approval['provider'],approval['operation'])
            if not ready['available']:raise PermissionError('Current runtime permissions/connection are unavailable or stale')
            if ready['operation']['kind']=='publish':
                item=self.hub.social.get(arguments.get('item_id'))
                result,_=approved_task(self.hub,item['qa_task_id'],'approved_content_ids',item['id']) if item['qa_task_id'] else ({},None)
                if task['department']!='social-media' or item['status']!='APPROVED' or not item['asset_integrity'] or item['content_hash']!=subject_hash or result.get('content_hashes',{}).get(item['id'])!=subject_hash or self.hub.task(approval['task_id'])['project_id']!=item['project_id']:
                    raise PermissionError('Publication requires the unchanged independently approved campaign content')
                if arguments!=self.hub.social.publication_payload(item['id'],arguments.get('mode')=='schedule'):raise PermissionError('Publication payload differs from reviewed copy/assets')
            if ready['operation']['kind']=='deploy':
                project=self.hub.projects.get(arguments.get('project_id'))
                result,_=approved_task(self.hub,project['qa_task_id'],'approved_project_ids',project['id']) if project['qa_task_id'] else ({},None)
                if task['department']!='web-development' or project['record_hash']!=subject_hash or result.get('project_record_hashes',{}).get(project['id'])!=subject_hash or self.hub.task(approval['task_id'])['project_id']!=project['id'] or arguments!=self.hub.projects.deployment_payload(project['id']):raise PermissionError('Deployment requires exact independently reviewed project artifact bytes')
            execution=self.db.execute("SELECT * FROM task_executions WHERE task_id=? AND state='STARTED' ORDER BY started_at DESC LIMIT 1",(task['id'],)).fetchone()
            if execution is None:raise ValueError('A budget-gated invocation is required')
            hold=self.db.execute('SELECT amount_usd FROM usage_reservations WHERE execution_key=?',(execution['execution_key'],)).fetchone()
            if hold and hold[0] is not None and projected>amount(hold[0]):raise PermissionError('Action forecast exceeds its invocation reservation')
            if self.db.execute('SELECT 1 FROM external_actions WHERE execution_key=?',(execution['execution_key'],)).fetchone():raise ValueError('This invocation already attempted an external action; inspect/reconcile its receipt before further work')
            if self.db.execute("SELECT 1 FROM external_actions WHERE subject_hash=? AND destination=? AND runtime_id=? AND provider=? AND operation=? AND status IN ('STARTED','UNKNOWN_NEEDS_RECONCILIATION','VERIFIED')",(subject_hash,destination,approval['runtime_id'],approval['provider'],approval['operation'])).fetchone():raise ValueError('This subject/action already ran or needs reconciliation; do not duplicate an external side effect')
            identity=str(uuid.uuid4())
            self.db.execute('INSERT INTO external_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (identity,approval_id,task['id'],approval['runtime_id'],approval['provider'],approval['operation'],subject_hash,destination,
                 execution['execution_key'],ready['evidence_kind'],'STARTED',None,None,now(),None))
            self.db.execute("UPDATE action_approvals SET status='CONSUMED' WHERE id=?",(approval_id,))
        # Intent is durable before a side effect. Never auto-retry an ambiguous provider result.
        try:
            result=adapter(approval['operation'],arguments,{'action_id':identity,'idempotency_key':identity,'destination':destination})
            if not isinstance(result,dict) or result.get('ok') is not True or result.get('verified') is not True:raise ValueError('Actual verified provider result is required')
            required(result.get('reference'),'Provider artifact/result reference')
        except Exception as exc:
            with self.db:self.db.execute("UPDATE external_actions SET status='UNKNOWN_NEEDS_RECONCILIATION',error=?,finished_at=? WHERE id=?",(str(redact(str(exc)))[:1000],now(),identity))
            raise
        clean=redact({k:result[k] for k in ['ok','verified','reference','artifact_references','actual_cost_usd','estimated_cost_usd','usage','model'] if k in result})
        with self.db:
            self.db.execute("UPDATE external_actions SET status='VERIFIED',result=?,finished_at=? WHERE id=?",(canonical(clean),now(),identity))
            self.db.execute("UPDATE connector_capabilities SET status='TESTED_WRITE',last_successful_test=?,updated_at=? WHERE runtime_id=? AND provider=?",(now(),now(),approval['runtime_id'],approval['provider']))
            self.hub.event(task['id'],'EXTERNAL_ACTION_RESULT',{'action_id':identity,'reference':clean['reference'],'evidence_kind':ready['evidence_kind']},task['owner'])
        telemetry_warning=None
        usage=result.get('usage',{})
        entry={'task_id':task['id'],'agent':task['owner'],'provider':approval['provider'],'model':result.get('model','non-model:'+approval['operation']),
            'invocation_id':identity,'execution_key':execution['execution_key'],'source':clean['reference'],'token_kind':'UNKNOWN',
            'duration_seconds':str((instant(now())-instant(self.db.execute('SELECT started_at FROM external_actions WHERE id=?',(identity,)).fetchone()[0])).total_seconds())}
        if isinstance(usage,dict) and any(usage.get(k) is not None for k in ['input_tokens','output_tokens','cache_read_tokens','cache_write_tokens']):
            entry.update({k:usage.get(k) for k in ['input_tokens','output_tokens','cache_read_tokens','cache_write_tokens']});entry['token_kind']='ESTIMATED' if ready['evidence_kind']=='SIMULATED' else 'MEASURED'
        entry['actual_cost']=result.get('actual_cost_usd') if ready['evidence_kind']!='SIMULATED' else None
        entry['estimated_cost']=result.get('estimated_cost_usd',result.get('actual_cost_usd') if ready['evidence_kind']=='SIMULATED' else None)
        try:self.hub.usage.record(entry)
        except (ValueError,TypeError) as exc:
            telemetry_warning='Provider receipt retained; telemetry rejected: '+str(redact(str(exc)))
            self.hub.usage.record({k:v for k,v in entry.items() if k not in {'input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','actual_cost','estimated_cost','token_kind'} }|{'token_kind':'UNKNOWN'})
        return {'id':identity,'status':'VERIFIED','result':clean,'evidence_kind':ready['evidence_kind'],'telemetry_warning':telemetry_warning}

    def reconcile(self,action_id,read_operation,arguments,adapter):
        row=self.db.execute('SELECT * FROM external_actions WHERE id=?',(action_id,)).fetchone()
        if row is None or row['status'] not in {'STARTED','UNKNOWN_NEEDS_RECONCILIATION'}:raise ValueError('Only unresolved actions require reconciliation')
        record=self.get(row['runtime_id'],row['provider']);op=self._operation(record,read_operation)
        if op['kind']!='read' or not self.plan(row['runtime_id'],row['provider'],read_operation)['available']:raise PermissionError('Use a currently permitted read-only verification operation')
        request_hash(arguments)
        if not callable(adapter):raise ValueError('Actual read adapter required')
        result=adapter(read_operation,arguments,{'purpose':'reconciliation','action_id':action_id,'subject_hash':row['subject_hash']})
        if not isinstance(result,dict) or result.get('authenticated') is not True or result.get('verified') is not True or result.get('subject_hash')!=row['subject_hash'] or result.get('state') not in {'NOT_APPLIED','PUBLISHED','SCHEDULED','APPLIED'}:raise ValueError('Actual exact-subject verification evidence is required')
        required(result.get('reference'),'Actual reconciliation reference')
        state='FAILED_NOT_APPLIED' if result['state']=='NOT_APPLIED' else 'VERIFIED'
        with atomic(self.db):
            self.db.execute('UPDATE external_actions SET status=?,result=?,error=NULL,finished_at=? WHERE id=?',(state,canonical(redact(result)),now(),action_id))
            if row['evidence_kind']!='SIMULATED' and result['state']=='NOT_APPLIED':
                for item in self.db.execute('SELECT id FROM content_items WHERE content_hash=?',(row['subject_hash'],)).fetchall():
                    self.db.execute("UPDATE content_items SET status='FAILED',revision=revision+1,updated_at=? WHERE id=?",(now(),item['id']))
                    self.hub.social._history(self.hub.social.get(item['id']),'social-platform-integration-specialist','Actual read verified no external publication; draft correction/reapproval required')
            if row['evidence_kind']!='SIMULATED' and result['state'] in {'PUBLISHED','SCHEDULED'}:
                for item in self.db.execute('SELECT id FROM content_items WHERE content_hash=?',(row['subject_hash'],)).fetchall():
                    current=self.hub.social.get(item['id'])
                    if not current['asset_integrity']:raise ValueError('Local content bytes changed; preserve receipt and reconcile the conflicting version manually')
                    self.db.execute('UPDATE content_items SET status=?,remote_reference=?,revision=revision+1,updated_at=? WHERE id=?',(result['state'],redact(result['reference']),now(),item['id']))
                    self.hub.social._history(self.hub.social.get(item['id']),'social-platform-integration-specialist','Verified reconciliation '+action_id)
        return {'id':action_id,'status':state,'evidence_kind':row['evidence_kind'],'automatic_retry':False}
