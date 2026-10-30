"""Behavioral v0.3 checks. All runtime/source/QA claims here are labeled fixtures."""
import copy
import json
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

import test_hub as old_fixtures
from agent_hub.core import Hub, ROLES, QA_CHECKS
from agent_hub.legacy import Hub as LegacyHub
from agent_hub.memory import ConflictError
from agent_hub.providers import MarkdownVaultProvider, NotionProviderStub, SQLiteProvider, MemoryProvider
from agent_hub.skill_finder import SkillFinderAdapter
from agent_hub.skills import skill_fingerprint
from agent_hub.migrations import migrate, restore
from agent_hub.ecommerce import unit_economics


class Support:
    # Keep the original v0.2 scenarios, adding only v0.3 setup gates in their fixture.
    setUp = old_fixtures.Workflow.setUp
    new = old_fixtures.Workflow.new
    plan = old_fixtures.Workflow.plan
    checks = old_fixtures.Workflow.checks
    preflight = old_fixtures.Workflow.preflight
    dispatch = old_fixtures.Workflow.dispatch
    ready = old_fixtures.Workflow.ready
    result = old_fixtures.Workflow.result
    qa_evidence = old_fixtures.Workflow.qa_evidence
    review = old_fixtures.Workflow.review


class ManagementAndQA(Support, unittest.TestCase):
    def test_management_cannot_be_bypassed(self):
        i=self.hub.create('Analyze a request','Measurable acceptance')['id']
        self.assertEqual(self.hub.task(i)['phase'],'CREATED')
        with self.assertRaises(ValueError): self.hub.dispatch(i)
        with self.assertRaises(ValueError): self.hub.assign(i,'Unplanned')
        with self.assertRaises(PermissionError): self.hub.management_review(i,'Owner shortcut',actor='trading-director')
        with self.assertRaises(ValueError): self.hub.submit(i,self.result())

    def test_complete_trace_and_approved_memory(self):
        i=self.ready(domain='ecommerce')
        self.review(i,'qa-auditor','PASS','Offline fixture criterion review')
        history=self.hub.history(i)
        phases=[e['detail']['to'] for e in history if e['kind']=='TRANSITION']
        self.assertEqual(phases,['MANAGEMENT_REVIEW','PLANNED','ASSIGNED','PREFLIGHT','IN_PROGRESS','SUBMITTED','QA_REVIEW','COMPLETED'])
        self.assertTrue(all(e['actor'] and e['at'] and isinstance(e['refs'],list) for e in history))
        records=self.hub.memory.search('Research','iraq-ecommerce-director','ecommerce')
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['confidence'],'QA_APPROVED_OPERATOR')
        self.assertIn('MEMORY_STORED',[e['kind'] for e in history])

    def test_ecommerce_roles_and_reporting_path(self):
        roles={k:v for k,v in ROLES.items() if v[0]=='ecommerce'}
        self.assertEqual(len(roles),8)
        self.assertEqual(ROLES['iraq-ecommerce-director'][1],'income-director')
        self.assertEqual(ROLES['income-director'][1],'management-director')
        i=self.new(domain='ecommerce')
        packet=self.dispatch(i)
        self.assertEqual(packet['owner'],'iraq-ecommerce-director')
        self.assertEqual(packet['logical_chain'][2],'management-director')

    def test_requested_agent_cannot_be_silently_replaced(self):
        i=self.hub.create('Specific worker','Criteria',agent='trading-director')['id']
        self.hub.management_review(i,'Fixture analysis')
        with self.assertRaises(ValueError):
            self.hub.plan(i,{'owner':'shorts-director','selected_skills':['master-workflow'],'acceptance_criteria':['Criteria'],'rationale':'Wrong worker'})

    def test_dependencies_gate_dispatch_and_reject_cycles(self):
        dependency=self.new();i=self.hub.create('Dependent work','Criteria')['id']
        self.hub.management_review(i,'Fixture dependency analysis')
        plan={'owner':'management-director','selected_skills':['master-workflow'],'acceptance_criteria':['Criteria'],
              'rationale':'Fixture dependency','dependencies':[dependency]}
        self.hub.plan(i,plan);self.hub.assign(i,'Fixture assignment')
        with self.assertRaisesRegex(ValueError,'dependency'):self.hub.dispatch(i)
        parent=self.new();child=self.hub.create('Child','Criteria',parent=parent)['id']
        self.hub.management_review(child,'Fixture child analysis')
        plan['dependencies']=[parent]
        with self.assertRaisesRegex(ValueError,'cycle'):self.hub.plan(child,plan)

    def test_preflight_needs_memory_retrieval_and_explicit_start(self):
        i=self.new();packet=self.hub.dispatch(i)
        with self.assertRaisesRegex(ValueError,'memory'):self.hub.preflight(i,self.checks(packet))
        self.hub.recall(i,'No prior fixture record')
        self.hub.preflight(i,self.checks(packet))
        with self.assertRaisesRegex(ValueError,'start'):self.hub.submit(i,self.result())
        self.hub.start(i,'Fixture starts after preflight')
        self.assertEqual(self.hub.submit(i,self.result())['phase'],'QA_REVIEW')

    def test_missing_skill_escalation_preserves_original_request(self):
        i=self.hub.create('Specialized task','Original acceptance')['id']
        t=self.hub.request_capability(i,'Missing specialized API','No reviewed local capability')
        self.assertEqual(t['phase'],'ESCALATION')
        self.assertEqual(t['criteria'],'Original acceptance')
        event=self.hub.history(i)[-1]
        self.assertEqual(event['detail']['assigned_to'],'agent-creator-researcher')
        self.assertEqual(event['detail']['finder']['status'],'REQUIRES_CONFIGURATION')
        with self.assertRaises(ValueError):self.hub.dispatch(i)

    def test_qa_requires_evidence_and_all_original_criteria(self):
        i=self.ready()
        with self.assertRaisesRegex(ValueError,'Structured'):self.hub.review(i,'qa-auditor','PASS','Fake review')
        evidence=self.qa_evidence(i);evidence['criteria']=[]
        with self.assertRaisesRegex(ValueError,'criterion'):self.hub.review(i,'qa-auditor','PASS','Omitted criterion',evidence)
        evidence=self.qa_evidence(i);del evidence['checks']['artifact_integrity']
        with self.assertRaisesRegex(ValueError,'every'):self.hub.review(i,'qa-auditor','PASS','Omitted check',evidence)
        self.assertEqual(self.hub.task(i)['phase'],'QA_REVIEW')

    def test_qa_rejects_failed_checks_or_tests_on_pass(self):
        i=self.ready();evidence=self.qa_evidence(i)
        evidence['checks']['source_freshness'].update(verdict='FAIL',correction='Get current source')
        with self.assertRaises(ValueError):self.hub.review(i,'qa-auditor','PASS','Failed source check',evidence)
        evidence=self.qa_evidence(i);evidence['tests'][0]['result']='FAIL'
        with self.assertRaises(ValueError):self.hub.review(i,'qa-auditor','PASS','Failed test',evidence)

    def test_contributing_qa_author_cannot_review(self):
        i=self.new();self.dispatch(i);result=self.result()
        result['authors']=[self.hub.task(i)['owner'],'qa-auditor']
        self.hub.submit(i,result)
        with self.assertRaisesRegex(ValueError,'contributing'):self.review(i,'qa-auditor','PASS','Self authored')

    def test_configurable_rework_escalation_and_authorized_resume(self):
        i=self.ready(cycle_limit=2)
        self.review(i,'qa-auditor','REWORK','Fixture specific correction')
        self.assertEqual(self.hub.task(i)['phase'],'ASSIGNED')
        self.dispatch(i);self.hub.submit(i,self.result())
        self.review(i,'qa-auditor','REWORK','Unresolved fixture criterion')
        self.assertEqual(self.hub.task(i)['phase'],'ESCALATION')
        with self.assertRaises(ValueError):self.hub.resume(i,'Diagnosis','')
        with self.assertRaises(ValueError):self.hub.resume(i,'Diagnosis','test://authorization',cycle_limit=2)
        self.hub.resume(i,'Fixture root cause resolved','test://actual-simulated-user-authorization',cycle_limit=3)
        self.hub.plan(i,{'owner':self.hub.task(i)['owner'],'selected_skills':['master-workflow'],
            'acceptance_criteria':[self.hub.task(i)['criteria']],'rationale':'Fixture revised plan'})
        self.hub.assign(i,'Fixture revised assignment');self.dispatch(i);self.hub.submit(i,self.result())
        self.review(i,'qa-auditor','PASS','Fixture correction reviewed')
        self.assertEqual(self.hub.task(i)['phase'],'COMPLETED')
        self.assertEqual(len([e for e in self.hub.history(i) if e['kind']=='QA_RECORD']),3)

    def test_audit_redacts_secrets_and_private_reasoning(self):
        i=self.new()
        self.hub.record(i,self.hub.task(i)['owner'],'DECISION','password=SHOULD_NOT_APPEAR',refs=['fixture://reference'])
        serialized=json.dumps(self.hub.history(i))
        self.assertNotIn('SHOULD_NOT_APPEAR',serialized)
        with self.assertRaises(PermissionError):self.hub.record(i,'trading-director','DECISION','Unassigned writer')

    def test_code_change_invalidates_inflight_task(self):
        code=self.root/'agent_hub';code.mkdir();(code/'helper.py').write_text('baseline')
        i=self.new();self.dispatch(i);(code/'helper.py').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Instructions changed'):self.hub.submit(i,self.result())


