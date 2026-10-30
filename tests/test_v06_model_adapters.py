"""Deterministic adapter checks: fake executable/HTTP responses are SIMULATED.
No external model, credential discovery, paid request or real account action occurs.
"""
import json
import os
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_hub.model_adapters import (
    InvocationRequest,UnconfiguredAdapter,CodexCLIAdapter,ClaudeCodeAdapter,
    OpenAIResponsesAdapter,from_config,RuntimeUnavailable,ModelProtocolError,
    ExecutionCancelled,ExecutionTimeout,UNAVAILABLE,
)

SCHEMA={'type':'object','properties':{'summary':{'type':'string'},'artifacts':{'type':'array','items':{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content'],'additionalProperties':False}}},'required':['summary','artifacts'],'additionalProperties':False}
DATA={'summary':'Synthetic output','artifacts':[{'path':'draft.txt','content':'Actual fake-provider bytes; not an AI output claim.'}]}


class Adapters(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.request=InvocationRequest('invocation-fixture','run-fixture',1,'fixture-agent','worker','Controller security and role context','Synthetic task',SCHEMA,self.root,3)
    def fake(self,body,provider='codex'):
        path=self.root/('fake-'+provider)
        prefix=f'''#!{sys.executable}
import sys,json,time,os,subprocess
args=sys.argv[1:]
if '--version' in args:
 print({'codex-cli 0.163.0' if provider=='codex' else '2.1.312 (Claude Code)'!r});sys.exit(0)
if args[:2]==['login','status']:
 print('Logged in using fixture credentials');sys.exit(0)
if args[:2]==['mcp','list']:
 print('[]');sys.exit(0)
if args[:2]==['auth','status']:
 print(json.dumps({{'loggedIn':True}}));sys.exit(0)
'''
        path.write_text(prefix+textwrap.dedent(body));path.chmod(0o700);return str(path)
    def codex(self,**changes):
        complete={'input_tokens':80,'output_tokens':15,'cached_input_tokens':20}
        events=[{'type':'thread.started','thread_id':'fixture-thread'},
                {'type':'item.completed','item':{'id':'private','type':'reasoning','text':'PRIVATE_THINKING_MUST_NOT_PERSIST'}},
                {'type':'item.completed','item':{'id':'final','type':'agent_message','text':json.dumps(DATA)}},
                {'type':'turn.completed','usage':complete}]
        body='''
assert '--sandbox' in args and args[args.index('--sandbox')+1]=='read-only'
assert '--ephemeral' in args and '--output-schema' in args
assert '--ignore-user-config' not in args and '--ignore-rules' not in args
assert not any('dangerously' in a for a in args)
sys.stdin.read()
'''+''.join('print('+repr(json.dumps(e))+',flush=True)\n' for e in events)
        return CodexCLIAdapter(self.fake(body),evidence_kind='SIMULATED',**changes)
    def response(self,identity='resp_fixture',text=None,usage=None):
        return {'id':identity,'model':'fixture-reported-model','status':'completed','output':[
            {'type':'reasoning','summary':[{'text':'PRIVATE_RESPONSE_THINKING'}]},
            {'type':'message','content':[{'type':'output_text','text':json.dumps(DATA) if text is None else text}]}],
            'usage':usage or {'input_tokens':20,'output_tokens':10,'input_tokens_details':{'cached_tokens':4}}}
    def test_missing_configuration_never_falls_back_to_simulated_success(self):
        for config in [None,{}, {'provider':'codex-cli'}, {'provider':'codex-cli','enabled':'true'}]:
            adapter=from_config(config);self.assertIsInstance(adapter,UnconfiguredAdapter)
            with self.assertRaisesRegex(RuntimeUnavailable,'MODEL RUNTIME NOT CONFIGURED'):adapter.invoke(self.request)
        with self.assertRaises(ValueError):from_config({'enabled':True,'provider':'mock'})
        with self.assertRaises(ValueError):from_config({'enabled':True,'provider':'codex-cli','evidence_kind':'SIMULATED'})
    def test_probe_checks_real_fake_executable_status_without_leaking_credentials(self):
        result=self.codex().probe();self.assertTrue(result['authenticated']);self.assertFalse(result['execution_tested'])
        self.assertNotIn('credentials',json.dumps(result))
        missing=CodexCLIAdapter(self.root/'absent');self.assertFalse(missing.probe()['available'])
    def test_codex_schema_result_usage_and_reasoning_filter(self):
        events=[];result=self.codex().invoke(self.request,on_event=events.append)
        self.assertEqual(result.data,DATA);self.assertEqual(result.evidence_kind,'SIMULATED');self.assertIsNone(result.model)
        self.assertEqual(result.usage['input_tokens'],80);self.assertEqual(result.usage['cache_read_tokens'],20)
        self.assertIsNone(result.usage['cache_write_tokens']);self.assertIsNone(result.usage['actual_cost'])
        self.assertNotIn('PRIVATE_THINKING',json.dumps(events)+repr(result))
        self.assertTrue(any(e['kind']=='PROVIDER_SESSION' for e in events))
    def test_codex_requires_terminal_success_and_correct_schema(self):
        malformed=self.fake("sys.stdin.read();print(json.dumps({'type':'turn.completed','usage':{}}))")
        with self.assertRaises(ModelProtocolError):CodexCLIAdapter(malformed,evidence_kind='SIMULATED').invoke(self.request)
        bad=self.fake("sys.stdin.read();print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'{}'}}));print(json.dumps({'type':'turn.completed'}))")
        with self.assertRaises(ModelProtocolError):CodexCLIAdapter(bad,evidence_kind='SIMULATED').invoke(self.request)
    def test_public_provider_errors_are_bounded_and_redacted(self):
        body="sys.stdin.read();print(json.dumps({'type':'turn.failed','error':{'code':'MODEL_UNAVAILABLE','message':'password=NEVER_LOG_THIS model unavailable'}}))"
        events=[]
        with self.assertRaises(ModelProtocolError):CodexCLIAdapter(self.fake(body),evidence_kind='SIMULATED').invoke(self.request,on_event=events.append)
        self.assertEqual(events[0]['code'],'MODEL_UNAVAILABLE');self.assertNotIn('NEVER_LOG_THIS',json.dumps(events))
    def test_nonzero_cli_exit_exposes_safe_diagnostic_not_raw_transcript(self):
        body="sys.stdin.read();print('error: permission denied secret=DO_NOT_LOG',file=sys.stderr);sys.exit(2)"
        events=[]
        with self.assertRaisesRegex(ModelProtocolError,'permission denied'):CodexCLIAdapter(self.fake(body),evidence_kind='SIMULATED').invoke(self.request,on_event=events.append)
        self.assertEqual(events[-1]['code'],'EXIT_2');self.assertNotIn('DO_NOT_LOG',json.dumps(events))
    def test_subprocess_timeout_and_cancellation_are_real(self):
        adapter=CodexCLIAdapter(self.fake('sys.stdin.read();time.sleep(10)'),evidence_kind='SIMULATED')
        self.request.timeout_seconds=.1
        with self.assertRaises(ExecutionTimeout):adapter.invoke(self.request)
        self.request.timeout_seconds=3
        with self.assertRaises(ExecutionCancelled):adapter.invoke(self.request,cancel_check=lambda:True)
    @unittest.skipUnless(os.name=='posix','POSIX process-group semantics')
    def test_timeout_terminates_owned_descendant_process_group(self):
        marker=self.root/'unexpected-descendant-write.txt'
        child="import time;from pathlib import Path;time.sleep(.6);Path("+repr(str(marker))+").write_text('should not happen')"
        adapter=CodexCLIAdapter(self.fake('sys.stdin.read();subprocess.Popen([sys.executable,"-c",'+repr(child)+']);time.sleep(10)'),evidence_kind='SIMULATED')
        self.request.timeout_seconds=.15
        with self.assertRaises(ExecutionTimeout):adapter.invoke(self.request)
        time.sleep(.8);self.assertFalse(marker.exists())
    def test_process_output_limit_blocks_unbounded_responses(self):
        adapter=CodexCLIAdapter(self.fake("sys.stdin.read();print('x'*10000)"),max_output_bytes=1024,evidence_kind='SIMULATED')
        with self.assertRaises(ModelProtocolError):adapter.invoke(self.request)
    def test_claude_disables_tools_and_mcp_then_parses_actual_reported_cost(self):
        body='''
assert args[args.index('--tools')+1]==''
assert '--strict-mcp-config' in args and '--setting-sources=' in args
assert '--permission-mode' in args and args[args.index('--permission-mode')+1]=='dontAsk'
assert not any('bypass' in a for a in args)
sys.stdin.read()
print(json.dumps({'type':'system','subtype':'init','session_id':'fixture-claude'}))
print(json.dumps({'type':'assistant','message':{'model':'fixture-reported-model','content':[{'type':'thinking','thinking':'PRIVATE_CLAUDE_THINKING','signature':'PRIVATE_SIGNATURE'}]}}))
print(json.dumps({'type':'result','subtype':'success','is_error':False,'session_id':'fixture-claude','structured_output':DATA,'usage':{'input_tokens':10,'output_tokens':3,'cache_read_input_tokens':4},'total_cost_usd':0.012}))
'''.replace('structured_output\':DATA','structured_output\':'+repr(DATA))
        events=[];result=ClaudeCodeAdapter(self.fake(body,'claude'),evidence_kind='SIMULATED').invoke(self.request,on_event=events.append)
        self.assertEqual(result.data,DATA);self.assertEqual(result.model,'fixture-reported-model');self.assertEqual(result.usage['actual_cost'],'0.012')
        self.assertNotIn('PRIVATE_CLAUDE',json.dumps(events)+repr(result))
    def test_openai_endpoint_auth_and_no_redirect_boundaries(self):
        for url in ['http://api.openai.com/v1','https://attacker.example/v1','https://api.openai.com/v1?key=secret']:
            with self.assertRaises(ValueError):OpenAIResponsesAdapter(model='fixture',base_url=url)
        with patch.dict(os.environ,{},clear=True):
            adapter=OpenAIResponsesAdapter(model='fixture');self.assertFalse(adapter.probe()['configured'])
            with self.assertRaises(RuntimeUnavailable):adapter.invoke(self.request)
    def test_openai_transport_is_explicitly_simulated_and_cost_unknown(self):
        with self.assertRaises(ValueError):OpenAIResponsesAdapter(model='fixture',transport=lambda *a:{}).invoke(self.request)
        events=[];adapter=OpenAIResponsesAdapter(model='fixture',transport=lambda *a:self.response(),evidence_kind='SIMULATED')
        result=adapter.invoke(self.request,on_event=events.append)
        self.assertEqual(result.data,DATA);self.assertEqual(result.model,'fixture-reported-model');self.assertIsNone(result.usage['actual_cost'])
        self.assertEqual(result.usage['cache_read_tokens'],4);self.assertNotIn('PRIVATE_RESPONSE',json.dumps(events)+repr(result))
    def test_openai_function_loop_uses_guarded_gateway_and_resends_instructions(self):
        calls=[]
        class Gateway:
            def schemas(self):return [{'type':'function','name':'read_artifact','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False},'strict':True}]
            def execute(self,name,args):
                self.called=(name,args);return {'content':'Actual fixture content','private_reasoning':'MUST_DROP'}
        gateway=Gateway()
        def transport(body,timeout):
            calls.append(body)
            if len(calls)==1:return {'id':'resp_tool','model':'fixture','status':'completed','usage':{'input_tokens':5,'output_tokens':1},'output':[{'type':'function_call','name':'read_artifact','call_id':'call_fixture','arguments':'{"path":"draft.txt"}'}]}
            return self.response()
        adapter=OpenAIResponsesAdapter(model='fixture',transport=transport,evidence_kind='SIMULATED')
        result=adapter.invoke(self.request,tool_gateway=gateway)
        self.assertEqual(gateway.called,('read_artifact',{'path':'draft.txt'}));self.assertEqual(result.data,DATA)
        self.assertTrue(all(c['instructions']==self.request.system_prompt for c in calls));self.assertFalse(calls[0]['parallel_tool_calls'])
        self.assertEqual(result.usage['input_tokens'],25);self.assertNotIn('MUST_DROP',calls[1]['input'][-1]['output'])
    def test_openai_unavailable_function_and_invalid_arguments_never_execute(self):
        class Gateway:
            def schemas(self):return [{'type':'function','name':'allowed','parameters':{'type':'object','properties':{},'additionalProperties':False},'strict':True}]
            def execute(self,*args):raise AssertionError('Must not execute')
        for name,args in [('unknown','{}'),('allowed','{"unexpected":1}')]:
            def transport(*a):return {'id':'fixture','model':'fixture','status':'completed','output':[{'type':'function_call','name':name,'call_id':'call1','arguments':args}]}
            adapter=OpenAIResponsesAdapter(model='fixture',transport=transport,evidence_kind='SIMULATED')
            with self.assertRaises(ModelProtocolError):adapter.invoke(self.request,tool_gateway=Gateway())
    def test_openai_refuses_incomplete_or_invalid_json_output(self):
        for change in [{'status':'incomplete'},{'output':[{'type':'message','content':[{'type':'output_text','text':'{"summary":NaN,"artifacts":[]}'}]}]}]:
            response=dict(self.response(),**change)
            adapter=OpenAIResponsesAdapter(model='fixture',transport=lambda *a:response,evidence_kind='SIMULATED')
            with self.assertRaises(ModelProtocolError):adapter.invoke(self.request)


if __name__=='__main__':unittest.main()
