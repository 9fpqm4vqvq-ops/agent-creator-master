"""Explicit supervised bridge to an authenticated interactive host's Agent tool.

This is an operator-mediated mailbox, not a subscription API or unattended broker.
Only a trusted host may instantiate it after verifying actual Agent-tool access.
Production JSON provider configuration cannot enable it. Local mailbox receipts
are operator attestations, not cryptographic provider-identity proof.
"""
import json,time,uuid
from pathlib import Path
from .model_adapters import InvocationResult,RuntimeUnavailable,ExecutionCancelled,ExecutionTimeout,_data,_public
from .legacy import now,required
from .security import canonical

class SupervisedHostAdapter:
 provider='supervised-host-agent-tool';model=None;evidence_kind='LIVE_HOST_MEDIATED'
 def __init__(self,directory,host_authorization_reference,evidence_kind='LIVE_HOST_MEDIATED'):
  required(host_authorization_reference,'Actual authenticated host Agent-tool authorization reference')
  self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
  if self.directory.is_symlink():raise ValueError('Host mailbox cannot be a symlink')
  if evidence_kind not in {'LIVE_HOST_MEDIATED','SIMULATED'}:raise ValueError('Explicit live host versus fixture evidence required')
  self.evidence_kind=evidence_kind
  self.reference=host_authorization_reference
 def probe(self):
  return {'provider':self.provider,'available':True,'configured':True,'authenticated':True,
   'authentication_basis':'SIMULATED fixture' if self.evidence_kind=='SIMULATED' else 'Trusted operator attests actual authenticated host Agent-tool access',
   'unattended_api':False,'execution_tested':False,'reference':self.reference}
 def invoke(self,request,on_event=None,cancel_check=None,tool_gateway=None):
  challenge=str(uuid.uuid4());start=time.monotonic();response=self.directory/(request.id+'.response.json')
  if response.exists():raise ValueError('Refuse stale/replayed host response')
  record={'invocation_id':request.id,'run_id':request.run_id,'task_id':request.task_id,'agent':request.agent,'stage':request.stage,
   'challenge':challenge,'created_at':now(),'system_prompt':request.system_prompt,'user_prompt':request.user_prompt,
   'output_schema':request.output_schema,'security':'Return JSON only. No tool execution, filesystem edits, deployment, publishing or reasoning transcript.'}
  target=self.directory/(request.id+'.request.json');target.write_text(canonical(record))
  while time.monotonic()-start<request.timeout_seconds:
   if cancel_check and cancel_check():raise ExecutionCancelled('Host execution cancellation requested; remote outcome may remain unknown')
   if response.exists():
    if response.is_symlink() or response.stat().st_size>4*1024*1024:raise ValueError('Unsafe or oversized host response')
    try:value=json.loads(response.read_text())
    except (json.JSONDecodeError,FileNotFoundError):
     time.sleep(.1);continue # A host may still be publishing; never treat partial JSON as a completed result.
    if value.get('challenge')!=challenge or value.get('invocation_id')!=request.id:raise ValueError('Host response challenge/invocation mismatch')
    required(value.get('reference'),'Actual host Agent-tool invocation reference')
    data=_data(_public(value.get('data')),request.output_schema)
    return InvocationResult(data,self.provider,None,request.id,value['reference'],{'token_kind':'UNKNOWN'},time.monotonic()-start,self.evidence_kind)
   time.sleep(.1)
  raise ExecutionTimeout('Host bridge timed out; no successful Agent-tool response received')


def publish_host_response(request_path,reference,data):
 """Trusted host helper: atomically publish a challenge-bound public response."""
 import os,tempfile
 request_path=Path(request_path)
 if request_path.is_symlink() or not request_path.name.endswith('.request.json'):raise ValueError('Use the actual regular host request path')
 request=json.loads(request_path.read_text());required(reference,'Actual host tool invocation reference')
 response=request_path.with_name(request_path.name.replace('.request.json','.response.json'))
 if response.exists():raise ValueError('Host response is already published')
 content=canonical({'invocation_id':request['invocation_id'],'challenge':request['challenge'],'reference':reference,'data':_public(data)})
 fd,name=tempfile.mkstemp(prefix='.response-',suffix='.tmp',dir=request_path.parent)
 try:
  with os.fdopen(fd,'w') as stream:stream.write(content);stream.flush();os.fsync(stream.fileno())
  os.replace(name,response)
 finally:
  if Path(name).exists():Path(name).unlink()
 return str(response)
