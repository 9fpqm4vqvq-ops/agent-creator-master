"""Tests for MAOS local governance; no credentials, internet, or Claude runtime required."""
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('maos',ROOT/'scripts'/'maos.py')
maos=importlib.util.module_from_spec(spec); spec.loader.exec_module(maos)

def args(**kwargs):return SimpleNamespace(**kwargs)

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/'t.sqlite'
        self.c=maos.connect(self.db)
        maos.init(self.c,args(db=str(self.db)))
    def tearDown(self):
        self.c.close();self.temp.cleanup()
    def task(self,owner='research-analyst',domain='research'):
        return maos.new_task(self.c,args(title='Research new tool',objective='Find reliable evidence',domain=domain,
                                      owner=owner,criteria='2 authoritative sources and a limitation',risk='low'))['task_id']
    def reach_qa(self,tid):
        for status in ('DIAGNOSING','ROUTING','EXECUTING','QA'):
            maos.advance(self.c,args(task_id=tid,to=status))
    def propose(self,name='synthetic-auditor'):
        return maos.propose_agent(self.c,args(name=name,department='analysis',capabilities='summarize,analysis',
                tools='Read,Glob,Grep',version='0.1.0',reason='Weekly regulated summaries reduce manual errors',
                repetitive=True,rule_based=True,valuable=True))

    def test_seed_ten_roles(self):
        names={row['name'] for row in maos.agents(self.c,args())}
        self.assertEqual(len(names),10)
        self.assertIn('qa-auditor',names)
        self.assertIn('token-watchdog',names)

    def test_normal_task_independent_qa(self):
        tid=self.task();self.reach_qa(tid)
        outcome=maos.qa(self.c,args(task_id=tid,reviewer='qa-auditor',result='PASS',notes='Sources verified'))
        self.assertEqual(outcome['status'],'COMPLETED')
        self.assertEqual(maos.get_task(self.c,tid)['last_qa'],'PASS')

    def test_cannot_skip_qa_or_self_approve(self):
        tid=self.task(owner='qa-auditor')
        with self.assertRaises(ValueError):maos.advance(self.c,args(task_id=tid,to='COMPLETED'))
        self.reach_qa(tid)
        with self.assertRaisesRegex(ValueError,'Independent'):
            maos.qa(self.c,args(task_id=tid,reviewer='qa-auditor',result='PASS',notes='Self review'))
        self.assertEqual(maos.get_task(self.c,tid)['status'],'QA')

    def test_rework_limit_three(self):
        tid=self.task();self.reach_qa(tid)
        for i in range(3):
            result=maos.qa(self.c,args(task_id=tid,reviewer='qa-auditor',result='REWORK',notes=f'Problem {i}'))
            if i<2:
                self.assertEqual(result['status'],'REWORK')
                maos.advance(self.c,args(task_id=tid,to='EXECUTING'))
                maos.advance(self.c,args(task_id=tid,to='QA'))
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(result['escalated'])
        self.assertEqual(result['reworks'],3)

    def test_fraud_or_missing_evidence_can_block(self):
        tid=self.task();self.reach_qa(tid)
        result=maos.qa(self.c,args(task_id=tid,reviewer='qa-auditor',result='BLOCKED',notes='No credible proof'))
        self.assertEqual(result['status'],'BLOCKED')

    def test_routing_does_not_execute(self):
        tid=self.task()
        r=maos.route(self.c,args(task_id=tid))
        self.assertEqual(r['lead_suggestion'],'research-analyst')
        self.assertTrue(r['does_not_execute_agent'])
        self.assertEqual(maos.get_task(self.c,tid)['status'],'QUEUED')

    def test_three_r_missing_blocks_creation(self):
        values=dict(name='new-analyst',department='research',capabilities='research',tools='Read',
                    version='0.1.0',reason='Some value',repetitive=False,rule_based=True,valuable=True)
        with self.assertRaisesRegex(ValueError,'3R'):
            maos.propose_agent(self.c,args(**values))

    def test_agent_activation_full_gates(self):
        name='synthetic-auditor';self.propose(name)
        with self.assertRaises(ValueError):maos.activate_agent(self.c,args(name=name))
        maos.agent_test(self.c,args(name=name,passed=True,reference='tests/check.md'))
        with self.assertRaises(ValueError):maos.activate_agent(self.c,args(name=name))
        maos.agent_qa(self.c,args(name=name,reviewer='qa-auditor',passed=True,notes='Independent pass'))
        with self.assertRaises(ValueError):maos.activate_agent(self.c,args(name=name))
        maos.approve(self.c,args(action='agent_deploy',scope=name,approver='USER',reference='conversation:approved'))
        # Can't claim installed without a real agent definition.
        with self.assertRaisesRegex(ValueError,'agent definition'):
            maos.activate_agent(self.c,args(name=name))
        fake_root=Path(self.temp.name)/'package';f=fake_root/'.claude'/'agents'/f'{name}.md'
        f.parent.mkdir(parents=True);f.write_text('---\nname: synthetic-auditor\ndescription: test\n---\n')
        with patch.object(maos,'__file__',str(fake_root/'scripts'/'maos.py')):
            result=maos.activate_agent(self.c,args(name=name))
        self.assertEqual(result['status'],'ACTIVE')

    def test_agent_qa_must_be_independent(self):
        name='synthetic-auditor';self.propose(name)
        maos.agent_test(self.c,args(name=name,passed=True,reference='test record'))
        with self.assertRaises(ValueError):
            maos.agent_qa(self.c,args(name=name,reviewer=name,passed=True,notes='Not independent'))

    def test_usage_truthfulness(self):
        tid=self.task()
        with self.assertRaisesRegex(ValueError,'telemetry'):
            maos.usage(self.c,args(task_id=tid,kind='measured',input_tokens=10,output_tokens=5,cost_usd=0.1,reference=''))
        result=maos.usage(self.c,args(task_id=tid,kind='estimated',input_tokens=200,output_tokens=50,cost_usd=0.0,reference=''))
        self.assertEqual(result['tokens'],250)
        self.assertIn('estimated',str(maos.report(self.c,args())['usage_by_kind']))

    def test_evidence_and_decision_separated(self):
        tid=self.task()
        maos.evidence(self.c,args(task_id=tid,statement='API has rate limits',source='https://example.org/manual',
                  checked_at='2026-10-28',classification='ASSUMPTION',freshness_days=14))
        maos.decision(self.c,args(task_id=tid,kind='PLANNING',reason='Need official docs',outcome='Research next'))
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM evidence').fetchone()[0],1)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],1)
        self.assertEqual(maos.get_task(self.c,tid)['status'],'QUEUED')

    def test_separate_task_status_and_registry(self):
        self.task()
        result=maos.report(self.c,args())
        self.assertEqual(result['tasks_by_status']['QUEUED'],1)
        self.assertIn('No automatic Claude usage telemetry',result['warning'])