class Skills(Support, unittest.TestCase):
    def candidate(self):
        folder=self.root/'work/skill-candidates/candidate';folder.mkdir(parents=True)
        (folder/'SKILL.md').write_text('---\nname: candidate\ndescription: Fixture only\n---\nDo not execute fixture code.')
        (folder/'payload.py').write_text("raise RuntimeError('This quarantined fixture must never run')")
        record=copy.deepcopy(self.hub.skills.get('master-workflow'))
        record.update(id='candidate',name='candidate',path='work/skill-candidates/candidate/SKILL.md',
                      fingerprint=skill_fingerprint(self.root,'work/skill-candidates/candidate/SKILL.md'),security_status='VALIDATED')
        return self.hub.skills.register_candidate(record,'agent-creator-researcher')

    def test_local_discovery_and_usage_history(self):
        self.assertEqual(self.hub.skills.search('workflow')[0]['id'],'master-workflow')
        i=self.ready()
        usage=self.hub.skills.usage('master-workflow')
        self.assertEqual(usage[0]['task_id'],i);self.assertTrue(usage[0]['used_at'])
        self.review(i,'qa-auditor','REWORK','Fixture correction')
        self.dispatch(i);self.hub.submit(i,self.result())
        self.assertEqual(len(self.hub.skills.usage('master-workflow')),2)

    def test_candidate_cannot_self_assert_trust_or_execute(self):
        record=self.candidate()
        self.assertEqual(record['security_status'],'QUARANTINED')
        with self.assertRaisesRegex(ValueError,'Unvalidated'):self.hub.skills.require(['candidate'],'management-director')
        with self.assertRaises(PermissionError):SkillFinderAdapter().install(record)

    def test_candidate_activation_needs_independent_evidence(self):
        self.candidate()
        tests=[{'result':'PASS','reference':'test://offline-candidate-tests'}]
        with self.assertRaises(ValueError):self.hub.skills.activate('candidate','agent-creator-researcher','agent-creator-researcher','test://auth',tests,'Fixture review')
        with self.assertRaises(ValueError):self.hub.skills.activate('candidate','qa-auditor','agent-creator-researcher','',tests,'Fixture review')
        result=self.hub.skills.activate('candidate','qa-auditor','agent-creator-researcher','test://scoped-activation',tests,'Fixture compatibility/license/permission review')
        self.assertEqual(result['security_status'],'VALIDATED')
        self.assertEqual(self.hub.skills.require(['candidate'],'management-director')[0]['id'],'candidate')

    def test_skill_drift_rejected_after_registration(self):
        self.candidate();(self.root/'work/skill-candidates/candidate/payload.py').write_text('changed')
        self.assertEqual(self.hub.skills.get('candidate')['security_status'],'QUARANTINED')
        with self.assertRaises(ValueError):self.hub.skills.activate('candidate','qa-auditor','agent-creator-researcher','test://auth',[{'result':'PASS','reference':'test://tests'}],'Fixture review')

    def test_unknown_and_malformed_selection_rejected(self):
        for selected in [['missing'],[],['master-workflow','master-workflow'],[{}]]:
            with self.assertRaises(ValueError):self.hub.skills.require(selected,'management-director')

    def test_unreviewed_candidate_cannot_be_registered_in_native_discovery(self):
        record=copy.deepcopy(self.hub.skills.get('master-workflow'))
        record.update(id='unsafe-native',name='unsafe-native')
        with self.assertRaisesRegex(ValueError,'outside native'):
            self.hub.skills.register_candidate(record,'agent-creator-researcher')

    def test_finder_documented_schema_is_candidates_only(self):
        calls=[]
        def transport(url):
            calls.append(url)
            return {'skills':[{'name':'candidate','namespace':'@fixture/repo/candidate','description':'Fixture',
                    'stars':9999999,'metadata':{'rawFileUrl':'https://example.com/SKILL.md'}}]}
        result=SkillFinderAdapter(transport).search('Iraq payments')
        self.assertIn('q=Iraq+payments',calls[0])
        self.assertEqual(result['candidates'][0]['security_status'],'QUARANTINED')
        self.assertFalse(result['candidates'][0]['installed'])
        self.assertEqual(SkillFinderAdapter().search('gap')['status'],'REQUIRES_CONFIGURATION')

    def test_finder_invalid_schema_and_transport_failure(self):
        with self.assertRaises(ValueError):SkillFinderAdapter(lambda _: {'skills':'bad'}).search('gap')
        def fail(_):raise RuntimeError('Offline fixture transport failure')
        with self.assertRaises(RuntimeError):SkillFinderAdapter(fail).search('gap')


