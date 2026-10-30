"""Supported model interfaces. No default paid call, mock fallback, or secret transcript.

CLI sessions are fresh. Stdout is parsed in transient memory and only public output,
usage, session identifiers and bounded tool metadata leave this module. Process
termination is not a guarantee a remote request/action was undone.
"""
from __future__ import annotations

import json
import math
import os
import queue
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .security import redact

UNAVAILABLE = 'EXECUTION UNAVAILABLE — MODEL RUNTIME NOT CONFIGURED'
PRIVATE_KEYS = {'thinking','reasoning','signature','encrypted_content','chain_of_thought','private_reasoning','hidden_reasoning'}
TOKEN_KEYS = ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens')


class RuntimeUnavailable(RuntimeError):
    pass


class ModelProtocolError(RuntimeError):
    pass


class ExecutionCancelled(RuntimeError):
    pass


class ExecutionTimeout(RuntimeError):
    pass


@dataclass
class InvocationRequest:
    id: str
    run_id: str
    task_id: int
    agent: str
    stage: str
    system_prompt: str
    user_prompt: str
    output_schema: dict
    workspace: Path
    timeout_seconds: float = 120


@dataclass
class InvocationResult:
    data: dict
    provider: str
    model: str | None
    invocation_id: str
    reference: str
    usage: dict
    duration_seconds: float
    evidence_kind: str = 'LIVE'
    tool_events: list = field(default_factory=list)


def _public(value):
    """Drop private blocks before callbacks/logging; recursively redact credentials."""
    if isinstance(value,dict):
        if value.get('type') in {'thinking','reasoning','redacted_thinking'}:return None
        value={k:_public(v) for k,v in value.items() if str(k).lower() not in PRIVATE_KEYS}
    elif isinstance(value,list):
        value=[_public(v) for v in value if not isinstance(v,dict) or v.get('type') not in {'thinking','reasoning','redacted_thinking'}]
    elif isinstance(value,str):
        value=re.sub(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}','[REDACTED]',value)
    return redact(value)


def _json(text):
    def invalid(_):raise ValueError('Non-finite JSON value')
    try:return json.loads(text,parse_constant=invalid)
    except (ValueError,TypeError):raise ModelProtocolError('Provider output is not valid JSON; raw output was not persisted') from None


def _validate(value,schema,root=None,path='$'):
    """Local defensive subset; providers and the controller apply their own schemas."""
    root=schema if root is None else root
    if not isinstance(schema,dict):raise ModelProtocolError('Output schema must be an object')
    if '$ref' in schema:
        ref=schema['$ref']
        if not isinstance(ref,str) or not ref.startswith('#/'):raise ModelProtocolError('Only local schema references are supported')
        target=root
        try:
            for part in ref[2:].split('/'):target=target[part.replace('~1','/').replace('~0','~')]
        except (KeyError,TypeError):raise ModelProtocolError('Unresolved output schema reference') from None
        return _validate(value,target,root,path)
    for mode in ['anyOf','oneOf']:
        if mode in schema:
            successes=0
            for variant in schema[mode]:
                try:_validate(value,variant,root,path);successes+=1
                except ModelProtocolError:pass
            if successes==0 or mode=='oneOf' and successes!=1:raise ModelProtocolError('Output does not match '+mode+' at '+path)
    for variant in schema.get('allOf',[]):_validate(value,variant,root,path)
    if 'enum' in schema and value not in schema['enum']:raise ModelProtocolError('Unexpected output enum at '+path)
    if 'const' in schema and value!=schema['const']:raise ModelProtocolError('Unexpected output constant at '+path)
    kind=schema.get('type')
    if isinstance(kind,list):
        for item in kind:
            try:_validate(value,dict(schema,type=item),root,path);return
            except ModelProtocolError:pass
        raise ModelProtocolError('Unexpected output type at '+path)
    matches={'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),
             'integer':type(value) is int,'number':type(value) is int or type(value) is float and math.isfinite(value),
             'boolean':type(value) is bool,'null':value is None}
    if kind and (kind not in matches or not matches[kind]):raise ModelProtocolError('Unexpected output type at '+path)
    if isinstance(value,dict):
        required=schema.get('required',[])
        if any(k not in value for k in required):raise ModelProtocolError('Missing required output field at '+path)
        props=schema.get('properties',{})
        if schema.get('additionalProperties') is False and set(value)-set(props):raise ModelProtocolError('Unexpected output fields at '+path)
        for key,child in value.items():
            if key in props:_validate(child,props[key],root,path+'.'+str(key))
            elif isinstance(schema.get('additionalProperties'),dict):_validate(child,schema['additionalProperties'],root,path+'.'+str(key))
    if isinstance(value,list):
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',10**9):raise ModelProtocolError('Output array length violates schema')
        if isinstance(schema.get('items'),dict):
            for item in value:_validate(item,schema['items'],root,path+'[]')
    if isinstance(value,str) and (len(value)<schema.get('minLength',0) or len(value)>schema.get('maxLength',10**9)):raise ModelProtocolError('Output string length violates schema')
    if type(value) in {int,float} and (value<schema.get('minimum',-math.inf) or value>schema.get('maximum',math.inf)):raise ModelProtocolError('Output number violates schema')


