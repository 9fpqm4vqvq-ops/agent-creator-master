"""v0.5 local integration checks. Model/QA/provider invocations are explicit fixtures.
Filesystem, SQLite, CLI, generated output and HTTP behavior are real local operations.
"""
import hashlib
import http.client
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from test_v03 import Support
from agent_hub.core import Hub,ROOT,QA_CHECKS
from agent_hub.departments import WEB_ROLES,SOCIAL_ROLES,EXTRA_QA,routing_suggestion
from agent_hub.roles import ROLES,DOMAINS
from agent_hub.legacy import now
from agent_hub.usage import instant
from agent_hub.security import canonical
from agent_hub.dashboard import make_server
from agent_hub.monitoring import snapshot
from agent_hub.skills import skill_fingerprint
from agent_hub.design import search


class Fixture(Support):
    def qa_evidence(self,task_id,verdict='PASS',notes='SIMULATED offline review'):
        data=Support.qa_evidence(self,task_id,verdict,notes)
        data['checks'].update({key:{'verdict':'PASS','evidence':['fixture://simulated-review']} for key in EXTRA_QA.get(self.hub.task(task_id)['department'],())})
        return data
    def project(self,kind='web'):
        return self.hub.projects.create('Fixture '+kind,'Synthetic brief for local behavior tests','Retain actual artifacts and disclose limitations',kind)
    def start_project(self,kind='web'):
        project=self.project(kind);i=project['task_id'];self.plan(i);self.dispatch(i)
        return self.hub.projects.get(project['id'])
    def complete(self,i,extra=None):
        result=dict(self.result(),**(extra or {}));self.hub.submit(i,result)
        self.review(i,'qa-auditor','PASS','SIMULATED independent QA fixture')
    def qa_packet(self,extra,agent='agent-creator-researcher'):
        i=self.new(agent=agent);self.dispatch(i);self.complete(i,extra);return i
    def reviewed_project(self):
        p=self.start_project();i=p['task_id']
        self.complete(i,{'approved_project_ids':[p['id']],'project_record_hashes':{p['id']:p['record_hash']}})
        return self.hub.projects.approve(p['id'],i)
    def content(self,reviewed=False):
        p=self.start_project('social')
        item=self.hub.social.create(p['id'],p['task_id'],'instagram','Synthetic launch caption',
            {'copy':'Original fixture copy. No actual claims.','sources':[]},scheduled_at=(instant(now())+timedelta(days=2)).isoformat())
        if not reviewed:return p,item
        self.hub.social.internal_review(item['id'],'SIMULATED internal content checks')
        self.complete(p['task_id'],{'approved_content_ids':[item['id']],'content_hashes':{item['id']:item['content_hash']}})
        return p,self.hub.social.approve(item['id'],p['task_id'])
    def connector(self,kind='write',permission=True,evidence_kind='SIMULATED'):
        operations=[{'name':'fixture_read','kind':'read'},{'name':'fixture_action','kind':kind}]
        self.hub.connectors.discover('fixture-runtime','Fixture provider','fixture-adapter',operations,'fixture://actual-local-discovery',evidence_kind=evidence_kind)
        def adapter(operation,args,context):
            return {'ok':True,'authenticated':True,'reference':'fixture://simulated-connected-read','granted_operations':['fixture_read','fixture_action'] if permission else ['fixture_read']}
        self.hub.connectors.test_read('fixture-runtime','Fixture provider','fixture_read',{},adapter)
    def action_task(self,project_id,department):
        parent=self.hub.projects.get(project_id)['task_id']
        # Approved parent is closed; a separately scoped project action task is not a new child of closed work.
        i=self.hub.create('SIMULATED external action','Inspect the exact reviewed subject and record a real receipt',domain=department,project_id=project_id)['id']
        self.plan(i);self.dispatch(i);return i
    def authorization(self,task_id,subject_hash,arguments,ceiling='1'):
        return self.hub.connectors.authorize(task_id,'fixture-runtime','Fixture provider','fixture_action',subject_hash,'fixture-account',arguments,'fixture://simulated-scoped-user-authorization',ceiling)['id']


