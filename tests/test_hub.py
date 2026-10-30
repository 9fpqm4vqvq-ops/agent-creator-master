import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_hub.core import Hub, ROLES, ROOT


class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ['CLAUDE.md', 'AGENTS.md', '.claude/skills/master-workflow/SKILL.md']:
            p = self.root/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('Test contract')
        for role, (_, _, bundle) in ROLES.items():
            (self.root/'.claude/agents').mkdir(exist_ok=True)
            (self.root/f'.claude/agents/{role}.md').write_text('Test role')
            (self.root/'vendor'/bundle).mkdir(parents=True, exist_ok=True)
            (self.root/'vendor'/bundle/'SKILL.md').write_text('Test specialist')
        (self.root/'deliverable.md').write_text('Reviewed result')
        self.hub = Hub(self.root/'hub.sqlite', self.root)
        self.addCleanup(self.hub.close)

    def new(self, **kwargs):
        return self.hub.create('Research a task', 'Document evidence and limitations', **kwargs)['id']

    def checks(self, packet):
        return {'instruction_fingerprint': packet['instructions']['fingerprint'],
                'skills_read': ['.claude/skills/master-workflow/SKILL.md'],
                'runtime_check': 'Offline unit-test harness; no model invocation',
                'freshness_status': 'NOT_REQUIRED', 'freshness_notes': 'Local workflow test only',
                'sources': []}

    def dispatch(self, task_id):
        packet = self.hub.dispatch(task_id)
        self.hub.preflight(task_id, self.checks(packet))
        return packet

    def result(self):
        return {'summary': 'Research result', 'artifacts': ['deliverable.md'],
                'sources': [{'location': 'deliverable.md', 'checked_at': '2026-01-01T00:00:00+00:00',
                             'classification': 'HISTORICAL'}], 'limitations': ['Offline test']}

    def ready(self, **kwargs):
        i = self.new(**kwargs)
        self.dispatch(i)
        self.hub.submit(i, self.result())
        return i

    def test_full_workflow_persists_and_reports(self):
        i = self.ready(domain='agent-development')
        self.assertEqual(self.hub.review(i, 'qa-auditor', 'PASS', 'Independently inspected artifact')['status'], 'COMPLETED')
        other = Hub(self.root/'hub.sqlite', self.root)
        self.addCleanup(other.close)
        self.assertEqual(other.report()['counts']['COMPLETED'], 1)
        self.assertEqual(other.task(i)['owner'], 'agent-creator-researcher')

    def test_direct_agent_routing_and_reporting_chain(self):
        i = self.new(agent='trading-director', mode='paper')
        packet = self.dispatch(i)
        self.assertEqual(packet['reports_to'], 'income-director')
        self.assertIn('HANDOFF_ONLY', packet['execution'])
        self.assertFalse(self.hub.report()['live_trading_enabled'])

    def test_no_live_execution_or_unknown_agents(self):
        for kwargs in [{'mode': 'live'}, {'agent': 'invented'}, {'domain': 'invented'}]:
            with self.assertRaises(ValueError): self.new(**kwargs)

    def test_no_empty_acceptance_criteria(self):
        with self.assertRaises(ValueError): self.hub.create('Task', ' ')

    def test_illegal_state_and_duplicate_dispatch(self):
        i = self.new()
        with self.assertRaises(ValueError): self.hub.submit(i, self.result())
        self.dispatch(i)
        with self.assertRaises(ValueError): self.dispatch(i)
        with self.assertRaises(ValueError): self.hub.review(i, 'qa-auditor', 'PASS', 'No result')

    def test_instruction_change_rejects_old_result(self):
        i = self.new()
        self.dispatch(i)
        (self.root/'CLAUDE.md').write_text('Updated authority')
        with self.assertRaisesRegex(ValueError, 'Instructions changed'): self.hub.submit(i, self.result())

    def test_tool_change_rejects_old_result(self):
        tool = self.root/'vendor/maos/tool.py'
        tool.write_text('baseline')
        i = self.new()
        self.dispatch(i)
        tool.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Instructions changed'): self.hub.submit(i, self.result())

    def test_no_missing_or_escaping_artifacts(self):
        i = self.new()
        self.dispatch(i)
        for path in ['missing.txt', '../outside', '/etc/passwd']:
            result = self.result(); result['artifacts'] = [path]
            with self.assertRaises(ValueError): self.hub.submit(i, result)
        (self.root/'escape').symlink_to('/etc/passwd')
        result = self.result(); result['artifacts'] = ['escape']
        with self.assertRaises(ValueError): self.hub.submit(i, result)

    def test_result_requires_evidence_shape_and_valid_dates(self):
        i = self.new(); self.dispatch(i)
        for patch in [{'artifacts': []}, {'summary': ''}, {'sources': 'fake'}, {'limitations': [42]}]:
            result = self.result(); result.update(patch)
            with self.assertRaises(ValueError): self.hub.submit(i, result)
        for date in ['2999-01-01T00:00:00+00:00', '2026-01-01']:
            result = self.result(); result['sources'][0]['checked_at'] = date
            with self.assertRaises(ValueError): self.hub.submit(i, result)

    def test_independence_and_review_notes_required(self):
        i = self.ready(agent='qa-auditor')
        with self.assertRaises(ValueError): self.hub.review(i, 'qa-auditor', 'PASS', 'Self review')
        i = self.ready()
        with self.assertRaises(ValueError): self.hub.review(i, 'master-agent', 'PASS', 'Owner review')
        with self.assertRaises(ValueError): self.hub.review(i, 'qa-auditor', 'PASS', '')

    def test_artifact_tampering_requires_rework(self):
        i = self.ready()
        (self.root/'deliverable.md').write_text('Changed after review packet')
        with self.assertRaisesRegex(ValueError, 'Artifact changed'):
            self.hub.review(i, 'qa-auditor', 'PASS', 'Check')
        self.assertEqual(self.hub.review(i, 'qa-auditor', 'REWORK', 'Recheck changed bytes')['status'], 'REWORK')
        self.dispatch(i); self.hub.submit(i, self.result())
        self.assertEqual(self.hub.review(i, 'qa-auditor', 'PASS', 'Checked corrected bytes')['status'], 'COMPLETED')

    def test_three_reworks_escalate(self):
        i = self.ready()
        for n in range(3):
            status = self.hub.review(i, 'qa-auditor', 'REWORK', 'Missing acceptance evidence')['status']
            if n < 2:
                self.assertEqual(status, 'REWORK')
                self.dispatch(i); self.hub.submit(i, self.result())
        self.assertEqual(status, 'BLOCKED')
        with self.assertRaises(ValueError): self.dispatch(i)

    def test_child_completion_required_for_parent(self):
        parent = self.ready()
        child = self.new(parent=parent, domain='income')
        with self.assertRaisesRegex(ValueError, 'child tasks'): self.hub.review(parent, 'qa-auditor', 'PASS', 'Check')
        self.dispatch(child); self.hub.submit(child, self.result())
        self.hub.review(child, 'qa-auditor', 'PASS', 'Check child')
        self.hub.review(parent, 'qa-auditor', 'PASS', 'Check integrated result')
        with self.assertRaises(ValueError): self.new(parent=parent)

    def test_cancelled_task_cannot_run(self):
        i = self.new(); self.hub.cancel(i, 'Replaced by updated task')
        with self.assertRaises(ValueError): self.dispatch(i)

    def test_preflight_required_again_after_rework(self):
        i = self.new()
        packet = self.hub.dispatch(i)
        with self.assertRaisesRegex(ValueError, 'preflight'): self.hub.submit(i, self.result())
        self.hub.preflight(i, self.checks(packet))
        self.hub.submit(i, self.result())
        self.hub.review(i, 'qa-auditor', 'REWORK', 'More evidence needed')
        self.hub.dispatch(i)
        with self.assertRaisesRegex(ValueError, 'preflight'): self.hub.submit(i, self.result())

    def test_preflight_rejects_false_freshness_and_unknown_skills(self):
        i = self.new(); packet = self.hub.dispatch(i)
        for patch in [{'instruction_fingerprint': 'old'}, {'skills_read': []},
                      {'skills_read': ['../untrusted/SKILL.md']},
                      {'freshness_status': 'VERIFIED'}, {'runtime_check': ''}]:
            checks = self.checks(packet); checks.update(patch)
            with self.assertRaises(ValueError): self.hub.preflight(i, checks)
        checks = self.checks(packet)
        checks.update(freshness_status='VERIFIED', sources=self.result()['sources'])
        with self.assertRaises(ValueError): self.hub.preflight(i, checks)

    def test_unverified_freshness_disclosed_in_result(self):
        i = self.new(); packet = self.hub.dispatch(i)
        checks = self.checks(packet); checks['freshness_status'] = 'UNVERIFIED'
        self.hub.preflight(i, checks)
        result = self.result(); result['limitations'] = []
        with self.assertRaisesRegex(ValueError, 'disclosed'): self.hub.submit(i, result)
        result['limitations'] = ['Current provider documentation was inaccessible']
        task = self.hub.submit(i, result)
        self.assertEqual(json.loads(task['result'])['preflight']['freshness_status'], 'UNVERIFIED')

    def test_department_policy_and_other_role_changes_invalidate_packet(self):
        docs = self.root/'docs'; docs.mkdir()
        policy = docs/'TRADING.md'; policy.write_text('Initial policy')
        i = self.new(domain='trading'); self.dispatch(i)
        policy.write_text('Updated trading mandate')
        with self.assertRaisesRegex(ValueError, 'Instructions changed'): self.hub.submit(i, self.result())
        j = self.new(); self.dispatch(j)
        (self.root/'.claude/agents/trading-director.md').write_text('New role')
        with self.assertRaisesRegex(ValueError, 'Instructions changed'): self.hub.submit(j, self.result())

    def test_materialized_skill_copy_is_snapshotted(self):
        skill = self.root/'.claude/skills/trader-risk'
        skill.mkdir(); (skill/'SKILL.md').write_text('Initial skill')
        i = self.new(domain='trading'); self.dispatch(i)
        (skill/'SKILL.md').write_text('Changed discoverable skill')
        with self.assertRaisesRegex(ValueError, 'Instructions changed'): self.hub.submit(i, self.result())

    def test_parent_rechecks_completed_child_artifact(self):
        (self.root/'child.md').write_text('Child evidence')
        parent = self.ready()
        child = self.new(parent=parent, domain='income'); self.dispatch(child)
        result = self.result(); result['artifacts'] = ['child.md']
        self.hub.submit(child, result)
        self.hub.review(child, 'qa-auditor', 'PASS', 'Checked child output')
        (self.root/'child.md').write_text('Changed child evidence')
        with self.assertRaisesRegex(ValueError, 'Artifact changed'):
            self.hub.review(parent, 'qa-auditor', 'PASS', 'Integrated report')

    def test_blocked_parent_cannot_accept_new_work(self):
        parent = self.ready()
        self.hub.review(parent, 'qa-auditor', 'BLOCKED', 'Missing prerequisite')
        with self.assertRaises(ValueError): self.new(parent=parent)

    def test_readable_report_preserves_uncertainty(self):
        from agent_hub.reporting import markdown_report
        self.ready(domain='trading')
        report = markdown_report(self.hub.report())
        self.assertIn('Asia/Baghdad', report)
        self.assertIn('Live trading: disabled', report)
        self.assertIn('Offline test', report)
        self.assertIn('HISTORICAL', report)
        self.assertIn('QA: 1', report)


