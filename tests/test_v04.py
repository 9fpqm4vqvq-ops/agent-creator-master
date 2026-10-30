"""v0.4 offline behavioral checks. QA/model/provider evidence is explicitly simulated.
HTTP and subprocess/filesystem/SQLite operations are real local operations.
"""
import copy
import hashlib
import http.client
import json
import sqlite3
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from test_v03 import Support
from agent_hub.core import Hub, ROOT
from agent_hub.legacy import now
from agent_hub.usage import UsageLedger, BudgetService, estimate_cost, instant
from agent_hub.scheduler import Scheduler, PRINCIPAL, next_due
from agent_hub.monitoring import snapshot, scorecards
from agent_hub.dashboard import make_server, connect_readonly
from agent_hub.improvements import file_hash


class Evidence(Support):
    def qa_result(self,extra,agent='knowledge-freshness-auditor',sources=None):
        i=self.new(agent=agent);self.dispatch(i)
        result=dict(self.result(),**extra)
        if sources is not None:result['sources']=sources
        self.hub.submit(i,result);self.review(i,'qa-auditor','PASS','SIMULATED independent QA for offline service tests')
        return i
    def put(self,title='Supplier price',payload=None,**options):
        return self.hub.memory.put('trading','fact',title,payload or {'value':10},'trading-director',category='supplier_price',**options)
    def fresh(self,record):
        task=self.qa_result({'verified_memory_ids':[record['id']],'memory_record_hashes':{record['id']:record['content_hash']}},
            sources=[{'location':'fixture://dated-source','checked_at':now(),'classification':'VERIFIED'}])
        return self.hub.freshness.verify(record['id'],task)