class Departments(Fixture,unittest.TestCase):
    def test_exact_thirteen_roles_each_and_income_hierarchy_retained(self):
        self.assertEqual(len(WEB_ROLES),13);self.assertEqual(len(SOCIAL_ROLES),13);self.assertEqual(len(ROLES),70)
        self.assertEqual(ROLES['web-application-director'][1],'management-director')
        self.assertEqual(ROLES['social-media-director'][1],'management-director')
        self.assertEqual(ROLES['shorts-director'][1],'income-director');self.assertEqual(ROLES['iraq-ecommerce-director'][1],'income-director')
    def test_management_routing_does_not_send_general_social_to_income(self):
        routes=routing_suggestion('Instagram caption and a landing page for our campaign')['suggestions']
        self.assertEqual({r['department'] for r in routes},{'web-development','social-media'})
        self.assertEqual(routing_suggestion('Fix the website API')['suggestions'][0]['department'],'web-development')
        self.assertEqual(routing_suggestion('A vague request')['default_if_ambiguous'],'management')
    def test_new_departments_cannot_bypass_management(self):
        for domain in ['web-development','social-media']:
            i=self.hub.create('Fixture request','Fixture criterion',domain=domain)['id']
            with self.assertRaises(ValueError):self.hub.dispatch(i)
            self.assertEqual(self.hub.task(i)['owner'],DOMAINS[domain])
    def test_new_department_skill_selection_is_scoped(self):
        self.assertTrue(self.hub.skills.require(['master-workflow'],'web-frontend-engineer'))
        record=self.hub.skills.get('master-workflow');record['supported_departments']=['web-development']
        with self.hub.db:self.hub.db.execute('UPDATE skill_registry SET record=? WHERE id=?',(canonical(record),'master-workflow'))
        with self.assertRaises(ValueError):self.hub.skills.require(['master-workflow'],'social-copywriter-scriptwriter')
    def test_specialized_qa_checks_cannot_be_omitted(self):
        p=self.start_project();i=p['task_id'];self.hub.submit(i,self.result())
        with self.assertRaisesRegex(ValueError,'every required'):self.hub.review(i,'qa-auditor','PASS','SIMULATED omitted checks',Support.qa_evidence(self,i))
        self.review(i,'qa-auditor','PASS','SIMULATED complete specialized checks')
    def test_new_department_qa_rework_and_author_independence(self):
        p=self.start_project('social');i=p['task_id'];self.hub.submit(i,self.result())
        self.review(i,'qa-auditor','REWORK','SIMULATED correction');self.assertEqual(self.hub.task(i)['phase'],'ASSIGNED')
        self.dispatch(i);result=dict(self.result(),authors=['social-media-director','qa-auditor']);self.hub.submit(i,result)
        with self.assertRaises(ValueError):self.review(i,'qa-auditor','PASS','SIMULATED self-approval attempt')
    def test_capability_gap_and_health_work_for_new_departments(self):
        p=self.start_project();self.hub.request_capability(p['task_id'],'Actual mobile SDK unavailable','SIMULATED missing tool')
        self.assertEqual(self.hub.task(p['task_id'])['phase'],'ESCALATION')
        review=self.hub.health.audit('social-media');self.assertEqual(review['outcome'],'PARTIALLY_VERIFIED')
    def test_namespaces_preserve_department_boundaries(self):
        for namespace in ['web-development','web-design-research','application-architecture']:
            r=self.hub.memory.put(namespace,'research','Synthetic framework finding',{},'web-technology-researcher',category='framework_version')
            self.assertEqual(r['responsible_department'],'web-development')
            with self.assertRaises(PermissionError):self.hub.memory.get(r['id'],'social-media-director')
        for namespace in ['social-media','social-trends','brand-assets','content-calendar','social-analytics']:
            self.hub.memory.put(namespace,'finding','Synthetic social finding',{},'social-media-director')
        with self.assertRaises(PermissionError):self.hub.memory.put('trading','fact','Denied',{},'web-frontend-engineer')
        with self.assertRaises(PermissionError):self.hub.memory.put('connector-capabilities','fact','Denied',{},'social-copywriter-scriptwriter')
        self.hub.memory.put('connector-capabilities','finding','Synthetic integration',{},'social-platform-integration-specialist')
    def test_expired_freshness_is_flagged_on_recall_without_scan(self):
        r=self.hub.memory.put('social-trends','finding','Fixture trends',{},'social-trends-researcher',category='social_trend')
        with self.hub.db:self.hub.db.execute("UPDATE memory_records SET verification_status='FRESH',next_review_at='2020-01-01T00:00:00+00:00' WHERE id=?",(r['id'],))
        i=self.new(agent='social-trends-researcher');records=self.hub.recall(i,'trends')
        self.assertEqual(records[0]['effective_verification_status'],'REQUIRES_VERIFICATION')
        self.assertIn(r['id'],self.hub.history(i)[-1]['detail']['stale_record_ids'])