def _data(value,schema):
    value=_json(value) if isinstance(value,str) else value
    if not isinstance(value,dict):raise ModelProtocolError('Expected structured object output')
    value=_public(value)
    _validate(value,schema)
    return value


def _usage(raw=None,provider='unknown',cost=None):
    raw=raw if isinstance(raw,dict) else {}
    if provider=='codex':mapping={'input_tokens':'input_tokens','output_tokens':'output_tokens','cache_read_tokens':'cached_input_tokens','cache_write_tokens':'cache_write_input_tokens'}
    else:mapping={'input_tokens':'input_tokens','output_tokens':'output_tokens','cache_read_tokens':'cache_read_input_tokens','cache_write_tokens':'cache_creation_input_tokens'}
    result={k:raw.get(v) for k,v in mapping.items()}
    if provider=='openai':
        details=raw.get('input_tokens_details') or {}
        result['cache_read_tokens']=details.get('cached_tokens')
        result['cache_write_tokens']=details.get('cache_write_tokens')
    for key,value in result.items():
        if value is not None and (type(value) is not int or value<0):raise ModelProtocolError('Provider returned invalid usage counters')
    result['token_kind']='MEASURED' if any(result[k] is not None for k in TOKEN_KEYS) else 'UNKNOWN'
    result['actual_cost']=None
    if cost is not None:
        try:amount=Decimal(str(cost))
        except (InvalidOperation,ValueError):raise ModelProtocolError('Provider returned invalid reported cost') from None
        if isinstance(cost,bool) or not amount.is_finite() or amount<0:raise ModelProtocolError('Provider returned invalid reported cost')
        result['actual_cost']=str(amount)
    result['estimated_cost']=None
    return result


def _diagnostic(message):
    if not isinstance(message,str):return 'Provider reported an execution failure'
    text=str(redact(message))[:1000]
    text=re.sub(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}','[REDACTED]',text)
    return text[:400]


def _emit(callback,event):
    clean=_public(event)
    if callback and clean is not None:callback(clean)


def _check(request,cancel_check,start):
    if cancel_check and cancel_check():raise ExecutionCancelled('Execution cancelled; external completion/charges may require reconciliation')
    if time.monotonic()-start>float(request.timeout_seconds):raise ExecutionTimeout('Model invocation timed out; remote completion/charges are unknown')


def _request_valid(request):
    if not isinstance(request,InvocationRequest):raise TypeError('Expected InvocationRequest')
    if isinstance(request.timeout_seconds,bool) or not isinstance(request.timeout_seconds,(int,float)) or not math.isfinite(request.timeout_seconds) or not 0<request.timeout_seconds<=86400:raise ValueError('Invocation timeout must be positive and at most 86400 seconds')
    if not Path(request.workspace).is_dir():raise ValueError('Invocation workspace must exist')
    if not isinstance(request.output_schema,dict):raise ValueError('Structured output schema is required')


def _binary(name):
    candidate=shutil.which(str(name))
    return str(Path(candidate).resolve()) if candidate else None


def _limits(max_output_bytes,evidence_kind):
    if type(max_output_bytes) is not int or not 1024<=max_output_bytes<=64*1024*1024:
        raise ValueError('Model output limit must be 1024..67108864 bytes')
    if evidence_kind not in {'LIVE','SIMULATED'}:raise ValueError('Unknown model evidence kind')


