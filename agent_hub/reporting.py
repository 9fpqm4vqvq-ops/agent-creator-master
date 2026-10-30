"""Render recorded task outcomes for the human controller."""
import json
from datetime import datetime, timedelta, timezone


def markdown_report(report):
    displayed = datetime.fromisoformat(report['generated_at']).astimezone(timezone(timedelta(hours=3)))
    lines = ['# Master agent report', '', f"Generated: {displayed.isoformat()} (Asia/Baghdad)", '',
             f"Execution: {report['execution_mode']}. Live trading: disabled.", '',
             ' | '.join(f'{state}: {count}' for state, count in report['counts'].items()), '']
    for task in report['tasks']:
        lines.extend([f"## Task {task['id']}: {task['status']}", '',
                      f"Request: {task['request']}", '',
                      f"Owner: {task['owner']}; parent: {task['parent'] or 'none'}; mode: {task['mode']}.", '',
                      f"Acceptance criteria: {task['criteria']}", ''])
        if task['result']:
            result = json.loads(task['result'])
            lines.extend([result['summary'], '', 'Artifacts:', ''])
            lines.extend(f'- {path}' for path in result['artifacts'])
            checks = result.get('preflight')
            if checks:
                lines.extend(['', f"Freshness: {checks['freshness_status']}. {checks['freshness_notes']}"])
            if result['limitations']:
                lines.extend(['', 'Limitations:', ''])
                lines.extend(f'- {note}' for note in result['limitations'])
            if result['sources']:
                lines.extend(['', 'Recorded sources:', ''])
                lines.extend(f"- {s['classification']}: {s['location']} (checked {s['checked_at']})" for s in result['sources'])
            lines.append('')
    lines.extend(['Usage/cost: unknown; no automatic token telemetry is connected.', '', report['qa_note'], '',
                  'Status reflects recorded review time. Completed outputs are rechecked when a parent passes; '
                  'this report does not re-audit completed work or prove that a source was visited.'])
    return '\n'.join(lines) + '\n'
