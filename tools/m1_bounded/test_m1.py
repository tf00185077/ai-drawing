"""Direct stdlib tests. Fresh supplied parent; never product conftest."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

PARENT = Path(sys.argv.pop(1)).resolve(strict=True)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

class Interface(unittest.TestCase):
    def test_callable_hierarchy_interface(self):
        self.assertTrue((HERE / 'hierarchy.py').is_file(), 'M1 hierarchy/metadata interface absent')
    def test_callable_observation_interface(self):
        self.assertTrue((HERE / 'observe.py').is_file(), 'M1 finite observation interface absent')


import errno
import hashlib
import json
import socket
import subprocess
import threading
import time
import uuid
from unittest.mock import patch
from ledger import Window, Stop, bounded_json
from hierarchy import Manifest, companion_name
from observe import Observations, capture_fixture, parse_json

class Cases(unittest.TestCase):
    def setUp(self):
        self.home=PARENT/('case-'+uuid.uuid4().hex);self.home.mkdir(mode=0o700)
        self.src=self.home/'source';self.src.mkdir(mode=0o700)
        self.windows=[];self.manifests=[]
    def tearDown(self):
        for m in self.manifests:m.close()
        for w in self.windows:w.close()
    def window(self,extra=None,cap=10000000):
        slots={'controls/error':('file',256)};slots.update(extra or {})
        w=Window(self.home,'out-'+uuid.uuid4().hex,slots,cap=cap);self.windows.append(w);return w
    def manifest(self,entries):
        m=Manifest({'named':self.src},entries);self.manifests.append(m);return m
    def nested(self,link=False):
        (self.src/'nested').mkdir(mode=0o750);(self.src/'nested/file').write_bytes(b'payload'*100)
        os.chmod(self.src/'nested/file',0o640)
        entries=[('named','nested','dir'),('named','nested/file','file')]
        if link:
            (self.src/'literal').symlink_to('nested');entries.append(('named','literal','link'))
        return entries
    def invariant(self,w):
        s=w.snapshot();self.assertEqual(s['charged']+s['reserved_remaining'],s['plan_total']);self.assertLessEqual(s['plan_total'],128849018880)
        (self.home/('accounting-'+w.name+'.json')).write_bytes(bounded_json(s,2097152))
        self.assertFalse(s['protection_verified']);self.assertFalse(s['source_start_allowed']);self.assertFalse(s['retry_b_allowed'])
    def test_actual_nested_roundtrip(self):
        m=self.manifest(self.nested());w=self.window(m.plan());result=m.protect(w)
        (self.home/'result.json').write_text(json.dumps(result))
        self.assertEqual(result['status'],'fixture_roundtrip',result)
        self.assertEqual((w.root/'restore-check/named/nested/file').read_bytes(),b'payload'*100)
        self.assertEqual((w.root/'pre-adoption/named/nested/file').stat().st_mode&511,0o600)
        self.assertEqual((w.root/'pre-adoption/named/nested').stat().st_mode&511,0o700)
        self.assertEqual((w.root/'restore-check/named/nested/file').stat().st_mode&511,0o640)
        self.invariant(w)
    def test_actual_link_roundtrip(self):
        m=self.manifest(self.nested(True));w=self.window(m.plan());result=m.protect(w)
        (self.home/'link-result.json').write_text(json.dumps(result))
        self.assertEqual(result['status'],'fixture_roundtrip',result)
        self.assertEqual(os.readlink(w.root/'restore-check/named/literal'),'nested')
        self.assertEqual((w.root/'pre-adoption/named/literal').read_bytes(),b'nested');self.invariant(w)
    def test_actual_xattr_roundtrip(self):
        entries=self.nested();fd=os.open(self.src/'nested/file',os.O_RDWR)
        try:
            from darwin_metadata import Metadata
            meta=Metadata();meta.call('fsetxattr',fd,b'com.aid68.fixture',b'xattr',5,0,2)
        finally:os.close(fd)
        m=self.manifest(entries);w=self.window(m.plan());result=m.protect(w)
        self.assertEqual(result['status'],'fixture_roundtrip',result)
        fd=os.open(w.root/'restore-check/named/nested/file',os.O_RDONLY)
        try:self.assertIn((b'com.aid68.fixture'.hex(),b'xattr'.hex()),meta.xattrs(fd))
        finally:os.close(fd)
    def test_aggregate_admission_before_any_root(self):
        slots={'controls/error':('file',256),'controls/a':('file',6),'controls/b':('file',6)}
        with self.assertRaises(Stop):Window(self.home,'forbidden',slots,cap=266)
        self.assertFalse((self.home/'forbidden').exists())
        w=self.window({'controls/a':('file',6),'controls/b':('file',4)},cap=266)
        self.assertEqual(w.run('copy',lambda:w.stream('controls/a',[b'123456']))['bytes'],6)
        result=w.run('copy',lambda:w.stream('controls/b',[b'123456']))
        self.assertEqual(result['code'],'limit');self.assertEqual((w.root/'controls/b').stat().st_size,0);self.invariant(w)
    def test_plan_is_immutable(self):
        w=self.window()
        with self.assertRaises(TypeError):w.plan['controls/new']=('file',4)
    def test_alias_collision_unknown_child_and_outside_target(self):
        entries=self.nested();(self.src/'extra').write_bytes(b'unchanged')
        with self.assertRaises(Stop):self.manifest(entries)
        with self.assertRaises(Stop):Manifest({'a':self.src,'b':self.src},entries)
        with self.assertRaises(Stop):self.manifest(entries+[entries[0]])
        (self.src/'link').symlink_to('/not-a-covered-root')
        with self.assertRaises(Stop):self.manifest(entries+[('named','extra','file'),('named','link','link')])
        self.assertEqual((self.src/'extra').read_bytes(),b'unchanged')
    def test_hardlink_symlink_ancestor_refused(self):
        (self.src/'a').write_bytes(b'abc');os.link(self.src/'a',self.src/'b')
        with self.assertRaises(Stop):self.manifest([('named','a','file'),('named','b','file')])
        alias=self.home/'alias';alias.symlink_to(self.src)
        with self.assertRaises(OSError):Manifest({'x':alias},[('x','a','file')])
    def test_source_and_output_drift(self):
        m=self.manifest(self.nested());w=self.window(m.plan());(self.src/'nested/file').write_bytes(b'drift')
        result=m.protect(w);self.assertEqual(result['code'],'drift');self.assertFalse((w.root/'pre-adoption/named').exists())
        other=self.window({'controls/a':('file',4)})
        (other.root/'controls').rename(other.root/'old-controls');(other.root/'controls').mkdir(mode=0o700)
        result=other.run('copy',lambda:other.stream('controls/a',[b'data']));self.assertEqual(result['code'],'drift');self.assertFalse((other.root/'controls/a').exists())
    def test_leading_dot_companions(self):
        u='12345678-1234-1234-1234-123456789abc'
        for name in ['ledger','ledger.owner','ledger.checkpoint','.ledger.'+u+'.tmp','.ledger.checkpoint.'+u+'.tmp']:
            self.assertTrue(companion_name('ledger',name))
        for name in ['ledger-ignored','.ledger.bad.tmp','.other.'+u+'.tmp']:
            self.assertFalse(companion_name('ledger',name))
    def test_short_write_retains_full_charge_and_stops(self):
        w=self.window({'controls/a':('file',20),'controls/later':('file',10)})
        original=os.write
        def short(fd,data):
            if data==b'123456':return original(fd,data[:2])
            return original(fd,data)
        with patch('os.write',short):result=w.run('copy',lambda:w.stream('controls/a',[b'123456']))
        self.assertEqual(result['code'],'short_write');self.assertEqual((w.root/'controls/a').read_bytes(),b'12')
        self.assertEqual(w.snapshot()['slots']['controls/a']['charged'],20)
        w.run('copy',lambda:w.stream('controls/later',[b'later']));self.assertFalse((w.root/'controls/later').exists());self.invariant(w)
    def test_partial_eio_and_receipt_failure_original(self):
        w=self.window({'controls/a':('file',20)})
        original=os.write;calls=[0]
        def fail(fd,data):
            calls[0]+=1
            if calls[0]==1:return original(fd,data)
            raise OSError(errno.EIO,'private details must never serialize')
        with patch('os.write',fail):result=w.run('copy',lambda:w.stream('controls/a',[b'part',b'next']))
        self.assertEqual(result['errno'],errno.EIO);self.assertFalse(result['local_error_receipt']);self.assertIn('code=os_error',result['native_fallback'])
        self.assertEqual((w.root/'controls/a').read_bytes(),b'part');self.assertEqual(w.snapshot()['slots']['controls/error']['charged'],256);self.invariant(w)
    def test_interrupt_stops_and_preserves(self):
        w=self.window({'controls/a':('file',20),'controls/later':('file',10)})
        def chunks():
            yield b'part'
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):w.run('copy',lambda:w.stream('controls/a',chunks()))
        self.assertTrue(w.stopped);self.assertEqual((w.root/'controls/a').read_bytes(),b'part')
        w.run('copy',lambda:w.stream('controls/later',[b'later']));self.assertFalse((w.root/'controls/later').exists());self.invariant(w)
    def test_original_error_survives_close_error(self):
        w=self.window({'controls/a':('file',20)})
        original_close=os.close;original_write=os.write;closed=[]
        def fail_write(fd,data):
            if data==b'part':raise OSError(errno.ENOSPC,'original')
            return original_write(fd,data)
        def fail_close(fd):
            if __import__('stat').S_ISREG(os.fstat(fd).st_mode):
                closed.append(fd);original_close(fd);raise OSError(errno.EIO,'close')
            return original_close(fd)
        # Failure injection only around stream payload; receipt uses the same
        # wrapper and may also fail, but ENOSPC must remain the original errno.
        with patch('os.write',fail_write),patch('os.close',fail_close):
            result=w.run('copy',lambda:w.stream('controls/a',[b'part']))
        self.assertEqual(result['errno'],errno.ENOSPC,result)
    def test_actual_acl_roundtrip(self):
        entries=self.nested()
        import ctypes as C
        principal=uuid.UUID('12345678-1234-1234-1234-123456789abc').bytes
        import struct
        from darwin_metadata import Metadata,Attr
        meta=Metadata()
        security=struct.pack('=I',0x012cc16d)+bytes(32)+struct.pack('=II',1,0)+bytes(principal)+struct.pack('=II',1,2)
        value=struct.pack('=iI',8,len(security))+security
        attrs=Attr(5,0,0x400000,0,0,0,0);fd=os.open(self.src/'nested/file',os.O_RDONLY)
        try:meta.call('fsetattrlist',fd,C.byref(attrs),C.c_char_p(value),len(value),0)
        finally:os.close(fd)
        m=self.manifest(entries);w=self.window(m.plan());result=m.protect(w)
        (self.home/'acl-result.json').write_text(json.dumps(result))
        self.assertEqual(result['status'],'fixture_roundtrip',result)
        self.assertGreater(len(bytes.fromhex(m.records['named','nested/file']['metadata']['attributes'])),72)
    def test_fsync_and_receipt_close_failure(self):
        w=self.window({'controls/a':('file',20)})
        original_close=os.close;closes=[]
        def close(fd):
            if __import__('stat').S_ISREG(os.fstat(fd).st_mode):
                closes.append(fd);original_close(fd);raise OSError(errno.EIO,'close')
            original_close(fd)
        with patch('os.fsync',side_effect=OSError(errno.ENOSPC,'fsync')),patch('os.close',close):
            result=w.run('copy',lambda:w.stream('controls/a',[b'part']))
        self.assertEqual(result['errno'],errno.ENOSPC);self.assertFalse(result['local_error_receipt'])
        self.assertEqual(len(closes),2);self.assertEqual((w.root/'controls/a').read_bytes(),b'part');self.invariant(w)
    def test_true_interrupt_during_receipt_close(self):
        w=self.window({'controls/a':('file',20)})
        original=os.close
        def close(fd):
            if __import__('stat').S_ISREG(os.fstat(fd).st_mode):
                original(fd);raise KeyboardInterrupt()
            original(fd)
        with patch('os.close',close):
            with self.assertRaises(KeyboardInterrupt):w.run('copy',lambda:w.stream('controls/a',[b'part']))
        self.assertTrue(w.stopped);self.invariant(w)
    def test_metadata_failure_preserves_storage_and_charge(self):
        m=self.manifest(self.nested());w=self.window(m.plan())
        with patch.object(m.meta,'restore',side_effect=OSError(errno.EIO,'metadata')):result=m.protect(w)
        self.assertEqual(result['stage'],'restore');self.assertEqual(result['errno'],errno.EIO)
        self.assertEqual((w.root/'pre-adoption/named/nested/file').read_bytes(),b'payload'*100)
        self.assertEqual((w.root/'restore-check/named/nested/file').read_bytes(),b'payload'*100)
        self.assertTrue(any(v['charged'] for k,v in w.snapshot()['slots'].items() if k.startswith('controls/native-')));self.invariant(w)
    def test_inherited_xattr_is_not_silently_deleted(self):
        entries=self.nested();m=self.manifest(entries);w=self.window(m.plan())
        original=m.meta.xattrs
        with patch.object(m.meta,'xattrs',return_value=[('616263','')]):result=m.protect(w)
        self.assertEqual(result['code'],'metadata');self.assertTrue(w.stopped);self.invariant(w)
    def test_unknown_commit_and_no_resume(self):
        w=Window(self.home,'retained',{'controls/error':('file',256)},commit='unknown');self.windows.append(w)
        self.assertEqual(w.snapshot()['commit_state'],'unknown')
        with self.assertRaises(FileExistsError):Window(self.home,'retained',{'controls/error':('file',256)},commit='unknown')
        self.assertFalse(w.snapshot()['retry_b_allowed'])
    def test_destination_collision_does_not_overwrite(self):
        w=self.window({'controls/a':('file',20)})
        (w.root/'controls/a').write_bytes(b'sentinel')
        r=w.run('copy',lambda:w.stream('controls/a',[b'new']))
        self.assertEqual(r['status'],'unverified');self.assertEqual((w.root/'controls/a').read_bytes(),b'sentinel')
        self.assertEqual(w.snapshot()['slots']['controls/a']['charged'],20);self.invariant(w)
    def test_interrupted_iterator_close(self):
        w=self.window({'controls/a':('file',20)})
        class Chunks:
            def __init__(self):self.sent=False
            def __iter__(self):return self
            def __next__(self):
                if self.sent:raise StopIteration()
                self.sent=True;return b'part'
            def close(self):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):w.run('copy',lambda:w.stream('controls/a',Chunks()))
        self.assertTrue(w.stopped);self.assertEqual((w.root/'controls/a').read_bytes(),b'part');self.invariant(w)
    def test_unknown_metadata_and_flags_stop(self):
        entries=self.nested();os.chflags(self.src/'nested/file',2) # fixture immutable
        try:
            with self.assertRaises(Stop):self.manifest(entries)
        finally:os.chflags(self.src/'nested/file',0) # fixture-only release after recorded refusal
    def test_bounded_serialization_parser(self):
        with self.assertRaises(Stop):bounded_json({'x':'a'*100},10)
        for raw in [b'{"a":1,"a":2}',b'['*20+b'0'+b']'*20,b'{"count":NaN}',b'{"n":1.5}']:
            with self.assertRaises(Stop):parse_json(raw)
        w=self.window({'controls/json':('file',10)})
        r=w.run('serialize',lambda:w.stream('controls/json',[bounded_json({'x':'a'*100},10)]))
        self.assertEqual(r['code'],'limit');self.assertFalse((w.root/'controls/json').exists())
    def http(self,response,seconds=.2,delay=None):
        client,server=socket.socketpair();errors=[]
        def serve():
            try:
                server.recv(4096)
                if delay:
                    for part in response:
                        server.sendall(part);time.sleep(delay)
                else:server.sendall(response)
            except (BrokenPipeError,ConnectionResetError):pass
            finally:server.close()
        thread=threading.Thread(target=serve);thread.start()
        request=b'GET /api/lora-train/status HTTP/1.1\r\nHost: 127.0.0.1:8001\r\nConnection: close\r\nAccept-Encoding: identity\r\n\r\n'
        w=self.window({'controls/http':('file',4096),'controls/request-pre-training':('native',len(request))})
        start=time.monotonic();r=Observations(w).http('pre-training',client,'controls/http',seconds=seconds);elapsed=time.monotonic()-start
        thread.join(timeout=2);self.assertFalse(thread.is_alive());self.invariant(w)
        return w,r,elapsed
    def test_http_training_null_missing_and_wire(self):
        for extra in ('',',"durable":null'):
            body=('{"status":"idle","current_job":null,"queue":[]'+extra+'}').encode()
            head=b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'
            w,r,_=self.http(head+body);self.assertEqual(r['status'],'captured',r)
            self.assertIsNone(r['projection']['durable']);self.assertEqual(r['projection']['durable_present'],bool(extra));self.assertEqual(r['wire_bytes'],len(head+body))
    def test_http_framing_header_body_overrun(self):
        for data in [b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\nx',
                     b'HTTP/1.1 200 OK\r\nContent-Length: 9999999\r\n\r\n',
                     b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nContent-Length: 0\r\n\r\n',
                     b'HTTP/1.1 200 OK\r\nX: '+b'x'*70000+b'\r\n\r\n',
                     b'HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\n{}']:
            w,r,_=self.http(data);self.assertEqual(r['status'],'unverified');self.assertFalse((w.root/'controls/http').exists())
    def test_http_total_deadline_slow_headers_and_body(self):
        for parts in [[b'H',b'T',b'T',b'P'],[b'HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n',b'a',b'b',b'c']]:
            w,r,elapsed=self.http(parts,seconds=.12,delay=.08);self.assertEqual(r['code'],'deadline');self.assertLess(elapsed,.5)
    def test_capture_partial_enospc(self):
        w=self.window({'controls/stdout':('file',32),'controls/stderr':('file',32),'controls/result':('file',1024)})
        original=os.write
        def fail(fd,data):
            if data==b'123\n':
                original(fd,data[:2]);raise OSError(errno.ENOSPC,'fixture')
            return original(fd,data)
        with patch('os.write',fail):r=capture_fixture(w,'ok','controls/stdout','controls/stderr','controls/result',self.home,seconds=.3)
        self.assertEqual(r['errno'],errno.ENOSPC);self.assertEqual(r['stage'],'capture')
        self.assertEqual((w.root/'controls/stdout').read_bytes(),b'12');self.assertFalse((w.root/'controls/result').exists());self.invariant(w)
    def test_socket_close_error_preserves_deadline(self):
        client,server=socket.socketpair()
        class Closing:
            def fileno(self):return client.fileno()
            def setblocking(self,value):client.setblocking(value)
            def send(self,value):return client.send(value)
            def recv(self,n):return client.recv(n)
            def close(self):client.close();raise OSError(errno.EIO,'close')
        request=b'GET /api/lora-train/status HTTP/1.1\r\nHost: 127.0.0.1:8001\r\nConnection: close\r\nAccept-Encoding: identity\r\n\r\n'
        w=self.window({'controls/http':('file',4096),'controls/request-pre-training':('native',len(request))})
        try:r=Observations(w).http('pre-training',Closing(),'controls/http',seconds=.01)
        finally:server.close()
        self.assertEqual(r['code'],'deadline',r);self.invariant(w)
    def test_subprocess_success_no_match_error_timeout_overflow(self):
        for name,outcome in [('ok','success'),('no-match','no_match'),('error','error'),('timeout','deadline'),('overflow','limit')]:
            w=self.window({'controls/stdout':('file',32),'controls/stderr':('file',32),'controls/result':('file',1024)})
            r=capture_fixture(w,name,'controls/stdout','controls/stderr','controls/result',self.home,seconds=.15)
            self.assertEqual(r.get('outcome',r.get('code')),outcome,r)
            if outcome in('deadline','limit'):self.assertTrue(w.stopped);self.assertFalse((w.root/'controls/result').exists())
            self.invariant(w)

class RepairCases(unittest.TestCase):
    """Actual owned effects at the four repaired API boundaries."""
    def setUp(self):
        self.home=PARENT/self._testMethodName;self.home.mkdir(mode=0o700);self.windows=[]
    def tearDown(self):
        for w in self.windows:w.close()
    def window(self,extra=None):
        slots={'controls/error':('file',256),'recovery/held':('file',9)};slots.update(extra or {})
        w=Window(self.home,'output-'+str(len(self.windows)),slots,commit='unknown');self.windows.append(w);return w
    def accounting(self,w):
        s=w.snapshot();self.assertEqual(s['charged']+s['reserved_remaining'],s['plan_total']);self.assertEqual(s['slots']['recovery/held']['reserved'],9)
        self.assertFalse(s['protection_verified'] or s['source_start_allowed'] or s['retry_b_allowed']);self.assertEqual(s['commit_state'],'unknown')
        (self.home/('accounting-'+w.name+'.json')).write_text(json.dumps(s,indent=2));return s
    @staticmethod
    def opened(fd):
        try:os.fstat(fd);return True
        except OSError:return False
    def test_receipt_fsync_only_does_not_inherit_outer_error(self):
        w=self.window({'controls/a':('file',20)});new=w.new_file;write=os.write;fsync=os.fsync;receipt=[None];syncs=[]
        def track(p):
            fd=new(p)
            if p=='controls/error':receipt[0]=fd
            return fd
        def fail_write(fd,data):
            if data==b'next':raise OSError(errno.ENOSPC,'private original')
            return write(fd,data)
        def sync(fd):
            syncs.append(fd)
            if fd==receipt[0]:raise OSError(errno.EIO,'private receipt')
            return fsync(fd)
        with patch.object(w,'new_file',track),patch('os.write',fail_write),patch('os.fsync',sync):r=w.run('copy',lambda:w.stream('controls/a',[b'part',b'next']))
        self.assertEqual((r['stage'],r['errno'],r['commit_state']),('copy',errno.ENOSPC,'unknown'));self.assertFalse(r['local_error_receipt']);self.assertIsNotNone(r['native_fallback']);self.assertNotIn('private',json.dumps(r))
        self.assertEqual((w.root/'controls/a').read_bytes(),b'part');self.assertFalse(self.opened(receipt[0]));self.assertEqual(syncs,[receipt[0]]);self.assertEqual(self.accounting(w)['slots']['controls/error']['charged'],256)
    def test_direct_mutating_entries_cannot_bypass_stop(self):
        w=self.window({'controls/a':('file',8),'controls/later':('file',8),'controls/dir':('dir',0),'controls/native':('native',3)})
        fd=w.new_file('controls/a');w.write(fd,'controls/a',b'part',0)
        w.run('copy',lambda:(_ for _ in ()).throw(Stop('hash')));before=w.snapshot();called=[]
        entries=[lambda:w.stream('controls/later',[b'later']),lambda:w.new_file('controls/later'),lambda:w.claim('controls/later','file'),lambda:w.mkdir('controls/dir'),lambda:w.effect('controls/native',3,lambda:called.append(True)),lambda:w.write(fd,'controls/a',b'x',4),lambda:w.stream('controls/error',[b'x'])]
        try:
            for action in entries:
                with self.assertRaises(Stop):action()
            self.assertEqual(w.snapshot(),before);self.assertEqual(called,[]);self.assertEqual((w.root/'controls/a').read_bytes(),b'part');self.assertFalse((w.root/'controls/later').exists());self.assertFalse((w.root/'controls/dir').exists());self.accounting(w)
        finally:os.close(fd)
    def test_direct_interruption_latches_and_nested_calls_work(self):
        w=self.window({'controls/a':('file',8),'controls/later':('file',8)})
        def interrupted():yield b'part';raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):w.stream('controls/a',interrupted())
        self.assertTrue(w.stopped)
        with self.assertRaises(Stop):w.stream('controls/later',[b'later'])
        self.assertFalse((w.root/'controls/later').exists());self.assertEqual((w.root/'controls/a').read_bytes(),b'part');self.accounting(w)
        other=self.window({'controls/a':('file',8),'controls/native':('native',1)})
        r=other.run('copy',lambda:other.effect('controls/native',1,lambda:other.stream('controls/a',[b'ok'])))
        self.assertEqual(r['bytes'],2);self.assertFalse(other.stopped);self.accounting(other)
    def test_parallel_entries_reject_without_charges_or_callbacks(self):
        w=self.window({'controls/a':('file',8),'controls/later':('file',8),'controls/dir':('dir',0),'controls/native':('native',3)})
        fd=w.new_file('controls/a');entered=threading.Event();release=threading.Event();errors=[];called=[]
        def owner():
            try:w.run('copy',lambda:(entered.set(),release.wait(2)))
            except BaseException as e:errors.append(type(e).__name__)
        thread=threading.Thread(target=owner);thread.start();self.assertTrue(entered.wait(1));before=w.snapshot()
        a,b=socket.socketpair()
        try:
            actions=[lambda:w.stream('controls/later',[b'x']),lambda:w.new_file('controls/later'),lambda:w.claim('controls/later','file'),lambda:w.mkdir('controls/dir'),lambda:w.effect('controls/native',3,lambda:called.append(True)),lambda:w.write(fd,'controls/a',b'x',0),lambda:w.run('copy',lambda:called.append(True)),lambda:w.close()]
            for action in actions:
                with self.assertRaisesRegex(Stop,'^busy$'):action()
            with self.assertRaisesRegex(Stop,'^busy$'):Observations(w).http('pre-training',a,'controls/later',seconds=.01)
            self.assertEqual(a.fileno(),-1);self.assertEqual(b.recv(1),b'');self.assertEqual(w.snapshot(),before);self.assertEqual(called,[]);self.assertFalse((w.root/'controls/later').exists());self.assertEqual((w.root/'controls/a').read_bytes(),b'');self.accounting(w)
        finally:release.set();thread.join(2);a.close();b.close();os.close(fd)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertFalse(w.stopped)
    def test_http_rejected_close_uncertainty_and_interruption(self):
        for kind in ('stopped','plan','interrupt'):
            with self.subTest(kind=kind):
                w=self.window({'controls/http':('file',32)})
                if kind!='plan':w.run('copy',lambda:(_ for _ in ()).throw(Stop('hash')))
                a,b=socket.socketpair();calls=[];cancel=KeyboardInterrupt('synthetic cancellation')
                class Owned:
                    def close(self):
                        calls.append('close')
                        if kind=='interrupt':raise cancel
                        raise OSError(errno.EIO,'private uncertain close')
                    def setblocking(self,value):calls.append('setblocking');a.setblocking(value)
                    def send(self,value):calls.append('send');return a.send(value)
                try:
                    if kind=='interrupt':
                        with self.assertRaises(KeyboardInterrupt) as caught:Observations(w).http('pre-training',Owned(),'controls/http',seconds=.01)
                        self.assertIs(caught.exception,cancel)
                    else:
                        r=Observations(w).http('pre-training',Owned(),'controls/http',seconds=.01)
                        self.assertEqual(r['code'],kind);self.assertEqual(r.get('owned_socket_close'),'unknown');self.assertNotIn('private',json.dumps(r))
                    self.assertEqual(calls.count('close'),1);self.assertNotIn('send',calls);self.assertTrue(w.stopped);self.assertTrue(a.fileno()>=0)
                    b.setblocking(False)
                    with self.assertRaises(BlockingIOError):b.recv(1)
                    if kind!='plan':self.assertEqual(w.observation_used,set())
                    state={'case':kind,'calls':calls,'socket_still_open':a.fileno()>=0,'result':r if kind!='interrupt' else None,'accounting':self.accounting(w)}
                    (self.home/('http-'+kind+'.json')).write_text(json.dumps(state,indent=2));self.assertNotIn('controls/http',w.used)
                finally:a.close();b.close() # fixture-only closure after recording uncertainty
    def capture_cleanup(self,phase,operation_interrupt=False):
        import observe
        w=self.window({'controls/out':('file',16),'controls/err':('file',16),'controls/result':('file',512)})
        children=[];fds=[];popen=observe.subprocess.Popen;new=w.new_file;selector=observe.selectors.DefaultSelector;close=os.close;write=w.write
        original=KeyboardInterrupt('original');later=KeyboardInterrupt('cleanup');attempts=[]
        def track(p):
            fd=new(p);fds.append(fd);return fd
        def interrupted_write(fd,p,data,pos):
            n=write(fd,p,data,pos)
            if operation_interrupt:raise original
            return n
        def start(*a,**kw):
            child=popen(*a,**kw);children.append(child)
            if phase=='kill':
                kill=child.kill
                def interrupt_kill():attempts.append('kill');kill();raise later
                child.kill=interrupt_kill
            if phase=='pipe':
                pipeclose=child.stdout.close
                def interrupt_pipe():attempts.append('stdout');pipeclose();raise later
                child.stdout.close=interrupt_pipe
            return child
        class Selector:
            def __init__(self):self.inner=selector()
            def register(self,*a,**kw):return self.inner.register(*a,**kw)
            def unregister(self,*a,**kw):return self.inner.unregister(*a,**kw)
            def get_map(self):return self.inner.get_map()
            def select(self,*a,**kw):return self.inner.select(*a,**kw)
            def close(self):
                self.inner.close()
                if phase=='selector':attempts.append('selector');raise later
        def interrupt_fd(fd):
            close(fd)
            if phase=='fd' and fds and fd==fds[0]:attempts.append('fd');raise later
        try:
            with patch.object(observe.subprocess,'Popen',start),patch.object(w,'new_file',track),patch.object(w,'write',interrupted_write),patch.object(observe.selectors,'DefaultSelector',Selector),patch('os.close',interrupt_fd):
                with self.assertRaises(KeyboardInterrupt) as caught:capture_fixture(w,'timeout','controls/out','controls/err','controls/result',self.home,seconds=.08)
            self.assertIs(caught.exception,original if operation_interrupt else later);self.assertEqual(len(attempts),1)
            self.assertEqual((w.root/'controls/out').read_bytes(),b'partial');self.assertIsNotNone(children[0].returncode);self.assertTrue(children[0].stdout.closed and children[0].stderr.closed);self.assertFalse(any(self.opened(fd) for fd in fds));self.assertTrue(w.stopped);self.assertFalse((w.root/'controls/result').exists())
            state={'phase':phase,'operation_interrupt':operation_interrupt,'child_returncode':children[0].returncode,'stdout_closed':children[0].stdout.closed,'stderr_closed':children[0].stderr.closed,'payload_fds_open':[self.opened(fd) for fd in fds],'partial':(w.root/'controls/out').read_bytes().decode(),'cleanup_interrupt_attempts':attempts,'accounting':self.accounting(w)}
            (self.home/'cleanup-state.json').write_text(json.dumps(state,indent=2));self.assertEqual(state['accounting']['charged'],32)
        finally:
            for child in children:
                if child.poll() is None:subprocess.Popen.kill(child);child.wait(timeout=.5)
                for pipe in (child.stdout,child.stderr):
                    if not pipe.closed:pipe.close()
            for fd in fds:
                if self.opened(fd):close(fd)
    def test_capture_cleanup_pipe_interrupt_finishes_remaining(self):self.capture_cleanup('pipe')
    def test_capture_cleanup_fd_interrupt_finishes_remaining(self):self.capture_cleanup('fd')
    def test_capture_cleanup_kill_interrupt_still_reaps(self):self.capture_cleanup('kill')
    def test_capture_preserves_original_interrupt_after_cleanup_interrupt(self):self.capture_cleanup('selector',True)

if __name__ == '__main__':
    unittest.main(verbosity=2)
