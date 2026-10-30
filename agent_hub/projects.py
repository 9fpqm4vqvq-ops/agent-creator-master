"""Persistent project/campaign briefs, scoped handoffs and real local software outputs."""
import hashlib
import html
import json
import uuid
from pathlib import Path

from .legacy import now,required,validate_sources
from .roles import ROLES,DOMAINS
from .security import canonical,redact,safe_file
from .usage import atomic
from .freshness import approved_task

FIELDS={'requirements','constraints','milestones','risks','technology_decisions','research_status','design_status','implementation_status',
        'test_results','defects','deployment_readiness','deliverables','objectives','audience','brand'}


def write_artifacts(root,folder,files):
    root=Path(root).resolve();directory=root/'outputs'/folder
    if not directory.resolve().is_relative_to(root) or any(p.is_symlink() for p in [root/'outputs',directory]):raise ValueError('Unsafe output directory')
    paths=[]
    for name,content in files.items():
        target=directory/name
        if Path(name).is_absolute() or '..' in Path(name).parts or not target.resolve().is_relative_to(directory.resolve()) or target.is_symlink():raise ValueError('Unsafe artifact path')
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_text()!=content:raise ValueError('Existing output differs; use a new revision rather than overwriting it')
        target.write_text(content);paths.append(target.relative_to(root).as_posix())
    return paths