def _stop(process):
    if process.poll() is not None and os.name!='posix':return
    try:
        if os.name=='posix':os.killpg(process.pid,signal.SIGTERM)
        else:process.terminate()
        process.wait(timeout=2)
    except (OSError,subprocess.TimeoutExpired):
        try:
            if os.name=='posix':os.killpg(process.pid,signal.SIGKILL)
            else:process.kill()
        except OSError:pass
        try:process.wait(timeout=2)
        except subprocess.TimeoutExpired:pass


def _process(request,args,prompt,consume,cancel_check,max_output_bytes):
    _request_valid(request);start=time.monotonic();_check(request,cancel_check,start)
    process=subprocess.Popen(args,cwd=Path(request.workspace).resolve(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        start_new_session=os.name=='posix')
    events=queue.Queue(maxsize=64)
    def read(pipe,label):
        try:
            while True:
                block=pipe.read1(4096)
                if not block:break
                while True:
                    try:events.put((label,block),timeout=.1);break
                    except queue.Full:
                        if process.poll() is not None:return
        finally:
            try:events.put((label,None),timeout=.2)
            except queue.Full:pass
    readers=[threading.Thread(target=read,args=(process.stdout,'out'),daemon=True),threading.Thread(target=read,args=(process.stderr,'err'),daemon=True)]
    for reader in readers:reader.start()
    def write():
        try:process.stdin.write(prompt.encode());process.stdin.close()
        except (BrokenPipeError,OSError,ValueError):pass
    writer=threading.Thread(target=write,daemon=True);writer.start()
    pending=b'';stderr_prefix=b'';total=0;closed=set()
    try:
        while len(closed)<2 or process.poll() is None:
            _check(request,cancel_check,start)
            try:label,block=events.get(timeout=.05)
            except queue.Empty:
                if process.poll() is not None and not any(t.is_alive() for t in readers):break
                continue
            if block is None:closed.add(label);continue
            total+=len(block)
            if total>max_output_bytes:raise ModelProtocolError('Model process output exceeded its configured limit')
            if label=='err':
                stderr_prefix=(stderr_prefix+block)[-4096:]
                continue # Never persist the raw stderr/transcript.
            pending+=block
            while b'\n' in pending:
                line,pending=pending.split(b'\n',1)
                if line.strip():consume(_json(line.decode('utf-8',errors='replace')))
        if pending.strip():consume(_json(pending.decode('utf-8',errors='replace')))
        code=process.wait(timeout=2)
        if code!=0:
            lines=stderr_prefix.decode('utf-8',errors='replace').splitlines()
            diagnostic=next((line for line in reversed(lines) if re.search(r'(?i)(?:^error|^fatal|^failed|permission denied|authentication failed|connection refused)',line)),'Model CLI exited unsuccessfully')
            consume({'type':'local_process_error','code':'EXIT_'+str(code),'message':_diagnostic(diagnostic)})
            raise ModelProtocolError('Model CLI exited unsuccessfully ('+str(code)+'): '+_diagnostic(diagnostic))
        return time.monotonic()-start
    finally:
        _stop(process)
        for pipe in [process.stdin,process.stdout,process.stderr]:
            try:pipe.close()
            except (OSError,ValueError):pass
        for reader in readers:reader.join(timeout=.2)
        writer.join(timeout=.2)


def _probe_command(args):
    try:
        result=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10,text=True,errors='replace')
        return result.returncode,(result.stdout+'\n'+result.stderr)[:20000]
    except (OSError,subprocess.TimeoutExpired):return None,''


class UnconfiguredAdapter:
    provider='unconfigured'
    def probe(self):return {'provider':self.provider,'available':False,'configured':False,'authenticated':False,'reason':UNAVAILABLE}
    def invoke(self,request,on_event=None,cancel_check=None,tool_gateway=None):raise RuntimeUnavailable(UNAVAILABLE)


