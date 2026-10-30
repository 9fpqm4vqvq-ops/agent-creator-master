"""Guarded real filesystem/process tests; sandbox simulation is labeled explicitly.

No third-party/untrusted script is executed by these deterministic unit tests.
Actual Docker isolation is a separate configured integration acceptance check.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_hub.workspaces import WorkspaceManager, ToolGateway, WorkspaceError, WorkspaceBlocked, WORKSPACE_SCHEMA


class Workspaces(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=sqlite3.connect(self.root/'unit.sqlite');self.db.row_factory=sqlite3.Row;self.addCleanup(self.db.close)
        self.db.executescript(WORKSPACE_SCHEMA)
        self.hub=SimpleNamespace(root=self.root,db=self.db,task=lambda i:{'id':i,'owner':'web-frontend-engineer'})
        self.manager=WorkspaceManager(self.hub,{'timeout_seconds':1,'max_output_bytes':1024})
        self.run=str(uuid.uuid4());self.invocation=str(uuid.uuid4())

    def test_scoped_files_hash_edits_and_immutable_artifact_versions(self):
        first=self.manager.write(self.run,'src/page.html','<h1>Original</h1>')
        with self.assertRaises(WorkspaceError):self.manager.write(self.run,'src/page.html','<h1>Edited</h1>')
        collected=self.manager.collect(self.run,['src/page.html'])
        self.assertEqual((self.root/collected['artifacts'][0]).read_text(),'<h1>Original</h1>')
        self.manager.write(self.run,'src/page.html','<h1>Edited</h1>',first['sha256'])
        later=self.manager.collect(self.run,['src/page.html'])
        self.assertNotEqual(collected['artifacts'],later['artifacts'])
        self.assertEqual((self.root/collected['artifacts'][0]).read_text(),'<h1>Original</h1>')

    def test_traversal_symlinks_hardlinks_and_private_files_are_refused(self):
        for name in ['../outside.txt','/tmp/outside.txt','a/../../outside.txt','a\\outside.txt','.env','private/auth.json','state.sqlite','.codex/auth.json']:
            with self.subTest(name=name),self.assertRaises(WorkspaceError):self.manager.write(self.run,name,'Synthetic value')
        folder=self.manager.create(self.run);outside=self.root/'outside.txt';outside.write_text('Original outside file')
        (folder/'linked.txt').symlink_to(outside)
        with self.assertRaises(WorkspaceError):self.manager.read(self.run,'linked.txt')
        (folder/'linked.txt').unlink();os.link(outside,folder/'hard.txt')
        with self.assertRaises(WorkspaceError):self.manager.write(self.run,'hard.txt','Modified',expected_hash='irrelevant')
        self.assertEqual(outside.read_text(),'Original outside file')

    def test_secret_and_private_reasoning_are_not_stored(self):
        for content in ['password=SYNTHETIC_VALUE','<think>private test fixture</think>',json.dumps({'chain_of_thought':'private fixture'})]:
            with self.assertRaises(WorkspaceError):self.manager.write(self.run,'report.json' if content.startswith('{') else 'report.txt',content)
        self.assertEqual(self.manager.list_files(self.run)['files'],{})

    def test_bounds_fail_without_replacing_valid_files(self):
        manager=WorkspaceManager(self.hub,{'max_file_bytes':10,'max_total_bytes':12,'max_files':2})
        first=manager.write(self.run,'a.txt','12345678')
        with self.assertRaises(WorkspaceError):manager.write(self.run,'a.txt','too long to store',first['sha256'])
        with self.assertRaises(WorkspaceError):manager.write(self.run,'b.txt','12345678')
        self.assertEqual(manager.read(self.run,'a.txt')['content'],'12345678')

    def test_collected_private_database_is_not_exported(self):
        self.manager.write(self.run,'readme.md','Local fixture')
        folder=self.manager.create(self.run);(folder/'runtime.sqlite').write_bytes(b'not an exported database')
        self.assertEqual(list(self.manager.snapshot(self.run)['files']),['readme.md'])
        with self.assertRaises(WorkspaceError):self.manager.collect(self.run,['runtime.sqlite'])

    def test_syntax_checks_do_not_execute_generated_python(self):
        self.manager.write(self.run,'main.py',"raise RuntimeError('must not execute during parsing')\n")
        self.manager.write(self.run,'bad.py','if :\n')
        results=self.manager.syntax_check(self.run)
        self.assertEqual(results['classification'],'SYNTAX_ONLY_NOT_FUNCTIONAL_TESTING')
        self.assertEqual(results['status'],'FAIL')
        verdicts={row['path']:row['result'] for row in results['results']}
        self.assertEqual(verdicts,{'bad.py':'FAIL','main.py':'PASS'})

    def test_no_actual_isolation_probe_means_no_code_execution(self):
        self.manager.write(self.run,'main.py','print(1)\n')
        approval=self.manager.approve_command(self.run,['python','main.py'],'fixture://authorized-local-test')
        with self.assertRaises(WorkspaceBlocked):self.manager.run_check(self.run,approval['command_key'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tool_processes').fetchone()[0],0)

    def test_installed_binary_is_not_reported_as_working_isolation(self):
        manager=WorkspaceManager(self.hub,{'isolation':'docker','docker_image':'python:fixture-only'})
        failed=SimpleNamespace(returncode=125,stderr='',stdout='SIMULATED daemon/image failure')
        with patch('agent_hub.workspaces.subprocess.run',return_value=failed):result=manager.probe_isolation()
        self.assertFalse(result['available']);self.assertIn('failure',result['reason'])

    def test_command_binding_rejects_changed_inputs_and_automatic_installs(self):
        first=self.manager.write(self.run,'main.py','print(1)\n')
        approval=self.manager.approve_command(self.run,['python','main.py'],'fixture://actual-scoped-test')
        self.manager.write(self.run,'main.py','print(2)\n',first['sha256'])
        with self.assertRaises(WorkspaceBlocked):self.manager.run_check(self.run,approval['command_key'])
        with self.assertRaises(WorkspaceBlocked):self.manager.approve_command(self.run,['npm','install'],'fixture://no-network')
        with self.assertRaises(WorkspaceBlocked):self.manager.approve_command(self.run,['npm','install'],'fixture://explicit-install',dependency_install=True)
        with self.assertRaises(WorkspaceBlocked):self.manager.approve_command(self.run,['bash','-c','true'],'fixture://not-a-shell-authorization')

    def _trusted_process_fixture(self,code,cancel_check=None):
        # Isolation is deliberately mocked here. Only this reviewed fixed test script executes.
        self.manager.write(self.run,'context.txt','SIMULATED process fixture')
        argv=[sys.executable,'-c',code]
        approval=self.manager.approve_command(self.run,argv,'fixture://SIMULATED-reviewed-process')
        with patch.object(self.manager,'probe_isolation',return_value={'available':True,'backend':'bwrap'}),patch.object(self.manager,'_bwrap_argv',return_value=argv):
            return self.manager.run_check(self.run,approval['command_key'],self.invocation,cancel_check)

    def test_real_trusted_fixture_process_records_output_and_redacts_secrets(self):
        result=self._trusted_process_fixture("print('pass'+'word='+'SYNTHETIC_SECRET')")
        self.assertEqual(result['status'],'PASS');self.assertNotIn('SYNTHETIC_SECRET',result['output'])
        row=self.db.execute('SELECT * FROM workspace_checks').fetchone()
        self.assertEqual(row['status'],'PASS');self.assertNotIn('SYNTHETIC_SECRET',row['output'])
        self.assertEqual(self.db.execute('SELECT status FROM tool_processes').fetchone()[0],'COMPLETED')

    def test_timeout_and_cancellation_stop_actual_fixture_processes(self):
        result=self._trusted_process_fixture('import time; time.sleep(10)')
        self.assertEqual(result['status'],'TIMED_OUT')
        self.run=str(uuid.uuid4());calls=[]
        def cancelled():
            calls.append(True);return len(calls)>2
        result=self._trusted_process_fixture('import time; time.sleep(10)',cancelled)
        self.assertEqual(result['status'],'CANCELLED')
        self.assertTrue(all(row[0]!='RUNNING' for row in self.db.execute('SELECT status FROM tool_processes')))

    def test_output_limit_stops_actual_fixture_process(self):
        result=self._trusted_process_fixture("print('x'*10000)")
        self.assertEqual(result['status'],'OUTPUT_LIMIT');self.assertLessEqual(len(result['output']),1024)

    def test_gateway_binds_actor_and_qa_cannot_modify_worker_files(self):
        self.manager.write(self.run,'main.py','print(1)\n')
        worker=ToolGateway(self.manager,1,self.run,self.invocation,'web-frontend-engineer')
        with self.assertRaises(PermissionError):worker.execute('read_file',{'path':'main.py','actor':'master-agent'})
        with self.assertRaises(PermissionError):ToolGateway(self.manager,1,self.run,self.invocation,'trading-director')
        qa=ToolGateway(self.manager,1,self.run,self.invocation,'qa-auditor','qa')
        with self.assertRaises(PermissionError):qa.execute('write_file',{'path':'main.py','content':'print(2)'})
        self.assertEqual(qa.execute('read_file',{'path':'main.py'})['content'],'print(1)\n')

    def test_gateway_exposes_only_attached_authorized_checks(self):
        gateway=ToolGateway(self.manager,1,self.run,self.invocation,'qa-auditor','qa',approved_checks=('a'*64,))
        with self.assertRaises(PermissionError):gateway.execute('run_check',{'command_key':'b'*64})
        self.assertNotIn('approve_command',{d['name'] for d in gateway.schemas()})

    def test_gateway_checks_persisted_task_run_and_invocation_binding(self):
        self.db.executescript('CREATE TABLE agent_runs(id TEXT PRIMARY KEY,task_id INTEGER,status TEXT,cancel_requested INTEGER); CREATE TABLE agent_invocations(id TEXT PRIMARY KEY,run_id TEXT,task_id INTEGER,agent TEXT,status TEXT);')
        self.db.execute("INSERT INTO agent_runs VALUES(?,2,'RUNNING',0)",(self.run,));self.db.commit()
        with self.assertRaises(PermissionError):ToolGateway(self.manager,1,self.run,self.invocation,'web-frontend-engineer')
        self.db.execute('UPDATE agent_runs SET task_id=1')
        self.db.execute('INSERT INTO agent_invocations VALUES(?,?,1,?,?)',(self.invocation,self.run,'web-frontend-engineer','RUNNING'));self.db.commit()
        gateway=ToolGateway(self.manager,1,self.run,self.invocation,'web-frontend-engineer')
        self.assertEqual(gateway.execute('list_files',{})['files'],{})
        self.db.execute("UPDATE agent_runs SET cancel_requested=1");self.db.commit()
        with self.assertRaises(PermissionError):gateway.execute('list_files',{})

    def test_sanitized_command_environment_has_no_model_keys_or_preloads(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'not-for-tool-process','ANTHROPIC_API_KEY':'not-for-tool-process','NODE_OPTIONS':'--require bad.js','DOCKER_HOST':'tcp://untrusted','HTTPS_PROXY':'http://fixture-proxy','DOCKER_CONFIG':'/fixture/docker-config'}):
            env=self.manager._safe_environment(docker=True)
        self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('ANTHROPIC_API_KEY',env);self.assertNotIn('NODE_OPTIONS',env);self.assertNotIn('DOCKER_HOST',env)
        self.assertEqual(env['HTTPS_PROXY'],'http://fixture-proxy');self.assertEqual(env['DOCKER_CONFIG'],'/fixture/docker-config')

    def test_docker_argv_does_not_mount_host_repository_or_credentials(self):
        manager=WorkspaceManager(self.hub,{'isolation':'docker','docker_image':'python:3.12-slim'})
        folder=manager.create(self.run)
        with patch.object(manager,'_docker',return_value=['docker','--host=unix:///var/run/docker.sock']):argv=manager._docker_argv(folder,['python','-V'],'maos-check-'+'a'*32)
        self.assertIn('none',argv);self.assertIn('--read-only',argv);self.assertIn('--cap-drop',argv);self.assertIn('--pull=never',argv)
        mounts=[a for a in argv if a.startswith('type=bind')]
        self.assertEqual(mounts,[f'type=bind,src={folder.resolve()},dst=/project'])
        self.assertNotIn('danger-full-access',argv)


    def test_unconfirmed_container_cleanup_blocks_further_execution(self):
        # SIMULATED Docker boundary; only fixed, reviewed test code executes on host.
        self.manager.write(self.run,'context.txt','SIMULATED cleanup fault')
        argv=[sys.executable,'-c','print("fixed fixture")']
        approval=self.manager.approve_command(self.run,argv,'fixture://explicit-fixed-process')
        with patch.object(self.manager,'probe_isolation',return_value={'available':True,'backend':'docker'}),patch.object(self.manager,'_docker_argv',return_value=argv),patch.object(self.manager,'_remove_container',return_value=False):
            result=self.manager.run_check(self.run,approval['command_key'])
        self.assertEqual(result['status'],'CLEANUP_REQUIRED')
        self.assertEqual(self.db.execute('SELECT status FROM tool_processes').fetchone()[0],'CLEANUP_REQUIRED')
        with self.assertRaisesRegex(WorkspaceBlocked,'cleanup'):self.manager.run_check(self.run,approval['command_key'])


if __name__=='__main__':unittest.main()