class Usage(Evidence,unittest.TestCase):
    def entry(self,**changes):
        entry={'task_id':self.new(),'agent':'management-director','provider':'fixture','model':'offline-fixture',
            'invocation_id':'fixture-invocation','source':'fixture://telemetry','token_kind':'MEASURED',
            'input_tokens':100,'output_tokens':20,'cache_read_tokens':40,'cache_write_tokens':10,'actual_cost':'0.03',
            'estimated_cost':'0.04','duration_seconds':'2.5','collected_at':now()}
        entry.update(changes);return entry
    def test_unknown_telemetry_is_not_zero(self):
        result=self.hub.usage.summary();self.assertEqual(result['availability'],'UNKNOWN')
        self.assertIsNone(result['actual_cost_usd']);self.assertIsNone(result['measured_tokens']['input_tokens'])
    def test_actual_estimated_and_cache_counts_stay_separate(self):
        entry=self.entry();self.hub.usage.record(entry)
        entry.update(invocation_id='second',token_kind='ESTIMATED',actual_cost=None)
        self.hub.usage.record(entry);s=self.hub.usage.summary()
        self.assertEqual(s['actual_cost_usd'],'0.03');self.assertEqual(s['estimated_cost_usd'],'0.08')
        self.assertEqual(s['measured_tokens']['input_tokens'],100);self.assertEqual(s['estimated_tokens']['input_tokens'],100)
    def test_cumulative_usage_idempotency_and_revision(self):
        entry=self.entry();first=self.hub.usage.record(entry)
        self.assertEqual(self.hub.usage.record(entry)['id'],first['id'])
        entry['output_tokens']=30
        with self.assertRaises(ValueError):self.hub.usage.record(entry)
        self.assertEqual(self.hub.usage.record(entry,1)['revision'],2)
        self.assertEqual(self.hub.usage.summary()['invocations'],1)
    def test_usage_rejects_invalid_numbers_and_future_dates(self):
        entry=self.entry()
        for change in [{'input_tokens':-1},{'input_tokens':True},{'actual_cost':'NaN'},
            {'actual_cost':'Infinity'},{'duration_seconds':-1},{'token_kind':'UNKNOWN'},
            {'collected_at':'2999-01-01T00:00:00+00:00'},{'task_id':True}]:
            with self.subTest(change=change),self.assertRaises(ValueError):self.hub.usage.record(dict(entry,**change))
    def test_usage_cannot_move_invocation_or_agent(self):
        entry=self.entry();self.hub.usage.record(entry)
        with self.assertRaises(ValueError):self.hub.usage.record(dict(entry,agent='trading-director'),1)
    def test_pricing_requires_cache_semantics_and_provenance(self):
        counts=dict(input_tokens=1000,output_tokens=100,cache_read_tokens=400,cache_write_tokens=100)
        rates=dict(input_includes_cache=True,source='fixture://rates',checked_at=now(),
            input_tokens_per_million=1,output_tokens_per_million=2,cache_read_tokens_per_million='.1',cache_write_tokens_per_million=1)
        result=estimate_cost(counts,rates)
        self.assertEqual(result['estimated_cost'],'0.00084');self.assertEqual(result['classification'],'ESTIMATED')
        del rates['input_includes_cache']
        with self.assertRaises(ValueError):estimate_cost(counts,rates)
    def test_budget_all_five_scopes_and_warning(self):
        i=self.new()
        for scope,key in [('TASK',str(i)),('AGENT','management-director'),('DEPARTMENT','management'),('DAILY','global'),('MONTHLY','global')]:self.hub.budgets.configure(scope,key,'1')
        check=self.hub.budgets.evaluate(i,'management-director','.85')
        self.assertEqual(len(check['budgets']),5);self.assertEqual({b['status'] for b in check['budgets']},{'WARNING'})
        self.assertFalse(check['requires_authorization'])
    def test_unknown_budget_requires_explicit_capped_authorization(self):
        i=self.new();self.hub.budgets.configure('DAILY','global','1')
        pending=self.hub.budgets.reserve(i,'management-director','fixture-key')
        self.assertFalse(pending['allowed'])
        with self.assertRaises(ValueError):self.hub.budgets.approve(pending['approval_id'],'fixture://authorization')
        self.hub.budgets.approve(pending['approval_id'],'fixture://authorization',maximum_usd='.5')
        self.assertTrue(self.hub.budgets.reserve(i,'management-director','fixture-key',approval_id=pending['approval_id'])['allowed'])
        hold=self.hub.db.execute('SELECT amount_usd FROM usage_reservations').fetchone()[0];self.assertEqual(hold,'0.5')
        with self.assertRaises(ValueError):self.hub.budgets.reserve(i,'management-director','fixture-key')
    def test_budget_approval_bound_to_estimate_and_changed_limit(self):
        i=self.new();self.hub.budgets.configure('DAILY','global','1')
        pending=self.hub.budgets.reserve(i,'management-director','a','2')
        self.hub.budgets.approve(pending['approval_id'],'fixture://authorization')
        changed=self.hub.budgets.reserve(i,'management-director','a','3',pending['approval_id']);self.assertFalse(changed['allowed'])
        self.hub.budgets.configure('DAILY','global','.5')
        self.assertFalse(self.hub.budgets.reserve(i,'management-director','a','2',pending['approval_id'])['allowed'])
    def test_reservation_reconciles_without_double_counting(self):
        i=self.new();self.hub.budgets.configure('DAILY','global','1')
        self.hub.budgets.reserve(i,'management-director','r','.4')
        self.hub.usage.record(self.entry(task_id=i,execution_key='r',actual_cost='.2',estimated_cost='.3'))
        budget=self.hub.budgets.evaluate(i,'management-director','0')['budgets'][0]
        self.assertEqual(budget['recorded_charge_usd'],'0.2');self.assertEqual(budget['reserved_usd'],'0')
    def test_task_start_gate_persists_pending_then_resumes_once(self):
        i=self.new();packet=self.hub.dispatch(i);self.hub.recall(i,'fixture');self.hub.preflight(i,self.checks(packet))
        self.hub.budgets.configure('TASK',str(i),'.1')
        with self.assertRaisesRegex(ValueError,'authorization required'):self.hub.start(i,'fixture://invocation',projected_cost='.2')
        pending=self.hub.db.execute("SELECT id FROM budget_approvals WHERE status='PENDING'").fetchone()[0]
        self.assertEqual(self.hub.task(i)['phase'],'PREFLIGHT')
        self.hub.budgets.approve(pending,'fixture://scoped-auth')
        self.hub.start(i,'fixture://invocation',projected_cost='.2',approval_id=pending)
        with self.assertRaises(ValueError):self.hub.start(i,'fixture://duplicate')
    def test_baghdad_daily_boundary_and_unknown_holds_carry(self):
        i=self.new();self.hub.budgets.configure('DAILY','global','1')
        clock=lambda:datetime(2025,10,30,22,tzinfo=timezone.utc) # October 31 in Baghdad
        budget=BudgetService(self.hub.db,clock)
        entry=self.entry(task_id=i,collected_at='2025-10-30T20:00:00+00:00');self.hub.usage.record(entry)
        self.assertEqual(budget.evaluate(i,'management-director','0')['budgets'][0]['recorded_charge_usd'],'0')
        with self.hub.db:self.hub.db.execute("INSERT INTO usage_reservations VALUES('old-unknown',?,'management-director','management',NULL,'ACTIVE','2020-01-01T00:00:00+00:00')",(i,))
        self.assertEqual(budget.evaluate(i,'management-director','0')['budgets'][0]['status'],'UNKNOWN_COST')
    def test_expired_approval_cannot_start_execution(self):
        i=self.new();self.hub.budgets.configure('DAILY','global','1')
        pending=self.hub.budgets.reserve(i,'management-director','expiring','2')
        self.hub.budgets.approve(pending['approval_id'],'fixture://authorization',valid_minutes=1)
        later=BudgetService(self.hub.db,lambda:instant(now())+timedelta(minutes=2))
        self.assertFalse(later.reserve(i,'management-director','expiring','2',pending['approval_id'])['allowed'])

    def test_duplicate_task_requests_are_explicit_and_atomic(self):
        a=self.hub.create('Fixture request','Fixture criterion',idempotency_key='request-1')
        b=self.hub.create('Fixture request','Fixture criterion',idempotency_key='request-1')
        self.assertEqual(a['id'],b['id'])
        with self.assertRaises(ValueError):self.hub.create('Different request','Fixture criterion',idempotency_key='request-1')
    def test_research_cache_returns_references_not_verified_facts(self):
        i=self.new();self.assertIsNone(self.hub.research_cache.lookup(i,'supplier prices','fixture-search'))
        self.hub.research_cache.record(i,'Supplier  prices','fixture-search',['fixture://result'])
        hit=self.hub.research_cache.lookup(i,'supplier prices','fixture-search')
        self.assertTrue(hit['usable']);self.assertEqual(hit['classification'],'UNVERIFIED_REFERENCES')
        self.assertIsNone(self.hub.research_cache.lookup(i,'supplier prices','different-source'))