class CodexCLIAdapter:
    provider='codex-cli'
    def __init__(self,cli_path='codex',model=None,max_output_bytes=4*1024*1024,evidence_kind='LIVE'):
        _limits(max_output_bytes,evidence_kind)
        self.cli_path=str(cli_path);self.model=model;self.max_output_bytes=int(max_output_bytes);self.evidence_kind=evidence_kind
    def probe(self):
        executable=_binary(self.cli_path)
        if not executable:return {'provider':self.provider,'available':False,'configured':False,'authenticated':False,'reason':UNAVAILABLE}
        code,text=_probe_command([executable,'--version']);version=re.search(r'codex-cli\s+([\w.\-]+)',text)
        auth_code,auth=_probe_command([executable,'login','status'])
        authenticated=auth_code==0 and bool(re.search(r'logged\s+in',auth,re.I)) and not bool(re.search(r'not\s+logged\s+in',auth,re.I))
        return {'provider':self.provider,'available':authenticated,'configured':True,'authenticated':authenticated,
            'version':version.group(1) if version else None,'execution_tested':False,
            'reason':'Authenticated CLI status observed; a real inference is still required' if authenticated else UNAVAILABLE}
    def invoke(self,request,on_event=None,cancel_check=None,tool_gateway=None):
        _request_valid(request);executable=_binary(self.cli_path)
        if not executable or not self.probe()['available']:raise RuntimeUnavailable(UNAVAILABLE)
        # Filesystem read-only does not constrain connected account tools.
        # Require the supported discovery command to prove no enabled MCP tools.
        mcp_code,mcp_text=_probe_command([executable,'mcp','list','--json'])
        try:mcp=json.loads(mcp_text)
        except (ValueError,TypeError):raise RuntimeUnavailable('Codex MCP isolation could not be verified; use a dedicated profile with no connected MCP tools') from None
        if mcp_code!=0 or not isinstance(mcp,list) or any(not isinstance(item,dict) or item.get('enabled',True) for item in mcp):
            raise RuntimeUnavailable('Codex connected MCP tools are not authorized by the runtime; use a dedicated profile with no enabled MCP servers')
        state={'session':None,'text':None,'usage':None,'completed':False,'failed':False,'tools':[],'error':None}
        def consume(event):
            if not isinstance(event,dict):raise ModelProtocolError('Malformed Codex event')
            kind=event.get('type')
            if kind=='thread.started':
                state['session']=event.get('thread_id');_emit(on_event,{'kind':'PROVIDER_SESSION','provider':self.provider,'session_id':state['session']})
            elif kind=='turn.completed':state.update(completed=True,usage=event.get('usage'))
            elif kind in {'turn.failed','error','local_process_error'}:
                error=event.get('error') if isinstance(event.get('error'),dict) else event
                diagnostic={'kind':'PROVIDER_ERROR','provider':self.provider,'code':str(error.get('code') or kind),'message':_diagnostic(error.get('message'))}
                state.update(failed=True,error=diagnostic);_emit(on_event,diagnostic)
            elif kind in {'item.started','item.updated','item.completed'}:
                item=event.get('item') or {};item_kind=item.get('type')
                if item_kind=='reasoning':return
                if item_kind=='agent_message' and kind=='item.completed':state['text']=item.get('text')
                elif item_kind in {'command_execution','file_change','mcp_tool_call','web_search','collab_tool_call'}:
                    safe={'kind':'PROVIDER_TOOL','tool':item_kind,'id':item.get('id'),'event':kind,'status':item.get('status')}
                    if type(item.get('exit_code')) is int:safe['exit_code']=item['exit_code']
                    state['tools'].append(safe);_emit(on_event,safe)
        with tempfile.TemporaryDirectory(prefix='agent-output-schema-') as directory:
            schema=Path(directory)/'output.json';schema.write_text(json.dumps(request.output_schema),encoding='utf-8')
            args=[executable,'exec','--json','--sandbox','read-only','--cd',str(Path(request.workspace).resolve()),
                '--ephemeral','--skip-git-repo-check','--output-schema',str(schema),'-c','web_search="disabled"']
            if self.model:args+=['--model',str(self.model)]
            args+=['-']
            prompt=json.dumps({'controller_instructions':request.system_prompt,'agent':request.agent,'stage':request.stage,
                'task':request.user_prompt,'execution_contract':'Return only the requested JSON. Do not invoke external actions, read credentials, install dependencies or modify any files. Artifacts are returned for the guarded controller.'},ensure_ascii=False)
            duration=_process(request,args,prompt,consume,cancel_check,self.max_output_bytes)
        if state['failed'] or not state['completed'] or state['text'] is None:raise ModelProtocolError('Codex did not report a successful structured terminal turn'+(': '+state['error']['message'] if state['error'] else ''))
        identity=state['session'] or request.id
        return InvocationResult(_data(state['text'],request.output_schema),self.provider,None,identity,'codex-session://'+str(identity),
            _usage(state['usage'],'codex'),duration,self.evidence_kind,state['tools'])


