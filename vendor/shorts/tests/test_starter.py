import importlib.util, json, pathlib, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('shortslab',ROOT/'scripts'/'shortslab.py');lib=importlib.util.module_from_spec(spec);spec.loader.exec_module(lib)
class StarterTests(unittest.TestCase):
 def test_skills(self):
  skills=list((ROOT/'.claude'/'skills').glob('*/SKILL.md'))
  self.assertEqual(len(skills),17)
  for p in skills:
   s=p.read_text();self.assertTrue(s.startswith('---\nname: '));self.assertIn('\ndescription: ',s)
 def test_subagents(self):
  agents=list((ROOT/'.claude'/'agents').glob('*.md'))
  self.assertEqual(len(agents),7)
  for a in agents:self.assertIn('model: inherit',a.read_text())
 def test_score(self):
  data=json.loads((ROOT/'examples'/'niches.json').read_text())
  self.assertTrue(all(0<=lib.niche_score(r)<=100 for r in data))
  with self.assertRaises(ValueError):lib.niche_score(dict(data[0],demand=8))
 def test_db_memory(self):
  original=lib.DB
  try:
   with tempfile.TemporaryDirectory() as d:
    lib.DB=pathlib.Path(d)/'test.db'
    with lib.connect() as c:
     c.execute('INSERT INTO decisions(created_at,title,rationale,evidence) VALUES(?,?,?,?)',('now','Test','Reason','Evidence'))
     self.assertEqual(c.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],1)
  finally:lib.DB=original
 def test_no_auto_publish(self):
  self.assertIn('no auto-publish tool',(ROOT/'CLAUDE.md').read_text().lower())
if __name__=='__main__':unittest.main()
