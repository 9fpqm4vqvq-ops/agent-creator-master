import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_hub.core import Hub, ROLES, ROOT, DOMAINS, QA_CHECKS
from agent_hub.skills import skill_fingerprint


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
        registry = self.root/'registry'; registry.mkdir()
        record = {'id':'master-workflow','name':'master-workflow','version':'test',
                  'description':'Offline test workflow','path':'.claude/skills/master-workflow/SKILL.md',
                  'source':'test fixture','fingerprint':skill_fingerprint(self.root,'.claude/skills/master-workflow/SKILL.md'),
                  'supported_agents':[],'supported_departments':list(DOMAINS), 'dependencies':[],
                  'permissions':['fixture'],'test_results':[], 'security_status':'BASELINE_REVIEWED',
                  'last_validation_date':'2026-01-01T00:00:00+00:00'}
        (registry/'skills.json').write_text(json.dumps({'skills':[record]}))
        self.hub = Hub(self.root/'hub.sqlite', self.root)
        self.addCleanup(self.hub.close)

    def new(self, **kwargs):
        i = self.hub.create('Research a task', 'Document evidence and limitations', **kwargs)['id']
        self.plan(i)
        return i

    def plan(self, i):
        self.hub.management_review(i, 'Offline fixture management analysis')
        self.hub.plan(i, {'owner':self.hub.task(i)['requested_owner'], 'selected_skills':['master-workflow'],
                         'acceptance_criteria':['Document evidence and limitations'], 'rationale':'Offline fixture role match',
                         'priority':'normal', 'dependencies':[]})
        self.hub.assign(i, 'Offline fixture Management assignment')

    def checks(self, packet):
        return {'instruction_fingerprint': packet['instructions']['fingerprint'],
                'skills_read': ['.claude/skills/master-workflow/SKILL.md'],
                'runtime_check': 'Offline unit-test harness; no model invocation',
                'freshness_status': 'NOT_REQUIRED', 'freshness_notes': 'Local workflow test only',
                'sources': []}

    def preflight(self, task_id, checks):
        self.hub.recall(task_id,'fixture prior outcomes')
        result = self.hub.preflight(task_id, checks)
        self.hub.start(task_id,'Offline fixture begins after all gates')
        return result

    def qa_evidence(self, task_id, verdict='PASS', notes='Offline test fixture'):
        criteria = json.loads(self.hub.task(task_id)['management_plan'])['acceptance_criteria']
        items = [{'criterion':c, 'verdict':'PASS', 'evidence':['test://offline-fixture']} for c in criteria]
        if verdict != 'PASS':
            items[0].update(verdict='FAIL' if verdict=='REWORK' else 'BLOCKED',correction=notes or 'Offline fixture correction')
        return {'review_reference':'test://simulated-independent-review', 'criteria':items,
                'checks':{k:{'verdict':'PASS','evidence':['test://offline-fixture']} for k in QA_CHECKS},
                'tests':[{'command':'offline fixture evaluation','result':'PASS','reference':'test://unit-fixture'}]}

    def review(self, task_id, reviewer, verdict, notes):
        return self.hub.review(task_id,reviewer,verdict,notes,self.qa_evidence(task_id,verdict,notes))

    def dispatch(self, task_id):
        packet = self.hub.dispatch(task_id)
        self.preflight(task_id, self.checks(packet))
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
        self.assertEqual(self.review(i, 'qa-auditor', 'PASS', 'Independently inspected artifact')['status'], 'COMPLETED')
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
        with self.assertRaises(ValueError): self.review(i, 'qa-auditor', 'PASS', 'No result')

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
        with self.assertRaises(ValueError): self.review(i, 'qa-auditor', 'PASS', 'Self review')
        i = self.ready()
        with self.assertRaises(ValueError): self.review(i, 'master-agent', 'PASS', 'Owner review')
        with self.assertRaises(ValueError): self.review(i, 'qa-auditor', 'PASS', '')

    def test_artifact_tampering_requires_rework(self):
        i = self.ready()
        (self.root/'deliverable.md').write_text('Changed after review packet')
        with self.assertRaisesRegex(ValueError, 'Artifact changed'):
            self.review(i, 'qa-auditor', 'PASS', 'Check')
        self.assertEqual(self.review(i, 'qa-auditor', 'REWORK', 'Recheck changed bytes')['status'], 'REWORK')
        self.dispatch(i); self.hub.submit(i, self.result())
        self.assertEqual(self.review(i, 'qa-auditor', 'PASS', 'Checked corrected bytes')['status'], 'COMPLETED')

    def test_three_reworks_escalate(self):
        i = self.ready()
        for n in range(3):
            status = self.review(i, 'qa-auditor', 'REWORK', 'Missing acceptance evidence')['status']
            if n < 2:
                self.assertEqual(status, 'REWORK')
                self.dispatch(i); self.hub.submit(i, self.result())
        self.assertEqual(status, 'BLOCKED')
        with self.assertRaises(ValueError): self.dispatch(i)

    def test_child_completion_required_for_parent(self):
        parent = self.ready()
        child = self.new(parent=parent, domain='income')
        with self.assertRaisesRegex(ValueError, 'child tasks'): self.review(parent, 'qa-auditor', 'PASS', 'Check')
        self.dispatch(child); self.hub.submit(child, self.result())
        self.review(child, 'qa-auditor', 'PASS', 'Check child')
        self.review(parent, 'qa-auditor', 'PASS', 'Check integrated result')
        with self.assertRaises(ValueError): self.new(parent=parent)

    def test_cancelled_task_cannot_run(self):
        i = self.new(); self.hub.cancel(i, 'Replaced by updated task')
        with self.assertRaises(ValueError): self.dispatch(i)

    def test_preflight_required_again_after_rework(self):
        i = self.new()
        packet = self.hub.dispatch(i)
        with self.assertRaisesRegex(ValueError, 'preflight'): self.hub.submit(i, self.result())
        self.preflight(i, self.checks(packet))
        self.hub.submit(i, self.result())
        self.review(i, 'qa-auditor', 'REWORK', 'More evidence needed')
        self.hub.dispatch(i)
        with self.assertRaisesRegex(ValueError, 'preflight'): self.hub.submit(i, self.result())

    def test_preflight_rejects_false_freshness_and_unknown_skills(self):
        i = self.new(); packet = self.hub.dispatch(i)
        for patch in [{'instruction_fingerprint': 'old'}, {'skills_read': []},
                      {'skills_read': ['../untrusted/SKILL.md']},
                      {'freshness_status': 'VERIFIED'}, {'runtime_check': ''}]:
            checks = self.checks(packet); checks.update(patch)
            with self.assertRaises(ValueError): self.preflight(i, checks)
        checks = self.checks(packet)
        checks.update(freshness_status='VERIFIED', sources=self.result()['sources'])
        with self.assertRaises(ValueError): self.preflight(i, checks)

    def test_unverified_freshness_disclosed_in_result(self):
        i = self.new(); packet = self.hub.dispatch(i)
        checks = self.checks(packet); checks['freshness_status'] = 'UNVERIFIED'
        self.preflight(i, checks)
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
        self.review(child, 'qa-auditor', 'PASS', 'Checked child output')
        (self.root/'child.md').write_text('Changed child evidence')
        with self.assertRaisesRegex(ValueError, 'Artifact changed'):
            self.review(parent, 'qa-auditor', 'PASS', 'Integrated report')

    def test_blocked_parent_cannot_accept_new_work(self):
        parent = self.ready()
        self.review(parent, 'qa-auditor', 'BLOCKED', 'Missing prerequisite')
        with self.assertRaises(ValueError): self.new(parent=parent)

    def test_readable_report_preserves_uncertainty(self):
        from agent_hub.reporting import markdown_report
        self.ready(domain='trading')
        report = markdown_report(self.hub.report())
        self.assertIn('Asia/Baghdad', report)
        self.assertIn('Live trading: disabled', report)
        self.assertIn('Offline test', report)
        self.assertIn('HISTORICAL', report)
        self.assertIn('QA_REVIEW: 1', report)


