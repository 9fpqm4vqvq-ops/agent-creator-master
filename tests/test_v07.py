"""Local operational regression; every model response is explicitly SIMULATED."""
import hashlib,json,sqlite3,sys,threading,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import test_hub
from test_v06_runtime import FixtureAdapter
from agent_hub.runtime import AgentRuntime
from agent_hub.runtime_control import CapacityPause
from agent_hub.acceptance import WEB,templates,validate_web
from agent_hub.native_sources import NativeSourceAdapter
from agent_hub.research import ResearchEngine
from agent_hub.web_search import NativeWebSearchAdapter,UnconfiguredWebSearch
from agent_hub.service_adapters import GitHubReadAdapter
from agent_hub.model_adapters import _probe_command,CodexCLIAdapter
from agent_hub.core import Hub

class Operational(unittest.TestCase):
 setUp=test_hub.Workflow.setUp
 def runtime(self,config=None):return AgentRuntime(self.hub,config,adapter=FixtureAdapter())
 def test_json_stdout_probe_ignores_warning_without_weakening_mcp_guard(self):
  fixture=self.root/'probe';fixture.write_text('#!'+sys.executable+'\nimport sys\nprint("[]")\nprint("warning: read-only filesystem",file=sys.stderr)\n');fixture.chmod(0o700)
  code,text=_probe_command([str(fixture)],json_stdout_only=True)
  self.assertEqual(code,0);self.assertEqual(json.loads(text),[])
 def test_successful_provider_receipt_survives_bad_telemetry(self):
  runtime=self.runtime();task=runtime.intake('Note','Deliver note')
  with patch.object(self.hub.usage,'record',side_effect=ValueError('fixture invalid usage')):result=runtime.execute_task(task['id'])
  self.assertEqual(result['status'],'COMPLETED',result['error'])
  self.assertTrue(all(i['status']=='COMPLETED' and i['reference'] and i['output'] for i in result['invocations']))
  self.assertEqual(sum(e['kind']=='TELEMETRY_UNRESOLVED' for e in result['events']),3)
  self.assertEqual(self.hub.db.execute('SELECT COUNT(*) FROM usage_reservations').fetchone()[0],3)
 def test_atomic_shared_capacity_backpressure(self):
  first=self.runtime();run=first.execute_task(first.intake('First','Note')['id'])
  # Completed fixture runs are restored to a claimed running fixture checkpoint.
  self.hub.db.execute("UPDATE agent_runs SET status='QUEUED' WHERE id=?",(run['id'],));self.hub.db.commit();first._claim(run['id'])
  second=self.runtime();waiting=second.execute_task(second.intake('Second','Note')['id'])
  self.assertEqual(waiting['status'],'QUEUED');self.assertIn('WAITING_FOR_CAPACITY',waiting['last_step']);self.assertFalse(second.adapter.calls)
  with self.assertRaises(ValueError):second.control.capacity(0,'fixture')
  second.control.capacity(2,'fixture authorized increase');done=second.execute_task(waiting['task_id'],waiting['id'])
  self.assertEqual(done['status'],'COMPLETED',done['error'])
 def test_capacity_race_two_connections_only_one_claim(self):
  seed=self.runtime();ids=[]
  for _ in range(2):
   run=AgentRuntime(self.hub).execute_task(seed.intake(str(uuid.uuid4()),'Criteria')['id'])
   self.hub.db.execute("UPDATE agent_runs SET status='QUEUED' WHERE id=?",(run['id'],));self.hub.db.commit();ids.append(run['id'])
  barrier=threading.Barrier(2);outcomes=[]
  def claim(run):
   hub=Hub(self.root/'hub.sqlite',self.root)
   try:
    runtime=AgentRuntime(hub);barrier.wait()
    try:runtime._claim(run);outcomes.append('CLAIMED')
    except CapacityPause:outcomes.append('QUEUED')
   finally:hub.close()
  workers=[threading.Thread(target=claim,args=(i,)) for i in ids]
  for t in workers:t.start()
  for t in workers:t.join(10)
  self.assertEqual(sorted(outcomes),['CLAIMED','QUEUED'])
 def test_run_budget_blocks_before_first_model_and_retains_unknown(self):
  runtime=self.runtime({'run_budget_usd':'0','projected_cost_usd':'0.01'})
  result=runtime.execute_task(runtime.intake('Note','Criteria')['id'])
  self.assertEqual(result['status'],'WAITING_FOR_APPROVAL');self.assertFalse(runtime.adapter.calls)
  runtime.control.set_run_budget(result['id'],'0.02','fixture ceiling')
  resumed=runtime.resume_execution(result['id'],'fixture resume')
  self.assertEqual(len(runtime.adapter.calls),1)
  self.assertEqual(resumed['status'],'WAITING_FOR_APPROVAL')
  self.assertEqual(runtime.control.run_budget(result['id'],'0.01')['status'],'UNKNOWN')
 def test_reconciliation_cannot_fabricate_receipt_or_release_holds(self):
  runtime=self.runtime();runtime.adapter=FixtureAdapter(cancel=True);result=runtime.execute_task(runtime.intake('Note','Criteria')['id'])
  invocation=result['invocations'][0]
  with self.assertRaises(ValueError):runtime.control.reconcile(result['id'],invocation['id'],'RECEIPT_RECORDED','fixture','no receipt')
  receipt=runtime.control.reconcile(result['id'],invocation['id'],'COST_UNKNOWN','fixture provider diagnosis','No output; costs still unknown')
  self.assertFalse(receipt['cost_holds_released'])
  report=runtime.control.inspect(result['id']);self.assertEqual(len(report['cost_reservations']),1)
 def test_authorized_replacement_is_idempotent_and_preserves_history(self):
  runtime=self.runtime();runtime.adapter=FixtureAdapter(cancel=True);result=runtime.execute_task(runtime.intake('Note','Criteria')['id'])
  old=self.hub.history(result['task_id']);runtime.control.reconcile(result['id'],result['invocations'][0]['id'],'COST_UNKNOWN','fixture','Provider stopped; unknown cost retained')
  first=runtime.control.replacement(result['id'],'fixture auth','Verified no external action')
  second=runtime.control.replacement(result['id'],'fixture auth','Verified no external action')
  self.assertEqual(first['id'],second['id']);self.assertEqual(self.hub.history(result['task_id'])[:len(old)],old)
  self.assertEqual(runtime.get(result['id'])['status'],'REPLACED')
  with self.assertRaises(ValueError):runtime.resume_execution(result['id'],'fixture forbidden old run resume')
 def test_web_trivial_command_and_forged_receipt_are_rejected(self):
  runtime=self.runtime();run=str(uuid.uuid4());runtime.workspaces.write(run,'verify.js','// reviewed verifier')
  snapshot=runtime.workspaces.snapshot(run);digest=snapshot['files']['verify.js']['sha256']
  runtime.config['acceptance']={'template':'backend-api','verifier_files':{'verify.js':digest}}
  rows=[{'status':'PASS','input_hash':snapshot['sha256'],'argv':'["/bin/true"]','output':'{}'}]
  with self.assertRaisesRegex(ValueError,'assertions'):validate_web(runtime,run,rows,snapshot)
  rows[0].update(argv='["node","verify.js"]',output=json.dumps({'status':'PASS','assertions':[{'id':k,'kind':{'security':'SECURITY','persistence':'PERSISTENCE'}.get(k,'FUNCTIONAL'),'status':'PASS','evidence':'fixture assertion'} for k in WEB['backend-api']]}))
  self.assertEqual(validate_web(runtime,run,rows,snapshot)['evidence_level'],'LOCAL_TESTED')
  rows[0]['input_hash']='other-bytes'
  with self.assertRaises(ValueError):validate_web(runtime,run,rows,snapshot)
  runtime.workspaces.write(run,'verify.js','// modified verifier',digest)
  with self.assertRaisesRegex(ValueError,'verifier bytes'):validate_web(runtime,run,rows,runtime.workspaces.snapshot(run))
 def test_templates_cover_six_web_and_seven_social_types(self):
  value=templates();self.assertEqual(len(value['web']),6);self.assertEqual(len(value['social']),7)
  self.assertIn('rendered_video',value['social']['short-video']['required_checks'])
 def test_native_source_uses_host_receipt_keeps_dates_and_dns_default(self):
  runtime=self.runtime();task=runtime.intake('Release','Record evidence')['id']
  source=NativeSourceAdapter(['example.com'],lambda url:{'status':200,'url':url,'body':json.dumps({'version':'test','published_at':'2026-01-01T00:00:00Z'}).encode(),'content_type':'application/json','reference':'fixture://document'},'SIMULATED')
  engine=ResearchEngine(self.hub,{'allowed_hosts':['example.com']},fetch_adapter=source)
  result=engine.fetch(task,'https://example.com/release')
  self.assertEqual(result['source_published_at'],'2026-01-01T00:00:00Z');self.assertEqual(result['evidence']['evidence_kind'],'SIMULATED')
  self.assertEqual(result['evidence']['host_reference'],'fixture://document')
  with self.assertRaises(PermissionError):source.validate_url('https://localhost/x')
 def test_native_general_search_and_unconfigured_explicit(self):
  adapter=NativeWebSearchAdapter(lambda req:{'reference':'fixture://search','results':[{'url':'https://example.com/docs','title':'Official example','snippet':'Fixture'}]},'SIMULATED')
  runtime=self.runtime();task=runtime.intake('Search','Evidence')['id'];engine=ResearchEngine(self.hub,search_adapter=adapter)
  result=engine.search(task,'framework');self.assertEqual(result['evidence_kind'],'SIMULATED');self.assertEqual(len(result['results']),1)
  with self.assertRaisesRegex(RuntimeError,'SEARCH BLOCKED'):UnconfiguredWebSearch()('framework')
 def test_extended_github_reads_use_bounded_documented_gets(self):
  calls=[]
  def transport(method,url,headers,timeout):calls.append((method,url));return {'status':200,'body':[]}
  adapter=GitHubReadAdapter(transport=transport)
  for name in ['github.commits','github.issues','github.pull_requests']:adapter(name,{'owner':'example','repo':'project','limit':3})
  self.assertTrue(all(m=='GET' for m,u in calls));self.assertTrue(calls[0][1].endswith('/commits?per_page=3'))
  with self.assertRaises(ValueError):adapter('github.issues',{'owner':'x','repo':'y','limit':10000})
 def test_resume_verified_specialist_receipt_after_interruption_without_reinvocation(self):
  runtime=self.runtime();task=runtime.intake('Note','Deliver note')
  with patch.object(runtime.workspaces,'write',side_effect=KeyboardInterrupt):
   with self.assertRaises(KeyboardInterrupt):runtime.execute_task(task['id'])
  run=dict(self.hub.db.execute('SELECT * FROM agent_runs WHERE task_id=?',(task['id'],)).fetchone())
  self.assertEqual(run['status'],'BLOCKED');self.assertEqual(self.hub.task(task['id'])['phase'],'IN_PROGRESS')
  self.assertEqual(len(runtime.adapter.calls),2)
  result=runtime.resume_execution(run['id'],'fixture explicit receipt recovery')
  self.assertEqual(result['status'],'COMPLETED',result['error'])
  self.assertEqual([c.stage for c in runtime.adapter.calls],['MANAGEMENT','SPECIALIST','QA'])
 def test_social_script_is_not_video_and_analytics_needs_supplied_data(self):
  from agent_hub.acceptance import validate_social
  runtime=self.runtime({'acceptance':{'template':'short-video'}})
  (self.root/'script.md').write_text('A production script only')
  with self.assertRaisesRegex(ValueError,'Rendered video absent'):validate_social(runtime,str(uuid.uuid4()),{'artifacts':['script.md']})
  runtime.config['acceptance']={'template':'analytics'}
  with self.assertRaisesRegex(ValueError,'dataset provenance'):validate_social(runtime,str(uuid.uuid4()),{'artifacts':['script.md']})
 def test_simulated_connector_never_becomes_live_tested_status(self):
  registry=self.hub.connectors;registry.discover('fixture','Test','fixture',[{'name':'read','kind':'read'}],'fixture://discovery',evidence_kind='SIMULATED')
  registry.test_read('fixture','Test','read',{},lambda *args:{'ok':True,'authenticated':True,'reference':'fixture://read'})
  status=registry.operational_status('fixture','Test')
  self.assertEqual(status['status'],'AVAILABLE');self.assertEqual(status['verified_operations'],[])
  self.assertEqual(registry.operational_status('fixture','missing')['status'],'UNAVAILABLE')
 def test_supervised_host_bridge_fixture_challenge_and_production_boundary(self):
  from agent_hub.host_bridge import SupervisedHostAdapter
  from agent_hub.model_adapters import InvocationRequest,from_config
  folder=self.root/'mailbox';adapter=SupervisedHostAdapter(folder,'fixture://not-live','SIMULATED')
  request=InvocationRequest(str(uuid.uuid4()),str(uuid.uuid4()),1,'management-director','MANAGEMENT','Fixture only','Return ready',{'type':'object','properties':{'ready':{'type':'boolean'}},'required':['ready'],'additionalProperties':False},self.root,2)
  def respond():
   import time
   path=folder/(request.id+'.request.json')
   while not path.exists():time.sleep(.01)
   value=json.loads(path.read_text())
   (folder/(request.id+'.response.json')).write_text(json.dumps({'invocation_id':request.id,'challenge':value['challenge'],'reference':'fixture://simulated-host','data':{'ready':True}}))
  thread=threading.Thread(target=respond);thread.start();result=adapter.invoke(request);thread.join(2)
  self.assertEqual(result.evidence_kind,'SIMULATED');self.assertTrue(result.data['ready'])
  with self.assertRaises(ValueError):from_config({'enabled':True,'provider':'supervised-host-agent-tool'})
 def test_completed_receipt_is_saved_when_cancellation_arrives_with_response(self):
  runtime=self.runtime();original=runtime.adapter.invoke
  def invoke(request,**kwargs):
   result=original(request,**kwargs);self.hub.cancel(request.task_id,'fixture cancellation concurrent with genuine result');return result
  runtime.adapter.invoke=invoke;result=runtime.execute_task(runtime.intake('Note','Criteria')['id'])
  self.assertEqual(result['status'],'CANCELLED');self.assertEqual(len(result['invocations']),1)
  inv=result['invocations'][0];self.assertEqual(inv['status'],'COMPLETED');self.assertTrue(inv['reference']);self.assertTrue(inv['output'])
  self.assertEqual(self.hub.db.execute('SELECT COUNT(*) FROM usage_events').fetchone()[0],1)
  self.assertFalse(runtime.workspaces.snapshot(result['id'])['files'])
 def test_native_source_must_satisfy_engine_and_adapter_allowlists(self):
  runtime=self.runtime();task=runtime.intake('Read','Evidence')['id']
  adapter=NativeSourceAdapter(['example.com','other.example'],lambda url:{'status':200,'body':b'source','url':url,'content_type':'text/plain','reference':'fixture://read'},'SIMULATED')
  engine=ResearchEngine(self.hub,{'allowed_hosts':['example.com']},fetch_adapter=adapter)
  with self.assertRaises(PermissionError):engine.fetch(task,'https://other.example/secret-scope')
 def test_video_header_and_trivial_command_cannot_prove_rendered_media(self):
  from agent_hub.acceptance import validate_social
  runtime=self.runtime({'acceptance':{'template':'short-video'},'checks':[{'argv':['/bin/true']}]})
  (self.root/'fake.mp4').write_bytes(b'\x00\x00\x00\x18ftypisom')
  with self.assertRaisesRegex(ValueError,'reviewed media verifier'):validate_social(runtime,str(uuid.uuid4()),{'artifacts':['fake.mp4']})
 def test_missing_verifier_null_hash_is_rejected(self):
  from agent_hub.acceptance import validate_verifiers
  with self.assertRaisesRegex(ValueError,'64-hex'):validate_verifiers({'files':{}},{'missing.js':None})
  with self.assertRaises(ValueError):validate_verifiers({'files':{}},{'missing.js':'a'*64})
 def test_host_bridge_tolerates_incomplete_publication_and_atomic_helper(self):
  from agent_hub.host_bridge import SupervisedHostAdapter,publish_host_response
  from agent_hub.model_adapters import InvocationRequest
  import time
  folder=self.root/'partial-mailbox';adapter=SupervisedHostAdapter(folder,'fixture://not-live','SIMULATED')
  request=InvocationRequest(str(uuid.uuid4()),str(uuid.uuid4()),1,'management-director','MANAGEMENT','fixture','fixture',{'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False},self.root,2)
  def respond():
   path=folder/(request.id+'.request.json')
   while not path.exists():time.sleep(.01)
   value=json.loads(path.read_text());response=folder/(request.id+'.response.json')
   response.write_text('{');time.sleep(.2);response.write_text(json.dumps({'invocation_id':request.id,'challenge':value['challenge'],'reference':'fixture://host','data':{'ok':True}}))
  thread=threading.Thread(target=respond);thread.start();result=adapter.invoke(request);thread.join(2)
  self.assertTrue(result.data['ok'])
  extra=folder/'extra.request.json';extra.write_text(json.dumps({'invocation_id':'extra','challenge':'fixture'}))
  published=publish_host_response(extra,'fixture://atomic',{'ok':True});self.assertEqual(json.loads(Path(published).read_text())['challenge'],'fixture')