class Memory(Support, unittest.TestCase):
    def put(self,**options):
        return self.hub.memory.put('trading','lesson','Fixture risk lesson',{'summary':'Validate timestamps'},'trading-director',**options)

    def test_memory_persists_and_retrieves_after_restart(self):
        record=self.put()
        other=Hub(self.root/'hub.sqlite',self.root);self.addCleanup(other.close)
        self.assertEqual(other.memory.get(record['id'],'trading-director')['payload']['summary'],'Validate timestamps')
        self.assertEqual(len(other.memory.search('timestamps','trading-director')),1)

    def test_namespace_acl_and_shared_access(self):
        record=self.put()
        with self.assertRaises(PermissionError):self.hub.memory.get(record['id'],'shorts-director')
        with self.assertRaises(PermissionError):self.hub.memory.put('trading','fact','Title',{},'shorts-director')
        self.hub.memory.put('shared','procedure','Approved fixture procedure',{},'master-agent')
        self.assertEqual(len(self.hub.memory.search('procedure','shorts-director')),1)
        with self.assertRaises(PermissionError):self.hub.memory.put('../escape','fact','Title',{},'master-agent')

    def test_redaction_and_no_hidden_reasoning(self):
        record=self.hub.memory.put('research','finding','Fixture',{'password':'never-log-this','nested':{'api_key':'never-export-this'},
                'chain_of_thought':'do-not-store-hidden-reasoning','summary':'password=VALUE123'},'agent-creator-researcher')
        serialized=json.dumps(record)
        for value in ['never-log-this','never-export-this','do-not-store-hidden-reasoning','VALUE123']:
            self.assertNotIn(value,serialized)
        self.assertIn('[REDACTED]',serialized)

    def test_idempotency_and_optimistic_revision_conflicts(self):
        record=self.put()
        same=self.put(record_id=record['id']);self.assertEqual(same['revision'],1)
        with self.assertRaises(ConflictError):self.hub.memory.put('trading','lesson','Fixture risk lesson',{'changed':True},'trading-director',record_id=record['id'])
        changed=self.hub.memory.put('trading','lesson','Fixture risk lesson',{'changed':True},'trading-director',record_id=record['id'],expected_revision=1)
        self.assertEqual(changed['revision'],2)

    def test_verified_memory_requires_dated_evidence(self):
        with self.assertRaises(ValueError):self.put(confidence='VERIFIED')
        with self.assertRaises(ValueError):self.put(sources=[{'location':'https://example.com','checked_at':'2999-01-01T00:00:00+00:00','classification':'VERIFIED'}])

    def test_export_import_idempotent_and_conflicting_import_atomic(self):
        record=self.put();document=self.hub.memory.export('master-agent',['trading'])
        self.hub.memory.import_records(document,'master-agent')
        self.assertEqual(self.hub.memory.get(record['id'],'master-agent')['revision'],1)
        document['records'][0]['payload']={'conflicting':'edited'}
        with self.assertRaises(ConflictError):self.hub.memory.import_records(document,'master-agent')
        self.assertEqual(self.hub.memory.get(record['id'],'master-agent')['payload']['summary'],'Validate timestamps')
        good=copy.deepcopy(document['records'][0]);good['id']=str(uuid.uuid4())
        bad=copy.deepcopy(good);bad['id']=str(uuid.uuid4());bad['namespace']='escape'
        with self.assertRaises(PermissionError):self.hub.memory.import_records({'format':'memory-vault-v1','records':[good,bad]},'master-agent')
        self.assertIsNone(self.hub.db.execute('SELECT id FROM memory_records WHERE id=?',(good['id'],)).fetchone())

    def test_task_memory_import_into_different_database_retains_provenance(self):
        i=self.ready();self.review(i,'qa-auditor','PASS','Offline fixture QA')
        document=self.hub.memory.export('master-agent')
        other=Hub(self.root/'other.sqlite',self.root);self.addCleanup(other.close)
        result=other.memory.import_records(document,'master-agent')
        self.assertEqual(result[0]['payload']['import_provenance']['origin_task_id'],i)
        self.assertIsNone(result[0]['task_id'])
        other.memory.import_records(document,'master-agent')
        self.assertEqual(len(other.memory.search('Research','master-agent')),1)

    def test_markdown_sync_is_idempotent_and_obsidian_compatible(self):
        record=self.put();provider=MarkdownVaultProvider(self.root/'vault')
        self.hub.memory.enqueue(record['id'],'markdown','trading-director')
        self.hub.memory.enqueue(record['id'],'markdown','trading-director')
        self.assertEqual(self.hub.memory.sync(provider,'trading-director')[0]['status'],'DONE')
        self.assertEqual(self.hub.memory.sync(provider,'trading-director'),[])
        self.assertEqual(provider.read('trading',record['id'])['id'],record['id'])
        self.assertEqual(len(list((self.root/'vault/trading').glob('*.md'))),1)

    def test_external_edit_conflict_preserves_file_and_local_record(self):
        record=self.put();provider=MarkdownVaultProvider(self.root/'vault')
        self.hub.memory.enqueue(record['id'],'markdown','trading-director');self.hub.memory.sync(provider,'trading-director')
        path=self.root/'vault/trading'/(record['id']+'.md');path.write_text('External human edit')
        self.hub.memory.put('trading','lesson','Fixture risk lesson',{'summary':'Updated local'},'trading-director',record_id=record['id'],expected_revision=1)
        self.hub.memory.enqueue(record['id'],'markdown','trading-director')
        self.assertEqual(self.hub.memory.sync(provider,'trading-director')[0]['status'],'CONFLICT')
        self.assertEqual(path.read_text(),'External human edit')
        self.assertEqual(self.hub.memory.get(record['id'],'trading-director')['payload']['summary'],'Updated local')
        queue=self.hub.db.execute("SELECT * FROM memory_sync_queue WHERE status='CONFLICT'").fetchone()
        with self.assertRaises(ConflictError):
            self.hub.memory.resolve_conflict(queue['id'],provider,'trading-director','outdated-hash','Fixture reviewed keep-local decision')
        self.hub.memory.resolve_conflict(queue['id'],provider,'trading-director',provider.current_hash(record),'Fixture reviewed explicit keep-local resolution')
        self.assertEqual(self.hub.memory.sync(provider,'trading-director')[0]['status'],'DONE')
        self.assertEqual(provider.read('trading',record['id'])['payload']['summary'],'Updated local')

    def test_notion_stub_fails_to_persistent_retry_queue(self):
        record=self.put();self.hub.memory.enqueue(record['id'],'notion','trading-director')
        outcome=self.hub.memory.sync(NotionProviderStub(),'trading-director')
        self.assertEqual(outcome[0]['status'],'RETRY')
        row=self.hub.db.execute('SELECT * FROM memory_sync_queue').fetchone()
        self.assertEqual(row['attempts'],1);self.assertIn('not configured',row['error'])
        self.assertEqual(self.hub.memory.sync(NotionProviderStub(),'trading-director'),[])
        other=Hub(self.root/'hub.sqlite',self.root);self.addCleanup(other.close)
        self.assertEqual(other.db.execute('SELECT status FROM memory_sync_queue').fetchone()[0],'RETRY')

    def test_unauthorized_sync_cannot_export_other_department(self):
        record=self.put();self.hub.memory.enqueue(record['id'],'markdown','trading-director')
        provider=MarkdownVaultProvider(self.root/'vault')
        with self.assertRaises(PermissionError):self.hub.memory.sync(provider,'shorts-director')
        self.assertFalse(list((self.root/'vault').rglob('*.md')))

    def test_newer_revision_supersedes_stale_queue_item(self):
        record=self.put();self.hub.memory.enqueue(record['id'],'markdown','trading-director')
        self.hub.memory.put('trading','lesson','Fixture risk lesson',{'summary':'Newest'},'trading-director',record_id=record['id'],expected_revision=1)
        provider=MarkdownVaultProvider(self.root/'vault')
        self.hub.memory.sync(provider,'trading-director')
        self.assertEqual(self.hub.db.execute('SELECT status FROM memory_sync_queue ORDER BY id LIMIT 1').fetchone()[0],'SUPERSEDED')
        self.assertEqual(self.hub.memory.sync(provider,'trading-director')[0]['status'],'DONE')

    def test_sqlite_provider_obeys_common_protocol_and_revision_guards(self):
        record=self.put();provider=SQLiteProvider(self.hub.memory,'trading-director')
        self.assertIsInstance(provider,MemoryProvider)
        self.assertEqual(provider.write(record),record['content_hash'])
        changed=dict(record,payload={'summary':'Reviewed change'})
        with self.assertRaises(ConflictError):provider.write(changed)
        provider.write(changed,expected_hash=record['content_hash'])
        self.assertEqual(provider.read(record['id'])['revision'],2)

    def test_retry_exhaustion_requires_explicit_diagnosis(self):
        record=self.put();self.hub.memory.enqueue(record['id'],'notion','trading-director')
        for _ in range(5):
            with self.hub.db:self.hub.db.execute("UPDATE memory_sync_queue SET next_at='2000-01-01T00:00:00+00:00'")
            result=self.hub.memory.sync(NotionProviderStub(),'trading-director')
        self.assertEqual(result[0]['status'],'FAILED')
        row=self.hub.db.execute('SELECT * FROM memory_sync_queue').fetchone()
        with self.assertRaises(ValueError):self.hub.memory.retry(row['id'],'trading-director','')
        self.hub.memory.retry(row['id'],'trading-director','Fixture: provider deliberately remains a stub')
        self.assertEqual(self.hub.db.execute('SELECT status FROM memory_sync_queue').fetchone()[0],'PENDING')