class PackageValidationTests(unittest.TestCase):
    def test_agent_frontmatter(self):
        paths=list((ROOT/'.claude'/'agents').glob('*.md'))
        self.assertEqual(len(paths),10)
        for f in paths:
            data=f.read_text()
            self.assertTrue(data.startswith('---\n'),str(f))
            self.assertRegex(data,r'(?m)^name: '+re.escape(f.stem)+r'$')
            for key in ('description','tools','model'):
                self.assertRegex(data,rf'(?m)^{key}: .+')
            self.assertNotIn('bypassPermissions',data)

    def test_skill_frontmatter(self):
        paths=list((ROOT/'.claude'/'skills').glob('*/SKILL.md'))
        self.assertEqual(len(paths),15)
        for f in paths:
            contents=f.read_text()
            self.assertTrue(contents.startswith('---\n'))
            name=re.search(r'(?m)^name: (.+)$',contents)
            desc=re.search(r'(?m)^description: (.+)$',contents)
            self.assertIsNotNone(name);self.assertIsNotNone(desc)
            self.assertEqual(name.group(1),f.parent.name)
            self.assertLessEqual(len(desc.group(1)),1024)
            self.assertLessEqual(len(name.group(1)),64)
            self.assertNotIn('<',desc.group(1))
            self.assertNotIn('>',desc.group(1))

    def test_documentation_exists(self):
        for f in ('README.md','CLAUDE.md','docs/OPERATIONS.md','docs/CONTRACT.md','docs/INTEGRATION.md'):
            self.assertTrue((ROOT/f).is_file(),f)

if __name__=='__main__':unittest.main()