class Freshness(Evidence,unittest.TestCase):
    def test_new_metadata_and_auditor_read_only_cross_department(self):
        record=self.put();self.assertIsNone(record['last_verified_at']);self.assertEqual(record['verification_status'],'UNVERIFIED')
        self.assertEqual(self.hub.memory.get(record['id'],'knowledge-freshness-auditor')['responsible_department'],'trading')
        from agent_hub.providers import SQLiteProvider
        SQLiteProvider(self.hub.memory,'trading-director').write(record,record['content_hash'])
        self.assertEqual(self.hub.memory.get(record['id'],'trading-director')['category'],'supplier_price')
        with self.assertRaises(PermissionError):self.hub.memory.put('trading','fact','Title',{},'knowledge-freshness-auditor')
    def test_staleness_scan_preserves_content_and_history(self):
        record=self.put();future=instant(now())+timedelta(days=2)
        audit=self.hub.freshness.scan(future)
        current=self.hub.memory.get(record['id'],'master-agent')
        self.assertEqual(current['payload'],record['payload']);self.assertEqual(current['verification_status'],'REQUIRES_VERIFICATION')
        self.assertEqual(audit['findings'][0]['status'],'STALE');self.assertEqual(len(self.hub.memory.history(record['id'],'master-agent')),2)
    def test_duplicate_and_potential_conflicting_claims(self):
        self.put();self.put();self.put(payload={'value':20})
        statuses={f['status'] for f in self.hub.freshness.scan()['findings']}
        self.assertIn('POTENTIAL_CONFLICT',statuses)
    def test_refresh_requests_are_deduplicated_and_unstarted(self):
        record=self.put();first=self.hub.freshness.queue(record['id']);second=self.hub.freshness.queue(record['id'])
        self.assertEqual(first,second);self.assertEqual(self.hub.task(first)['phase'],'CREATED')
    def test_verification_requires_qa_exact_hash_and_dated_sources(self):
        record=self.put()
        task=self.qa_result({'verified_memory_ids':[record['id']],'memory_record_hashes':{record['id']:'wrong'}})
        with self.assertRaises(ValueError):self.hub.freshness.verify(record['id'],task)
        fresh=self.fresh(record);self.assertEqual(fresh['verification_status'],'FRESH')
        self.assertEqual(fresh['revision'],2)
    def test_old_source_qa_cannot_refresh_expired_knowledge(self):
        record=self.put();task=self.qa_result({'verified_memory_ids':[record['id']],
            'memory_record_hashes':{record['id']:record['content_hash']}},sources=[{'location':'fixture://old','checked_at':'2020-01-01T00:00:00+00:00','classification':'VERIFIED'}])
        self.assertEqual(self.hub.freshness.verify(record['id'],task)['verification_status'],'REQUIRES_VERIFICATION')
    def test_content_update_invalidates_prior_verification(self):
        record=self.fresh(self.put());updated=self.put(payload={'value':20},record_id=record['id'],expected_revision=record['revision'])
        self.assertEqual(updated['verification_status'],'UNVERIFIED');self.assertIsNone(updated['last_verified_at'])
        self.assertEqual(len(self.hub.memory.history(record['id'],'master-agent')),3)
    def test_supersession_requires_qa_and_preserves_explicit_retrieval(self):
        old=self.put();replacement=self.fresh(self.put(payload={'value':20}))
        extra={'superseded_memory_ids':[old['id']],'supersession':{old['id']:replacement['id']},
               'memory_record_hashes':{old['id']:old['content_hash'],replacement['id']:replacement['content_hash']}}
        task=self.qa_result(extra);self.hub.freshness.supersede(old['id'],replacement['id'],task)
        self.assertEqual(self.hub.memory.get(old['id'],'trading-director')['superseded_by'],replacement['id'])
        self.assertEqual(len(self.hub.memory.search('Supplier','trading-director')),1)
        self.assertEqual(len(self.hub.memory.search('Supplier','trading-director',include_superseded=True)),2)
        self.hub.memory.import_records(self.hub.memory.export('master-agent',['trading']),'master-agent')
        self.assertEqual(self.hub.memory.get(old['id'],'master-agent')['superseded_by'],replacement['id'])
    def test_configurable_ttl_is_bounded_and_snapshot_changes(self):
        config=self.root/'registry/freshness-policies.json';config.write_text(json.dumps({'ttl_seconds':{'supplier_price':60}}))
        record=self.put();self.assertEqual(json.loads(record['expiry_policy'])['ttl_seconds'],60)
        config.write_text(json.dumps({'ttl_seconds':{'supplier_price':-1}}))
        with self.assertRaises(ValueError):self.put()