class Projects(Fixture,unittest.TestCase):
    def test_persistent_project_record_and_revision_conflict(self):
        p=self.project();self.hub.projects.update(p['id'],{'constraints':['Local only']},1)
        with self.assertRaises(ValueError):self.hub.projects.update(p['id'],{'risks':['stale edit']},1)
        other=Hub(self.root/'hub.sqlite',self.root);self.addCleanup(other.close)
        self.assertEqual(other.projects.get(p['id'])['record']['constraints'],['Local only'])
    def test_web_project_and_social_campaign_decomposition(self):
        for kind in ['web','social']:
            p=self.project(kind)
            with self.assertRaises(ValueError):self.hub.projects.decompose(p['id'],[{'name':'web','department':'web-development','request':'Build page','criteria':'Actual page'}])
            self.hub.management_review(p['task_id'],'SIMULATED Management scoping')
            scopes=[{'name':'page','department':'web-development','agent':'web-frontend-engineer','request':'Build a landing page','criteria':'Actual tested page'},
                    {'name':'launch','department':'social-media','request':'Draft launch content','criteria':'Original reviewed content','depends_on':['page']}]
            children=self.hub.projects.decompose(p['id'],scopes);again=self.hub.projects.decompose(p['id'],scopes)
            self.assertEqual([c['id'] for c in children],[c['id'] for c in again]);self.assertTrue(all(c['project_id']==p['id'] for c in children))
            self.assertEqual(json.loads(children[1]['dependencies']),[children[0]['id']])
            self.plan(children[1]['id']);self.assertEqual(json.loads(self.hub.task(children[1]['id'])['dependencies']),[children[0]['id']])
            with self.assertRaises(ValueError):self.hub.dispatch(children[1]['id'])
    def test_invalid_decomposition_rolls_back_all_children(self):
        p=self.project();self.hub.management_review(p['task_id'],'SIMULATED scoping')
        with self.assertRaises(ValueError):self.hub.projects.decompose(p['id'],[{'name':'a','department':'web-development','request':'A','criteria':'A','depends_on':['missing']}])
        self.assertEqual(self.hub.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],1)
    def test_cross_department_handoff_acknowledgement_restricts_actor(self):
        p=self.project();self.hub.management_review(p['task_id'],'SIMULATED scoping')
        child=self.hub.projects.decompose(p['id'],[{'name':'launch','department':'social-media','request':'Draft launch','criteria':'Actual content'}])[0]
        with self.assertRaises(PermissionError):self.hub.projects.accept_handoff(child['id'],'trading-director','Unassigned actor')
        self.hub.projects.accept_handoff(child['id'],'social-media-director','SIMULATED receipt')
        self.assertEqual(snapshot(self.hub.db)['expansion']['pending_handoffs'],[])
    def test_static_site_and_api_are_real_scoped_local_outputs(self):
        p=self.start_project();result=self.hub.projects.scaffold(p['id'],p['task_id'])
        self.assertFalse(result['deployed']);self.assertIn('Skip to content',(self.root/result['artifacts'][0]).read_text())
        api=self.hub.projects.scaffold(p['id'],p['task_id'],'python-api')
        compile((self.root/api['artifacts'][0]).read_text(),api['artifacts'][0],'exec')
        self.assertIn('sqlite3',(self.root/api['artifacts'][0]).read_text())
        with self.assertRaises(ValueError):self.hub.projects.scaffold(p['id'],p['task_id'],'ios-build')
    def test_unstarted_or_wrong_department_cannot_scaffold(self):
        p=self.project()
        with self.assertRaises(ValueError):self.hub.projects.scaffold(p['id'],p['task_id'])
    def test_generated_api_runs_and_persists_validated_data(self):
        import os
        p=self.start_project();output=self.hub.projects.scaffold(p['id'],p['task_id'],'python-api');script=self.root/output['artifacts'][0]
        process=subprocess.Popen([sys.executable,str(script)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,WEB_PROJECT_PORT='0'))
        self.addCleanup(lambda:process.wait(timeout=5));self.addCleanup(process.terminate)
        line=process.stdout.readline().strip();port=int(line.rsplit(':',1)[1])
        conn=http.client.HTTPConnection('127.0.0.1',port,timeout=5);self.addCleanup(conn.close)
        conn.request('POST','/api/items',body=json.dumps({'title':"Fixture ' item"}),headers={'Content-Type':'application/json'})
        response=conn.getresponse();self.assertEqual(response.status,201);response.read()
        conn.request('GET','/api/items');response=conn.getresponse();self.assertEqual(json.loads(response.read())[0]['title'],"Fixture ' item")
        conn.request('POST','/api/items',body=json.dumps({'title':''}),headers={'Content-Type':'application/json'})
        response=conn.getresponse();response.read();self.assertEqual(response.status,400)
        process.terminate();process.wait(timeout=5);process.stdout.close();process.stderr.close()

    def test_project_approval_is_exact_and_update_invalidates_link(self):
        p=self.reviewed_project();self.assertTrue(p['qa_task_id'])
        self.hub.projects.update(p['id'],{'risks':['Changed after QA']},p['revision'])
        self.assertIsNone(self.hub.projects.get(p['id'])['qa_task_id'])
    def test_project_qa_cannot_be_borrowed_from_another_department_or_project(self):
        p=self.start_project()
        other=self.qa_packet({'approved_project_ids':[p['id']],'project_record_hashes':{p['id']:p['record_hash']}},agent='agent-creator-researcher')
        with self.assertRaises(PermissionError):self.hub.projects.approve(p['id'],other)

    def test_project_budget_aggregates_cross_department_child_usage(self):
        p=self.project();self.hub.management_review(p['task_id'],'SIMULATED scope')
        child=self.hub.projects.decompose(p['id'],[{'name':'social','department':'social-media','request':'Draft','criteria':'Original'}])[0]
        self.hub.budgets.configure('PROJECT',p['id'],'1')
        self.hub.usage.record({'task_id':child['id'],'agent':'social-media-director','provider':'SIMULATED','model':'fixture','invocation_id':'child-use','source':'fixture://usage','actual_cost':'.6'})
        budget=next(b for b in self.hub.budgets.evaluate(p['task_id'],'web-application-director','.5')['budgets'] if b['scope']=='PROJECT')
        self.assertEqual(budget['status'],'EXCEEDED');self.assertEqual(self.hub.usage.summary(project_id=p['id'])['actual_cost_usd'],'0.6')
        self.assertEqual(snapshot(self.hub.db)['budgets'][0]['scope'],'PROJECT')
    def test_verified_technology_claim_requires_dated_sources(self):
        p=self.project()
        with self.assertRaises(ValueError):self.hub.projects.update(p['id'],{'technology_decisions':[{'selection':'Newest framework','classification':'VERIFIED','sources':[]}]},1)


