"""Closed cooperative M1 ledger. No production authority, quota or crash resume."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading
from types import MappingProxyType

CAP = 128849018880
CHUNK = 65536
STAGES = {'pre-adoption', 'restore-check', 'post-B-state', 'post-start-state', 'controls', 'temp', 'recovery'}
COMMITS = {'not_attempted', 'known_not_committed', 'known_committed', 'unknown'}
CODES = {'plan', 'limit', 'path', 'alias', 'collision', 'drift', 'type', 'metadata',
         'unsupported', 'hash', 'short_write', 'os_error', 'protocol', 'deadline',
         'schema', 'capture', 'stopped', 'busy', 'input', 'cleanup'}

class Stop(ValueError):
    pass

def integer(n):
    if type(n) is not int or not 0 <= n <= CAP:
        raise Stop('plan')
    return n

def path_parts(s):
    if type(s) is not str or not 1 <= len(s.encode('utf-8')) <= 1024:
        raise Stop('path')
    p = s.split('/')
    if len(p) > 16 or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', x) or x in ('.', '..') for x in p):
        raise Stop('path')
    return p

def directory(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise Stop('path')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for p in path.parts[1:]:
            other = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            old, fd = fd, other
            os.close(old)
        return fd
    except BaseException:
        close_once(fd)
        raise

def close_once(fd):
    """Preserve an active operation error; never retry an uncertain close."""
    active=sys.exc_info()[1]
    try:os.close(fd)
    except Exception:
        if active is None:raise


def finish_owned(actions, error=None):
    """Attempt each owned finalizer once, retaining the local operation error.

    Cancellation wins over ordinary errors; an original cancellation wins over
    later cleanup cancellation. Callers pass their OWN error, never ambient state.
    """
    first = None
    for action in actions:
        try: action()
        except BaseException as e:
            if first is None or (isinstance(first, Exception) and not isinstance(e, Exception)):
                first = e
    if first is not None and (error is None or (isinstance(error, Exception) and not isinstance(first, Exception))):
        raise first


def inode(st):
    return st.st_dev, st.st_ino

def bounded_json(value, limit):
    """Validate before encoding; bounded containers/strings/integers, no custom hooks."""
    integer(limit)
    nodes = [0]
    def walk(v, depth=0):
        nodes[0] += 1
        if depth > 16 or nodes[0] > 100000:
            raise Stop('schema')
        if v is None or type(v) is bool:
            return
        if type(v) is int and -(2**63) <= v < 2**63:
            return
        if type(v) is str and len(v) <= 131072 and len(v.encode('utf-8')) <= 131072:
            return
        if type(v) in (list, tuple) and len(v) <= 100000:
            for x in v: walk(x, depth+1)
            return
        if type(v) is dict and len(v) <= 128:
            for k, x in v.items():
                if type(k) is not str or len(k.encode('utf-8')) > 255:
                    raise Stop('schema')
                walk(k, depth+1); walk(x, depth+1)
            return
        raise Stop('schema')
    walk(value)
    # iterencode avoids constructing an oversized serialized output first.
    out = bytearray()
    for piece in json.JSONEncoder(ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).iterencode(value):
        raw = piece.encode('ascii')
        if len(raw) > limit-len(out):
            raise Stop('limit')
        out.extend(raw)
    return bytes(out)

@dataclass(frozen=True)
class OperationBinding:
    """Cooperative operation/source epoch, fixed before any Window root effect."""
    operation_id: str
    epoch: str
    source_id: str

    def __post_init__(self):
        for value in (self.operation_id, self.epoch):
            if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', value):
                raise Stop('plan')
        if type(self.source_id) is not str or not re.fullmatch(r'[0-9a-f]{64}', self.source_id):
            raise Stop('plan')


class Window:
    """Slots: {relative_path: (kind, full_logical_reservation)}; dirs explicit.

    Kind file/dir/native. Native slots are effect declarations, never files.
    All slot reservations are immutable, fully admitted before root creation.
    Entire slot is charged before its first side effect; no refunds/borrowing.
    """
    def __init__(self, parent, name, slots, cap=CAP, commit='not_attempted', *, binding=None, lifetimes=None):
        if commit not in COMMITS or len(path_parts(name)) != 1:
            raise Stop('plan')
        if type(slots) is not dict or not 1 <= len(slots) <= 100000:
            raise Stop('plan')
        plan = {}
        for p, spec in slots.items():
            parts = path_parts(p)
            if len(parts) < 2 or parts[0] not in STAGES or type(spec) not in (list, tuple) or len(spec) != 2:
                raise Stop('plan')
            kind, amount = spec
            if kind not in ('file', 'dir', 'native'):
                raise Stop('plan')
            plan[p] = kind, integer(amount)
        if plan.get('controls/error') != ('file', 256):
            raise Stop('plan')
        if integer(cap) > CAP or sum(x[1] for x in plan.values()) > cap:
            raise Stop('limit')
        for p in plan:
            parts = p.split('/')
            for n in range(2, len(parts)):
                if plan.get('/'.join(parts[:n]), ('',))[0] != 'dir':
                    raise Stop('plan')
        if binding is not None:
            if commit=='unknown':raise Stop('stopped')
            if type(binding) is not OperationBinding or type(lifetimes) is not dict or set(lifetimes) != set(plan):
                raise Stop('plan')
            if any(type(v) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}',v) for v in lifetimes.values()):
                raise Stop('plan')
        elif lifetimes is not None:
            raise Stop('plan')
        self._binding=binding
        self._lifetimes=MappingProxyType(dict(lifetimes or {}))
        self._leases={}; self._child_active=None; self._close_state='open'; self._mutation_depth=0
        digest=hashlib.sha256()
        if binding is not None:
            for p,v in sorted(plan.items()):
                digest.update(bounded_json([p,*v,self._lifetimes[p]],4096));digest.update(b'\n')
        self._plan_digest=digest.hexdigest() if binding is not None else None
        self._plan = MappingProxyType(plan)
        self.charged = {}; self.used = set(); self.stopped = False
        self.commit = commit; self.receipt = None; self.lock = threading.RLock(); self._running=False; self._receipt_owner=None; self.observation_used=set(); self.phase='copy'; self.sealed=set()
        self.parent = Path(parent); self.name = name; self.root = self.parent/name
        self.fds = {}; self.ids = {}; self.parent_fd = directory(parent)
        self.parent_id = inode(os.fstat(self.parent_fd)); self.root_fd = None
        try:
            os.mkdir(name, 0o700, dir_fd=self.parent_fd)
            self.root_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.parent_fd)
            self.root_id = inode(os.fstat(self.root_fd))
            if stat.S_IMODE(os.fstat(self.root_fd).st_mode) != 0o700:
                raise Stop('metadata')
            from darwin_metadata import Metadata
            import struct
            if struct.unpack_from('=iI',Metadata().attributes(self.root_fd),64)[1]!=0:
                raise Stop('unsupported')
            # Structural stage dirs have explicit zero logical-payload effects;
            # their physical allocation is NOT bounded by this ledger.
            for stage in sorted(STAGES if any(p.startswith('post-start-state/') for p in plan) else STAGES-{'post-start-state'}):
                os.mkdir(stage, 0o700, dir_fd=self.root_fd)
                fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.root_fd)
                self.fds[stage] = fd; self.ids[stage] = inode(os.fstat(fd))
        except BaseException:
            self.close()
            raise

    @property
    def plan(self): return self._plan

    @property
    def binding(self): return self._binding

    @property
    def lifetimes(self): return self._lifetimes

    @property
    def stopped(self): return self._stopped

    @stopped.setter
    def stopped(self, value):
        if type(value) is not bool: raise Stop('plan')
        if self.binding is not None and getattr(self,'_stopped',False) and not value:
            raise Stop('stopped')
        self._stopped=value

    @property
    def commit(self): return self._commit

    @commit.setter
    def commit(self, value):
        if value not in COMMITS: raise Stop('plan')
        if self.binding is not None and getattr(self,'_commit','not_attempted')!='not_attempted' and value!=self._commit:
            raise Stop('stopped')
        self._commit=value
        if self.binding is not None and value=='unknown': self.stopped=True

    def reserve_child(self, binding):
        """Issue exactly one nontransferable capture view; no slot is charged twice."""
        from reservation import reserve
        return reserve(self,binding)

    def _charge(self, p, kind, lease=None):
        # Caller has validated the pinned roots; this method acquires no FD.
        with self._mutation(p,lease):
            if p not in self.plan or self.plan[p][0]!=kind or p in self.used:
                raise Stop('plan')
            self.used.add(p); self.charged[p]=self.plan[p][1]

    @contextmanager
    def _mutation(self, p, lease=None):
        if not self.lock.acquire(False):
            raise Stop('busy')
        try:
            if self._child_active is not None and self._child_active is not lease:
                raise Stop('busy')
            if p in self._leases and self._leases[p] is not lease:
                raise Stop('plan')
            if self.binding is not None and self.commit=='unknown': self.stopped=True
            # Only the internal, one-shot failure receipt may cross the latch.
            if self.stopped and not (p == 'controls/error' and self._receipt_owner == threading.get_ident()):
                raise Stop('stopped')
            self._mutation_depth+=1
            try:
                yield
            except BaseException:
                self.stopped = True
                raise
            finally:
                self._mutation_depth-=1
        finally:
            self.lock.release()

    def snapshot(self):
        total = sum(v[1] for v in self.plan.values()); charged = sum(self.charged.values())
        result=dict(plan_total=total, charged=charged, reserved_remaining=total-charged,
                    slots={p: {'charged': self.charged.get(p, 0), 'reserved': v[1]-self.charged.get(p, 0)} for p,v in self.plan.items()},
                    stopped=self.stopped, commit_state=self.commit, protection_verified=False,
                    source_start_allowed=False, retry_b_allowed=False)
        if self.binding is not None:
            result.update(closure_state=self._close_state,binding={'operation_id':self.binding.operation_id,'epoch':self.binding.epoch,'source_id':self.binding.source_id,'parent_plan_sha256':self._plan_digest,'parent_root_identity':[str(n) for n in self.root_id]})
        return result

    def roots(self):
        fd = directory(self.parent)
        try:
            if inode(os.fstat(fd)) != self.parent_id or inode(os.stat(self.name, dir_fd=fd, follow_symlinks=False)) != self.root_id:
                raise Stop('drift')
            st = os.fstat(self.root_fd)
            if not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o700:
                raise Stop('drift')
        finally:
            close_once(fd)

    def parent_for(self, p):
        self.roots(); parts = path_parts(p); current = parts[0]
        for child in parts[1:-1]:
            old = current; current += '/'+child
            if current not in self.fds:
                raise Stop('plan')
            st = os.stat(child, dir_fd=self.fds[old], follow_symlinks=False)
            if inode(st) != self.ids[current] or not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode)!=0o700 or current in self.sealed:
                raise Stop('drift')
        # Recheck the stage itself, not just its open FD.
        st = os.stat(parts[0], dir_fd=self.root_fd, follow_symlinks=False)
        if inode(st) != self.ids[parts[0]] or stat.S_IMODE(st.st_mode) != 0o700:
            raise Stop('drift')
        return self.fds['/'.join(parts[:-1])], parts[-1]

    def claim(self, p, kind):
        with self._mutation(p):
            if p not in self.plan or self.plan[p][0] != kind or p in self.used:
                raise Stop('plan')
            self.roots(); self._charge(p,kind)

    def mkdir(self, p):
        with self._mutation(p):
            self.claim(p, 'dir'); fd, name = self.parent_for(p)
            os.mkdir(name, 0o700, dir_fd=fd)
            other = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            self.fds[p] = other; self.ids[p] = inode(os.fstat(other))
            if stat.S_IMODE(os.fstat(other).st_mode) != 0o700:
                raise Stop('metadata')

    def new_file(self, p):
        with self._mutation(p):
            self.claim(p, 'file'); fd, name = self.parent_for(p)
            out = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            if stat.S_IMODE(os.fstat(out).st_mode) != 0o600:
                os.close(out); raise Stop('metadata')
            return out

    def write(self, fd, p, data, position):
        with self._mutation(p):
            if type(data) is not bytes or len(data) > CHUNK or position+len(data) > self.plan[p][1]:
                raise Stop('limit')
            parent, name = self.parent_for(p)
            st = os.fstat(fd); named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if inode(st) != inode(named) or not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size != position or stat.S_IMODE(st.st_mode) != 0o600:
                raise Stop('drift')
            if os.write(fd, data) != len(data):
                raise Stop('short_write')
            return position+len(data)

    def stream(self, p, chunks, expected=None):
        with self._mutation(p):
            fd = self.new_file(p); digest = hashlib.sha256(); position = 0; iterator=None; error=None
            try:
                iterator=iter(chunks)
                for raw in iterator:
                    position = self.write(fd,p,raw,position); digest.update(raw)
                os.fsync(fd); os.lseek(fd,0,0); actual = hashlib.sha256()
                for _ in range((position+CHUNK-1)//CHUNK):
                    raw = os.read(fd,min(CHUNK,position-(os.lseek(fd,0,1))))
                    actual.update(raw)
                if os.lseek(fd,0,1) != position or os.read(fd,1) or actual.digest() != digest.digest() or (expected is not None and digest.hexdigest() != expected):
                    raise Stop('hash')
                # Zero-byte write performs the final path/inode/length check without a new syscall.
                self.check_file(fd,p,position)
            except BaseException as e:
                error=e
                raise
            finally:
                def close_iterator():
                    close=getattr(iterator,'close',None)
                    if close is not None:close()
                finish_owned((close_iterator, lambda:os.close(fd)), error)
            return {'bytes':position,'sha256':digest.hexdigest()}

    def check_file(self, fd, p, position):
        with self._mutation(p):
            parent,name=self.parent_for(p);st=os.fstat(fd);named=os.stat(name,dir_fd=parent,follow_symlinks=False)
            if inode(st)!=inode(named) or not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size!=position or stat.S_IMODE(st.st_mode)!=0o600:
                raise Stop('drift')

    def effect(self,p,declared_bytes, action):
        """Cooperative native binding: precharge before the reviewed callback."""
        with self._mutation(p):
            if self.plan.get(p) != ('native', declared_bytes):
                raise Stop('plan')
            self.claim(p,'native'); return action()

    def _failure(self,stage,error):
        self.stopped=True
        code=str(error) if type(error) is Stop and str(error) in CODES else 'os_error' if isinstance(error,OSError) else 'input'
        number=getattr(error,'errno',None)
        number=number if type(number)is int and 0<=number<=65535 else None
        if self.receipt is None:
            self.receipt=False
            raw=('stage='+stage+';commit='+self.commit+';code='+code).encode('ascii').ljust(256,b' ')
            self._receipt_owner=threading.get_ident()
            try:
                self.stream('controls/error',[raw]);self.receipt=True
            except Exception:
                pass
            finally:
                self._receipt_owner=None
        return {'status':'unverified','stage':stage,'code':code,'errno':number,'commit_state':self.commit,
                'local_error_receipt':self.receipt,'native_fallback':None if self.receipt else 'stage='+stage+';commit='+self.commit+';code='+code+';local_receipt=failed',
                'protection_verified':False,'source_start_allowed':False,'retry_b_allowed':False}

    def run(self,stage,action):
        if stage not in ('copy','restore','capture','serialize','metadata'):
            raise Stop('input')
        if not self.lock.acquire(False):
            raise Stop('busy')
        try:
            if self._running or self._child_active is not None or self._mutation_depth:raise Stop('busy')
            self._running=True
            try:
                if self.stopped:return self._failure(stage,Stop('stopped'))
                self.phase=stage
                try:
                    return action()
                except Exception as e:
                    return self._failure(self.phase,e)
                except BaseException:
                    self.stopped=True;raise
            finally:
                self._running=False
        finally:
            self.lock.release()

    def close(self):
        if not self.lock.acquire(False):raise Stop('busy')
        try:
            if self._child_active is not None or self._mutation_depth:raise Stop('busy')
            if self._close_state in ('closed','unknown'):return
            self.stopped=True;self._close_state='unknown';actions=[]
            for p in list(self.fds):
                fd=self.fds.pop(p);actions.append(lambda fd=fd:os.close(fd))
            for a in ('root_fd','parent_fd'):
                fd=getattr(self,a,None);setattr(self,a,None)
                if fd is not None:actions.append(lambda fd=fd:os.close(fd))
            finish_owned(actions)
            self._close_state='closed'
        finally:
            self.lock.release()