class RealPackage(unittest.TestCase):
    def test_cli_memory_export_markdown_backup_and_finder(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            base=[sys.executable,'-m','agent_hub','--db',str(directory/'db')]
            def run(*args):
                result=subprocess.run(base+list(args),cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                return json.loads(result.stdout)
            record={'namespace':'ecommerce','kind':'lesson','title':'Offline fixture memory',
                    'payload':{'summary':'Validate delivery timestamps'},'sources':[],'confidence':'UNVERIFIED'}
            path=directory/'record.json';path.write_text(json.dumps(record))
            saved=run('memory','put','--actor','iraq-ecommerce-director','--record',str(path))
            run('memory','export','--actor','iraq-ecommerce-director','--out',str(directory/'export.json'))
            self.assertTrue((directory/'export.json').is_file())
            run('memory','enqueue','--actor','iraq-ecommerce-director','--id',saved['id'],'--provider','markdown')
            synced=run('memory','sync','--actor','iraq-ecommerce-director','--provider','markdown','--directory',str(directory/'vault'))
            self.assertEqual(synced[0]['status'],'DONE')
            run('backup','--out',str(directory/'backup.sqlite'))
            run('restore','--source',str(directory/'backup.sqlite'),'--out',str(directory/'restored.sqlite'))
            self.assertTrue((directory/'restored.sqlite').is_file())
            self.assertEqual(run('skills','finder','unavailable live registry')['status'],'REQUIRES_CONFIGURATION')

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
            def run(*args, expected=0):
                p = subprocess.run(base+list(args),cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(p.returncode,expected,p.stderr)
                return json.loads(p.stdout) if expected==0 and p.stdout.lstrip().startswith(('{','[')) else p.stdout
            task=run('new','Plan a paper trading workflow','--criteria','List missing inputs','--department','trading','--mode','paper')
            i=str(task['id'])
            run('dispatch',i,expected=1)
            run('management-review',i,'--analysis','Offline CLI fixture analysis')
            plan={'owner':'trading-director','selected_skills':['master-workflow'],'acceptance_criteria':['List missing inputs'],
                  'rationale':'Offline CLI fixture role match','dependencies':[]}
            path=Path(temp)/'plan.json';path.write_text(json.dumps(plan))
            run('plan',i,'--plan',str(path));run('assign',i,'--evidence','Offline CLI fixture assignment')
            packet=run('dispatch',i)
            self.assertEqual(packet['owner'],'trading-director')
            evidence={'review_reference':'test://simulated-review','criteria':[{'criterion':'List missing inputs','verdict':'PASS','evidence':['test://fixture']}],
                      'checks':{k:{'verdict':'PASS','evidence':['test://fixture']} for k in QA_CHECKS},
                      'tests':[{'command':'offline fixture','result':'PASS','reference':'test://fixture'}]}
            qa=Path(temp)/'qa.json';qa.write_text(json.dumps(evidence))
            run('review',i,'--reviewer','qa-auditor','--verdict','PASS','--notes','No work done','--evidence',str(qa),expected=1)
            checks={'instruction_fingerprint':packet['instructions']['fingerprint'],'skills_read':['.claude/skills/master-workflow/SKILL.md'],
                    'runtime_check':'Offline CLI test only','freshness_status':'NOT_REQUIRED','freshness_notes':'No external claims','sources':[]}
            check_path=Path(temp)/'checks.json';check_path.write_text(json.dumps(checks))
            run('recall',i,'--query','prior fixture outcomes')
            run('preflight',i,'--checks',str(check_path));run('start',i,'--evidence','Offline fixture work starts')
            result={'summary':'Offline CLI fixture','artifacts':['README.md'],'sources':[],
                    'limitations':['Test fixture only; no actual research or independent review']}
            result_path=Path(temp)/'result.json';result_path.write_text(json.dumps(result))
            run('submit',i,'--result',str(result_path))
            run('review',i,'--reviewer','qa-auditor','--verdict','PASS','--notes','Simulated review for offline test','--evidence',str(qa))
            output=run('report','--format','markdown');self.assertIn('COMPLETED: 1',output)


if __name__ == '__main__':
    unittest.main()
