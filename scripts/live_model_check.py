#!/usr/bin/env python3
"""Explicit authorized live inference probe. Not part of automatic unit tests."""
import argparse,hashlib,json,os,shutil,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_hub.model_adapters import CodexCLIAdapter,ClaudeCodeAdapter,OpenAIResponsesAdapter,InvocationRequest,_public,_probe_command,_diagnostic,from_config
from agent_hub.legacy import now

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--config',type=Path);args=p.parse_args()
 identity=str(uuid.uuid4());workspace=args.out.parent/'model-probe-workspace';workspace.mkdir(parents=True,exist_ok=True)
 schema={'type':'object','properties':{'test_id':{'type':'string','enum':[identity]},'status':{'type':'string','enum':['READY']}},'required':['test_id','status'],'additionalProperties':False}
 adapters=[ClaudeCodeAdapter(),CodexCLIAdapter(),OpenAIResponsesAdapter(model=os.environ.get('MAS_OPENAI_MODEL'))]
 if args.config:adapters=[from_config(json.loads(args.config.read_text()).get('model',{}))]
 report={'test_id':identity,'started_at':now(),'classification':'LIVE_ATTEMPT_NO_MOCKS','providers':[]}
 for adapter in adapters:
  item={'provider':adapter.provider,'started_at':now(),'probe':adapter.probe(),'status':'BLOCKED'}
  if adapter.provider=='codex-cli' and shutil.which('codex'):
   code,data=_probe_command(['codex','mcp','list','--json'],json_stdout_only=True)
   try:parsed=json.loads(data);item['mcp_check']={'exit_code':code,'parseable':isinstance(parsed,list),'server_count':len(parsed) if isinstance(parsed,list) else None}
   except ValueError:item['mcp_check']={'exit_code':code,'parseable':False,'error':_diagnostic(data)}
  if item['probe'].get('available') and item['probe'].get('authenticated'):
   request=InvocationRequest(str(uuid.uuid4()),str(uuid.uuid4()),0,'runtime-probe','PROBE',
    'Authorized harmless inference test. No tools, filesystem reads, external actions or private reasoning. Return requested JSON only.',
    'Return status READY and test_id '+identity,schema,workspace,60)
   events=[]
   try:
    result=adapter.invoke(request,on_event=events.append)
    item.update(status='PASS',model=result.model,invocation_id=result.invocation_id,reference=result.reference,usage=result.usage,
     output_hash=hashlib.sha256(json.dumps(result.data,sort_keys=True).encode()).hexdigest(),output=result.data,evidence_kind=result.evidence_kind)
   except Exception as exc:item.update(error_type=type(exc).__name__,error=str(_public(str(exc))))
   item['events']=events
  else:item['error']='Executable, authentication or explicit API model/credential configuration unavailable'
  item['finished_at']=now();report['providers'].append(item)
 report['finished_at']=now();args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(_public(report),indent=2)+'\n');print(json.dumps(_public(report),indent=2))
if __name__=='__main__':main()
