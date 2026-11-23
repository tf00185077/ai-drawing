"""Synthetic component controls. Native writes here are harness effects, not capped B."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
PRESENT = (HERE / 'contract.py').is_file()
if PRESENT:
    import contract as m
    from ledger import Window

class Interface(unittest.TestCase):
    def test_retained_callable_exists(self):
        self.assertTrue(PRESENT, 'new M2 callable refusal contract is missing')

@unittest.skipUnless(PRESENT, 'new interface not authored yet')
class Component(unittest.TestCase):
    def setUp(self):
        self.home = ROOT / self._testMethodName
        self.home.mkdir(mode=0o700)
        self.connections = []
    def tearDown(self):
        for c in self.connections:
            c.close()  # exactly one harness close; never a candidate retry
    def connect(self, name='fixture.db'):
        c = sqlite3.connect(str(self.home / name), isolation_level=None, timeout=0)
        self.connections.append(c)
        return c
    def fixture(self):
        c = self.connect()
        c.execute(m.FIXTURE_SCHEMA)
        ids = m.exact_ids((HERE / 'exact408.txt').read_bytes())
        rows = [(i, 'queued', 'queued', None, None, '2025-01-01 00:00:00', '{"seed":1}', b'\x00\xff', 7, 1.5, 'models/x', 'datasets/y') for i in ids]
        rows += [('terminal-' + str(i), 'completed', 'completed', None, '2025-01-01 00:00:00', '2025-01-01 00:00:00', None, b'', i, None, None, '') for i in range(2)]
        c.executemany('INSERT INTO lora_training_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', rows)
        return c, ids
    def save(self, name, value):
        (self.home / name).write_text(json.dumps(value, indent=2, sort_keys=True))
    def test_pre_access_stop_and_shared_plan_unchanged(self):
        c, ids = self.fixture()
        trace = []; c.set_trace_callback(trace.append)
        w = Window(self.home, 'window', {'controls/error':('file',256), 'post-B-state/db':('file',1000000), 'temp/db-native':('native',1000000), 'recovery/held':('file',17)})
        before = w.snapshot(); raw = (self.home/'fixture.db').read_bytes()
        try:
            for api in (m.execute_exact408, m.read_exact408):
                r = api(c, w, '2026-10-29 00:00:00')
                self.assertEqual(r.commit_state, 'not_attempted')
                self.assertEqual(r.status, 'unavailable')
                self.assertIsNone(r.full_db_bound)
                self.assertFalse(r.source_start_allowed or r.retry_b_allowed)
            self.assertEqual(trace, [])
            self.assertEqual(w.snapshot(), before)
            self.assertEqual((self.home/'fixture.db').read_bytes(), raw)
            self.assertFalse((w.root/'controls/error').exists())
            self.save('stop.json', dict(result=r.__dict__, accounting=before, trace=trace))
        finally: w.close()
        class Poison:
            def __getattribute__(self, name): raise AssertionError('unexpected connection/window access')
        self.assertEqual(m.execute_exact408(Poison(),Poison(),Poison()).commit_state,'not_attempted')
    def test_exact_set_and_typed_boundaries(self):
        raw = (HERE/'exact408.txt').read_bytes(); ids=m.exact_ids(raw)
        self.assertEqual(len(ids),408)
        for bad in (raw[:-1],raw+raw[:37],raw.replace(b'00be',b'00BE',1), b'\n'.join(reversed(raw.splitlines()))+b'\n'):
            with self.assertRaises(m.Stop):m.exact_ids(bad)
        values = [None, -2**63, 2**63-1, 1.5, '', 'x\x00y', b'', b'\x00\xff']
        tags = [m.cell(v) for v in values]
        self.assertEqual([t[0] for t in tags],['null','integer','integer','real','text','text','blob','blob'])
        self.assertNotEqual(tags[-2], tags[4])
        for bad in (True, 2**63, float('inf'), object(), 'x'*4097, b'x'*4097):
            with self.assertRaises(m.Stop):m.cell(bad)
        with self.assertRaises(m.Stop):m.encode_records([tuple('x'*4096 for _ in range(12))]*413)
        self.save('typed.json',tags)
    def test_full_guard_and_exact408_synthetic_sql(self):
        c, ids = self.fixture(); pre=m.fixture_snapshot(c);m.guard_preimages(pre,pre,ids)
        trace=[];c.set_trace_callback(trace.append)
        c.execute('BEGIN IMMEDIATE')
        fresh=m.fixture_snapshot(c);m.guard_preimages(pre,fresh,ids)
        T='2026-10-29 00:00:00.123456'
        for i in ids:
            self.assertEqual(c.execute(m.UPDATE_SQL,{'T':T,'approved_job_id':i}).rowcount,1)
        post=m.fixture_snapshot(c);m.guard_postimages(pre,post,ids,T)
        c.execute('COMMIT')
        self.assertFalse(c.in_transaction)
        self.assertEqual(sum(x=='BEGIN IMMEDIATE' for x in trace),1)
        self.assertEqual(sum(x=='COMMIT' for x in trace),1)
        self.assertEqual(sum(x.startswith('UPDATE lora_training_jobs') for x in trace),408)
        self.assertEqual(m.transaction_state(True, True, True, False, c.in_transaction),'known_committed')
        self.save('preimages.json',pre);self.save('postimages.json',post)
        self.save('sql-counts.json',{'begin':1,'updates':408,'commit_attempts':1,'fixture_only':True})
    def test_original_guard_change_missing_new_nonterminal_and_other_columns(self):
        for scenario in ('change','missing','new','active','outside','oversize'):
            c,ids=self.fixture() if scenario=='change' else (None,None)
            if c is None:
                c=self.connect(scenario+'.db');c.execute(m.FIXTURE_SCHEMA)
                base=self.connections[0].execute('SELECT * FROM lora_training_jobs').fetchall()
                c.executemany('INSERT INTO lora_training_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',base)
                ids=m.exact_ids((HERE/'exact408.txt').read_bytes())
            pre=m.fixture_snapshot(c)
            if scenario=='change':c.execute('UPDATE lora_training_jobs SET recipe=? WHERE job_id=?',(b'changed',ids[0]))
            if scenario=='missing':c.execute('DELETE FROM lora_training_jobs WHERE job_id=?',(ids[0],))
            if scenario=='new':c.execute('INSERT INTO lora_training_jobs(job_id,status,stage) VALUES (?,?,?)',('new','queued','queued'))
            if scenario=='active':c.execute('UPDATE lora_training_jobs SET status=? WHERE job_id=?',('running',ids[0]))
            if scenario=='outside':c.execute('UPDATE lora_training_jobs SET reservation=99 WHERE job_id=?',('terminal-0',))
            if scenario=='oversize':c.execute('UPDATE lora_training_jobs SET params=? WHERE job_id=?',('x'*4097,ids[0]))
            with self.assertRaises(m.Stop):m.guard_preimages(pre,m.fixture_snapshot(c),ids)
    def test_schema_attach_udf_and_collation_are_not_inferred_absent(self):
        c,ids=self.fixture();baseline=m.fixture_facts(c);self.save('build.json',baseline)
        c.execute('CREATE TRIGGER altered AFTER UPDATE ON lora_training_jobs BEGIN SELECT 1; END')
        with self.assertRaises(m.Stop):m.fixture_snapshot(c)
        c.execute('DROP TRIGGER altered')
        c.execute('ATTACH DATABASE ? AS extra',(str(self.home/'extra.db'),))
        with self.assertRaises(m.Stop):m.fixture_snapshot(c)
        c.execute('DETACH DATABASE extra')
        c.create_function('fixture_udf',0,lambda:1)
        c.create_collation('fixture_collation',lambda a,b:(a>b)-(a<b))
        facts=m.fixture_facts(c)
        self.assertNotEqual(facts['functions'],baseline['functions'])
        self.assertNotEqual(facts['collations'],baseline['collations'])
        self.assertIsNone(facts['vfs_binding'])
        self.assertIsNone(facts['complete_registered_effects'])
        self.save('registered-effects.json',facts)
    def test_guard_rejects_subset_foreign_connection_and_nonterminal(self):
        c,ids=self.fixture();pre=m.fixture_snapshot(c)
        with self.assertRaises(m.Stop):m.guard_preimages(pre,pre,ids[:1])
        other=self.connect('foreign.db');other.execute(m.FIXTURE_SCHEMA)
        other.executemany('INSERT INTO lora_training_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',c.execute('SELECT * FROM lora_training_jobs').fetchall())
        with self.assertRaises(m.Stop):m.guard_preimages(pre,m.fixture_snapshot(other),ids)
        c.execute("UPDATE lora_training_jobs SET status='running' WHERE job_id='terminal-0'")
        now=m.fixture_snapshot(c)
        with self.assertRaises(m.Stop):m.guard_preimages(now,now,ids)
    def test_unsupported_schema_and_serialization_and_time(self):
        for i,ddl in enumerate((
            m.FIXTURE_SCHEMA.replace('params,','params CHECK(length(params)<99),'),
            m.FIXTURE_SCHEMA.replace('params,','params REFERENCES missing(id),'),
            m.FIXTURE_SCHEMA.replace('params,','params GENERATED ALWAYS AS (status),'),
        )):
            c=self.connect('schema-'+str(i)+'.db');c.execute(ddl)
            with self.assertRaises(m.Stop):m.fixture_snapshot(c)
        c,ids=self.fixture();pre=m.fixture_snapshot(c)
        with self.assertRaisesRegex(m.Stop,'serialization_bound'):
            m.encode_records([tuple('x'*4096 for _ in range(12))]*100)
        for bad in ('2026-10-29T00:00:00Z','2026-02-31 00:00:00','2026-10-29 00:00:00+00:00'):
            with self.assertRaises(m.Stop):m.guard_postimages(pre,pre,ids,bad)
        c.execute("UPDATE lora_training_jobs SET params=CAST(X'80' AS TEXT) WHERE job_id=?",(ids[0],))
        with self.assertRaises(sqlite3.DatabaseError):m.fixture_snapshot(c)
    def test_live_journal_and_unknown_sidecar_stop_without_touches(self):
        c,ids=self.fixture();c.execute('BEGIN IMMEDIATE')
        c.execute('UPDATE lora_training_jobs SET reservation=8 WHERE job_id=?',(ids[0],))
        journal=self.home/'fixture.db-journal';self.assertTrue(journal.is_file())
        before=journal.read_bytes();(self.home/'retained-active-journal').write_bytes(before);trace=[];c.set_trace_callback(trace.append)
        r=m.execute_exact408(c,None,'2026-10-29 00:00:00')
        self.assertFalse(r.database_access_attempted);self.assertEqual(trace,[])
        self.assertTrue(c.in_transaction);self.assertEqual(journal.read_bytes(),before)
        c.set_trace_callback(None);c.execute('ROLLBACK')
        # An unknown sidecar is retained, never opened as a recovery trigger.
        unknown=self.home/'fixture.db-journal';unknown.write_bytes(b'unknown-not-a-certified-hot-journal')
        trace=[];c.set_trace_callback(trace.append)
        r=m.read_exact408(c,None,None)
        self.assertEqual(trace,[]);self.assertEqual(unknown.read_bytes(),b'unknown-not-a-certified-hot-journal')
        self.save('sidecar-stop.json',dict(result=r.__dict__,actual_active_journal_bytes=len(before),hot_recovery_not_attempted=True))
    def test_main_cap_same_connection_reopen_and_full_error(self):
        c=self.connect();c.execute('CREATE TABLE data(value BLOB)')
        size=c.execute('PRAGMA page_size').fetchone()[0];pages=c.execute('PRAGMA page_count').fetchone()[0]
        prior=c.execute('PRAGMA max_page_count').fetchone()[0]
        proposed=pages+2
        returned=c.execute('PRAGMA main.max_page_count='+str(proposed)).fetchone()[0]
        effective=c.execute('PRAGMA main.max_page_count').fetchone()[0]
        before=self.home.joinpath('fixture.db').read_bytes()
        c.execute('BEGIN IMMEDIATE')
        with self.assertRaises(sqlite3.DatabaseError) as error:c.execute('INSERT INTO data VALUES (?)',(b'x'*(size*8),))
        active=c.in_transaction
        if active:c.execute('ROLLBACK')
        self.assertEqual(c.execute('SELECT count(*) FROM data').fetchone()[0],0)
        self.assertEqual(returned,effective);self.assertEqual(effective,proposed)
        other=self.connect();reopened=other.execute('PRAGMA max_page_count').fetchone()[0]
        self.assertEqual(reopened,prior)
        evidence={'connection_id':id(c),'python':sys.version,'sqlite':sqlite3.sqlite_version,'prior':prior,'proposed':proposed,'setter_return':returned,'effective':effective,'reopened_other_connection':reopened,'page_size':size,'pages':pages,'error':m.error_record('update',error.exception,active),'transaction_active_after_error':active,'after_handled':c.in_transaction,'header_before_sha':hashlib.sha256(before).hexdigest()}
        # No alternate library, ctypes pointer or private CPython layout.
        if hasattr(c,'getlimit') and hasattr(c,'setlimit'):
            cat=sqlite3.SQLITE_LIMIT_LENGTH;p=c.getlimit(cat);ret=c.setlimit(cat,8192);now=c.getlimit(cat)
            self.assertEqual(ret,p);self.assertEqual(now,8192)
            evidence['sqlite_limit']={'prior':p,'proposed':8192,'setter_return':ret,'effective':now,'other':other.getlimit(cat)}
        else:evidence['sqlite_limit']={'status':'unsupported_same_connection_API','getlimit':hasattr(c,'getlimit'),'setlimit':hasattr(c,'setlimit')}
        self.save('limits.json',evidence)
    def test_main_page_limit_does_not_bound_rollback_or_wal_files(self):
        c,ids=self.fixture();pages=c.execute('PRAGMA page_count').fetchone()[0]
        c.execute('PRAGMA max_page_count='+str(pages));main=(self.home/'fixture.db').stat().st_size
        c.execute('BEGIN IMMEDIATE');c.execute('UPDATE lora_training_jobs SET reservation=8')
        journal=self.home/'fixture.db-journal';self.assertTrue(journal.is_file());n=journal.stat().st_size;self.assertGreater(n,0)
        (self.home/'retained-rollback-journal').write_bytes(journal.read_bytes())
        c.execute('ROLLBACK')
        mode=c.execute('PRAGMA journal_mode=WAL').fetchone()[0];self.assertEqual(mode,'wal')
        c.execute('PRAGMA wal_autocheckpoint=0')
        for i in range(5):c.execute('UPDATE lora_training_jobs SET reservation=?',(i,))
        sizes={p.name:p.stat().st_size for p in self.home.iterdir() if p.is_file()}
        self.assertGreater(sizes.get('fixture.db-wal',0),0);self.assertGreater(sizes.get('fixture.db-shm',0),0)
        self.save('native-companions.json',{'rollback_journal_peak_observed':n,'wal_fixture_files_at_observation':sizes,'main_initial':main,'main_page_cap':pages,'not_upper_bounds':True})
        # Retain actual companion bytes before the one normal harness close removes them.
        for suffix in ('-wal','-shm'):(self.home/('retained'+suffix)).write_bytes((self.home/('fixture.db'+suffix)).read_bytes())
    def test_full_length_tail_and_future_main_differ_from_current(self):
        c,ids=self.fixture();path=self.home/'fixture.db';raw=path.read_bytes();size=c.execute('PRAGMA page_size').fetchone()[0];pages=c.execute('PRAGMA page_count').fetchone()[0]
        result=m.main_file_derivation(raw[:100],len(raw),pages,size,pages+10)
        self.assertGreater(result['conditional_main_full_later'],len(raw));self.assertIsNone(result['full_D_B'])
        # Own fixture tail is not silently dropped from a full later copy.
        with path.open('ab') as f:f.write(b'tail')
        with self.assertRaises(m.Stop):m.main_file_derivation(path.read_bytes()[:100],path.stat().st_size,pages,size,pages+10)
        self.save('main-derivation.json',result)
    def test_real_constraint_interruption_and_commit_ack_uncertainty(self):
        c,ids=self.fixture();pre=m.fixture_snapshot(c)
        c.execute('BEGIN IMMEDIATE')
        with self.assertRaises(sqlite3.IntegrityError) as err:c.execute('INSERT INTO lora_training_jobs(job_id) VALUES (?)',(ids[0],))
        self.assertTrue(c.in_transaction)
        self.assertEqual(m.transaction_state(True,False,False,False,c.in_transaction),'known_not_committed')
        constraint=m.error_record('update',err.exception,c.in_transaction)
        c.execute('ROLLBACK');self.assertEqual(pre,m.fixture_snapshot(c))
        c.execute('BEGIN IMMEDIATE');c.set_progress_handler(lambda:1,1)
        with self.assertRaises(sqlite3.OperationalError) as interrupted:c.execute('UPDATE lora_training_jobs SET reservation=reservation+1')
        c.set_progress_handler(None,0);active=c.in_transaction
        if active:c.execute('ROLLBACK')
        self.assertEqual(pre,m.fixture_snapshot(c))
        interrupt=m.error_record('update',interrupted.exception,active)
        # Real commit, injected loss of its caller acknowledgement. No retry/rewrite.
        c.execute('BEGIN IMMEDIATE');c.execute('UPDATE lora_training_jobs SET reservation=9 WHERE job_id=?',(ids[0],))
        attempts=0;ack=False
        try:
            attempts+=1;c.execute('COMMIT');raise OSError(5,'private injected lost acknowledgement')
        except OSError as err:lost=m.error_record('commit',err,c.in_transaction)
        self.assertEqual(attempts,1);self.assertFalse(c.in_transaction)
        state=m.transaction_state(True,True,ack,False,c.in_transaction)
        self.assertEqual(state,'commit_unknown');self.assertEqual(c.execute('SELECT reservation FROM lora_training_jobs WHERE job_id=?',(ids[0],)).fetchone()[0],9)
        self.save('errors.json',dict(constraint=constraint,interrupt=interrupt,commit_lost=lost,commit_state=state,attempts=attempts,raw_message_retained=False))
    def test_failed_rollback_keeps_unknown_and_retains_journal(self):
        c,ids=self.fixture();c.execute('BEGIN IMMEDIATE')
        c.execute('UPDATE lora_training_jobs SET reservation=55 WHERE job_id=?',(ids[0],))
        def authorizer(action,arg1,arg2,db,source):
            return sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_TRANSACTION and arg1=='ROLLBACK' else sqlite3.SQLITE_OK
        c.set_authorizer(authorizer)
        with self.assertRaises(sqlite3.DatabaseError) as err:c.execute('ROLLBACK')
        self.assertTrue(c.in_transaction)
        state=m.transaction_state(True,False,False,False,c.in_transaction,rollback_attempted=True)
        self.assertEqual(state,'commit_unknown')
        journal=self.home/'fixture.db-journal';self.assertGreater(journal.stat().st_size,0)
        (self.home/'retained-journal').write_bytes(journal.read_bytes())
        self.save('rollback-unknown.json',dict(state=state,error=m.error_record('rollback',err.exception,c.in_transaction),rollback_attempts=1,transaction_active=c.in_transaction,one_harness_close_follows=True))
        c.set_authorizer(None) # no retry; one normal owned harness close at tearDown
    def test_m1_partial_receipt_failure_and_true_interrupt_preserved(self):
        w=Window(self.home,'out',{'controls/error':('file',256),'controls/partial':('file',20),'recovery/unused':('file',19)},commit='known_committed')
        write=os.write
        def fail(fd,data):
            if data==b'fail':raise OSError(28,'private payload')
            if data.startswith(b'stage='):raise OSError(5,'private receipt')
            return write(fd,data)
        try:
            with patch('os.write',fail):r=w.run('copy',lambda:w.stream('controls/partial',[b'part',b'fail']))
            self.assertEqual((w.root/'controls/partial').read_bytes(),b'part');self.assertFalse(r['local_error_receipt'])
            self.assertEqual(r['errno'],28);self.assertEqual(r['commit_state'],'known_committed')
            state=w.snapshot();self.assertEqual(state['charged'],276);self.assertEqual(state['reserved_remaining'],19)
            self.save('receipt-failure.json',dict(result=r,accounting=state))
        finally:w.close()
        other=Window(self.home,'interrupt',{'controls/error':('file',256),'controls/partial':('file',20)},commit='unknown');original=KeyboardInterrupt('private interrupt')
        def chunks():yield b'part';raise original
        try:
            with self.assertRaises(KeyboardInterrupt) as caught:other.run('copy',lambda:other.stream('controls/partial',chunks()))
            self.assertIs(caught.exception,original);self.assertTrue(other.stopped)
            self.assertEqual((other.root/'controls/partial').read_bytes(),b'part')
            self.assertFalse((other.root/'controls/error').exists())
            self.save('interrupt-accounting.json',other.snapshot())
        finally:other.close()

if __name__=='__main__':unittest.main(verbosity=2)
