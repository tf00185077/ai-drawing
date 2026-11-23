"""Minimal SELECT-only durable observation; never use trainer lazy DB helpers.

Memory membership is a point-in-time snapshot, not proof of scheduler ownership.
Unsupported stores and incomplete schemas remain unknown. This does not recover jobs.
"""
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
from app.db import database

LIMIT = 50
PENDING = "(status IS NULL OR status NOT IN ('completed','failed','cancelled'))"

@contextmanager
def _reader():
    engine = database.engine
    if engine.url.get_backend_name() != 'sqlite':
        raise ValueError('unsupported observation store')
    name = engine.url.database
    if name in (None, '', ':memory:'):
        # Test/in-process SQLite has no separately reopenable durable file.
        connection = engine.raw_connection()
        try:
            yield connection
        finally:
            connection.close()
    else:
        path = Path(name)
        if not path.is_file():
            raise ValueError('observation database absent')
        # SQLite may create or update WAL shared-memory sidecars even with mode=ro.
        # Fail unknown for WAL rather than silently omit uncheckpointed state or write.
        before = path.stat()
        journal = path.with_name(path.name+'-journal')
        if journal.exists():
            raise ValueError('rollback journal requires a separately approved reader')
        with path.open('rb') as source:
            header = source.read(20)
        if len(header) >= 20 and (header[18] == 2 or header[19] == 2):
            raise ValueError('WAL observation requires a separately approved reader')
        connection = sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1', uri=True, timeout=0.25)
        try:
            # Immutable prevents all SQLite sidecar writes, including a WAL-mode
            # transition after header inspection. Reject changed/journaled files
            # after the read; never treat immutable as a valid WAL snapshot.
            connection.execute('BEGIN')
            yield connection
            after = path.stat()
            signature = lambda st: (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
            if signature(before) != signature(after) or journal.exists():
                raise ValueError('observation store changed during read')
        finally:
            connection.close()


def observe(memory_ids):
    unavailable = dict(availability='unavailable', nonterminal_total=None,
                       tracked_total=None, untracked_total=None, jobs=[],
                       limit=LIMIT, truncated=None, order='job_id_asc')
    try:
        ids = sorted(set(memory_ids))
        with _reader() as db:
            total = db.execute('SELECT COUNT(*) FROM lora_training_jobs WHERE '+PENDING).fetchone()[0]
            tracked = 0
            for start in range(0,len(ids),500):
                part = ids[start:start+500]
                tracked += db.execute('SELECT COUNT(*) FROM lora_training_jobs WHERE '+PENDING+' AND job_id IN ('+','.join('?' for _ in part)+')',part).fetchone()[0]
            rows = db.execute('SELECT job_id, status FROM lora_training_jobs WHERE '+PENDING+' ORDER BY job_id COLLATE BINARY ASC LIMIT ?', (LIMIT,)).fetchall()
        jobs=[]
        for job_id,status in rows:
            if not isinstance(job_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',job_id):
                return unavailable
            jobs.append(dict(job_id=job_id,status=status if status in {'queued','running'} else 'unknown',memory_tracked=job_id in ids))
        return dict(availability='available',nonterminal_total=total,tracked_total=tracked,
                    untracked_total=total-tracked,jobs=jobs,limit=LIMIT,
                    truncated=total>len(jobs),order='job_id_asc')
    except Exception:
        # Never expose SQL, paths, driver diagnostics, or a false zero.
        return unavailable


def contains(job_id):
    """Tri-state read after an ambiguous insertion return: present/absent/unknown."""
    try:
        with _reader() as db:
            return db.execute('SELECT 1 FROM lora_training_jobs WHERE job_id = ? LIMIT 1',(job_id,)).fetchone() is not None
    except Exception:
        return None