class Monitoring(Evidence,unittest.TestCase):
    def test_health_observation_never_claims_current_upstream(self):
        review=self.hub.health.audit('trading','daily')
        self.assertEqual(review['outcome'],'PARTIALLY_VERIFIED');self.assertEqual(review['review_status'],'OBSERVED_UNREVIEWED')
        self.assertEqual(review['verified_versions']['external_currency'],'NOT_VERIFIED_OFFLINE')
    def test_missing_runtime_and_profile_are_reported(self):
        (self.root/'.claude/agents/trading-director.md').unlink()
        with patch('agent_hub.monitoring.shutil.which',return_value=None):review=self.hub.health.audit('trading')
        kinds={f['kind'] for f in review['findings']};self.assertIn('MISSING_ROLE',kinds);self.assertIn('RUNTIME_UNAVAILABLE',kinds)
    def test_missing_skill_catalog_survives_restart_for_audit(self):
        (self.root/'.claude/skills/master-workflow/SKILL.md').unlink()
        other=Hub(self.root/'hub.sqlite',self.root);self.addCleanup(other.close)
        self.assertEqual(other.skills.list()[0]['security_status'],'QUARANTINED')
        self.assertIn('SKILL_UNAVAILABLE',{f['kind'] for f in other.health.audit('management')['findings']})

    def test_changed_skill_is_reported(self):
        (self.root/'.claude/skills/master-workflow/SKILL.md').write_text('changed')
        self.assertIn('SKILL_DRIFT',{f['kind'] for f in self.hub.health.audit('management')['findings']})
    def test_health_qa_is_separate_and_partial_remains_partial(self):
        review=self.hub.health.audit('trading');task=self.qa_result({'health_review_ids':[review['id']]},agent='department-health-auditor')
        accepted=self.hub.health.approve(review['id'],task)
        self.assertEqual(accepted['review_status'],'QA_REVIEWED');self.assertEqual(accepted['outcome'],'PARTIALLY_VERIFIED')
    def test_qa_queue_and_department_open_counts_agree(self):
        i=self.ready();self.assertEqual(snapshot(self.hub.db)['qa']['queue'],[i])
        self.review(i,'qa-auditor','BLOCKED','SIMULATED unavailable source')
        state=snapshot(self.hub.db)
        self.assertEqual(sum(d['active'] for d in state['departments']),state['active'])
        self.assertEqual(sum(d['blocked'] for d in state['departments']),state['blocked'])

    def test_global_counts_and_seven_department_panels(self):
        parent=self.hub.create('Parent','Criteria');self.hub.create('Child','Criteria',agent='trading-director',parent=parent['id'])
        result=snapshot(self.hub.db)
        self.assertEqual(sum(result['phase_counts'].values()),result['task_total']);self.assertEqual(result['task_total'],2)
        self.assertEqual(len(result['departments']),len(__import__('agent_hub.roles',fromlist=['DOMAINS']).DOMAINS));self.assertEqual(sum(d['tasks'] for d in result['departments']),2)
    def test_qa_failed_criteria_and_scorecards_have_evidence(self):
        i=self.ready();self.review(i,'qa-auditor','REWORK','SIMULATED precise correction')
        state=snapshot(self.hub.db);self.assertEqual(state['rework_cycles'],1)
        self.assertEqual(state['qa']['failed_criteria_recurrences']['Document evidence and limitations'],1)
        card=next(c for c in state['scorecards'] if c['agent']=='management-director')
        self.assertEqual(card['qa_failures'],1);self.assertIsNone(card['usage']['actual_cost_usd']);self.assertIn('No ranking',card['sample_caution'])
    def test_tool_failures_need_explicit_evidence(self):
        i=self.new();self.hub.record(i,'management-director','ERROR','SIMULATED generic error')
        card=lambda:next(c for c in scorecards(self.hub.db) if c['agent']=='management-director')
        self.assertEqual(card()['verified_tool_failures'],0)
        with self.assertRaises(ValueError):self.hub.verified_tool_failure(i,'fixture-tool','SIMULATED error','')
        self.hub.verified_tool_failure(i,'fixture-tool','SIMULATED error','fixture://tool-transcript')
        self.assertEqual(card()['verified_tool_failures'],1)


