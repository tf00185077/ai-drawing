"""Strict single-owner attempt journal. Unfinished intent is a no-resend hold.

Provisioning is an explicit offline action for a new history, never a loader
fallback or migration. Restoring old state requires a separate owner decision;
no local journal can detect a consistently rolled-back filesystem checkpoint.
"""
from __future__ import annotations
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import uuid


class StoreError(Exception):
    pass


def _path(path, binding):
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.parent.is_dir():
        raise StoreError('absolute existing state root required')
    if any(v.is_symlink() for v in p.parents):
        # /var is a standard system alias; callers bind the resolved path instead.
        raise StoreError('state path aliases forbidden')
    if set(binding) != {'cwd', 'root', 'config', 'source'} or not all(isinstance(v,str) and v for v in binding.values()):
        raise StoreError('state binding required')
    if str(Path.cwd().resolve()) != binding['cwd'] or str(p.parent.resolve()) != binding['root']:
        raise StoreError('cwd/state root binding mismatch')
    return p


def _atomic(path, data):
    temporary = path.parent / ('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(data, stream, sort_keys=True, separators=(',',':'))
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,path)
        fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        if temporary.exists(): temporary.unlink()


class AttemptStore:
    @classmethod
    def provision(cls, path, *, binding):
        path = _path(path, binding)
        # Same ownership lock as loader; never replace an existing history.
        lock = cls._acquire(path)
        try:
            anchor=path.with_name(path.name+'.checkpoint')
            if path.exists() or anchor.exists(): raise StoreError('history already exists')
            data={'schema_version':1,'ledger_id':str(uuid.uuid4()),'binding':binding,'attempts':{}}
            _atomic(path,data)
            _atomic(anchor,{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        except OSError as exc:
            raise StoreError('state provisioning failed') from exc
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN); os.close(lock)

    @staticmethod
    def _acquire(path):
        lock_path=path.with_name(path.name+'.owner')
        fd=None
        try:
            fd=os.open(lock_path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return fd
        except OSError as exc:
            if fd is not None:os.close(fd)
            raise StoreError('state owner unavailable') from exc

    def __init__(self, path, *, binding):
        self._path = _path(path,binding)
        self._anchor=self._path.with_name(self._path.name+'.checkpoint')
        self._binding=deepcopy(binding)
        self._lock=self._acquire(self._path)
        self._failed=False
        try:
            self._data=self._load()
            self._identity=self._path.stat().st_ino
        except BaseException:
            self.close();raise

    def _load(self):
        try:
            if self._path.is_symlink():raise ValueError()
            if self._anchor.is_symlink():raise ValueError()
            raw=self._path.read_bytes()
            anchor=json.loads(self._anchor.read_text(encoding='utf-8'))
            if anchor != {'sha256':hashlib.sha256(raw).hexdigest()}:raise ValueError()
            data=json.loads(raw)
            if data.get('schema_version') != 1 or data.get('binding') != self._binding or not isinstance(data.get('ledger_id'),str) or not data['ledger_id']:
                raise ValueError()
            attempts=data['attempts']
            if not isinstance(attempts,dict):raise ValueError()
            for aid,a in attempts.items():
                if (not isinstance(aid,str) or not isinstance(a,dict)
                    or a.get('status') not in ('intent','complete')
                    or not all(isinstance(a.get(k),str) and a[k] for k in ('key','job_id','destination','epoch'))
                    or type(a.get('sequence')) is not int or a['sequence']<1
                    or not isinstance(a.get('message_ids'),list)
                    or not all(isinstance(m,str) and m for m in a['message_ids'])
                    or (a['status']=='complete' and (type(a.get('artifact_count')) is not int or a['artifact_count']<0 or not a['message_ids']))):
                    raise ValueError()
            return data
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise StoreError('state missing, corrupt, legacy or incorrectly bound') from exc

    def _check(self):
        if self._failed or self._lock is None:raise StoreError('state held after I/O/close')
        try:
            _path(self._path,self._binding)
            if self._path.stat().st_ino != self._identity or self._load()!=self._data:
                raise StoreError('state replacement/restore hold')
        except (OSError,StoreError) as exc:
            self._failed=True
            raise StoreError('state changed; hold') from exc

    def _save(self,data):
        self._check()
        try:
            _atomic(self._path,data)
            _atomic(self._anchor,{'sha256':hashlib.sha256(self._path.read_bytes()).hexdigest()})
            self._identity=self._path.stat().st_ino
            self._data=data
        except (OSError,ValueError,TypeError) as exc:
            self._failed=True
            raise StoreError('state persistence failed; hold') from exc

    @property
    def uncertain_count(self):
        self._check()
        return sum(a['status']!='complete' for a in self._data['attempts'].values())

    def get(self,key):
        self._check()
        matches=[a for a in self._data['attempts'].values() if a['key']==key]
        if any(a['status']!='complete' for a in matches):raise StoreError('unfinished attempt hold')
        if not matches:return None
        a=max(matches,key=lambda a:a['sequence'])
        return tuple(a['message_ids']),a['artifact_count']

    def begin(self,key,*,job_id,destination,epoch,force=False):
        prior=self.get(key)
        # Any hold closes this owner, including attempts for a different key.
        if self.uncertain_count:raise StoreError('unfinished attempt hold')
        if prior and not force:raise StoreError('completed attempt exists')
        aid=str(uuid.uuid4());data=deepcopy(self._data)
        data['attempts'][aid]={'sequence':len(data['attempts'])+1,'key':key,'job_id':job_id,'destination':destination,
                              'epoch':epoch,'status':'intent','message_ids':[]}
        self._save(data)
        return aid

    def receipt(self,attempt,message_id):
        if not isinstance(message_id,str) or not message_id:raise StoreError('missing external receipt; hold')
        data=deepcopy(self._data);data['attempts'][attempt]['message_ids'].append(message_id)
        self._save(data)

    def complete(self,attempt,artifact_count):
        data=deepcopy(self._data);a=data['attempts'][attempt]
        if not a['message_ids'] or type(artifact_count) is not int or artifact_count<0:
            raise StoreError('incomplete receipt; hold')
        a.update(status='complete',artifact_count=artifact_count)
        self._save(data)

    def close(self):
        if self._lock is not None:
            fcntl.flock(self._lock,fcntl.LOCK_UN);os.close(self._lock);self._lock=None

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