class Social(Fixture,unittest.TestCase):
    def test_draft_calendar_is_not_a_live_schedule(self):
        p,item=self.content();self.assertEqual(item['status'],'DRAFT');self.assertEqual(item['timing_basis'],'HYPOTHESIS')
        result=self.hub.social.export(p['id']);self.assertEqual(result['live_scheduled_posts_created'],0)
        self.assertIn('Asia/Baghdad',(self.root/result['artifacts'][0]).read_text())
    def test_calendar_validates_timezone_and_actual_analytics_basis(self):
        p=self.start_project('social')
        for change in [{'timezone':'Invalid/Zone'},{'timing_basis':'ACCOUNT_ANALYTICS'}]:
            with self.assertRaises(ValueError):self.hub.social.create(p['id'],p['task_id'],'instagram','Title',{'copy':'Draft'},**change)
    def test_internal_review_does_not_grant_independent_approval(self):
        p,item=self.content();reviewed=self.hub.social.internal_review(item['id'],'SIMULATED internal checks')
        self.assertEqual(reviewed['status'],'REVIEWED')
        with self.assertRaises(ValueError):self.hub.social.approve(item['id'],p['task_id'])
    def test_exact_independent_qa_then_content_edit_invalidates_approval(self):
        p,item=self.content(True);self.assertEqual(item['status'],'APPROVED')
        updated=self.hub.social.update(item['id'],{'copy':'Edited fixture copy'},item['revision'])
        self.assertEqual(updated['status'],'DRAFT');self.assertIsNone(updated['qa_task_id'])
    def test_content_qa_cannot_be_borrowed_from_another_department_or_campaign(self):
        p,item=self.content();self.hub.social.internal_review(item['id'],'SIMULATED internal checks')
        other=self.qa_packet({'approved_content_ids':[item['id']],'content_hashes':{item['id']:item['content_hash']}},agent='agent-creator-researcher')
        with self.assertRaises(PermissionError):self.hub.social.approve(item['id'],other)

    def test_graphic_exists_and_escapes_untrusted_text(self):
        p,item=self.content();self.hub.social.update(item['id'],{'copy':'<script>alert(1)</script>'},item['revision'])
        result=self.hub.social.graphic(item['id']);source=(self.root/result['artifacts'][0]).read_text();ET.fromstring(source)
        self.assertNotIn('<script>',source);self.assertIn('&lt;script&gt;',source)
    def test_supplied_analytics_keeps_missing_values_unknown(self):
        p=self.project('social');report=self.hub.social.analytics(p['id'],'instagram',[{'impressions':100,'likes':10}],'fixture://supplied-csv',now())
        self.assertIsNone(report['engagement_rate_per_impression']);self.assertIsNone(report['totals_of_available_values']['reach'])
        self.assertEqual(report['classification'],'SUPPLIED_DATA')
        with self.assertRaises(ValueError):self.hub.social.analytics(p['id'],'instagram',[{}],'fixture://source',now(),classification='CONNECTED')
    def test_analytics_known_rate_and_invalid_metrics(self):
        p=self.project('social');row={'impressions':100,'likes':10,'comments':2,'shares':3,'saves':5}
        report=self.hub.social.analytics(p['id'],'instagram',[row],'fixture://supplied',now());self.assertEqual(report['engagement_rate_per_impression'],.2)
        for value in [-1,True,1.5]:
            with self.assertRaises(ValueError):self.hub.social.analytics(p['id'],'instagram',[{'likes':value}],'fixture://source',now())
    def test_simulated_publication_does_not_claim_live_success(self):
        p,item=self.content(True);self.connector('publish');task=self.action_task(p['id'],'social-media')
        args=self.hub.social.publication_payload(item['id']);approval=self.authorization(task,item['content_hash'],args)
        result=self.hub.social.publish(item['id'],approval,'fixture-account',args,'0',lambda *a:{'ok':True,'verified':True,'reference':'fixture://simulated-post'})
        self.assertFalse(result['content_state_changed']);self.assertEqual(self.hub.social.get(item['id'])['status'],'APPROVED')
    def test_publication_payload_cannot_substitute_unreviewed_copy(self):
        p,item=self.content(True);self.connector('publish');task=self.action_task(p['id'],'social-media')
        args=self.hub.social.publication_payload(item['id']);args['copy']='Unreviewed substitute';approval=self.authorization(task,item['content_hash'],args)
        with self.assertRaises(PermissionError):self.hub.social.publish(item['id'],approval,'fixture-account',args,'0',lambda *a:{'ok':True,'verified':True,'reference':'fixture://bad'})


