"""Draft-first content/calendar records, verified publication receipts and supplied analytics."""
import csv
import hashlib
import html
import io
import json
import uuid
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError

from .legacy import now,required,validate_sources
from .usage import atomic,instant,amount
from .security import canonical,redact,safe_file
from .freshness import approved_task
from .projects import write_artifacts

PLATFORMS={'instagram','facebook','tiktok','youtube','linkedin','x','pinterest','other'}


class SocialService:
    def __init__(self,hub):self.hub=hub;self.db=hub.db
    def _hash(self,platform,title,payload,scheduled_at,timezone,timing_basis):
        assets={p:hashlib.sha256(safe_file(self.hub.root,p).read_bytes()).hexdigest() for p in payload.get('assets',[])}
        return hashlib.sha256(canonical({'platform':platform,'title':title,'payload':payload,'assets':assets,
            'scheduled_at':scheduled_at,'timezone':timezone,'timing_basis':timing_basis}).encode()).hexdigest()
    def get(self,identity):
        row=self.db.execute('SELECT * FROM content_items WHERE id=?',(identity,)).fetchone()
        if row is None:raise ValueError('Unknown content item')
        item=dict(row,payload=json.loads(row['payload']))
        item['current_hash']=self._hash(item['platform'],item['title'],item['payload'],item['scheduled_at'],item['timezone'],item['timing_basis'])
        item['asset_integrity']=item['current_hash']==item['content_hash']
        return item
    def list(self,project_id=None):return [self.get(r['id']) for r in self.db.execute('SELECT id,project_id FROM content_items ORDER BY scheduled_at,created_at') if project_id is None or r['project_id']==project_id]
    def _history(self,item,actor,reason):
        self.db.execute('INSERT OR IGNORE INTO content_history VALUES(?,?,?,?,?,?)',(item['id'],item['revision'],canonical(item),actor,reason,now()))
    def _validate(self,platform,title,payload,scheduled_at,timezone,timing_basis):
        if platform not in PLATFORMS:raise ValueError('Unknown content platform')
        required(title,'Content title')
        if not isinstance(payload,dict) or not isinstance(payload.get('copy'),str) or not payload['copy'].strip():raise ValueError('Original draft copy is required')
        if not isinstance(payload.get('assets',[]),list):raise ValueError('Assets must be local file paths')
        for asset in payload.get('assets',[]):safe_file(self.hub.root,asset)
        validate_sources(payload.get('sources',[]))
        try:ZoneInfo(timezone)
        except (ZoneInfoNotFoundError,TypeError):raise ValueError('Use an actual IANA audience timezone') from None
        if scheduled_at:instant(scheduled_at)
        if timing_basis not in {'HYPOTHESIS','ACCOUNT_ANALYTICS'}:raise ValueError('Posting times need an explicit evidence basis')
        if timing_basis=='ACCOUNT_ANALYTICS':required(payload.get('analytics_reference'),'Actual account analytics reference')
    def create(self,project_id,task_id,platform,title,payload,scheduled_at=None,timezone='Asia/Baghdad',timing_basis='HYPOTHESIS'):
        project=self.hub.projects.get(project_id);task=self.hub.task(task_id)
        if project['kind']!='social' or task['project_id']!=project_id or task['department']!='social-media' or task['phase']!='IN_PROGRESS':raise ValueError('Create content within a started Social Media task and campaign')
        self.hub.check_snapshot(task);self._validate(platform,title,payload,scheduled_at,timezone,timing_basis)
        payload=redact(payload);title=redact(title);digest=self._hash(platform,title,payload,scheduled_at,timezone,timing_basis);identity=str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO content_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (identity,project_id,task_id,platform,title,canonical(payload),digest,1,'DRAFT',scheduled_at,timezone,timing_basis,None,None,now(),now()))
            self._history(self.get(identity),task['owner'],'Draft created; calendar entry does not schedule a platform post')
            self.hub.event(task_id,'CONTENT_DRAFT',{'item_id':identity,'hash':digest,'platform':platform},task['owner'])
        return self.get(identity)
    def update(self,identity,payload,expected_revision,scheduled_at=None,timezone=None,timing_basis=None):
        item=self.get(identity)
        if item['revision']!=expected_revision or item['status'] in {'SCHEDULED','PUBLISHED','ARCHIVED'}:raise ValueError('Content revision conflict or external/archived item; create a new draft')
        scheduled_at=scheduled_at if scheduled_at is not None else item['scheduled_at'];timezone=timezone or item['timezone'];timing_basis=timing_basis or item['timing_basis']
        self._validate(item['platform'],item['title'],payload,scheduled_at,timezone,timing_basis);payload=redact(payload)
        digest=self._hash(item['platform'],item['title'],payload,scheduled_at,timezone,timing_basis)
        with atomic(self.db):
            if self.db.execute("SELECT 1 FROM external_actions WHERE subject_hash=? AND (status IN ('STARTED','UNKNOWN_NEEDS_RECONCILIATION') OR (status='VERIFIED' AND evidence_kind!='SIMULATED'))",(item['content_hash'],)).fetchone():raise ValueError('External action already started; reconcile its receipt before editing content')
            cur=self.db.execute("UPDATE content_items SET payload=?,content_hash=?,revision=revision+1,status='DRAFT',scheduled_at=?,timezone=?,timing_basis=?,qa_task_id=NULL,remote_reference=NULL,updated_at=? WHERE id=? AND revision=?",(canonical(payload),digest,scheduled_at,timezone,timing_basis,now(),identity,expected_revision))
            if cur.rowcount!=1:raise ValueError('Content revision conflict')
            self._history(self.get(identity),self.hub.task(item['task_id'])['owner'],'Edited content invalidates review and approval')
        return self.get(identity)
    def internal_review(self,identity,evidence,actor='social-compliance-content-reviewer'):
        required(evidence,'Actual internal content/brand/license checks')
        item=self.get(identity)
        if actor not in {'social-compliance-content-reviewer','social-media-director'} or item['status']!='DRAFT' or not item['asset_integrity']:raise ValueError('Only unchanged draft content can enter internal review')
        with self.db:
            self.db.execute("UPDATE content_items SET status='REVIEWED',revision=revision+1,updated_at=? WHERE id=?",(now(),identity))
            self._history(self.get(identity),actor,'Internal review: '+redact(evidence))
        return self.get(identity)
    def approve(self,identity,qa_task_id):
        item=self.get(identity)
        if item['status']!='REVIEWED' or not item['asset_integrity']:raise ValueError('Perform internal review before independent QA approval')
        result,_=approved_task(self.hub,qa_task_id,'approved_content_ids',identity)
        review_task=self.hub.task(qa_task_id)
        if review_task['department']!='social-media' or review_task['project_id']!=item['project_id'] or self.hub.task(item['task_id'])['owner'] not in result.get('authors',[]):raise PermissionError('Content QA must belong to this campaign and Social Media, with its actual authors recorded')
        if result.get('content_hashes',{}).get(identity)!=item['content_hash']:raise ValueError('Independent QA did not assess these exact content/calendar/asset bytes')
        with self.db:
            cur=self.db.execute("UPDATE content_items SET status='APPROVED',revision=revision+1,qa_task_id=?,updated_at=? WHERE id=? AND revision=?",(qa_task_id,now(),identity,item['revision']))
            if cur.rowcount!=1:raise ValueError('Content changed during QA linking')
            self._history(self.get(identity),'qa-auditor','Linked actual independent QA record '+str(qa_task_id))
        return self.get(identity)
    def archive(self,identity,reason):
        required(reason,'Archive reason');item=self.get(identity)
        if self.db.execute("SELECT 1 FROM external_actions WHERE subject_hash=? AND status IN ('STARTED','UNKNOWN_NEEDS_RECONCILIATION')",(item['content_hash'],)).fetchone():raise ValueError('Reconcile the external action before archiving its content record')
        if item['status']=='SCHEDULED':raise ValueError('Cancel the real platform schedule through a separately authorized connector action first')
        with self.db:
            self.db.execute("UPDATE content_items SET status='ARCHIVED',revision=revision+1,updated_at=? WHERE id=?",(now(),identity))
            self._history(self.get(identity),'social-media-director','Archived: '+redact(reason))
        return self.get(identity)
    def export(self,project_id):
        project=self.hub.projects.get(project_id)
        if project['kind']!='social':raise ValueError('Calendar requires a Social Media campaign')
        rows=self.list(project_id);stream=io.StringIO();writer=csv.writer(stream)
        writer.writerow(['id','platform','title','status','proposed_time','audience_timezone','timing_basis','qa_task','remote_reference'])
        safe=lambda value:"'"+value if isinstance(value,str) and value.startswith(('=','+','-','@','\t','\r')) else value
        for item in rows:writer.writerow([safe(item[k]) for k in ['id','platform','title','status','scheduled_at','timezone','timing_basis','qa_task_id','remote_reference']])
        summary='# '+project['title']+' — content calendar\n\nA local plan is not a live publishing schedule. HYPOTHESIS times require testing.\n\n'
        for item in rows:summary+='## '+item['title']+'\n\nPlatform: '+item['platform']+'; state: '+item['status']+'; proposed: '+str(item['scheduled_at'])+' ('+item['timezone']+'); basis: '+item['timing_basis']+'\n\n'+item['payload']['copy']+'\n\n'
        digest=hashlib.sha256(canonical(rows).encode()).hexdigest()[:12]
        paths=write_artifacts(self.hub.root,'campaigns/'+project_id+'/calendar-'+digest,{'calendar.csv':stream.getvalue(),'calendar.md':summary})
        return {'artifacts':paths,'live_scheduled_posts_created':0,'items':len(rows)}
    def graphic(self,identity):
        item=self.get(identity);text=html.escape(item['title']);short_title=html.escape(item['title'][:36]);copy=html.escape(item['payload']['copy'][:260])
        svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350" role="img" aria-labelledby="title desc"><title id="title">{text}</title><desc id="desc">{copy}</desc><rect width="1080" height="1350" fill="#f1f3ef"/><rect x="72" y="92" width="72" height="8" fill="#306444"/><text x="72" y="210" font-family="sans-serif" font-size="54" fill="#202923">{short_title}</text><foreignObject x="72" y="310" width="920" height="800"><div xmlns="http://www.w3.org/1999/xhtml" dir="auto" style="font:48px/1.5 sans-serif;color:#202923;overflow-wrap:anywhere">{copy}</div></foreignObject><text x="72" y="1250" font-family="sans-serif" font-size="24" fill="#4c5d50">Local draft · Review language, platform fit and content rights</text></svg>'''
        paths=write_artifacts(self.hub.root,'campaigns/'+item['project_id']+'/graphics/'+identity+'-'+str(item['revision']),{'graphic.svg':svg})
        return {'artifacts':paths,'classification':'LOCAL_DRAFT','published':False}
    def publication_payload(self,identity,schedule=False):
        item=self.get(identity)
        return {'item_id':identity,'content_hash':item['content_hash'],'mode':'schedule' if schedule else 'publish',
            'platform':item['platform'],'title':item['title'],'copy':item['payload']['copy'],
            'assets':{p:hashlib.sha256(safe_file(self.hub.root,p).read_bytes()).hexdigest() for p in item['payload'].get('assets',[])},
            'proposed_time':item['scheduled_at'] if schedule else None,'audience_timezone':item['timezone']}

    def publish(self,identity,approval_id,destination,arguments,projected_cost,adapter,schedule=False):
        item=self.get(identity)
        if item['status']!='APPROVED' or not item['asset_integrity']:raise ValueError('Only unchanged independently approved content is eligible')
        result,_=approved_task(self.hub,item['qa_task_id'],'approved_content_ids',identity)
        if result.get('content_hashes',{}).get(identity)!=item['content_hash']:raise ValueError('Approved content changed')
        approval=self.db.execute('SELECT * FROM action_approvals WHERE id=?',(approval_id,)).fetchone()
        if approval is None:raise ValueError('Unknown publication approval')
        operation=self.hub.connectors._operation(self.hub.connectors.get(approval['runtime_id'],approval['provider']),approval['operation'])
        action_task=self.hub.task(approval['task_id'])
        if operation['kind']!='publish' or action_task['project_id']!=item['project_id'] or action_task['department']!='social-media':raise PermissionError('Use a scoped Social Media publication task and publish permission')
        if arguments!=self.publication_payload(identity,schedule):raise PermissionError('Publication arguments must match the exact independently reviewed copy, assets and calendar')
        if schedule and (not item['scheduled_at'] or instant(item['scheduled_at'])<=instant(now())):raise ValueError('A future timezone-aware schedule is required')
        receipt=self.hub.connectors.execute(approval_id,item['content_hash'],destination,arguments,projected_cost,adapter)
        # A fixture connector cannot turn local simulated work into live publication.
        if receipt['evidence_kind']=='SIMULATED':return dict(receipt,content_state_changed=False,note='Simulated adapter; no live publication recorded')
        with self.db:
            self.db.execute('UPDATE content_items SET status=?,revision=revision+1,remote_reference=?,updated_at=? WHERE id=?',('SCHEDULED' if schedule else 'PUBLISHED',receipt['result']['reference'],now(),identity))
            self._history(self.get(identity),'social-platform-integration-specialist','Verified external receipt '+receipt['id'])
        return dict(receipt,content_state_changed=True)
    def analytics(self,project_id,platform,rows,source,collected_at,classification='SUPPLIED_DATA'):
        project=self.hub.projects.get(project_id)
        if project['kind']!='social' or platform not in PLATFORMS:raise ValueError('Analytics requires a Social Media campaign/platform')
        required(source,'Actual connected or supplied dataset reference')
        if classification not in {'SUPPLIED_DATA','ESTIMATE','SIMULATED'}:raise ValueError('Use supplied data or a separately tested connected adapter; never label a hand-entered dataset CONNECTED')
        collected=instant(collected_at)
        if collected>instant(now()):raise ValueError('Analytics collection cannot be in the future')
        if not isinstance(rows,list) or not rows:raise ValueError('Supply actual rows, not invented missing metrics')
        fields=['impressions','reach','likes','comments','shares','saves','clicks'];totals={f:None for f in fields}
        for row in rows:
            if not isinstance(row,dict):raise ValueError('Analytics rows must be objects')
            for field in fields:
                value=row.get(field)
                if value is not None and (type(value) is not int or value<0):raise ValueError('Analytics counts must be nonnegative integers or unknown')
                if value is not None:totals[field]=(totals[field] or 0)+value
        interaction_fields=['likes','comments','shares','saves']
        interactions=sum(totals[f] for f in interaction_fields) if all(totals[f] is not None for f in interaction_fields) else None
        # Rates are defined only when every row supplies the required numerator/denominator.
        complete=all(all(row.get(f) is not None for f in interaction_fields+['impressions']) for row in rows)
        rate=interactions/totals['impressions'] if complete and totals['impressions'] else None
        dataset={'rows':redact(rows),'totals_of_available_values':totals,'engagement_rate_per_impression':rate,
            'rate_definition':'(likes + comments + shares + saves) / impressions; missing required data => UNKNOWN',
            'reach_note':'Summed supplied reach is not deduplicated audience reach.','row_count':len(rows)}
        identity=str(uuid.uuid4())
        with self.db:self.db.execute('INSERT INTO analytics_observations VALUES(?,?,?,?,?,?,?)',(identity,project_id,platform,canonical(dataset),classification,redact(source),collected.isoformat()))
        return dict(dataset,id=identity,classification=classification,source=redact(source),collected_at=collected.isoformat())