class ClaudeCodeAdapter:
    provider='claude-code'
    def __init__(self,cli_path='claude',model=None,max_turns=1,max_budget_usd=None,max_output_bytes=4*1024*1024,evidence_kind='LIVE'):
        _limits(max_output_bytes,evidence_kind)
        self.cli_path=str(cli_path);self.model=model;self.max_turns=int(max_turns);self.max_budget_usd=max_budget_usd;self.max_output_bytes=int(max_output_bytes);self.evidence_kind=evidence_kind
        if not 1<=self.max_turns<=20:raise ValueError('Claude max_turns must be 1..20')
        if max_budget_usd is not None:
            parsed=Decimal(str(max_budget_usd))
            if isinstance(max_budget_usd,bool) or not parsed.is_finite() or parsed<0:raise ValueError('Invalid Claude budget ceiling')
    def probe(self):
        executable=_binary(self.cli_path)
        if not executable:return {'provider':self.provider,'available':False,'configured':False,'authenticated':False,'reason':UNAVAILABLE}
        code,text=_probe_command([executable,'--version']);version=re.search(r'\b\d+\.\d+\.\d+\b',text)
        auth_code,auth=_probe_command([executable,'auth','status'])
        authenticated=False
        if auth_code==0:
            try:
                status=json.loads(auth.strip());authenticated=status.get('loggedIn') is True or status.get('authenticated') is True
            except (ValueError,AttributeError):authenticated=bool(re.search(r'logged in (?:as|using|with)|authenticated\s*[:=]\s*(?:true|yes)',auth,re.I)) and not bool(re.search(r'not\s+logged\s+in',auth,re.I))
        return {'provider':self.provider,'available':authenticated,'configured':True,'authenticated':authenticated,
            'version':version.group(0) if version else None,'execution_tested':False,'reason':'Authenticated CLI status observed; inference remains untested' if authenticated else UNAVAILABLE}
    def invoke(self,request,on_event=None,cancel_check=None,tool_gateway=None):
        _request_valid(request);executable=_binary(self.cli_path)
        if not executable or not self.probe()['available']:raise RuntimeUnavailable(UNAVAILABLE)
        state={'session':None,'model':None,'result':None,'structured':None,'usage':None,'cost':None,'completed':False,'failed':False,'tools':[],'error':None}
        def consume(event):
            if not isinstance(event,dict):raise ModelProtocolError('Malformed Claude event')
            kind=event.get('type')
            if kind=='system' and event.get('subtype')=='init':
                state['session']=event.get('session_id');_emit(on_event,{'kind':'PROVIDER_SESSION','provider':self.provider,'session_id':state['session']})
            elif kind=='assistant':
                message=event.get('message') or {};state['model']=message.get('model') or state['model']
                for block in message.get('content',[]):
                    if block.get('type') in {'thinking','redacted_thinking'}:continue
                    if block.get('type')=='tool_use':
                        safe={'kind':'PROVIDER_TOOL','tool':block.get('name'),'id':block.get('id'),'event':'tool_use'}
                        state['tools'].append(safe);_emit(on_event,safe)
            elif kind=='local_process_error':
                _emit(on_event,{'kind':'PROVIDER_ERROR','provider':self.provider,'code':event.get('code'),'message':_diagnostic(event.get('message'))})
            elif kind=='result':
                state.update(completed=True,failed=bool(event.get('is_error')) or event.get('subtype')!='success',
                    session=event.get('session_id') or state['session'],result=event.get('result'),structured=event.get('structured_output'),
                    usage=event.get('usage'),cost=event.get('total_cost_usd'))
                if event.get('terminal_reason') in {'aborted_streaming','aborted_tools'}:state['failed']=True
                if state['failed']:_emit(on_event,{'kind':'PROVIDER_ERROR','provider':self.provider,'code':event.get('api_error_status') or event.get('terminal_reason') or event.get('subtype'),'message':_diagnostic(event.get('result') or 'Claude reported an unsuccessful terminal result')})
        args=[executable,'--print','--output-format','stream-json','--verbose','--tools','',
            '--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--setting-sources=',
            '--permission-mode','dontAsk','--system-prompt',request.system_prompt,'--json-schema',json.dumps(request.output_schema),
            '--max-turns',str(self.max_turns)]
        if self.model:args+=['--model',str(self.model)]
        if self.max_budget_usd is not None:args+=['--max-budget-usd',str(self.max_budget_usd)]
        duration=_process(request,args,request.user_prompt,consume,cancel_check,self.max_output_bytes)
        if not state['completed'] or state['failed']:raise ModelProtocolError('Claude did not report a successful terminal result')
        identity=state['session'] or request.id
        value=state['structured'] if state['structured'] is not None else state['result']
        return InvocationResult(_data(value,request.output_schema),self.provider,state['model'],identity,'claude-session://'+str(identity),
            _usage(state['usage'],'claude',state['cost']),duration,self.evidence_kind,state['tools'])


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ModelProtocolError('Provider redirect refused; authentication never follows another endpoint')