class Connectors(Fixture,unittest.TestCase):
    def test_named_candidate_and_configuration_do_not_establish_connection(self):
        self.assertEqual(self.hub.connectors.candidates()[0]['status'],'NOT_DISCOVERED')
        self.hub.connectors.discover('runtime','Figma','MCP',[{'name':'read','kind':'read'}],'fixture://tool-list')
        self.assertEqual(self.hub.connectors.get('runtime','Figma')['status'],'AVAILABLE_NOT_CONNECTED')
        self.assertFalse(self.hub.connectors.plan('runtime','Figma','read')['available'])
    def test_read_test_requires_actual_success_and_authentication(self):
        self.hub.connectors.discover('runtime','Figma','MCP',[{'name':'read','kind':'read'}],'fixture://tool-list',evidence_kind='SIMULATED')
        with self.assertRaises(ValueError):self.hub.connectors.test_read('runtime','Figma','read',{},lambda *a:{'ok':True,'authenticated':False})
        self.assertEqual(self.hub.connectors.get('runtime','Figma')['status'],'FAILED')
        self.hub.connectors.test_read('runtime','Figma','read',{},lambda *a:{'ok':True,'authenticated':True,'reference':'fixture://read'})
        self.assertEqual(self.hub.connectors.get('runtime','Figma')['status'],'READ_ONLY')
    def test_read_permission_does_not_grant_write_or_cross_runtime_access(self):
        self.connector(permission=False)
        self.assertFalse(self.hub.connectors.plan('fixture-runtime','Fixture provider','fixture_action')['available'])
        self.assertFalse(self.hub.connectors.plan('different-runtime','Fixture provider','fixture_read')['available'])
    def test_unavailable_connector_produces_useful_local_fallback(self):
        result=self.hub.connectors.plan('missing-runtime','Higgsfield','generate_video')
        self.assertFalse(result['available']);self.assertIn('local artifact',result['fallback'])
    def test_runtime_refresh_invalidates_removed_tools(self):
        self.connector();self.hub.connectors.discover_tools('fixture-runtime',[],'fixture://tools-removed',evidence_kind='SIMULATED')
        self.assertEqual(self.hub.connectors.get('fixture-runtime','Fixture provider')['status'],'NOT_DISCOVERED')
        self.assertFalse(self.hub.connectors.plan('fixture-runtime','Fixture provider','fixture_read')['available'])

    def test_reconciliation_requires_read_proof_and_preserves_simulation(self):
        self.connector();i=self.new();self.dispatch(i);approval=self.authorization(i,'a'*64,{})
        with self.assertRaises(ValueError):self.hub.connectors.execute(approval,'a'*64,'fixture-account',{},'0',lambda *a:{'ok':False})
        action=self.hub.db.execute('SELECT id FROM external_actions').fetchone()[0]
        result=self.hub.connectors.reconcile(action,'fixture_read',{},lambda *a:{'authenticated':True,'verified':True,'subject_hash':'a'*64,'state':'NOT_APPLIED','reference':'fixture://simulated-read-proof'})
        self.assertEqual(result['status'],'FAILED_NOT_APPLIED');self.assertEqual(result['evidence_kind'],'SIMULATED')

    def test_write_connection_test_is_prohibited(self):
        self.connector()
        with self.assertRaises(PermissionError):self.hub.connectors.test_read('fixture-runtime','Fixture provider','fixture_action',{},lambda *a:{})
    def test_action_approval_binds_destination_payload_cost_and_replay(self):
        self.connector();i=self.new();self.dispatch(i);args={'file':'fixture.svg'};subject='a'*64;approval=self.authorization(i,subject,args)
        for destination,arguments,cost in [('other-account',args,'0'),('fixture-account',{'file':'changed.svg'},'0'),('fixture-account',args,'2')]:
            with self.assertRaises(PermissionError):self.hub.connectors.execute(approval,subject,destination,arguments,cost,lambda *a:{})
        result=self.hub.connectors.execute(approval,subject,'fixture-account',args,'0',lambda *a:{'ok':True,'verified':True,'reference':'fixture://write'})
        self.assertEqual(result['status'],'VERIFIED')
        with self.assertRaises(PermissionError):self.hub.connectors.execute(approval,subject,'fixture-account',args,'0',lambda *a:{})
    def test_ambiguous_failure_is_persistent_and_not_retried(self):
        self.connector();i=self.new();self.dispatch(i);approval=self.authorization(i,'a'*64,{'file':'fixture.svg'})
        def fail(*args):raise OSError('password=DO_NOT_LOG')
        with self.assertRaises(OSError):self.hub.connectors.execute(approval,'a'*64,'fixture-account',{'file':'fixture.svg'},'0',fail)
        row=dict(self.hub.db.execute('SELECT * FROM external_actions').fetchone())
        self.assertEqual(row['status'],'UNKNOWN_NEEDS_RECONCILIATION');self.assertNotIn('DO_NOT_LOG',row['error'])
        with self.assertRaises(PermissionError):self.hub.connectors.execute(approval,'a'*64,'fixture-account',{'file':'fixture.svg'},'0',fail)
    def test_no_adapter_no_secret_payload_and_disabled_connector(self):
        self.connector();i=self.new();self.dispatch(i)
        with self.assertRaises(ValueError):self.authorization(i,'a'*64,{'api_key':'not-recordable'})
        approval=self.authorization(i,'a'*64,{})
        with self.assertRaises(ValueError):self.hub.connectors.execute(approval,'a'*64,'fixture-account',{},'0',None)
        self.hub.connectors.disable('fixture-runtime','Fixture provider')
        self.assertFalse(self.hub.connectors.plan('fixture-runtime','Fixture provider','fixture_action')['available'])
    def test_deployment_requires_independent_project_qa(self):
        p=self.start_project();self.connector('deploy');i=self.action_task(p['id'],'web-development')
        args=self.hub.projects.deployment_payload(p['id']);approval=self.authorization(i,p['record_hash'],args)
        with self.assertRaises(ValueError):self.hub.projects.deploy(p['id'],approval,args,'fixture-account','0',lambda *a:{})
    def test_reviewed_deployment_uses_actual_adapter_receipt(self):
        p=self.reviewed_project();self.connector('deploy');i=self.action_task(p['id'],'web-development')
        args=self.hub.projects.deployment_payload(p['id']);approval=self.authorization(i,p['record_hash'],args)
        result=self.hub.projects.deploy(p['id'],approval,args,'fixture-account','0',lambda *a:{'ok':True,'verified':True,'reference':'fixture://simulated-deployment'})
        self.assertEqual(result['evidence_kind'],'SIMULATED')