class RealPackage(unittest.TestCase):
    def test_real_profiles_and_skill_links_exist(self):
        with tempfile.TemporaryDirectory() as temp:
            hub = Hub(Path(temp)/'db')
            try:
                for role in ROLES: self.assertTrue(hub.manifest(role)['files'])
                skills = list((ROOT/'.claude/skills').glob('trader-*'))
                self.assertEqual(len(skills), 11)
                self.assertTrue(all((p/'SKILL.md').is_file() for p in skills))
            finally: hub.close()

    def test_cli_end_to_end_and_failure_exit_status(self):
        with tempfile.TemporaryDirectory() as temp:
            base = [sys.executable, '-m', 'agent_hub', '--db', str(Path(temp)/'db')]
            p = subprocess.run(base+['new', 'Plan a paper trading workflow', '--criteria', 'List missing inputs',
                                     '--department', 'trading', '--mode', 'paper'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            i = json.loads(p.stdout)['id']
            p = subprocess.run(base+['dispatch', str(i)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            packet = json.loads(p.stdout)
            self.assertEqual(packet['owner'], 'trading-director')
            p = subprocess.run(base+['review', str(i), '--reviewer', 'qa-auditor', '--verdict', 'PASS',
                                     '--notes', 'No work done'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 1)
            checks = {'instruction_fingerprint': packet['instructions']['fingerprint'],
                      'skills_read': ['.claude/skills/master-workflow/SKILL.md'],
                      'runtime_check': 'CLI offline test only', 'freshness_status': 'NOT_REQUIRED',
                      'freshness_notes': 'No external claims under test', 'sources': []}
            check_path = Path(temp)/'checks.json'; check_path.write_text(json.dumps(checks))
            p = subprocess.run(base+['preflight', str(i), '--checks', str(check_path)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            result = {'summary': 'Offline CLI workflow fixture', 'artifacts': ['README.md'],
                      'sources': [], 'limitations': ['Test fixture; no real research or independent review']}
            result_path = Path(temp)/'result.json'; result_path.write_text(json.dumps(result))
            p = subprocess.run(base+['submit', str(i), '--result', str(result_path)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            p = subprocess.run(base+['review', str(i), '--reviewer', 'qa-auditor', '--verdict', 'PASS',
                                     '--notes', 'Simulated review for offline CLI test only'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            p = subprocess.run(base+['report', '--format', 'markdown'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn('COMPLETED: 1', p.stdout)


if __name__ == '__main__':
    unittest.main()
