"""Evidence policies: command success alone never proves application acceptance."""
import hashlib,json,re
from .security import safe_file

WEB={
 'static-website':['content','responsive','accessibility','security'],
 'frontend-application':['functionality','input_handling','error_handling','persistence','responsive','accessibility','security'],
 'backend-api':['functionality','input_handling','error_handling','persistence','security'],
 'full-stack':['functionality','input_handling','error_handling','persistence','responsive','accessibility','security'],
 'ecommerce':['catalogue','cart','checkout_validation','payment_sandbox','persistence','security','accessibility'],
 'dashboard':['data_accuracy','filters','empty_error_states','responsive','accessibility','security']}
SOCIAL={
 'post':['accuracy','brand','originality','readability','platform','authorization'],
 'campaign':['strategy','accuracy','brand','sources','originality','calendar','authorization'],
 'calendar':['dates_timezone','audience','brand','sources','authorization'],
 'carousel':['asset_exists','dimensions','readability','brand','licensing','platform','authorization'],
 'short-video':['rendered_video','duration','dimensions','audio_licensing','sources','brand','platform','authorization'],
 'analytics':['actual_dataset','metric_definitions','period','calculations','limitations','sources'],
 'brand-identity':['assets_exist','brand','originality','licensing','readability','usage_guidelines']}


def validate_web(runtime,run_id,checks,snapshot):
 policy=runtime.config.get('acceptance',{})
 template=policy.get('template','frontend-application')
 if template not in WEB:raise ValueError('Choose a registered web acceptance template')
 required=set(WEB[template])|set(policy.get('required_assertions',[]))
 verifiers=policy.get('verifier_files',{})
 if not verifiers:raise ValueError('Web functional acceptance needs reviewed verifier_files hashes; trivial commands are insufficient')
 validate_verifiers(snapshot,verifiers)
 covered=set()
 for check in checks:
  if check['status']!='PASS' or check['input_hash']!=snapshot['sha256']:continue
  argv=json.loads(check['argv'])
  # A verifier must actually be an argument to the executed command, not just exist.
  if not any(path in argv for path in verifiers):continue
  try:result=json.loads(check['output'])
  except (ValueError,TypeError):continue
  if result.get('status')!='PASS' or not isinstance(result.get('assertions'),list):continue
  for row in result['assertions']:
   if not isinstance(row,dict) or row.get('status')!='PASS' or not row.get('evidence'):continue
   if row.get('kind') not in {'FUNCTIONAL','BROWSER','SECURITY','ACCESSIBILITY','RESPONSIVE','PERSISTENCE'}:continue
   required_kind={'responsive':'RESPONSIVE','accessibility':'ACCESSIBILITY','security':'SECURITY','persistence':'PERSISTENCE'}.get(row.get('id'))
   if required_kind and row['kind']!=required_kind:continue
   covered.add(row.get('id'))
 missing=sorted(required-covered)
 if missing:raise ValueError('Missing current-byte functional acceptance assertions: '+', '.join(missing))
 return {'template':template,'assertions':sorted(covered),'input_hash':snapshot['sha256'],
         'evidence_level':'LOCAL_TESTED','limitation':'Reviewed verifier provenance is required; JSON assertion text alone is not independent proof.'}


def templates():
 return {'web':{k:{'required_assertions':v,'requires':'Reviewed verifier hash, executed command, exact workspace bytes and structured assertion results'} for k,v in WEB.items()},
 'social':{k:{'required_checks':v,'rule':'Scripts are briefs, scheduling plans are drafts, publishing requires independent explicit authorization; absent rendering is BLOCKED'} for k,v in SOCIAL.items()}}


def validate_social(runtime,run_id,result):
 policy=runtime.config.get('acceptance',{});template=policy.get('template')
 if template is None:return {'template':'post','status':'QA_CHECKS_REQUIRED','limitation':'No specialized media/analytics acceptance profile selected'}
 if template not in SOCIAL:raise ValueError('Unknown Social Media acceptance template')
 files=[runtime.hub.root/p for p in result['artifacts']]
 if template=='short-video':
  media=[p for p in files if p.suffix.lower() in {'.mp4','.webm','.mov'}]
  if not media:raise ValueError('Rendered video absent: script/production brief is not a completed video')
  for p in media:
   with p.open('rb') as stream:header=stream.read(32)
   if b'ftyp' not in header and not header.startswith(b'\x1aE\xdf\xa3'):raise ValueError('Video file has no supported container signature')
  snapshot=runtime.workspaces.snapshot(run_id);verifiers=policy.get('media_verifier_files',{})
  if not verifiers:raise ValueError('Video acceptance BLOCKED: reviewed media verifier and current-byte decode/dimension/duration checks required')
  validate_verifiers(snapshot,verifiers)
  assertions=set()
  for row in runtime.db.execute('SELECT * FROM workspace_checks WHERE run_id=?',(run_id,)):
   if row['status']!='PASS' or row['input_hash']!=snapshot['sha256']:continue
   if not any(path in json.loads(row['argv']) for path in verifiers):continue
   try:payload=json.loads(row['output'])
   except (ValueError,TypeError):continue
   if payload.get('status')!='PASS':continue
   for assertion in payload.get('assertions',[]):
    if isinstance(assertion,dict) and assertion.get('status')=='PASS' and assertion.get('kind')=='MEDIA' and assertion.get('evidence'):assertions.add(assertion.get('id'))
  if not {'media_decode','dimensions','duration'}.issubset(assertions):raise ValueError('Video acceptance BLOCKED: actual current-byte media checks missing')
 if template in {'carousel','brand-identity'} and not any(p.suffix.lower() in {'.png','.jpg','.jpeg','.svg','.webp','.pdf'} for p in files):
  raise ValueError('Actual visual assets absent; a brief alone cannot satisfy asset delivery')
 if template=='analytics':
  inputs=policy.get('dataset_inputs',{})
  if not inputs:raise ValueError('Analytics requires operator-supplied dataset provenance, not invented metrics')
  for path,digest in inputs.items():
   source=safe_file(runtime.hub.root,path)
   if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise ValueError('Analytics dataset bytes changed')
 return {'template':template,'required_review_checks':SOCIAL[template],
  'publication_state':'DRAFT_ONLY; no publication inferred','status':'STRUCTURAL_CHECKS_PASSED_NOT_CONTENT_OR_LICENSE_VERIFICATION'}


def validate_verifiers(snapshot,verifiers):
 if not isinstance(verifiers,dict) or not verifiers:raise ValueError('Reviewed verifier files must be a nonempty hash map')
 for path,digest in verifiers.items():
  if not isinstance(path,str) or not isinstance(digest,str) or not re.fullmatch(r'[a-fA-F0-9]{64}',digest):raise ValueError('Reviewed verifier requires an existing file and 64-hex SHA256')
  if path not in snapshot['files'] or snapshot['files'][path].get('sha256')!=digest.lower():raise ValueError('Reviewed verifier bytes changed or are absent')