class Maintenance(Evidence,unittest.TestCase):
    def test_disabled_by_default_no_work_runs(self):
        self.assertTrue(all(not j['enabled'] for j in self.hub.scheduler.jobs()));self.assertEqual(self.hub.scheduler.tick(),[])
        self.assertEqual(self.hub.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],0)
    def test_enabled_deterministic_check_has_persistent_history(self):
        self.hub.scheduler.configure('daily-freshness',True)
        run=self.hub.scheduler.tick();self.assertEqual(len(run),1);self.assertEqual(run[0]['status'],'SUCCEEDED')
        self.assertEqual(self.hub.scheduler.tick(),[])
        self.assertEqual(self.hub.db.execute('SELECT COUNT(*) FROM maintenance_runs').fetchone()[0],1)
    def test_ai_maintenance_only_queues_authenticated_runtime_request(self):
        self.hub.scheduler.configure('monthly-capability',True)
        run=self.hub.scheduler.tick()[0]['outcome'];self.assertFalse(run['model_invoked']);self.assertFalse(run['paid_api_called'])
        self.assertEqual(self.hub.task(run['task_id'])['phase'],'CREATED')
    def test_claim_prevents_overlap_across_connections(self):
        self.hub.scheduler.configure('daily-freshness',True)
        first=self.hub.scheduler.claim('daily-freshness','fixture-worker1');self.assertIsNotNone(first)
        other=Hub(self.root/'hub.sqlite',self.root);self.addCleanup(other.close)
        self.assertIsNone(other.scheduler.claim('daily-freshness','fixture-worker2'))
    def test_interrupted_lease_recovery_and_retry(self):
        self.hub.scheduler.configure('daily-freshness',True);claim=self.hub.scheduler.claim('daily-freshness','fixture-crashed-worker')
        clock=lambda:instant(now())+timedelta(minutes=6)
        service=Scheduler(self.hub,clock)
        self.assertEqual(service.recover(),[claim['run_id']]);job=next(j for j in service.jobs() if j['id']=='daily-freshness')
        self.assertEqual(job['failures'],1);self.assertTrue(job['enabled'])
        status=self.hub.db.execute('SELECT status FROM maintenance_runs').fetchone()[0];self.assertEqual(status,'INTERRUPTED')
    def test_failures_backoff_and_disable_after_exhaustion(self):
        self.hub.scheduler.configure('daily-freshness',True)
        with patch.object(self.hub.scheduler,'handle',side_effect=RuntimeError('password=DO_NOT_LOG')):
            for attempt in range(3):
                with self.hub.db:self.hub.db.execute("UPDATE maintenance_jobs SET due_at=? WHERE id='daily-freshness'",(now(),))
                result=self.hub.scheduler.tick();self.assertEqual(result[0]['status'],'FAILED')
        job=next(j for j in self.hub.scheduler.jobs() if j['id']=='daily-freshness');self.assertFalse(job['enabled'])
        self.assertNotIn('DO_NOT_LOG',str([dict(r) for r in self.hub.db.execute('SELECT * FROM maintenance_runs')]))
    def test_scheduler_rejects_arbitrary_principals_handlers_and_intervals(self):
        with self.assertRaises(PermissionError):self.hub.scheduler.configure('daily-health',True,principal='untrusted')
        with self.assertRaises(ValueError):self.hub.scheduler.configure('arbitrary-shell',True)
        with self.assertRaises(ValueError):self.hub.scheduler.configure('daily-health',True,cadence='interval',interval_seconds=1)
    def test_calendar_monthly_and_quarterly_due_dates(self):
        at=datetime(2026,1,31,tzinfo=timezone.utc)
        self.assertEqual(next_due(at,'monthly').day,28);self.assertEqual(next_due(at,'quarterly').month,4)