class Migration(Support, unittest.TestCase):
    def test_v02_migration_backup_and_replan_hold(self):
        path=self.root/'v02.sqlite';legacy=LegacyHub(path,self.root)
        i=legacy.create('Existing task','Existing criteria')['id'];legacy.close()
        upgraded=Hub(path,self.root);self.addCleanup(upgraded.close)
        self.assertEqual(upgraded.task(i)['request'],'Existing task')
        self.assertEqual(upgraded.task(i)['phase'],'MANAGEMENT_REVIEW')
        self.assertTrue(upgraded.task(i)['migration_hold'])
        with self.assertRaises(ValueError):upgraded.dispatch(i)
        self.assertTrue(Path(upgraded.migration['backup']).is_file())
        original=sqlite3.connect(upgraded.migration['backup'])
        self.addCleanup(original.close)
        self.assertNotIn('phase',{r[1] for r in original.execute('PRAGMA table_info(tasks)')})
        again=Hub(path,self.root);self.addCleanup(again.close)
        self.assertIsNone(again.migration['backup'])

    def test_backup_restore_and_refuse_overwrite(self):
        i=self.new();destination=self.root/'consistent-backup.sqlite'
        self.hub.backup(destination)
        with self.assertRaises(ValueError):self.hub.backup(destination)
        restored=self.root/'restored.sqlite';restore(destination,restored)
        other=Hub(restored,self.root);self.addCleanup(other.close)
        self.assertEqual(other.task(i)['request'],self.hub.task(i)['request'])
        with self.assertRaises(ValueError):restore(destination,restored)

    def test_failed_ddl_migration_rolls_back_atomically(self):
        path=self.root/'broken.sqlite';connection=sqlite3.connect(path)
        self.addCleanup(connection.close)
        connection.executescript("CREATE TABLE tasks(id INTEGER PRIMARY KEY,status TEXT); CREATE TABLE events(id INTEGER PRIMARY KEY); INSERT INTO tasks VALUES(1,'QUEUED');")
        before={r[1] for r in connection.execute('PRAGMA table_info(tasks)')}
        with self.assertRaises(sqlite3.OperationalError):migrate(connection,path)
        self.assertEqual({r[1] for r in connection.execute('PRAGMA table_info(tasks)')},before)
        self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],0)

    def test_future_database_version_is_refused(self):
        path=self.root/'future.sqlite';connection=sqlite3.connect(path)
        connection.execute('PRAGMA user_version=8');connection.close()
        with self.assertRaises(ValueError):Hub(path,self.root)


