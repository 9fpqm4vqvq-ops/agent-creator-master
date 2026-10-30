"""Real local SQLite concurrency and lifecycle guards; no model/provider calls."""
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent_hub.memory import MemoryVault, ConflictError, initialize
from agent_hub.freshness import FreshnessAuditor
from agent_hub.intelligence_schema import SCHEMA, FRESHNESS_COLUMNS
from agent_hub.improvements import Improvements


class DelayedReadCursor:
    """Pause after a real SQLite read so concurrent old-code writes overlap."""
    def __init__(self, cursor):
        self.cursor = cursor

    def fetchone(self):
        row = self.cursor.fetchone()
        self.cursor.close()
        time.sleep(0.08)
        return row


class SlowReadConnection(sqlite3.Connection):
    def execute(self, sql, parameters=()):
        cursor = super().execute(sql, parameters)
        if sql == 'SELECT * FROM memory_records WHERE id=?':
            return DelayedReadCursor(cursor)
        return cursor


class ReliabilityFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'vault.sqlite'
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE tasks(id INTEGER PRIMARY KEY,idempotency_key TEXT,phase TEXT);
            CREATE TABLE events(id INTEGER PRIMARY KEY);
        ''')
        initialize(self.db)
        self.db.executescript(SCHEMA)
        for name, declaration in FRESHNESS_COLUMNS.items():
            self.db.execute('ALTER TABLE memory_records ADD COLUMN '+name+' '+declaration)
        self.db.commit()
        self.addCleanup(self.db.close)
        self.vault = MemoryVault(self.db, self.root)
        self.hub = SimpleNamespace(db=self.db, root=self.root, memory=self.vault)
        self.auditor = FreshnessAuditor(self.hub)

    def put(self, payload=None, **options):
        return self.vault.put('trading','fixture','Concurrent fixture',
            payload or {'writer':'initial'},'trading-director',**options)


class MemoryConcurrency(ReliabilityFixture):
    def test_two_sqlite_writers_cannot_both_replace_the_same_revision(self):
        record = self.put()
        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()

        def write(name):
            db = sqlite3.connect(self.path, timeout=5, factory=SlowReadConnection)
            db.row_factory = sqlite3.Row
            try:
                barrier.wait(timeout=5)
                result = MemoryVault(db,self.root).put('trading','fixture','Concurrent fixture',
                    {'writer':name},'trading-director',record_id=record['id'],expected_revision=1)
                outcome = ('accepted',name,result['revision'])
            except ConflictError:
                outcome = ('conflict',name,None)
            except BaseException as exc:
                outcome = ('unexpected',name,type(exc).__name__+': '+str(exc))
            finally:
                db.close()
            with lock:
                results.append(outcome)

        first = threading.Thread(target=write,args=('A',))
        second = threading.Thread(target=write,args=('B',))
        first.start(); second.start()
        first.join(timeout=10); second.join(timeout=10)
        self.assertFalse(first.is_alive() or second.is_alive(),'Concurrent writers did not finish')
        self.assertEqual(sorted(r[0] for r in results),['accepted','conflict'],results)
        current = self.vault.get(record['id'],'trading-director')
        history = self.vault.history(record['id'],'trading-director')
        self.assertEqual(current['revision'],2)
        self.assertEqual([r['revision'] for r in history],[1,2])
        self.assertEqual(json.loads(history[-1]['snapshot']['payload']),current['payload'])

    def test_put_preserves_caller_transaction_and_history_rolls_back_together(self):
        record = self.put()
        other = sqlite3.connect(self.path)
        self.addCleanup(other.close)
        self.db.execute('BEGIN IMMEDIATE')
        self.put({'writer':'not committed'},record_id=record['id'],expected_revision=1)
        self.assertEqual(other.execute('SELECT revision FROM memory_records WHERE id=?',(record['id'],)).fetchone()[0],1)
        self.db.rollback()
        self.assertEqual(self.vault.get(record['id'],'trading-director')['revision'],1)
        self.assertEqual(len(self.vault.history(record['id'],'trading-director')),1)

    def test_commit_false_stays_uncommitted_until_caller_commits(self):
        record = self.put(commit=False)
        other = sqlite3.connect(self.path)
        self.addCleanup(other.close)
        self.assertIsNone(other.execute('SELECT id FROM memory_records WHERE id=?',(record['id'],)).fetchone())
        self.db.commit()
        self.assertIsNotNone(other.execute('SELECT id FROM memory_records WHERE id=?',(record['id'],)).fetchone())

    def test_failed_write_does_not_leave_partial_history_or_abort_outer_work(self):
        record = self.put()
        self.db.execute('BEGIN IMMEDIATE')
        self.db.execute("INSERT INTO tasks VALUES(1,'outer-fixture','CREATED')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.put({'writer':'invalid FK'},record_id=record['id'],expected_revision=1,task_id=999,commit=False)
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],1)
        self.assertEqual(self.vault.get(record['id'],'trading-director')['revision'],1)
        self.assertEqual(len(self.vault.history(record['id'],'trading-director')),1)
        self.db.rollback()


class FreshnessConcurrency(ReliabilityFixture):
    def test_review_of_old_body_cannot_mark_a_concurrently_edited_record_fresh(self):
        old = self.put()
        other = sqlite3.connect(self.path)
        other.row_factory = sqlite3.Row
        self.addCleanup(other.close)
        MemoryVault(other,self.root).put('trading','fixture','Concurrent fixture',
            {'writer':'new evidence'},'trading-director',record_id=old['id'],expected_revision=1)
        with self.assertRaises(ConflictError):
            self.auditor._metadata(old,{'verification_status':'FRESH'},'Old synthetic review')
        current = self.vault.get(old['id'],'trading-director')
        self.assertEqual(current['revision'],2)
        self.assertEqual(current['verification_status'],'UNVERIFIED')
        self.assertEqual(current['payload'],{'writer':'new evidence'})
        self.assertEqual(len(self.vault.history(old['id'],'trading-director')),2)

    def test_metadata_only_concurrent_change_also_invalidates_an_old_review(self):
        old = self.put()
        first = self.auditor._metadata(old,{'verification_status':'REQUIRES_VERIFICATION'},'First review')
        self.assertEqual(first['revision'],2)
        with self.assertRaises(ConflictError):
            self.auditor._metadata(old,{'verification_status':'FRESH'},'Stale duplicate review')
        self.assertEqual(self.vault.get(old['id'],'trading-director')['verification_status'],'REQUIRES_VERIFICATION')
        self.assertEqual([r['revision'] for r in self.vault.history(old['id'],'trading-director')],[1,2])


class UpgradeStaging(ReliabilityFixture):
    def test_stage_keeps_reviewed_ui_source_data_but_excludes_operational_data(self):
        reviewed = self.root/'vendor/supplementary/ui-ux-pro-max-skill/data'
        reviewed.mkdir(parents=True)
        (reviewed/'guidance.csv').write_text('topic,guidance\nfocus,visible\n')
        for name in ['data','outputs','memory']:
            folder = self.root/name; folder.mkdir()
            (folder/'private.txt').write_text('Synthetic operational file; must not copy')
        unrelated = self.root/'vendor/unreviewed/data'
        unrelated.mkdir(parents=True);(unrelated/'private.txt').write_text('Synthetic private vendor data')
        changes = Improvements(self.hub)
        proposal = changes.propose('agent-development','Synthetic staging check',{'docs/review.md':'Reviewed fixture'})
        sandbox = Path(changes.stage(proposal['id'])['sandbox'])
        self.assertEqual((sandbox/'vendor/supplementary/ui-ux-pro-max-skill/data/guidance.csv').read_text(),(reviewed/'guidance.csv').read_text())
        for name in ['data','outputs','memory','vendor/unreviewed/data']:
            self.assertFalse((sandbox/name).exists(),name)

    def test_idle_guard_feature_detects_active_runs_and_invocations(self):
        changes = Improvements(self.hub)
        self.db.execute('CREATE TABLE agent_runs(id TEXT,status TEXT)')
        self.db.execute("INSERT INTO agent_runs VALUES('run','WAITING_FOR_APPROVAL')");self.db.commit()
        with self.assertRaisesRegex(ValueError,'active agent'):
            changes._idle()
        self.db.execute("UPDATE agent_runs SET status='CANCELLED'")
        self.db.execute('CREATE TABLE agent_invocations(id TEXT,state TEXT)')
        self.db.execute("INSERT INTO agent_invocations VALUES('invocation','RUNNING')");self.db.commit()
        with self.assertRaisesRegex(ValueError,'agent_invocations'):
            changes._idle()
        self.db.execute("UPDATE agent_invocations SET state='COMPLETED'");self.db.commit()
        changes._idle()

    def test_cancelled_parent_does_not_hide_a_live_tool_process(self):
        self.db.execute("INSERT INTO tasks VALUES(1,'cancelled-parent','CANCELLED')")
        self.db.execute('CREATE TABLE tool_processes(id TEXT,status TEXT,pid INTEGER,finished_at TEXT)')
        self.db.execute("INSERT INTO tool_processes VALUES('tool','TERMINATING',?,NULL)",(os.getpid(),));self.db.commit()
        changes = Improvements(self.hub)
        with self.assertRaisesRegex(ValueError,'tool_processes'):
            changes._idle()
        # A premature terminal flag still is not proof that the process stopped.
        self.db.execute("UPDATE tool_processes SET status='CANCELLED'");self.db.commit()
        with self.assertRaisesRegex(ValueError,'live tool'):
            changes._idle()
        self.db.execute("UPDATE tool_processes SET finished_at='2026-01-01T00:00:00+00:00'");self.db.commit()
        changes._idle()

    def test_finished_tool_limits_and_check_outcomes_do_not_block_idle_updates(self):
        self.db.execute('CREATE TABLE tool_processes(id TEXT,status TEXT,finished_at TEXT)')
        self.db.executemany('INSERT INTO tool_processes VALUES(?,?,?)',[
            ('timeout','TIMED_OUT','2026-01-01T00:00:00+00:00'),
            ('output','OUTPUT_LIMIT','2026-01-01T00:00:00+00:00')])
        self.db.execute('CREATE TABLE workspace_checks(id TEXT,status TEXT)')
        self.db.execute("INSERT INTO workspace_checks VALUES('check','PASS')");self.db.commit()
        Improvements(self.hub)._idle()

    def test_existing_runtime_table_with_unknown_lifecycle_fails_closed(self):
        self.db.execute('CREATE TABLE agent_invocations(id TEXT)');self.db.commit()
        with self.assertRaisesRegex(ValueError,'lifecycle state is unavailable'):
            Improvements(self.hub)._idle()


if __name__=='__main__':
    unittest.main()