class SupplyChain(unittest.TestCase):
    def test_all_archives_have_individual_source_dispositions_and_immutable_bytes(self):
        audits=json.loads((ROOT/'registry/supplementary-skill-audit.json').read_text());self.assertEqual(len(audits),12)
        self.assertEqual(sum(len(a['skills']) for a in audits),417)
        for archive in audits:
            for skill in archive['skills']:
                self.assertIn(skill['disposition'],{'SCOPED_WRAPPER','DUPLICATE_REFERENCE','REFERENCE_ONLY_OUT_OF_SCOPE','TEST_FIXTURE_NOT_INSTALLABLE'})
                self.assertEqual(hashlib.sha256((ROOT/skill['preserved_path']).read_bytes()).hexdigest(),skill['sha256'])
    def test_new_wrappers_have_scopes_provenance_and_no_automatic_hooks(self):
        records=json.loads((ROOT/'registry/skills.json').read_text())['skills'];self.assertEqual(len(records),176)
        for record in records:
            if not (record['id'].startswith('v05-') or record['id'] in {'web-project-workflow','social-campaign-workflow','connector-capability-check'}):continue
            self.assertEqual(record['fingerprint'],skill_fingerprint(ROOT,record['path']))
            self.assertLess(len(record['supported_departments']),len(DOMAINS))
            folder=(ROOT/record['path']).parent
            self.assertFalse(any(p.name in {'hooks.json','.mcp.json','settings.json'} for p in folder.rglob('*')))
    def test_all_requested_profiles_exist_and_have_specific_outputs(self):
        for name,metadata in dict(WEB_ROLES,**SOCIAL_ROLES).items():
            text=(ROOT/'.claude/agents'/(name+'.md')).read_text();self.assertIn(metadata[0],text);self.assertIn('Outputs:',text)
    def test_ui_data_search_uses_real_supplied_csv_without_assumed_stack(self):
        result=search(ROOT,'keyboard focus',limit=2)
        self.assertTrue(result['results']);self.assertIsNone(result['stack']);self.assertEqual(result['classification'],'ARCHIVED_GUIDANCE_UNVERIFIED_CURRENTNESS')
        self.assertIn('Focus',str(result['results']))
        with self.assertRaises(ValueError):search(ROOT,'query',stack='../escape')
    def test_upstream_substitutions_are_pinned_and_honestly_labeled(self):
        for name in ['HYPERFRAMES','HEADROOM']:
            receipt=json.loads((ROOT/'docs'/('V05-'+name+'-SOURCE.json')).read_text())
            self.assertFalse(receipt['uploaded_archive_examined']);self.assertEqual(len(receipt['commit']),40)


