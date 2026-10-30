"""Safe, explicit IOI local CLI: no external effects except local SQLite and report files."""
import argparse,json,sys,shutil,os
from pathlib import Path
from . import core as c

def parser():
    p=argparse.ArgumentParser(prog='ioi',description='Income Opportunity Intelligence: local evidence, feasibility and experiment memory')
    p.add_argument('--db',help='Optional SQLite path; default data/ioi.db')
    sub=p.add_subparsers(dest='cmd',required=True)
    def cmd(name,help):return sub.add_parser(name,help=help)
    cmd('init','Initialize SQLite memory and required tables')
    cmd('doctor','Check local project configuration without authenticating to services')
    q=cmd('add','Create an opportunity (all six payout stages default UNVERIFIED)')
    q.add_argument('--title',required=True);q.add_argument('--model',default='');q.add_argument('--buyer',default='');q.add_argument('--creator',default='main-agent')
    cmd('list','List current opportunity statuses and scores')
    q=cmd('show','Print opportunity, payout, QA and score as JSON');q.add_argument('--id',type=int,required=True)
    q=cmd('evidence-add','Record a dated source, not independent verification')
    q.add_argument('--id',type=int,required=True);q.add_argument('--claim',required=True);q.add_argument('--url',required=True);q.add_argument('--class',dest='classification',choices=['A','B','C'],default='B');q.add_argument('--confidence',choices=['LOW','MEDIUM','HIGH'],default='MEDIUM');q.add_argument('--caveats',default='')
    q=cmd('payout-set','Record the result of one of six payment route stages')
    q.add_argument('--id',type=int,required=True);q.add_argument('--stage',required=True,choices=c.STAGES);q.add_argument('--status',required=True,choices=sorted(c.STATUS));q.add_argument('--provider',default='');q.add_argument('--url',default='');q.add_argument('--details',default='')
    q=cmd('rate','Record one documented, provisional criterion score')
    q.add_argument('--id',type=int,required=True);q.add_argument('--criterion',required=True,choices=list(c.WEIGHTS));q.add_argument('--value',type=float,required=True);q.add_argument('--rationale',required=True)
    q=cmd('score','Show score (not QA permission)');q.add_argument('--id',type=int,required=True)
    q=cmd('risk-add','Record blocker, major, minor risk')
    q.add_argument('--id',type=int,required=True);q.add_argument('--severity',required=True,choices=['BLOCKER','MAJOR','MINOR']);q.add_argument('--summary',required=True)
    q=cmd('risk-close','Resolve one risk with explanation');q.add_argument('--flag-id',type=int,required=True);q.add_argument('--note',required=True)
    q=cmd('qa-check','Structural QA gate checklist; NOT semantic verification');q.add_argument('--id',type=int,required=True)
    q=cmd('qa-attest','Record independent reviewed verdict, only structural pass can receive PASS')
    q.add_argument('--id',type=int,required=True);q.add_argument('--reviewer',required=True);q.add_argument('--verdict',choices=['PASS','FAIL','NEEDS_EVIDENCE'],required=True);q.add_argument('--findings',required=True)
    q=cmd('gate','Show if independent QA and payout gates currently permit testing');q.add_argument('--id',type=int,required=True)
    q=cmd('rework-add','Open one of up to three corrective cycles')
    q.add_argument('--id',type=int,required=True);q.add_argument('--cause',required=True);q.add_argument('--correction',required=True);q.add_argument('--owner',required=True)
    q=cmd('decision','Record main agent decision, requiring gates for proceed/test/scale')
    q.add_argument('--id',type=int,required=True);q.add_argument('--action',required=True,choices=sorted(c.DECISIONS));q.add_argument('--why',required=True);q.add_argument('--alternatives',default='');q.add_argument('--trigger',default='')
    q=cmd('finance','Model low, base, high revenue in USD; assumptions only')
    for a in ['price','low','base','high','unit-cost','fee-pct','monthly-fixed','hours']:
        q.add_argument('--'+a,type=float,required=True)
    q=cmd('experiment-create','Create experiment plan; does NOT execute it')
    q.add_argument('--id',type=int,required=True);q.add_argument('--hypothesis',required=True);q.add_argument('--metric',required=True);q.add_argument('--target',type=float,required=True);q.add_argument('--max-cost',type=float,required=True);q.add_argument('--max-hours',type=float,required=True)
    q=cmd('approve','Record explicit human approval: does NOT initiate external actions')
    q.add_argument('--id',type=int,required=True);q.add_argument('--action',choices=['EXPERIMENT','OUTREACH','ACCOUNT','PURCHASE','PUBLICATION'],required=True);q.add_argument('--experiment-id',type=int,help='Required for EXPERIMENT approval');q.add_argument('--max-cost',type=float,default=0);q.add_argument('--by',required=True);q.add_argument('--scope',required=True)
    q=cmd('experiment-start','Mark a planned experiment ACTIVE with current QA PASS and matching human approval')
    q.add_argument('--experiment-id',type=int,required=True);q.add_argument('--approval-id',type=int,required=True)
    q=cmd('event','Record actual observed experiment event within caps')
    q.add_argument('--experiment-id',type=int,required=True);q.add_argument('--metric-value',type=float);q.add_argument('--revenue',type=float,default=0);q.add_argument('--cost',type=float,default=0);q.add_argument('--hours',type=float,default=0);q.add_argument('--note',required=True)
    q=cmd('experiment-close','Finish experiment with actual summary')
    q.add_argument('--experiment-id',type=int,required=True);q.add_argument('--notes',required=True)
    q=cmd('monitor-add','Create event-triggered reconsideration note (not scheduled)')
    q.add_argument('--id',type=int,required=True);q.add_argument('--trigger',required=True)
    q=cmd('report','Create local markdown dashboard based on actual records')
    q.add_argument('--out',help='Optional output file; stdout otherwise')
    return p

