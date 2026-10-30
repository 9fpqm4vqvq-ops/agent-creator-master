"""Supervised v0.5 CLI. Handoffs and attestations never invoke a model."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from .core import Hub, ROOT, ROLES, DOMAINS
from .security import redact


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Master Agent System v0.5 — supervised control plane')
    parser.add_argument('--db', default=str(ROOT/'data/hub.sqlite'))
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('agents'); sub.add_parser('migrate')
    report = sub.add_parser('report'); report.add_argument('--format', choices=['json','markdown'], default='json')
    new = sub.add_parser('new'); new.add_argument('request'); new.add_argument('--criteria', required=True)
    new.add_argument('--department', choices=DOMAINS, default='management'); new.add_argument('--agent', choices=ROLES)
    new.add_argument('--parent', type=int); new.add_argument('--mode', choices=['research','paper'], default='research')
    new.add_argument('--cycle-limit', type=int, default=3);new.add_argument('--idempotency-key');new.add_argument('--project')
    for name in ['management-review','plan','assign','dispatch','recall','preflight','start','show','submit','review',
                 'resume','capability-gap','record','history','cancel']:
        command = sub.add_parser(name); command.add_argument('task_id', type=int)
        if name == 'management-review': command.add_argument('--analysis', required=True)
        if name == 'plan': command.add_argument('--plan', type=Path, required=True)
        if name in {'assign','start'}: command.add_argument('--evidence', required=True)
        if name=='start':
            command.add_argument('--execution-key');command.add_argument('--projected-cost');command.add_argument('--approval-id')
        if name == 'recall':
            command.add_argument('--query', required=True); command.add_argument('--actor', choices=ROLES)
        if name == 'preflight': command.add_argument('--checks', type=Path, required=True)
        if name == 'submit': command.add_argument('--result', type=Path, required=True)
        if name == 'review':
            command.add_argument('--reviewer', choices=['qa-auditor'], required=True)
            command.add_argument('--verdict', choices=['PASS','REWORK','BLOCKED'], required=True)
            command.add_argument('--notes', required=True); command.add_argument('--evidence', type=Path, required=True)
        if name == 'resume':
            command.add_argument('--diagnosis', required=True); command.add_argument('--authorization-reference', required=True)
            command.add_argument('--cycle-limit', type=int)
        if name == 'capability-gap':
            command.add_argument('--capability', required=True); command.add_argument('--evidence', required=True)
        if name == 'record':
            command.add_argument('--actor', choices=ROLES, required=True); command.add_argument('--kind', required=True)
            command.add_argument('--summary', required=True); command.add_argument('--refs', nargs='*', default=[])
        if name == 'cancel': command.add_argument('--reason', required=True)
    for name in ['backup','restore']:
        command = sub.add_parser(name); command.add_argument('--out', type=Path, required=True)
        if name == 'restore': command.add_argument('--source', type=Path, required=True)
    skills = sub.add_parser('skills'); actions = skills.add_subparsers(dest='skill_action', required=True)
    actions.add_parser('list')
    search = actions.add_parser('search'); search.add_argument('query'); search.add_argument('--department', choices=DOMAINS)
    for name in ['show','usage']:
        p = actions.add_parser(name); p.add_argument('skill_id')
    p = actions.add_parser('register'); p.add_argument('--record', type=Path, required=True)
    p.add_argument('--actor', choices=['agent-creator-researcher'], required=True)
    p = actions.add_parser('activate'); p.add_argument('skill_id'); p.add_argument('--review', type=Path, required=True)
    p = actions.add_parser('finder'); p.add_argument('query')
    actions.add_parser('baseline-diff')
    p=actions.add_parser('reconcile-baseline');p.add_argument('--review',type=Path,required=True)
    memory = sub.add_parser('memory'); actions = memory.add_subparsers(dest='memory_action', required=True)
    for name in ['put','get','search','export','import','enqueue','sync','queue','retry','markdown-import','resolve']:
        p = actions.add_parser(name); p.add_argument('--actor', choices=ROLES, required=True)
        if name in {'put','import'}: p.add_argument('--record' if name=='put' else '--source', type=Path, required=True)
        if name in {'get','enqueue','markdown-import'}: p.add_argument('--id', required=True)
        if name in {'search','markdown-import'}: p.add_argument('--namespace')
        if name == 'search': p.add_argument('--query', required=True)
        if name == 'export': p.add_argument('--out', type=Path, required=True); p.add_argument('--namespaces', nargs='+')
        if name in {'enqueue','sync'}: p.add_argument('--provider', choices=['markdown','notion'], required=True)
        if name in {'sync','markdown-import','resolve'}: p.add_argument('--directory', type=Path, default=ROOT/'memory')
        if name == 'retry': p.add_argument('--queue-id', type=int, required=True); p.add_argument('--resolution', required=True)
        if name == 'resolve':
            p.add_argument('--queue-id', type=int, required=True); p.add_argument('--expected-remote-hash', required=True)
            p.add_argument('--resolution', required=True)
    p = sub.add_parser('ecommerce-finance'); p.add_argument('--assumptions', type=Path, required=True)
    p=sub.add_parser('dashboard');p.add_argument('--port',type=int,default=8765)
    p=sub.add_parser('replan');p.add_argument('task_id',type=int);p.add_argument('--evidence',required=True)
    p=sub.add_parser('runtime');p.add_argument('action',choices=['intake','execute','get','recover','resume','cancel','probe']);p.add_argument('--data',type=Path);p.add_argument('--config',type=Path)
    operations={'usage':['record','summary','estimate'], 'budget':['configure','evaluate','approve'],
        'health':['audit','get','approve'], 'freshness':['scan','verify','supersede','queue','history'],
        'scheduler':['list','configure','tick','recover','history','run'],
        'improvements':['propose','get','stage','test','qa','activate','rollback','recover'],
        'research-cache':['record','lookup'], 'scorecards':['list'],
        'projects':['create','get','list','update','decompose','accept_handoff','scaffold','approve','deployment_payload'],
        'social':['create','get','list','update','internal_review','approve','archive','export','graphic','analytics','publication_payload'],
        'connectors':['candidates','discover','discover_tools','get','list','plan','disable','authorize'],
        'route':['suggest'], 'design-search':['search']}
    for name,actions in operations.items():
        p=sub.add_parser(name);p.add_argument('action',choices=actions);p.add_argument('--data',type=Path,help='JSON keyword arguments; see docs/INTELLIGENCE-V04.md')
    args = parser.parse_args(argv)
    hub = None
    try:
        if args.command=='dashboard':
            from .dashboard import serve
            serve(args.db,ROOT,args.port)
            return 0
        if args.command == 'restore':
            from .migrations import restore
            result = {'restored_to': restore(args.source,args.out)}
        else:
            hub = Hub(args.db)
            if args.command == 'agents':
                result = [{'name':k,'department':v[0],'reports_to':v[1],
                    'profile':f'.claude/agents/{k}.md','instruction_fingerprint':hub.manifest(k)['fingerprint']} for k,v in ROLES.items()]
            elif args.command == 'new': result = hub.create(args.request,args.criteria,args.department,args.agent,args.mode,args.parent,args.cycle_limit,args.idempotency_key,args.project)
            elif args.command=='replan':result=hub.replan_migrated(args.task_id,args.evidence)
            elif args.command=='runtime':
                from .runtime import AgentRuntime
                runtime=AgentRuntime(hub,read_json(args.config) if args.config else {})
                data=read_json(args.data) if args.data else {}
                methods={'intake':runtime.intake,'execute':runtime.execute_task,'get':runtime.get,
                    'recover':runtime.recover,'resume':runtime.resume_execution,'cancel':runtime.cancel_execution,
                    'probe':runtime.adapter.probe}
                result=methods[args.action](**data)
            elif args.command in operations:
                from .intelligence_cli import execute
                result=execute(hub,args.command,args.action,read_json(args.data) if args.data else {})
            elif args.command == 'management-review': result = hub.management_review(args.task_id,args.analysis)
            elif args.command == 'plan': result = hub.plan(args.task_id,read_json(args.plan))
            elif args.command == 'assign': result = hub.assign(args.task_id,args.evidence)
            elif args.command == 'dispatch': result = hub.dispatch(args.task_id)
            elif args.command == 'recall': result = hub.recall(args.task_id,args.query,args.actor)
            elif args.command == 'preflight': result = hub.preflight(args.task_id,read_json(args.checks))
            elif args.command == 'start': result = hub.start(args.task_id,args.evidence,args.execution_key,args.projected_cost,args.approval_id)
            elif args.command == 'show': result = hub.task(args.task_id)
            elif args.command == 'submit': result = hub.submit(args.task_id,read_json(args.result))
            elif args.command == 'review': result = hub.review(args.task_id,args.reviewer,args.verdict,args.notes,read_json(args.evidence))
            elif args.command == 'resume': result = hub.resume(args.task_id,args.diagnosis,args.authorization_reference,args.cycle_limit)
            elif args.command == 'capability-gap': result = hub.request_capability(args.task_id,args.capability,args.evidence)
            elif args.command == 'record': result = hub.record(args.task_id,args.actor,args.kind,args.summary,args.refs) or {'recorded':True}
            elif args.command == 'history': result = hub.history(args.task_id)
            elif args.command == 'cancel': result = hub.cancel(args.task_id,args.reason)
            elif args.command == 'migrate': result = hub.migration
            elif args.command == 'backup': result = {'backup':hub.backup(args.out)}
            elif args.command == 'skills':
                action = args.skill_action
                if action == 'list': result = hub.skills.list()
                elif action == 'search': result = hub.skills.search(args.query,args.department)
                elif action == 'show': result = hub.skills.get(args.skill_id)
                elif action == 'usage': result = hub.skills.usage(args.skill_id)
                elif action == 'register': result = hub.skills.register_candidate(read_json(args.record),args.actor)
                elif action == 'activate': result = hub.skills.activate(args.skill_id,**read_json(args.review))
                elif action=='baseline-diff':result=hub.skills.baseline_diff()
                elif action=='reconcile-baseline':result=hub.skills.reconcile_baseline(**read_json(args.review))
                else:
                    from .skill_finder import SkillFinderAdapter
                    result = SkillFinderAdapter().search(args.query)
            elif args.command == 'memory':
                action = args.memory_action
                if action == 'put': result = hub.memory.put(actor=args.actor,**read_json(args.record))
                elif action == 'get': result = hub.memory.get(args.id,args.actor)
                elif action == 'search': result = hub.memory.search(args.query,args.actor,args.namespace)
                elif action == 'export':
                    result = hub.memory.export(args.actor,args.namespaces)
                    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2)+'\n')
                    result = {'exported_to':str(args.out),'records':len(result['records'])}
                elif action == 'import': result = hub.memory.import_records(read_json(args.source),args.actor)
                elif action == 'enqueue': result = hub.memory.enqueue(args.id,args.provider,args.actor)
                elif action == 'sync':
                    from .providers import MarkdownVaultProvider, NotionProviderStub
                    provider = MarkdownVaultProvider(args.directory) if args.provider=='markdown' else NotionProviderStub()
                    result = hub.memory.sync(provider,args.actor)
                elif action == 'queue':
                    result = []
                    for row in hub.db.execute('SELECT * FROM memory_sync_queue ORDER BY id'):
                        try: hub.memory.get(row['record_id'],args.actor)
                        except PermissionError: continue
                        result.append(dict(row))
                elif action == 'retry': result = hub.memory.retry(args.queue_id,args.actor,args.resolution) or {'retry_queued':True}
                elif action == 'resolve':
                    from .providers import MarkdownVaultProvider
                    result = hub.memory.resolve_conflict(args.queue_id,MarkdownVaultProvider(args.directory),args.actor,args.expected_remote_hash,args.resolution)
                else:
                    from .providers import MarkdownVaultProvider
                    record = MarkdownVaultProvider(args.directory).read(args.namespace,args.id)
                    result = hub.memory.import_records({'format':'memory-vault-v1','records':[record]},args.actor)
            elif args.command == 'ecommerce-finance':
                from .ecommerce import unit_economics
                result = unit_economics(read_json(args.assumptions))
            else: result = hub.report()
        if args.command == 'report' and args.format == 'markdown':
            from .reporting import markdown_report
            print(markdown_report(result))
        else: print(json.dumps(redact(result),indent=2))
        return 0
    except (ValueError,OSError,PermissionError,sqlite3.Error,KeyError,TypeError) as exc:
        print('Error: '+str(redact(str(exc))),file=sys.stderr)
        return 1
    finally:
        if hub is not None: hub.close()


if __name__ == '__main__':
    sys.exit(main())
