"""SIMULATED model responses; actual Hub/SQLite/workspace operations.
No model inference or independent model QA is claimed by these tests.
"""
import json
import os
import unittest
import uuid

import test_hub
from agent_hub.runtime import AgentRuntime
from agent_hub.model_adapters import InvocationResult


class FixtureAdapter:
    provider='test-fixture';model='SIMULATED';evidence_kind='SIMULATED'
    def __init__(self, defect=False, cancel=False):self.calls=[];self.defect=defect;self.cancel=cancel
    def probe(self):return {'available':True,'authenticated':True,'evidence_kind':'SIMULATED'}
    def invoke(self,request,**kwargs):
        self.calls.append(request)
        if self.cancel:
            from agent_hub.model_adapters import ExecutionCancelled
            raise ExecutionCancelled('Fixture interruption')
        payload=json.loads(request.user_prompt);task=payload['task'];stage=payload['stage_input']
        if request.stage=='MANAGEMENT':
            data={'analysis':'SIMULATED route','owner':task['requested_owner'] or 'income-director','selected_skills':['master-workflow'],
                'acceptance_criteria':[task['criteria']],'rationale':'SIMULATED smallest qualified team'}
        elif request.stage=='SPECIALIST':
            data={'summary':'SIMULATED deliverable','status':'READY','files':[{'path':'result.md','content':'fixed' if task['reworks'] else 'first'}],
                'limitations':['SIMULATED model; no live evidence']}
        else:
            rework=self.defect and task['reworks']==0
            def assessment():return {'verdict':'PASS','evidence':['fixture://explicitly-simulated-review'],'correction':'','reason':''}
            criteria=[dict(assessment(),criterion=c) for c in stage['required_criteria']]
            if rework:criteria[0].update(verdict='FAIL',correction='Replace first with fixed')
            data={'verdict':'REWORK' if rework else 'PASS','notes':'SIMULATED review',
                'evidence':{'criteria':criteria,'checks':{k:assessment() for k in stage['required_checks']},'tests':[],
                    'test_rationale':'Text fixture; executable checks do not apply'}}
        return InvocationResult(data,self.provider,self.model,request.id,'fixture://'+request.id,
            {'token_kind':'UNKNOWN'},0.01,'SIMULATED')