class Upgrades(Evidence,unittest.TestCase):
    def proposal(self,content='Reviewed candidate fixture'):
        return self.hub.improvements.propose('agent-development','SIMULATED research improvement',{'docs/candidate.md':content})
    def make_tested(self,proposal=None):
        # Fixed sandbox fixture runner is an actual subprocess, not real model QA.
        scripts=self.root/'scripts';scripts.mkdir(exist_ok=True)
        (scripts/'validate_all.py').write_text("print('OFFLINE fixture validation passed; no model invocation')\n")
        proposal=proposal or self.proposal();self.hub.improvements.stage(proposal['id']);return self.hub.improvements.test(proposal['id'])
    def reviewed(self,proposal=None):
        proposal=self.make_tested(proposal)
        task=self.qa_result({'change_proposal_ids':[proposal['id']],
            'change_manifest_hashes':{proposal['id']:proposal['manifest_hash']}},agent='agent-creator-researcher')
        return self.hub.improvements.qa(proposal['id'],task)
    def test_proposals_quarantined_and_isolated_stage(self):
        proposal=self.proposal();self.assertFalse((self.root/'docs/candidate.md').exists())
        stage=self.hub.improvements.stage(proposal['id']);self.assertFalse(stage['executed'])
        self.assertTrue((Path(stage['sandbox'])/'docs/candidate.md').is_file())
    def test_untrusted_paths_and_symlinks_rejected(self):
        for name in ['../escape.md','/tmp/escape.md','.git/config','data/secret.json','vendor/income/test.py']:
            with self.subTest(name=name),self.assertRaises(ValueError):self.hub.improvements.propose('management','Fixture',{name:'bad'})
        docs=self.root/'docs';docs.mkdir(exist_ok=True);(docs/'link.md').symlink_to(self.root/'deliverable.md')
        with self.assertRaises(ValueError):self.hub.improvements.propose('management','Fixture',{'docs/link.md':'bad'})
    def test_candidate_and_sandbox_tampering_rejected(self):
        proposal=self.proposal();stage=self.hub.improvements.stage(proposal['id'])
        (Path(stage['sandbox'])/'docs/candidate.md').write_text('tampered')
        with self.assertRaises(ValueError):self.hub.improvements.test(proposal['id'])
        candidate=self.hub.improvements.folder(proposal['id'])/'candidate/docs/candidate.md';candidate.write_text('tampered')
        with self.assertRaises(ValueError):self.hub.improvements.stage(proposal['id'])
    def test_activation_requires_independent_qa_and_authorization(self):
        proposal=self.make_tested()
        with self.assertRaises(ValueError):self.hub.improvements.activate(proposal['id'],'fixture://authorization')
        proposal=self.reviewed(proposal)
        with self.assertRaises(ValueError):self.hub.improvements.activate(proposal['id'],'')
        activated=self.hub.improvements.activate(proposal['id'],'fixture://scoped-user-authorization')
        self.assertEqual(activated['status'],'ACTIVE');self.assertTrue((self.root/'docs/candidate.md').exists())
        self.assertTrue(list((self.root/activated['backup_path']).glob('vault-*.sqlite')))
    def test_active_work_blocks_instruction_changes(self):
        proposal=self.reviewed();self.new()
        with self.assertRaisesRegex(ValueError,'active tasks'):self.hub.improvements.activate(proposal['id'],'fixture://authorization')
    def test_permission_expansion_requires_explicit_scope(self):
        proposal=self.hub.improvements.propose('agent-development','Fixture tools change',{
            '.claude/agents/trading-director.md':'---\nname: trading-director\ntools: Read, Bash, WebFetch\n---\nFixture'})
        proposal=self.reviewed(proposal)
        with self.assertRaises(PermissionError):self.hub.improvements.activate(proposal['id'],'fixture://authorization')
        self.hub.improvements.activate(proposal['id'],'fixture://explicit-tool-expansion',True)
    def test_rollback_restores_old_and_removes_new_files(self):
        docs=self.root/'docs';docs.mkdir(exist_ok=True);(docs/'candidate.md').write_text('Original fixture')
        proposal=self.reviewed();self.hub.improvements.activate(proposal['id'],'fixture://authorization')
        self.hub.improvements.rollback(proposal['id'],'fixture://rollback');self.assertEqual((docs/'candidate.md').read_text(),'Original fixture')
    def test_partial_activation_failure_restores_every_file(self):
        docs=self.root/'docs';docs.mkdir(exist_ok=True);(docs/'existing.md').write_text('Original fixture')
        proposal=self.hub.improvements.propose('agent-development','Fixture rollback',{'docs/existing.md':'Changed','docs/new.md':'New'})
        proposal=self.reviewed(proposal)
        import os
        real_replace=os.replace;calls=[]
        def failing(source,target):
            calls.append(str(target))
            if len(calls)==2:raise OSError('SIMULATED disk write failure')
            return real_replace(source,target)
        with patch('agent_hub.improvements.os.replace',side_effect=failing),self.assertRaises(OSError):self.hub.improvements.activate(proposal['id'],'fixture://authorization')
        self.assertEqual((docs/'existing.md').read_text(),'Original fixture');self.assertFalse((docs/'new.md').exists())
        self.assertEqual(self.hub.improvements.get(proposal['id'])['status'],'ROLLED_BACK')
    def test_skill_update_keeps_registry_valid_and_rollback_preserves_usage(self):
        from agent_hub.security import canonical
        source=self.root/'.claude/skills/master-workflow/SKILL.md'
        candidate='Reviewed new fixture skill instructions'
        records=json.loads((self.root/'registry/skills.json').read_text())
        records['skills'][0]['version']='fixture-v04'
        records['skills'][0]['fingerprint']=hashlib.sha256(canonical({'SKILL.md':hashlib.sha256(candidate.encode()).hexdigest()}).encode()).hexdigest()
        proposal=self.hub.improvements.propose('agent-development','Fixture skill refresh',{
            '.claude/skills/master-workflow/SKILL.md':candidate,'registry/skills.json':json.dumps(records)})
        proposal=self.reviewed(proposal);self.hub.improvements.activate(proposal['id'],'fixture://authorization')
        self.assertEqual(self.hub.skills.require(['master-workflow'],'management-director')[0]['version'],'fixture-v04')
        self.hub.improvements.rollback(proposal['id'],'fixture://rollback')
        self.assertEqual(source.read_text(),'Test contract')
        self.assertTrue(self.hub.skills.usage('master-workflow'))
        self.assertTrue(self.hub.memory.search('ROLLED_BACK','agent-creator-researcher'))

    def test_interrupted_activation_blocks_work_until_recovered(self):
        proposal=self.reviewed();activated=self.hub.improvements.activate(proposal['id'],'fixture://authorization')
        # Simulated process state after persisted intent, with candidate bytes on disk.
        with self.hub.db:self.hub.db.execute("UPDATE change_proposals SET status='ACTIVATING' WHERE id=?",(proposal['id'],))
        with self.assertRaisesRegex(ValueError,'Recover'):self.hub.create('New work','Fixture criterion')
        recovered=self.hub.improvements.rollback(proposal['id'],'fixture://incident',recovery=True)
        self.assertEqual(recovered['status'],'ROLLED_BACK');self.assertFalse((self.root/'docs/candidate.md').exists())
        self.hub.create('Resumed work','Fixture criterion')

    def test_later_user_edits_block_rollback(self):
        proposal=self.reviewed();self.hub.improvements.activate(proposal['id'],'fixture://authorization')
        (self.root/'docs/candidate.md').write_text('Later human fixture edit')
        with self.assertRaisesRegex(ValueError,'later edits'):self.hub.improvements.rollback(proposal['id'],'fixture://rollback')


