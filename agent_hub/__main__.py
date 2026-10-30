import argparse
import json
import sys
from pathlib import Path
from .core import Hub, ROOT, ROLES, DOMAINS


def main():
    p = argparse.ArgumentParser(description='Master agent supervised task hub')
    p.add_argument('--db', default=str(ROOT/'data/hub.sqlite'))
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('agents')
    report = sub.add_parser('report')
    report.add_argument('--format', choices=['json', 'markdown'], default='json')
    new = sub.add_parser('new')
    new.add_argument('request')
    new.add_argument('--criteria', required=True)
    new.add_argument('--department', choices=DOMAINS, default='management')
    new.add_argument('--agent', choices=ROLES)
    new.add_argument('--parent', type=int)
    new.add_argument('--mode', choices=['research', 'paper'], default='research')
    for name in ['dispatch', 'show', 'preflight', 'submit', 'review', 'cancel']:
        cmd = sub.add_parser(name)
        cmd.add_argument('task_id', type=int)
        if name == 'submit': cmd.add_argument('--result', type=Path, required=True)
        if name == 'preflight': cmd.add_argument('--checks', type=Path, required=True)
        if name == 'review':
            cmd.add_argument('--reviewer', choices=['qa-auditor'], required=True)
            cmd.add_argument('--verdict', choices=['PASS', 'REWORK', 'BLOCKED'], required=True)
            cmd.add_argument('--notes', required=True)
        if name == 'cancel': cmd.add_argument('--reason', required=True)
    args = p.parse_args()
    hub = Hub(args.db)
    try:
        if args.command == 'agents':
            result = [{'name': k, 'department': v[0], 'reports_to': v[1],
                       'instruction_fingerprint': hub.manifest(k)['fingerprint']} for k,v in ROLES.items()]
        elif args.command == 'new':
            result = hub.create(args.request, args.criteria, args.department, args.agent, args.mode, args.parent)
        elif args.command == 'dispatch': result = hub.dispatch(args.task_id)
        elif args.command == 'show': result = hub.task(args.task_id)
        elif args.command == 'preflight': result = hub.preflight(args.task_id, json.loads(args.checks.read_text()))
        elif args.command == 'submit': result = hub.submit(args.task_id, json.loads(args.result.read_text()))
        elif args.command == 'review': result = hub.review(args.task_id, args.reviewer, args.verdict, args.notes)
        elif args.command == 'cancel': result = hub.cancel(args.task_id, args.reason)
        else: result = hub.report()
        if args.command == 'report' and args.format == 'markdown':
            from .reporting import markdown_report
            print(markdown_report(result))
        else:
            print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    finally:
        hub.close()


if __name__ == '__main__':
    sys.exit(main())
