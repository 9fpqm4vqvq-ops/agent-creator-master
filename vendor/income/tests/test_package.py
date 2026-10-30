import sys,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PackageTests(unittest.TestCase):
    def test_skill_metadata_and_count(self):
        files=list((ROOT/'.claude'/'skills').glob('*/SKILL.md'))
        self.assertEqual(len(files),17)
        for p in files:
            data=p.read_text()
            self.assertTrue(data.startswith('---\n'),str(p))
            self.assertEqual(data.count('\n---\n'),1,str(p))
            self.assertIn('name: '+p.parent.name,data)
            self.assertRegex(data,r'(?m)^description: .{20,}$')
            self.assertNotIn('<xml>',data)
    def test_all_agents_and_existing_preload_skills(self):
        files=list((ROOT/'.claude'/'agents').glob('*.md'))
        self.assertEqual(len(files),11)
        names={p.parent.name for p in (ROOT/'.claude'/'skills').glob('*/SKILL.md')}
        for p in files:
            txt=p.read_text();self.assertTrue(txt.startswith('---\n'))
            self.assertIn('name: '+p.stem,txt)
            for line in txt.splitlines():
                if line.startswith('  - '):self.assertIn(line[4:],names)
    def test_source_template_is_present(self):
        for p in ['CLAUDE.md','README.md','references/payment-route.md','references/qa-gates.md','scripts/ioi.py']:
            self.assertTrue((ROOT/p).exists(),p)