class Migration(Fixture,unittest.TestCase):
    def test_baseline_diff_requires_exact_review_and_capability_authorization(self):
        seed=json.loads((self.root/'registry/skills.json').read_text())['skills'][0]
        old=dict(seed,supported_departments=['management'],version='old-fixture')
        with self.hub.db:self.hub.db.execute('UPDATE skill_registry SET record=? WHERE id=?',(canonical(old),'master-workflow'))
        diff=self.hub.skills.baseline_diff();review={'reviewer':'qa-auditor','author':'agent-creator-researcher',
            'review_reference':'fixture://SIMULATED-baseline-review','authorization_reference':'fixture://SIMULATED-scope',
            'tests':[{'result':'PASS','reference':'fixture://local-tests'}],'expected_diff_hash':diff['diff_hash']}
        with self.assertRaises(PermissionError):self.hub.skills.reconcile_baseline(**review)
        result=self.hub.skills.reconcile_baseline(**review,allow_capability_expansion=True)
        self.assertEqual(result['updated'],['master-workflow']);self.assertTrue(self.hub.skills.require(['master-workflow'],'web-application-director'))
        self.assertEqual(self.hub.db.execute('SELECT COUNT(*) FROM skill_baseline_revisions').fetchone()[0],1)
        with self.assertRaises(ValueError):self.hub.skills.reconcile_baseline(**review,allow_capability_expansion=True)

    def test_baseline_reconcile_blocks_active_nonmigration_work(self):
        self.new()
        diff=self.hub.skills.baseline_diff()
        with self.assertRaises(ValueError):self.hub.skills.reconcile_baseline('qa-auditor','agent-creator-researcher','fixture://SIMULATED-review','fixture://SIMULATED-auth',[{'result':'PASS','reference':'fixture://tests'}],diff['diff_hash'])

    def test_actual_v04_schema_preserves_phase_history_memory_and_reservations(self):
        path=self.root/'prior-v04.sqlite';db=sqlite3.connect(path);db.executescript((ROOT/'tests/fixtures/v04-snapshot.sql').read_text())
        events=db.execute('SELECT COUNT(*) FROM events').fetchone()[0];holds=db.execute('SELECT COUNT(*) FROM usage_reservations').fetchone()[0];db.close()
        upgraded=Hub(path,self.root);self.addCleanup(upgraded.close)
        self.assertEqual(upgraded.task(1)['phase'],'IN_PROGRESS');self.assertTrue(upgraded.task(1)['migration_hold'])
        self.assertEqual(upgraded.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],events)
        self.assertEqual(upgraded.db.execute('SELECT COUNT(*) FROM usage_reservations').fetchone()[0],holds)
        self.assertEqual(upgraded.memory.get('00000000-0000-4000-8000-000000000005','master-agent')['payload'],{'value':'synthetic'})
        self.assertTrue(Path(upgraded.migration['backup']).exists());self.assertEqual(upgraded.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        with self.assertRaises(ValueError):upgraded.start(1,'fixture://old-invocation')
        upgraded.replan_migrated(1,'Synthetic v0.5 review');self.assertEqual(upgraded.task(1)['phase'],'MANAGEMENT_REVIEW')


class Reporting(Fixture,unittest.TestCase):
    def test_dashboard_contains_project_campaign_connectors_and_handoffs(self):
        web=self.project();social=self.project('social');state=snapshot(self.hub.db)
        self.assertEqual(len(state['departments']),9);self.assertEqual(state['expansion']['web_projects'][0]['id'],web['id'])
        self.assertEqual(state['expansion']['social_campaigns'][0]['id'],social['id']);self.assertTrue(state['expansion']['connector_candidates'])
        self.assertIsNone(state['expansion']['web_projects'][0]['usage']['actual_cost_usd'])
    def test_real_http_new_sections_are_read_only(self):
        self.project();server=make_server(self.root/'hub.sqlite',ROOT,0)
        threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port);self.addCleanup(conn.close);conn.request('GET','/api/snapshot')
        response=conn.getresponse();body=json.loads(response.read());self.assertEqual(response.status,200);self.assertEqual(len(body['expansion']['web_projects']),1)
        conn.request('POST','/api/snapshot');response=conn.getresponse();response.read();self.assertEqual(response.status,405)
    def test_cli_can_route_and_create_local_project(self):
        result=subprocess.run([sys.executable,'-m','agent_hub','--db',str(self.root/'cli.sqlite'),'route','suggest','--data',str(self.root/'query.json')],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,1) # missing input is refused, never silently fabricated
        data=self.root/'query.json';data.write_text(json.dumps({'request':'Instagram caption'}))
        result=subprocess.run([sys.executable,'-m','agent_hub','--db',str(self.root/'cli.sqlite'),'route','suggest','--data',str(data)],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['suggestions'][0]['department'],'social-media')


if __name__=='__main__':unittest.main()