class OpenAIResponsesAdapter:
    provider='openai-responses'
    def __init__(self,model=None,api_key_env='OPENAI_API_KEY',base_url='https://api.openai.com/v1',max_output_tokens=4096,max_tool_rounds=4,max_output_bytes=4*1024*1024,evidence_kind='LIVE',transport=None):
        _limits(max_output_bytes,evidence_kind)
        parsed=urllib.parse.urlsplit(base_url)
        if parsed.scheme!='https' or parsed.netloc!='api.openai.com' or parsed.path.rstrip('/')!='/v1' or parsed.query or parsed.fragment:raise ValueError('Only the documented official OpenAI Responses endpoint is supported')
        if not isinstance(api_key_env,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',api_key_env):raise ValueError('Invalid configured API credential variable name')
        self.model=model;self.api_key_env=api_key_env;self.base_url=base_url.rstrip('/');self.max_output_tokens=int(max_output_tokens)
        self.max_tool_rounds=int(max_tool_rounds);self.max_output_bytes=int(max_output_bytes);self.evidence_kind=evidence_kind;self.transport=transport
        if not 1<=self.max_output_tokens<=128000 or not 0<=self.max_tool_rounds<=20:raise ValueError('Invalid model output/tool-call limits')
    def probe(self):
        configured=bool(self.model and os.environ.get(self.api_key_env))
        return {'provider':self.provider,'available':configured,'configured':configured,'authenticated':None if configured else False,
            'execution_tested':False,'reason':'Configured credential reference; real authentication/inference untested' if configured else UNAVAILABLE}
    def _call(self,body,timeout):
        if self.transport is not None:
            if self.evidence_kind!='SIMULATED':raise ValueError('Injected test HTTP transports must be explicitly SIMULATED')
            result=self.transport(body,timeout)
            if isinstance(result,(str,bytes)):result=_json(result)
            return result
        token=os.environ.get(self.api_key_env)
        if not token or not self.model:raise RuntimeUnavailable(UNAVAILABLE)
        request=urllib.request.Request(self.base_url+'/responses',data=json.dumps(body).encode(),method='POST',
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request,timeout=timeout) as response:
                content=response.read(self.max_output_bytes+1)
                if len(content)>self.max_output_bytes:raise ModelProtocolError('Model HTTP output exceeded configured limit')
                return _json(content)
        except urllib.error.HTTPError as exc:raise ModelProtocolError('OpenAI HTTP request failed with status '+str(exc.code)+'; response body not persisted') from None
        except urllib.error.URLError:raise ModelProtocolError('OpenAI network request failed; remote completion/cost may be unknown') from None
    def invoke(self,request,on_event=None,cancel_check=None,tool_gateway=None):
        _request_valid(request)
        if not self.model or (not os.environ.get(self.api_key_env) and self.transport is None):raise RuntimeUnavailable(UNAVAILABLE)
        start=time.monotonic();items=[{'role':'user','content':request.user_prompt}];tools=[];events=[];usages=[];last_id=None;served_model=None
        if tool_gateway is not None:
            for name in ['schemas','definitions']:
                candidate=getattr(tool_gateway,name,None)
                if candidate is not None:tools=candidate() if callable(candidate) else candidate;break
            if not isinstance(tools,list) or any(not isinstance(t,dict) or t.get('type')!='function' or not isinstance(t.get('name'),str) for t in tools):raise ValueError('Only explicitly injected function tool definitions are supported')
        allowed={t['name'] for t in tools}
        for step in range(self.max_tool_rounds+1):
            _check(request,cancel_check,start)
            remaining=float(request.timeout_seconds)-(time.monotonic()-start)
            body={'model':self.model,'instructions':request.system_prompt,'input':items,'max_output_tokens':self.max_output_tokens,
                'store':False,'parallel_tool_calls':False,'text':{'format':{'type':'json_schema','name':'agent_result','strict':True,'schema':request.output_schema}}}
            if tools:body['tools']=tools
            result=self._call(body,max(.01,remaining));_check(request,cancel_check,start)
            if not isinstance(result,dict):raise ModelProtocolError('Malformed OpenAI response')
            identity=result.get('id')
            if not isinstance(identity,str) or not identity:raise ModelProtocolError('Provider response identifier is missing')
            last_id=identity;served_model=result.get('model') or served_model
            _emit(on_event,{'kind':'PROVIDER_RESPONSE','provider':self.provider,'response_id':identity,'status':result.get('status')})
            usages.append(_usage(result.get('usage'),'openai'))
            if result.get('status')!='completed':raise ModelProtocolError('Provider response did not complete successfully')
            output=result.get('output',[])
            if not isinstance(output,list):raise ModelProtocolError('Malformed OpenAI output array')
            calls=[o for o in output if isinstance(o,dict) and o.get('type')=='function_call']
            if calls:
                if tool_gateway is None or step>=self.max_tool_rounds:raise ModelProtocolError('Provider tool-call limit or permission boundary reached')
                items.extend(output) # Private continuation state remains only in transient RAM.
                for call in calls:
                    name=call.get('name');call_id=call.get('call_id')
                    if name not in allowed or not isinstance(call_id,str):raise ModelProtocolError('Provider requested an unauthorized function')
                    arguments=_json(call.get('arguments','{}'))
                    if not isinstance(arguments,dict):raise ModelProtocolError('Function arguments must be an object')
                    definition=next(t for t in tools if t['name']==name)
                    _validate(arguments,definition.get('parameters') or {'type':'object'})
                    _check(request,cancel_check,start)
                    event={'kind':'PROVIDER_TOOL','tool':name,'id':call_id,'event':'tool_call'};events.append(event);_emit(on_event,event)
                    executor=getattr(tool_gateway,'execute',None) or (tool_gateway if callable(tool_gateway) else None)
                    if executor is None:raise ValueError('Tool gateway has no guarded executor')
                    tool_result=executor(name,arguments)
                    items.append({'type':'function_call_output','call_id':call_id,'output':json.dumps(_public(tool_result),ensure_ascii=False)})
                continue
            texts=[]
            for item in output:
                if isinstance(item,dict) and item.get('type')=='message':
                    for content in item.get('content',[]):
                        if isinstance(content,dict) and content.get('type')=='output_text':texts.append(content.get('text',''))
            data=_data(''.join(texts),request.output_schema)
            total={k:sum(u[k] for u in usages) if all(u[k] is not None for u in usages) else None for k in TOKEN_KEYS}
            total.update(actual_cost=None,estimated_cost=None,token_kind='MEASURED' if any(total[k] is not None for k in TOKEN_KEYS) else 'UNKNOWN')
            return InvocationResult(data,self.provider,served_model,last_id,'openai-response://'+last_id,total,time.monotonic()-start,self.evidence_kind,events)
        raise ModelProtocolError('Provider tool-call loop did not produce a final result')


def from_config(config=None):
    if not isinstance(config,dict) or config.get('enabled',False) is not True:return UnconfiguredAdapter()
    provider=config.get('provider');options={k:v for k,v in config.items() if k not in {'enabled','provider'}}
    classes={'claude-code':ClaudeCodeAdapter,'claude':ClaudeCodeAdapter,'codex-cli':CodexCLIAdapter,'codex':CodexCLIAdapter,'openai-responses':OpenAIResponsesAdapter,'openai':OpenAIResponsesAdapter}
    if provider not in classes:raise ValueError('Unsupported model runtime provider')
    # A config file can never install a test transport or label fake execution live.
    if 'transport' in options or options.get('evidence_kind','LIVE')!='LIVE':raise ValueError('Production runtime config cannot enable a simulated provider')
    return classes[provider](**options)