class Dashboard(Evidence,unittest.TestCase):
    def server(self):
        server=make_server(self.root/'hub.sqlite',ROOT,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        return server
    def request(self,server,method,path,host=None):
        client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
        self.addCleanup(client.close);client.request(method,path,headers={'Host':host or '127.0.0.1:'+str(server.server_port)})
        response=client.getresponse();return response.status,response.read(),dict(response.getheaders())
    def test_real_http_counts_and_task_history(self):
        i=self.new();server=self.server();status,body,headers=self.request(server,'GET','/api/snapshot')
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['task_total'],1)
        status,body,_=self.request(server,'GET','/api/tasks/'+str(i));self.assertEqual(status,200);self.assertTrue(json.loads(body)['history'])
        self.assertIn("default-src 'self'",headers['Content-Security-Policy'])
    def test_gets_do_not_mutate_database_and_mutations_refused(self):
        self.new();before=file_hash(self.root/'hub.sqlite');server=self.server()
        self.assertEqual(self.request(server,'GET','/api/snapshot')[0],200)
        self.assertEqual(self.request(server,'POST','/api/snapshot')[0],405)
        self.assertEqual(file_hash(self.root/'hub.sqlite'),before)
        db=connect_readonly(self.root/'hub.sqlite');self.addCleanup(db.close)
        with self.assertRaises(sqlite3.OperationalError):db.execute('DELETE FROM tasks')
    def test_host_rebinding_and_file_traversal_refused(self):
        server=self.server();self.assertEqual(self.request(server,'GET','/api/snapshot','evil.example')[0],403)
        self.assertEqual(self.request(server,'GET','/../CLAUDE.md')[0],404)
        self.assertEqual(self.request(server,'GET','/api/tasks/999999')[0],404)
    def test_untrusted_content_is_text_not_html(self):
        self.hub.create('<script>alert(1)</script>','XSS fixture')
        script=(ROOT/'dashboard/app.js').read_text();self.assertNotIn('innerHTML',script)
        self.assertIn('textContent',script);self.assertEqual(self.request(self.server(),'GET','/app.js')[0],200)


