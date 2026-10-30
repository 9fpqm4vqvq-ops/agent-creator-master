"""Immutable staged proposals, independent QA links, scoped activation and recovery."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath

from .legacy import now, required
from .security import canonical, redact
from .freshness import approved_task
from .usage import atomic
from .migrations import backup


def file_hash(path):return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def safe_target(root,name):
    parts=PurePosixPath(name).parts
    if not parts or name!=PurePosixPath(name).as_posix() or '\\' in name or '..' in parts or PurePosixPath(name).is_absolute():raise ValueError('Unsafe change path')
    allowed=(parts[:2] in {('.claude','agents'),('.claude','skills')} or parts[0] in {'docs','agent_hub','dashboard'} or name in {'CLAUDE.md','AGENTS.md','README.md','registry/skills.json','registry/freshness-policies.json'})
    if not allowed or any(p in {'.git','__pycache__','.env','data','work'} for p in parts) or Path(name).suffix not in {'.py','.md','.json','.html','.css','.js'}:raise ValueError('Target is outside reviewed instruction/code paths')
    target=root/name
    # Reject links at every component, including links resolving back inside root.
    if any((root.joinpath(*parts[:i])).is_symlink() for i in range(1,len(parts)+1)) or not target.resolve().is_relative_to(root.resolve()):raise ValueError('Symlink change targets are prohibited')
    return target


class Improvements:
    def __init__(self,hub):self.hub=hub;self.db=hub.db;self.root=hub.root
    def folder(self,identity):
        try:uuid.UUID(identity)
        except (ValueError,TypeError):raise ValueError('Invalid proposal identity') from None
        path=self.root/'work/agent-changes'/identity
        if not path.resolve().is_relative_to(self.root.resolve()) or path.is_symlink():raise ValueError('Unsafe staging directory')
        return path
    def get(self,identity):
        row=self.db.execute('SELECT * FROM change_proposals WHERE id=?',(identity,)).fetchone()
        if row is None:raise ValueError('Unknown change proposal')
        result=dict(row)
        for key in ['files','tests','history']:result[key]=json.loads(result[key])
        return result
    def _update(self,proposal,status,detail,**fields):
        history=proposal['history']+[{'at':now(),'status':status,'detail':redact(detail)}]
        fields.update(status=status,updated_at=now(),history=canonical(history))
        self.db.execute('UPDATE change_proposals SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),proposal['id']))
    def propose(self,department,reason,files,health_review_id=None):
        from .roles import DOMAINS
        if department not in DOMAINS:raise ValueError('Unknown proposal department')
        required(reason,'Research-backed improvement reason')
        if not isinstance(files,dict) or not files:raise ValueError('Proposed text files are required')
        if health_review_id:
            review=self.hub.health.get(health_review_id)
            if review['department']!=department:raise ValueError('Health evidence must belong to this department')
        if any(n.startswith('.claude/skills/') for n in files) and 'registry/skills.json' not in files:raise ValueError('Skill updates must include reviewed registry metadata and candidate fingerprints')
        identity=str(uuid.uuid4());folder=self.folder(identity);folder.mkdir(parents=True)
        manifest={}
        try:
            for name,content in files.items():
                target=safe_target(self.root,name)
                if not isinstance(content,str) or len(content.encode())>1_000_000:raise ValueError('Proposal files must be bounded text')
                clean=redact(content)
                candidate=folder/'candidate'/name;candidate.parent.mkdir(parents=True,exist_ok=True);candidate.write_text(clean)
                manifest[name]={'baseline_sha256':file_hash(target),'candidate_sha256':file_hash(candidate)}
            manifest_hash=hashlib.sha256(canonical(manifest).encode()).hexdigest()
            with self.db:self.db.execute('INSERT INTO change_proposals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (identity,department,redact(reason),health_review_id,canonical(manifest),manifest_hash,'PROPOSED','[]',None,None,None,now(),now(),
                 canonical([{'at':now(),'status':'PROPOSED','detail':'Quarantined candidate; no activation implied'}])))
        except Exception:
            shutil.rmtree(folder);raise
        return self.get(identity)
    def _check(self,proposal):
        if hashlib.sha256(canonical(proposal['files']).encode()).hexdigest()!=proposal['manifest_hash']:raise ValueError('Proposal manifest changed')
        for name,hashes in proposal['files'].items():
            target=safe_target(self.root,name)
            candidate=self.folder(proposal['id'])/'candidate'/name
            if candidate.is_symlink() or not candidate.resolve().is_relative_to(self.folder(proposal['id']).resolve()):raise ValueError('Unsafe candidate')
            if file_hash(candidate)!=hashes['candidate_sha256']:raise ValueError('Candidate bytes changed; create a new proposal')
            if file_hash(target)!=hashes['baseline_sha256']:raise ValueError('Active baseline changed; research and rebase proposal')
    def stage(self,identity):
        proposal=self.get(identity)
        if proposal['status'] not in {'PROPOSED','STAGED','TESTED'}:raise ValueError('Only pending proposals can be staged')
        self._check(proposal);destination=self.folder(identity)/'sandbox'
        if destination.exists():shutil.rmtree(destination)
        def ignore(directory,names):
            for name in names:
                path=Path(directory)/name
                if path.is_symlink() and not path.resolve().is_relative_to(self.root):raise ValueError('External staging symlink refused')
            reviewed_data=self.root/'vendor/supplementary/ui-ux-pro-max-skill/data'
            excluded={'.git','data','memory','work','outputs','releases','node_modules','__pycache__'}
            return [n for n in names if
                (n in excluded and Path(directory)/n != reviewed_data) or
                n.endswith(('.sqlite','.pyc','.db')) or n.startswith('.env')]
        shutil.copytree(self.root,destination,ignore=ignore,symlinks=False)
        for name in proposal['files']:
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(self.folder(identity)/'candidate'/name,target)
        staged={str(p.relative_to(destination)):file_hash(p) for p in destination.rglob('*') if p.is_file()}
        (self.folder(identity)/'sandbox-manifest.json').write_text(canonical(staged))
        with self.db:self._update(proposal,'STAGED','Isolated copy created; candidate code has not been executed',tests='[]',qa_task_id=None)
        return {'proposal':identity,'sandbox':str(destination),'executed':False}
    def test(self,identity):
        proposal=self.get(identity)
        if proposal['status']!='STAGED':raise ValueError('Stage before explicitly running tests')
        self._check(proposal);sandbox=self.folder(identity)/'sandbox'
        staged=json.loads((self.folder(identity)/'sandbox-manifest.json').read_text())
        if any(file_hash(sandbox/name)!=value for name,value in staged.items()):raise ValueError('Isolated stage changed; stage again before testing')
        # Explicit operator command runs project tests, never a command supplied by a skill.
        command=[sys.executable,'scripts/validate_all.py']
        if not (sandbox/'scripts/validate_all.py').is_file():raise ValueError('Validation runner missing')
        result=subprocess.run(command,cwd=sandbox,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
        log=self.folder(identity)/'test-results.txt';log.write_text(redact(result.stdout))
        tests=[{'command':'python scripts/validate_all.py','result':'PASS' if result.returncode==0 else 'FAIL',
                'reference':str(log.relative_to(self.root)),'sha256':file_hash(log),'manifest_hash':proposal['manifest_hash']}]
        with self.db:self._update(proposal,'TESTED' if result.returncode==0 else 'TEST_FAILED','Executed isolated regression suite',tests=canonical(tests))
        return self.get(identity)
    def qa(self,identity,task_id):
        proposal=self.get(identity);self._check(proposal)
        if proposal['status']!='TESTED' or not proposal['tests'] or any(t['result']!='PASS' or file_hash(self.root/t['reference'])!=t['sha256'] for t in proposal['tests']):raise ValueError('Unchanged passing staged test evidence is required')
        result,record=approved_task(self.hub,task_id,'change_proposal_ids',identity)
        if result.get('change_manifest_hashes',{}).get(identity)!=proposal['manifest_hash']:raise ValueError('QA did not assess this exact immutable change manifest')
        if 'agent-creator-researcher' not in result.get('authors',[]) and 'agent-creator' not in result.get('authors',[]):raise ValueError('Agent Development must author the researched change review packet')
        with self.db:self._update(proposal,'QA_APPROVED','Independent QA completed; Management authorization still required',qa_task_id=task_id)
        return self.get(identity)
    def _idle(self):
        if self.db.execute("SELECT 1 FROM tasks WHERE phase NOT IN ('COMPLETED','CANCELLED') LIMIT 1").fetchone():raise ValueError('Finish or cancel active tasks before changing instructions')
        if self.db.execute("SELECT 1 FROM maintenance_runs WHERE status='RUNNING' LIMIT 1").fetchone():raise ValueError('Stop active maintenance before activation')
        # Runtime tables are additive and may not exist in older Vaults or test
        # fixtures. Do not infer idleness from a cancelled task while its provider
        # or tool process still has a live lifecycle record.
        terminal={'COMPLETED','FAILED','BLOCKED','CANCELLED','SUCCEEDED','DONE','INTERRUPTED','EXPIRED','REJECTED','TIMED_OUT','OUTPUT_LIMIT','REPLACED'}
        tables={row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ('agent_runs','agent_invocations','tool_processes','runtime_tool_processes','workspace_processes'):
            if table not in tables:
                continue
            columns={row[1] for row in self.db.execute('PRAGMA table_info('+table+')')}
            state='status' if 'status' in columns else 'state' if 'state' in columns else None
            if state:
                marks=','.join('?' for _ in terminal)
                active=self.db.execute('SELECT 1 FROM '+table+' WHERE '+state+' IS NULL OR UPPER('+state+') NOT IN ('+marks+') LIMIT 1',tuple(terminal)).fetchone()
            elif 'finished_at' in columns:
                active=self.db.execute('SELECT 1 FROM '+table+' WHERE finished_at IS NULL LIMIT 1').fetchone()
            else:
                raise ValueError('Cannot establish runtime idleness for '+table+'; lifecycle state is unavailable')
            if active:
                raise ValueError('Stop active agent/provider/tool execution before changing instructions: '+table)
            for flag in ('process_active','process_alive','is_running'):
                if flag in columns and self.db.execute('SELECT 1 FROM '+table+' WHERE '+flag+'=1 LIMIT 1').fetchone():
                    raise ValueError('Stop the live tool/provider process before changing instructions: '+table)
            if 'pid' in columns and 'finished_at' in columns:
                for process in self.db.execute('SELECT pid FROM '+table+' WHERE finished_at IS NULL AND pid IS NOT NULL'):
                    pid=process[0]
                    if not isinstance(pid,int) or pid<=0:
                        raise ValueError('Cannot establish unfinished process idleness: '+table)
                    try:
                        os.kill(pid,0)
                    except ProcessLookupError:
                        continue
                    except PermissionError:
                        pass # A live but inaccessible process is not safely idle.
                    raise ValueError('Stop the live tool/provider process before changing instructions: '+table)

    def activate(self,identity,authorization_reference,allow_permission_expansion=False):
        required(authorization_reference,'Actual scoped activation authorization')
        proposal=self.get(identity)
        if proposal['status']!='QA_APPROVED':raise ValueError('Independent QA must precede Management activation')
        self._check(proposal)
        if any(file_hash(self.root/t['reference'])!=t['sha256'] for t in proposal['tests']):raise ValueError('Test evidence changed')
        result,_=approved_task(self.hub,proposal['qa_task_id'],'change_proposal_ids',identity)
        if result.get('change_manifest_hashes',{}).get(identity)!=proposal['manifest_hash']:raise ValueError('Reviewed manifest changed')
        permission_change=bool(result.get('permission_expansion',False))
        for name in proposal['files']:
            if name.startswith('.claude/agents/'):
                old=safe_target(self.root,name);oldtext=old.read_text() if old.exists() else ''
                new=(self.folder(identity)/'candidate'/name).read_text()
                tools=lambda text:next((line for line in text.splitlines() if line.startswith('tools:')),'')
                if tools(oldtext)!=tools(new):permission_change=True
        if permission_change and not allow_permission_expansion:raise PermissionError('Explicit scoped permission-expansion authorization is required')
        if 'registry/skills.json' in proposal['files']:
            records=json.loads((self.folder(identity)/'candidate/registry/skills.json').read_text())['skills']
            for record in records:
                prior=self.db.execute('SELECT record FROM skill_registry WHERE id=?',(record.get('id'),)).fetchone()
                if not prior:permission_change=True
                elif any(json.loads(prior[0]).get(k)!=record.get(k) for k in ['permissions','supported_agents','supported_departments','dependencies']):permission_change=True
            if permission_change and not allow_permission_expansion:raise PermissionError('Registry capability or dependency changes need explicit scoped authorization')
        saved=self.folder(identity)/'backup';saved.mkdir(exist_ok=True)
        (saved/'skill-registry.json').write_text(canonical([dict(r) for r in self.db.execute('SELECT * FROM skill_registry')]))
        backup(self.db,saved/('vault-'+str(uuid.uuid4())+'.sqlite'))
        with atomic(self.db):
            self._idle();self._check(proposal)
            for name in proposal['files']:
                target=safe_target(self.root,name)
                if target.exists():
                    destination=saved/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,destination)
            self._update(proposal,'ACTIVATING','Backup complete; recover() restores after process interruption',backup_path=str(saved.relative_to(self.root)),authorization_reference=redact(authorization_reference))
        # Persist intent before filesystem mutations so restart can recover partial writes.
        try:
            for name in proposal['files']:
                target=safe_target(self.root,name);target.parent.mkdir(parents=True,exist_ok=True)
                temp=target.with_name(target.name+'.v04-tmp');shutil.copyfile(self.folder(identity)/'candidate'/name,temp);os.replace(temp,target)
            with atomic(self.db):
                if 'registry/skills.json' in proposal['files']:
                    from .skills import skill_fingerprint
                    document=json.loads((self.root/'registry/skills.json').read_text())
                    for record in document['skills']:
                        self.hub.skills._validate_shape(record)
                        current=skill_fingerprint(self.root,record['path'])
                        if current!=record['fingerprint']:raise ValueError('Reviewed registry fingerprint does not match activated skill bytes')
                        old=self.db.execute('SELECT * FROM skill_registry WHERE id=?',(record['id'],)).fetchone()
                        if old and old['fingerprint']==current and json.loads(old['record'])==record:continue
                        self.db.execute("INSERT INTO skill_registry VALUES(?,?,?,'VALIDATED',?) ON CONFLICT(id) DO UPDATE SET record=excluded.record,fingerprint=excluded.fingerprint,security_status='VALIDATED',validated_at=excluded.validated_at",
                            (record['id'],canonical(record),current,now()))
                self._remember(proposal,'ACTIVATED',authorization_reference)
        except BaseException:
            self._restore(proposal,saved)
            with self.db:self._update(self.get(identity),'ROLLED_BACK','Activation failed; original files restored')
            raise
        with self.db:self._update(self.get(identity),'ACTIVE','Reviewed bytes activated; authorization reference is operator attestation, not identity authentication')
        return self.get(identity)
    def _restore(self,proposal,saved):
        for name,hashes in proposal['files'].items():
            safe_target(self.root,name)
            if hashes['baseline_sha256'] is not None and file_hash(saved/name)!=hashes['baseline_sha256']:raise ValueError('Rollback backup hash mismatch')
        for name,hashes in proposal['files'].items():
            target=safe_target(self.root,name)
            if hashes['baseline_sha256'] is None:target.unlink(missing_ok=True)
            else:
                source=saved/name
                if file_hash(source)!=hashes['baseline_sha256']:raise ValueError('Rollback backup hash mismatch')
                shutil.copyfile(source,target)
            target.with_name(target.name+'.v04-tmp').unlink(missing_ok=True)
        metadata=saved/'skill-registry.json'
        if metadata.is_file():
            original=json.loads(metadata.read_text());ids={r['id'] for r in original}
            with atomic(self.db):
                for row in self.db.execute('SELECT id FROM skill_registry').fetchall():
                    if row[0] not in ids:self.db.execute("UPDATE skill_registry SET security_status='QUARANTINED' WHERE id=?",(row[0],))
                for row in original:self.db.execute('INSERT INTO skill_registry VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record,fingerprint=excluded.fingerprint,security_status=excluded.security_status,validated_at=excluded.validated_at',tuple(row[k] for k in ['id','record','fingerprint','security_status','validated_at']))

    def _remember(self,proposal,action,reference):
        self.hub.memory.put('research','reviewed-agent-change',action+' '+proposal['id'],
            {'proposal_id':proposal['id'],'manifest_hash':proposal['manifest_hash'],'qa_task_id':proposal['qa_task_id'],
             'authorization_reference':reference,'files':proposal['files'],'action':action},'agent-creator-researcher',
            sources=[{'location':'change://'+proposal['id'],'checked_at':now(),'classification':'HISTORICAL'}],confidence='QA_APPROVED_OPERATOR',category='procedure',commit=False)

    def rollback(self,identity,authorization_reference,recovery=False):
        required(authorization_reference,'Rollback authorization/incident reference')
        proposal=self.get(identity)
        if proposal['status'] not in ({'ACTIVATING','ROLLING_BACK'} if recovery else {'ACTIVE'}):raise ValueError('No matching activated/interrupted change')
        self._idle()
        for name,hashes in proposal['files'].items():
            observed=file_hash(safe_target(self.root,name))
            allowed={hashes['candidate_sha256'],hashes['baseline_sha256']} if recovery else {hashes['candidate_sha256']}
            if observed not in allowed:raise ValueError('Active file has later edits; manual conflict review required')
        with atomic(self.db):
            self._idle()
            self._update(proposal,'ROLLING_BACK',{'reference':authorization_reference,'recovery':recovery})
        self._restore(proposal,self.root/proposal['backup_path'])
        with self.db:
            self._remember(proposal,'ROLLED_BACK',authorization_reference)
        with self.db:self._update(proposal,'ROLLED_BACK',{'reference':authorization_reference,'recovery':recovery})
        return self.get(identity)