def emit(value):
    if isinstance(value,(dict,list)): print(json.dumps(value,ensure_ascii=False,indent=2,default=str))
    else: print(value)

def run(argv=None):
    args=parser().parse_args(argv)
    if args.cmd=='finance':
        emit(c.finance(args.price,args.low,args.base,args.high,args.unit_cost,args.fee_pct,args.monthly_fixed,args.hours));return 0
    if args.cmd=='doctor':
        emit({'python':'available','sqlite_stdlib':'available','claude_cli':bool(shutil.which('claude')),
              'db_path':str(c.location(args.db)),'youtube_public_api_key_configured':bool(os.environ.get('YOUTUBE_API_KEY')),
              'monitoring_service_configured':False,
              'notice':'Integrations and source verification must be set up separately; CLI tests never require network access.'});return 0
    conn=c.connect(args.db)
    try:
        c.init(conn)
        cmd=args.cmd
        if cmd=='init':emit({'initialized':str(c.location(args.db))})
        elif cmd=='add':emit({'opportunity_id':c.create(conn,args.title,args.model,args.buyer,args.creator)})
        elif cmd=='list':emit([{'id':r['id'],'title':r['title'],'status':r['status'],'score':c.score(conn,r['id'])['score'],'gate':c.gate(conn,r['id'])['allowed']} for r in conn.execute('SELECT * FROM opportunities ORDER BY id')])
        elif cmd=='show':
            r=c.get(conn,args.id)
            emit({'opportunity':dict(r),'score':c.score(conn,args.id),'payout':[dict(x) for x in conn.execute('SELECT * FROM payout_checks WHERE opportunity_id=?',(args.id,))],'evidence':[dict(x) for x in conn.execute('SELECT * FROM evidence WHERE opportunity_id=?',(args.id,))], 'gate':c.gate(conn,args.id)})
        elif cmd=='evidence-add':c.evidence_add(conn,args.id,args.claim,args.url,args.classification,args.confidence,args.caveats);emit('Evidence added (not automatically verified).')
        elif cmd=='payout-set':c.payout_set(conn,args.id,args.stage,args.status,args.provider,args.url,args.details);emit('Payout stage recorded; independent source review still required.')
        elif cmd=='rate':c.rating_set(conn,args.id,args.criterion,args.value,args.rationale);emit(c.score(conn,args.id))
        elif cmd=='score':emit({'score':c.score(conn,args.id),'gate':c.gate(conn,args.id)})
        elif cmd=='risk-add':emit({'risk_id':c.flag_add(conn,args.id,args.severity,args.summary)})
        elif cmd=='risk-close':c.flag_close(conn,args.flag_id,args.note);emit('Risk resolution recorded; previous QA PASS, if any, is now stale.')
        elif cmd=='qa-check':emit(c.qa_check(conn,args.id))
        elif cmd=='qa-attest':emit({'qa_verdict':c.qa_attest(conn,args.id,args.reviewer,args.verdict,args.findings),'gate':c.gate(conn,args.id)})
        elif cmd=='gate':emit(c.gate(conn,args.id))
        elif cmd=='rework-add':emit({'attempt':c.rework_add(conn,args.id,args.cause,args.correction,args.owner),'max':3})
        elif cmd=='decision':c.decision_add(conn,args.id,args.action,args.why,alternatives=args.alternatives,trigger=args.trigger);emit('Main agent decision recorded.')
        elif cmd=='experiment-create':emit({'experiment_id':c.experiment_create(conn,args.id,args.hypothesis,args.metric,args.target,args.max_cost,args.max_hours),'status':'PLANNED'})
        elif cmd=='approve':emit({'approval_id':c.approve(conn,args.id,args.action,args.max_cost,args.by,args.scope,args.experiment_id),'notice':'Local approval record only: human consent still required before any actual external action.'})
        elif cmd=='experiment-start':c.experiment_activate(conn,args.experiment_id,args.approval_id);emit('Experiment ACTIVE; this command does not contact anyone or spend money.')
        elif cmd=='event':c.event_add(conn,args.experiment_id,args.metric_value,args.revenue,args.cost,args.hours,args.note);emit('Actual event recorded, as entered.')
        elif cmd=='experiment-close':c.experiment_close(conn,args.experiment_id,args.notes);emit('Experiment marked COMPLETED.')
        elif cmd=='monitor-add':emit({'monitor_id':c.monitoring_add(conn,args.id,args.trigger),'note':'Queue only; no background scheduler running'})
        elif cmd=='report':
            body=c.dashboard(conn)
            if args.out:
                path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body,encoding='utf-8');emit({'report_file':str(path.resolve())})
            else: print(body)
        else:raise c.IOIError('Unknown command')
    finally:conn.close()
    return 0

def main():
    try:return run()
    except (c.IOIError,ValueError) as e:
        print('IOI ERROR: '+str(e),file=sys.stderr);return 2
    except KeyboardInterrupt:
        print('Interrupted',file=sys.stderr);return 130

if __name__=='__main__':raise SystemExit(main())
