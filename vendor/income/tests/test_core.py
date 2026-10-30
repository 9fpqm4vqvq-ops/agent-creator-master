import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ioi import core as c

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'x.sqlite';self.cx=c.connect(self.db);c.init(self.cx)
        self.oid=c.create(self.cx,'Fictional demo only','B2B service','Small companies',created_by='global-opportunity-researcher')
    def tearDown(self):self.cx.close();self.tmp.cleanup()
    def test_schema_and_new_opportunity_hold(self):
        self.assertEqual(self.cx.execute('SELECT COUNT(*) FROM payout_checks').fetchone()[0],6)
        self.assertFalse(c.gate(self.cx,self.oid)['allowed'])
    def test_score_is_weighted_and_missing_criteria_are_not_normalized(self):
        c.rating_set(self.cx,self.oid,'demand',10,'illustrative')
        self.assertEqual(c.score(self.cx,self.oid)['score'],20)
        self.assertFalse(c.score(self.cx,self.oid)['complete'])
    def test_payout_requirements_and_fake_attest_fail(self):
        with self.assertRaises(c.IOIError):c.payout_set(self.cx,self.oid,'customer_payment','VERIFIED',url='https://example.com')
        c.evidence_add(self.cx,self.oid,'Illustrative claim, not proof','https://example.com')
        with self.assertRaises(c.IOIError):c.qa_attest(self.cx,self.oid,'quality-fraud-auditor','PASS','I checked')
        with self.assertRaises(c.IOIError):c.decision_add(self.cx,self.oid,'TEST','looks good')
    def _pass_gate_as_test_fixture_only(self):
        c.evidence_add(self.cx,self.oid,'Fictional fixture claim','https://example.com')
        for s in c.STAGES:
            c.payout_set(self.cx,self.oid,s,'VERIFIED',provider='FAKE_TEST_ONLY',url='https://example.com/fictional',details='This is fictional test fixture, NEVER use for research')
        c.qa_attest(self.cx,self.oid,'quality-fraud-auditor','PASS','Fictional unit test only; not reviewed real source')
    def test_qa_stale_after_material_change(self):
        self._pass_gate_as_test_fixture_only()
        self.assertTrue(c.gate(self.cx,self.oid)['allowed'])
        c.flag_add(self.cx,self.oid,'MAJOR','fictional serious issue')
        self.assertFalse(c.gate(self.cx,self.oid)['allowed'])
        self.assertEqual(c.qa_current(self.cx,self.oid)['verdict'],'STALE')
    def test_creator_cannot_attest_own_work(self):
        c.evidence_add(self.cx,self.oid,'Fictional fixture claim','https://example.com')
        with self.assertRaises(c.IOIError):c.qa_attest(self.cx,self.oid,'global-opportunity-researcher','FAIL','No actual verification')
    def test_rework_three_attempt_limit(self):
        for i in range(3):self.assertEqual(c.rework_add(self.cx,self.oid,'cause','correction','researcher'),i+1)
        with self.assertRaises(c.IOIError):c.rework_add(self.cx,self.oid,'cause','correction','researcher')
    def test_approval_required_for_activation_and_cost_cap(self):
        self._pass_gate_as_test_fixture_only()
        eid=c.experiment_create(self.cx,self.oid,'hypothesis','conversion',5,10,2)
        with self.assertRaises(c.IOIError):c.experiment_activate(self.cx,eid,999)
        with self.assertRaises(c.IOIError):c.approve(self.cx,self.oid,'EXPERIMENT',10,'test-user','missing experiment ID')
        app=c.approve(self.cx,self.oid,'EXPERIMENT',10,'test-user','fictional approval for unit tests only',eid)
        c.experiment_activate(self.cx,eid,app)
        c.event_add(self.cx,eid,1,5,4,1,'fictional event')
        with self.assertRaises(c.IOIError):c.event_add(self.cx,eid,1,0,7,1,'exceeds allowed cost')
        c.experiment_close(self.cx,eid,'fictional test complete')
    def test_finance_math_and_malformed_inputs(self):
        res=c.finance(25,0,10,20,5,10,40,8)
        self.assertEqual(res['break_even_units'],3)
        self.assertEqual(res['scenarios'][1]['net'],135)
        with self.assertRaises(c.IOIError):c.finance(25,20,10,0,5,10,40,8)
    def test_dashboard_actual_records_only(self):
        report=c.dashboard(self.cx)
        self.assertIn('Fictional demo only',report)
        self.assertIn('Revenue logged: $0.00',report)
        self.assertIn('HOLD',report)

if __name__=='__main__':unittest.main()