class Economics(unittest.TestCase):
    def assumptions(self):
        return dict(sale_price=100,unit_cost=30,outbound_shipping=5,return_shipping=2,packaging=1,
                    ad_cost_per_attempt=10,cancellation_rate=0,delivery_success_rate=1,return_rate=0,
                    cod_fee_rate=0,inventory_recovery_rate=0,fixed_monthly_cost=108,currency='fixture')

    def test_known_unit_economics_and_breakeven(self):
        result=unit_economics(self.assumptions())
        self.assertEqual(result['expected_contribution'],'54.00')
        self.assertEqual(result['monthly_breakeven_attempts'],2)
        self.assertEqual(result['classification'],'ESTIMATE')

    def test_cancellations_and_failed_deliveries_are_costed(self):
        assumptions=self.assumptions();assumptions.update(cancellation_rate=.5,delivery_success_rate=0)
        result=unit_economics(assumptions)
        self.assertEqual(result['expected_revenue'],'0.00')
        self.assertEqual(result['expected_contribution'],'-29.00')
        self.assertIsNone(result['monthly_breakeven_attempts'])

    def test_invalid_or_missing_assumptions_rejected(self):
        for patch in [{'return_rate':1.1},{'unit_cost':-1},{'sale_price':'NaN'},{'ad_cost_per_attempt':'Infinity'}]:
            assumptions=self.assumptions();assumptions.update(patch)
            with self.assertRaises(ValueError):unit_economics(assumptions)
        with self.assertRaises(ValueError):unit_economics({})


if __name__=='__main__':unittest.main()