class Runtime(unittest.TestCase):
    setUp=test_hub.Workflow.setUp
    def runtime(self,**kwargs):return AgentRuntime(self.hub,adapter=FixtureAdapter(**kwargs))
    def test_actual_state_transitions_separate_simulated_contexts_and_usage(self):
        runtime=self.runtime();task=runtime.intake('Write a text note','Deliver a note')
        self.assertIsNone(task['requested_owner'])
        result=runtime.execute_task(task['id'])
        self.assertEqual(result['status'],'COMPLETED',result.get('error'))
        self.assertEqual([r.agent for r in runtime.adapter.calls],['management-director','income-director','qa-auditor'])
        self.assertEqual(len({r.id for r in runtime.adapter.calls}),3)
        self.assertEqual(len(result['invocations']),3)
        self.assertTrue(all(i['evidence_kind']=='SIMULATED' for i in result['invocations']))
        self.assertEqual(self.hub.db.execute('SELECT COUNT(*) FROM usage_events').fetchone()[0],3)
        self.assertTrue(json.loads(result['task']['result'])['artifacts'])
    def test_qa_rejection_correction_and_recheck(self):
        runtime=self.runtime(defect=True);task=runtime.intake('Note','Deliver note')
        result=runtime.execute_task(task['id'])
        self.assertEqual(result['status'],'COMPLETED',result.get('error'))
        self.assertEqual([r.stage for r in runtime.adapter.calls],['MANAGEMENT','SPECIALIST','QA','SPECIALIST','QA'])
        self.assertEqual(result['task']['reworks'],1)
        self.assertEqual(runtime.workspaces.read(result['id'],'result.md')['content'],'fixed')
    def test_unconfigured_never_invokes_or_completes(self):
        runtime=AgentRuntime(self.hub);task=runtime.intake('Task','Criteria')
        result=runtime.execute_task(task['id'])
        self.assertEqual(result['status'],'BLOCKED');self.assertEqual(result['error'],'EXECUTION UNAVAILABLE — MODEL RUNTIME NOT CONFIGURED')
        self.assertFalse(result['invocations']);self.assertEqual(result['task']['phase'],'CREATED')
    def test_explicit_owner_honored(self):
        runtime=self.runtime();task=runtime.intake('Note','Deliver note',agent='trading-director')
        result=runtime.execute_task(task['id'])
        self.assertEqual(result['status'],'COMPLETED',result.get('error'))
        self.assertEqual(result['task']['owner'],'trading-director')
    def test_duplicate_active_run_rejected(self):
        runtime=self.runtime();task=runtime.intake('Task','Criteria');run=str(uuid.uuid4())
        # A run stuck before any invocation still occupies the active-task constraint.
        from agent_hub.legacy import now
        self.hub.db.execute("INSERT INTO agent_runs(id,task_id,status,provider,stage,input_hash,config,created_at,updated_at) VALUES(?,?,'QUEUED','fixture','MANAGEMENT','x','{}',?,?)",(run,task['id'],now(),now()));self.hub.db.commit()
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):runtime.execute_task(task['id'])
    def test_interruption_retains_reservations_and_refuses_blind_replay(self):
        runtime=self.runtime(cancel=True);task=runtime.intake('Note','Deliver note')
        result=runtime.execute_task(task['id'])
        self.assertEqual(result['status'],'CANCELLED')
        self.assertEqual(self.hub.db.execute('SELECT COUNT(*) FROM usage_reservations').fetchone()[0],1)
        with self.assertRaises(ValueError):runtime.resume_execution(result['id'],'fixture recovery')
    def test_recovery_only_dead_worker_no_provider_replay(self):
        runtime=AgentRuntime(self.hub);task=runtime.intake('Task','Criteria');result=runtime.execute_task(task['id'])
        import socket
        self.hub.db.execute("UPDATE agent_runs SET status='RUNNING',worker_id='dead',worker_pid=2147483647,worker_host=? WHERE id=?",(socket.gethostname(),result['id']));self.hub.db.commit()
        recovered=runtime.recover()
        self.assertEqual(recovered['recovered'],[result['id']]);self.assertEqual(runtime.get(result['id'])['status'],'BLOCKED')
    def test_live_worker_cannot_be_recovered_or_claimed(self):
        runtime=AgentRuntime(self.hub);task=runtime.intake('Task','Criteria');result=runtime.execute_task(task['id'])
        import socket
        self.hub.db.execute("UPDATE agent_runs SET status='RUNNING',worker_id='other',worker_pid=?,worker_host=? WHERE id=?",(os.getpid(),socket.gethostname(),result['id']));self.hub.db.commit()
        self.assertEqual(runtime.recover()['recovered'],[])
        with self.assertRaises(ValueError):runtime.execute_task(task['id'],result['id'])

    def test_budget_pauses_before_model_and_resumes_same_intent(self):
        runtime=self.runtime();task=runtime.intake('Note','Deliver note')
        self.hub.budgets.configure('TASK',str(task['id']),'0')
        result=runtime.execute_task(task['id'])
        self.assertEqual(result['status'],'WAITING_FOR_APPROVAL',result.get('error'))
        self.assertFalse(runtime.adapter.calls)
        invocation=result['invocations'][0]
        self.assertEqual(invocation['status'],'WAITING_FOR_APPROVAL')
        self.hub.budgets.approve(invocation['approval_id'],'fixture explicit bounded test authorization',maximum_usd='1')
        runtime.config['approval_ids']={invocation['id']:invocation['approval_id']}
        resumed=runtime.resume_execution(result['id'],'fixture resume reference')
        self.assertEqual(len(runtime.adapter.calls),1) # worker needs its own authorization
        self.assertEqual(resumed['status'],'WAITING_FOR_APPROVAL')
        self.assertEqual(resumed['invocations'][0]['id'],invocation['id'])

    def test_qa_cannot_invent_test_execution(self):
        runtime=self.runtime();original=runtime.adapter.invoke
        def invoke(request,**kwargs):
            result=original(request,**kwargs)
            if request.stage=='QA':result.data['evidence']['tests']=[{'command':'invented test','result':'PASS','reference':'check://does-not-exist'}]
            return result
        runtime.adapter.invoke=invoke
        result=runtime.execute_task(runtime.intake('Note','Deliver note')['id'])
        self.assertEqual(result['status'],'BLOCKED')
        self.assertIn('actual workspace check',result['error'])
        self.assertNotEqual(result['task']['phase'],'COMPLETED')

    def test_web_cannot_pass_without_executed_checks(self):
        runtime=self.runtime();task=runtime.intake('Working website','Demonstrate functionality',domain='web-development')
        result=runtime.execute_task(task['id'])
        self.assertEqual(result['status'],'BLOCKED')
        self.assertIn('executed functional checks',result['error'])

    def test_failed_dispatch_rolls_back_handoff_and_usage(self):
        runtime=self.runtime();task=runtime.intake('Note','Deliver note')
        from unittest.mock import patch
        original=self.hub.event
        def event(task,kind,*args,**kwargs):
            if kind=='DEPARTMENT_HANDOFF':raise ValueError('fixture transaction fault')
            return original(task,kind,*args,**kwargs)
        with patch.object(self.hub,'event',side_effect=event):result=runtime.execute_task(task['id'])
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['task']['status'],'QUEUED')
        self.assertFalse([e for e in self.hub.history(task['id']) if e['kind']=='HANDOFF'])

    def test_identical_repeated_failures_escalate_instead_of_looping(self):
        runtime=self.runtime(defect=True);original=runtime.adapter.invoke
        def invoke(request,**kwargs):
            result=original(request,**kwargs)
            if request.stage=='QA':
                result.data['verdict']='REWORK'
                result.data['evidence']['criteria'][0].update(verdict='FAIL',correction='Same unresolved defect')
            return result
        runtime.adapter.invoke=invoke
        result=runtime.execute_task(runtime.intake('Note','Deliver note')['id'])
        self.assertEqual(result['status'],'BLOCKED',result.get('error'))
        self.assertEqual(result['task']['phase'],'ESCALATION')
        self.assertEqual(len([c for c in runtime.adapter.calls if c.stage=='QA']),2)