class ProjectService:
    def __init__(self,hub):self.hub=hub;self.db=hub.db
    def create(self,title,brief,criteria,kind='web',constraints=None):
        for value,label in [(title,'Project title'),(brief,'Project brief'),(criteria,'Project acceptance criteria')]:required(value,label)
        if kind not in {'web','social'}:raise ValueError('Project kind must be web or social')
        identity=str(uuid.uuid4());department='web-development' if kind=='web' else 'social-media'
        record={'requirements':[criteria],'constraints':constraints or [],'milestones':[],'risks':[],
            'technology_decisions':[],'research_status':'UNVERIFIED','design_status':'NOT_STARTED',
            'implementation_status':'NOT_STARTED','test_results':[],'defects':[],
            'deployment_readiness':'NOT_REVIEWED','deliverables':[]}
        with atomic(self.db):
            task=self.hub.create(title+': '+brief,criteria,domain=department,idempotency_key='project-root:'+identity)
            self.db.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?,?)',(identity,task['id'],kind,redact(title),redact(brief),canonical(redact(record)),1,None,now(),now()))
            self.db.execute('UPDATE tasks SET project_id=? WHERE id=?',(identity,task['id']))
            self.db.execute('INSERT INTO project_history VALUES(?,?,?,?,?)',(identity,1,canonical(record),'management-director',now()))
        return self.get(identity)
    def get(self,identity):
        row=self.db.execute('SELECT * FROM projects WHERE id=?',(identity,)).fetchone()
        if row is None:raise ValueError('Unknown project')
        result=dict(row,record=json.loads(row['record']))
        manifest={}
        for path in result['record'].get('deliverables',[]):
            manifest[path]=hashlib.sha256(safe_file(self.hub.root,path).read_bytes()).hexdigest()
        result['artifact_hashes']=manifest
        result['record_hash']=hashlib.sha256(canonical({k:result[k] for k in ['id','kind','title','brief','record','artifact_hashes']}).encode()).hexdigest()
        result['phase']=self.hub.task(row['task_id'])['phase']
        return result
    def list(self,kind=None):return [self.get(r['id']) for r in self.db.execute('SELECT id,kind FROM projects ORDER BY created_at DESC') if kind is None or r['kind']==kind]
    def update(self,identity,changes,expected_revision,actor='management-director'):
        project=self.get(identity)
        if actor not in {'master-agent','management-director',DOMAINS['web-development' if project['kind']=='web' else 'social-media']}:raise PermissionError('Project director or Management must maintain the project record')
        if project['revision']!=expected_revision:raise ValueError('Project revision conflict')
        if not isinstance(changes,dict) or not changes or set(changes)-FIELDS:raise ValueError('Unsupported project record field')
        if 'deliverables' in changes:
            if not isinstance(changes['deliverables'],list) or any(not isinstance(p,str) for p in changes['deliverables']):raise ValueError('Deliverables must be actual local file paths')
            for path in changes['deliverables']:safe_file(self.hub.root,path)
        for decision in changes.get('technology_decisions',[]):
            if not isinstance(decision,dict) or decision.get('classification') not in {'VERIFIED','UNVERIFIED','ASSUMPTION'}:raise ValueError('Technology decisions need an explicit evidence classification')
            validate_sources(decision.get('sources',[]))
            if decision['classification']=='VERIFIED' and not any(s['classification']=='VERIFIED' for s in decision.get('sources',[])):raise ValueError('Verified technology claims need dated verified primary evidence')
        record=redact(dict(project['record'],**changes));revision=project['revision']+1
        with atomic(self.db):
            if self.db.execute("SELECT 1 FROM external_actions WHERE subject_hash=? AND status IN ('STARTED','UNKNOWN_NEEDS_RECONCILIATION')",(project['record_hash'],)).fetchone():raise ValueError('Reconcile the in-flight external project action before editing its approved subject')
            cur=self.db.execute('UPDATE projects SET record=?,revision=?,qa_task_id=NULL,updated_at=? WHERE id=? AND revision=?',(canonical(record),revision,now(),identity,expected_revision))
            if cur.rowcount!=1:raise ValueError('Project revision conflict')
            self.db.execute('INSERT INTO project_history VALUES(?,?,?,?,?)',(identity,revision,canonical(record),actor,now()))
            self.hub.event(project['task_id'],'PROJECT_RECORD',{'project_id':identity,'revision':revision,'changed_fields':sorted(changes)},actor)
        return self.get(identity)
    def decompose(self,identity,scopes,actor='management-director'):
        if actor!='management-director':raise PermissionError('Management coordinates department handoffs')
        project=self.get(identity);parent=self.hub.task(project['task_id'])
        if parent['phase'] not in {'MANAGEMENT_REVIEW','PLANNED','ASSIGNED','PREFLIGHT','IN_PROGRESS'} or parent['migration_hold']:raise ValueError('Management must review the parent before decomposition')
        if not isinstance(scopes,list) or not scopes:raise ValueError('Supply the smallest necessary scoped child tasks')
        names=[s.get('name') for s in scopes if isinstance(s,dict)]
        if len(names)!=len(scopes) or len(set(names))!=len(names):raise ValueError('Scopes need unique stable names')
        results=[]
        with atomic(self.db):
            for scope in scopes:
                for key in ['name','request','criteria']:required(scope.get(key),'Child '+key)
                if scope.get('department') not in DOMAINS:raise ValueError('Unknown child department')
                agent=scope.get('agent') or DOMAINS[scope['department']]
                if agent not in ROLES or ROLES[agent][0]!=scope['department']:raise ValueError('Child owner must belong to its scoped department')
                task=self.hub.create(scope['request'],scope['criteria'],domain=scope['department'],agent=agent,parent=parent['id'],idempotency_key='project:'+identity+':scope:'+scope['name'])
                self.db.execute('INSERT OR IGNORE INTO department_handoffs VALUES(?,?,?,?,?,?,?,?)',
                    (str(uuid.uuid4()),parent['id'],task['id'],parent['department'],scope['department'],redact(scope['request']),None,now()))
                results.append(dict(task,scope_name=scope['name']))
            for scope,task in zip(scopes,results):
                dependencies=scope.get('depends_on',[])
                if not isinstance(dependencies,list) or any(n not in names for n in dependencies):raise ValueError('Dependency scope name is unknown')
                ids=[results[names.index(n)]['id'] for n in dependencies]
                self.hub._check_graph(task['id'],ids)
                self.db.execute('UPDATE tasks SET dependencies=? WHERE id=?',(canonical(ids),task['id']))
                self.hub.event(task['id'],'SCOPED_HANDOFF',{'parent':parent['id'],'project_id':identity,'dependencies':ids,'department':task['department']},actor)
        return [self.hub.task(t['id']) for t in results]
    def accept_handoff(self,child_task_id,actor,evidence):
        required(evidence,'Actual handoff acknowledgement')
        task=self.hub.task(child_task_id)
        if actor not in {task['owner'],DOMAINS[task['department']]}:raise PermissionError('Only the assigned department can acknowledge its handoff')
        with self.db:
            cur=self.db.execute('UPDATE department_handoffs SET accepted_at=? WHERE child_task_id=?',(now(),child_task_id))
            if cur.rowcount!=1:raise ValueError('No scoped handoff')
            self.hub.event(child_task_id,'HANDOFF_ACCEPTED',{'evidence':evidence},actor)
        return {'accepted':True,'task_id':child_task_id,'execution_implied':False}
    def approve(self,identity,qa_task_id):
        project=self.get(identity);result,qa=approved_task(self.hub,qa_task_id,'approved_project_ids',identity)
        review_task=self.hub.task(qa_task_id);expected_department='web-development' if project['kind']=='web' else 'social-media'
        if review_task['department']!=expected_department or review_task['project_id']!=identity or self.hub.task(project['task_id'])['owner'] not in result.get('authors',[]):raise PermissionError('Project QA must be scoped to this project and its owning department, with its actual authors recorded')
        if result.get('project_record_hashes',{}).get(identity)!=project['record_hash']:raise ValueError('QA did not review the exact current project and output bytes')
        with self.db:
            cur=self.db.execute('UPDATE projects SET qa_task_id=? WHERE id=? AND revision=?',(qa_task_id,identity,project['revision']))
            if cur.rowcount!=1:raise ValueError('Project changed during QA linking')
        return self.get(identity)
    def scaffold(self,identity,task_id,template='static-site'):
        project=self.get(identity);task=self.hub.task(task_id)
        if project['kind']!='web' or task['project_id']!=identity or task['department']!='web-development' or task['phase']!='IN_PROGRESS':raise ValueError('Use a started, assigned Web task within this project')
        self.hub.check_snapshot(task)
        if template not in {'static-site','python-api'}:raise ValueError('Supported local scaffolds: static-site or python-api; other stacks require actual runtime engineering')
        title=html.escape(project['title']);brief=html.escape(project['brief']);folder='projects/'+identity+'/revision-'+str(project['revision'])
        if template=='static-site':
            files={'index.html':f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><link rel="stylesheet" href="style.css"></head><body><a class="skip" href="#main">Skip to content</a><header><a href="#main">{title}</a><nav aria-label="Main"><a href="#overview">Overview</a><a href="#requirements">Requirements</a></nav></header><main id="main"><section id="overview"><p>Project prototype</p><h1>{title}</h1><p class="lead">{brief}</p><a class="button" href="#requirements">Explore the requirements</a></section><section id="requirements"><h2>What this project needs</h2><ul>{''.join('<li>'+html.escape(str(x))+'</li>' for x in project['record']['requirements'])}</ul></section></main><footer>Local prototype. Content, integration, accessibility and deployment require project-specific review.</footer></body></html>''',
                'style.css':'''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:#202522;background:#f5f6f3;font:18px/1.6 system-ui,sans-serif}header,main,footer{max-width:1120px;margin:auto;padding:24px}header,nav{display:flex;align-items:center;justify-content:space-between;gap:24px}a{color:#285e43;text-underline-offset:5px}a:focus-visible{outline:3px solid #285e43;outline-offset:4px}.skip{position:absolute;top:-80px}.skip:focus{top:12px}section{padding:56px 0;border-bottom:1px solid #b8c3bc}h1{max-width:850px;font-size:clamp(36px,7vw,76px);line-height:1.08;letter-spacing:-.04em}h2{font-size:30px}.lead{max-width:700px}.button{display:inline-block;padding:12px 20px;background:#285e43;color:white;border-radius:5px}footer{font-size:14px}@media(max-width:600px){header{align-items:flex-start;flex-direction:column}nav{gap:20px}section{padding:32px 0}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}''',
                'README.md':'# '+project['title']+'\n\nLocal static prototype; no service was deployed.\nRun `python -m http.server 8000 --bind 127.0.0.1` here.\nInspect at mobile/desktop widths, keyboard navigation, content rights and actual requirements before QA.\n'}
        else:
            files={'server.py':API_TEMPLATE,'README.md':'# '+project['title']+' — local API prototype\n\nRun `python server.py`, then open http://127.0.0.1:8081/api/items.\nPOST JSON {"title":"Example"} to /api/items. Data stays in app.sqlite beside this file.\nLoopback prototype only; production authentication, authorization, deployment and load testing are not implemented.\n'}
        paths=write_artifacts(self.hub.root,folder,files)
        updated=self.update(identity,{'deliverables':paths,'implementation_status':'LOCAL_PROTOTYPE_CREATED',
            'deployment_readiness':'NOT_DEPLOYED','technology_decisions':[{'selection':template,'classification':'ASSUMPTION','sources':[],
            'rationale':'Explicit small local scaffold; suitability for full requirements still requires technology research and QA.'}]},project['revision'])
        with self.db:self.hub.event(task_id,'LOCAL_SOFTWARE_OUTPUT',{'project_id':identity,'artifacts':paths,'template':template,'model_invoked':False},task['owner'])
        return {'project':updated,'artifacts':paths,'deployed':False}
    def deployment_payload(self,identity):
        project=self.get(identity)
        return {'project_id':identity,'project_hash':project['record_hash'],'artifact_hashes':project['artifact_hashes']}

    def deploy(self,identity,approval_id,arguments,destination,projected_cost,adapter):
        project=self.get(identity)
        if project['kind']!='web' or not project['qa_task_id']:raise ValueError('Project must pass independent QA before deployment')
        result,_=approved_task(self.hub,project['qa_task_id'],'approved_project_ids',identity)
        if result.get('project_record_hashes',{}).get(identity)!=project['record_hash']:raise ValueError('Approved project bytes changed')
        approval=self.db.execute('SELECT operation,runtime_id,provider,task_id FROM action_approvals WHERE id=?',(approval_id,)).fetchone()
        if approval is None:raise ValueError('Unknown deployment approval')
        op=self.hub.connectors._operation(self.hub.connectors.get(approval['runtime_id'],approval['provider']),approval['operation'])
        if op['kind']!='deploy' or self.hub.task(approval['task_id'])['project_id']!=identity:raise PermissionError('A scoped deployment task and deploy operation are required')
        if arguments!=self.deployment_payload(identity):raise PermissionError('Deployment arguments must identify exactly the reviewed local artifact bytes')
        return self.hub.connectors.execute(approval_id,project['record_hash'],destination,arguments,projected_cost,adapter)