class Migration(Evidence,unittest.TestCase):
    def test_v03_migration_preserves_ids_history_and_holds_work(self):
        i=self.new();record=self.put();before=len(self.hub.history(i))
        with self.hub.db:self.hub.db.execute('PRAGMA user_version=3')
        upgraded=Hub(self.root/'hub.sqlite',self.root);self.addCleanup(upgraded.close)
        self.assertEqual(upgraded.task(i)['phase'],'ASSIGNED');self.assertTrue(upgraded.task(i)['migration_hold'])
        self.assertEqual(len(upgraded.history(i)),before);self.assertEqual(upgraded.memory.get(record['id'],'master-agent')['payload'],record['payload'])
        self.assertTrue(Path(upgraded.migration['backup']).is_file())
        with self.assertRaises(ValueError):upgraded.dispatch(i)
        upgraded.replan_migrated(i,'Fixture v0.4 migration replan');self.assertEqual(upgraded.task(i)['phase'],'MANAGEMENT_REVIEW')
    def test_actual_released_v03_schema_migrates_without_new_columns(self):
        path=self.root/'actual-v03.sqlite';db=sqlite3.connect(path)
        db.executescript((ROOT/'tests/fixtures/v03-snapshot.sql').read_text())
        self.assertNotIn('date_collected',{r[1] for r in db.execute('PRAGMA table_info(memory_records)')})
        self.assertNotIn('idempotency_key',{r[1] for r in db.execute('PRAGMA table_info(tasks)')})
        history=db.execute('SELECT COUNT(*) FROM events').fetchone()[0];db.close()
        upgraded=Hub(path,self.root);self.addCleanup(upgraded.close)
        self.assertEqual(upgraded.task(1)['phase'],'ASSIGNED');self.assertTrue(upgraded.task(1)['migration_hold'])
        self.assertEqual(upgraded.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],history)
        record=upgraded.memory.get('00000000-0000-4000-8000-000000000004','master-agent')
        self.assertEqual(record['payload'],{'value':10});self.assertEqual(record['verification_status'],'UNVERIFIED')
        self.assertEqual(upgraded.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_memory_only_database_is_backed_up(self):
        self.put()
        with self.hub.db:self.hub.db.execute('PRAGMA user_version=3')
        upgraded=Hub(self.root/'hub.sqlite',self.root);self.addCleanup(upgraded.close)
        self.assertTrue(Path(upgraded.migration['backup']).is_file())


if __name__=='__main__':unittest.main()