API_TEMPLATE='''"""Generated loopback-only SQLite API prototype. No production auth/deployment claims."""
import json,sqlite3,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
DB=Path(__file__).with_name('app.sqlite')
PORT=int(os.environ.get('WEB_PROJECT_PORT','8081'))
class Handler(BaseHTTPRequestHandler):
 def send(self,status,data):
  body=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def permitted(self):
  host=self.headers.get('Host','');origin=self.headers.get('Origin');allowed={'127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)}
  return host in allowed and (not origin or origin in {'http://'+h for h in allowed})
 def do_GET(self):
  if not self.permitted():return self.send(403,{'error':'Loopback only'})
  if self.path!='/api/items':return self.send(404,{'error':'Not found'})
  with sqlite3.connect(DB) as db:self.send(200,[{'id':r[0],'title':r[1]} for r in db.execute('SELECT id,title FROM items ORDER BY id')])
 def do_POST(self):
  if not self.permitted():return self.send(403,{'error':'Loopback only'})
  if self.path!='/api/items':return self.send(404,{'error':'Not found'})
  try:
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=8192 or self.headers.get_content_type()!='application/json':raise ValueError()
   data=json.loads(self.rfile.read(size))
   if not isinstance(data,dict) or set(data)!={'title'} or not isinstance(data['title'],str) or not 1<=len(data['title'].strip())<=200:raise ValueError()
   with sqlite3.connect(DB) as db:
    cur=db.execute('INSERT INTO items(title) VALUES(?)',(data['title'].strip(),));identity=cur.lastrowid
   self.send(201,{'id':identity,'title':data['title'].strip()})
  except (ValueError,TypeError):self.send(400,{'error':'Expected JSON title, 1-200 characters'})
if __name__=='__main__':
 with sqlite3.connect(DB) as db:db.execute('CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,title TEXT NOT NULL)')
 server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
 print('Local prototype: http://127.0.0.1:'+str(server.server_port),flush=True)
 server.serve_forever()
'''
