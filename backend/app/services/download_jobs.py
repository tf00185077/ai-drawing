"""Bounded SQLite operation history and fenced single-Backend ownership.

No provider requests or model filesystem observations belong in status reads.
SQLite BEGIN IMMEDIATE and unique claims protect independent connections. The
process-held sidecar lock proves prior supported thread workers have exited;
neither a PID nor an elapsed time is treated as evidence of death.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import uuid
import weakref

from sqlalchemy import delete, text
from sqlalchemy.exc import OperationalError

from app.db.models import DownloadJob, DownloadComponent, DownloadClaim, DownloadedResource
from app.services.civitai_provider import CivitaiProviderError
from app.services.resource_records import safe_evidence, publish_download_state

ACTIVE = frozenset({'queued', 'running'})
MAX_COMPONENTS = 128
JOB_ID = re.compile(r'dl_[0-9a-f]{32}\Z')
KEY = re.compile(r'[A-Za-z0-9._:-]{1,128}\Z', re.ASCII)
_owners = {}
_memory_owners = weakref.WeakKeyDictionary()
_mutex = threading.RLock()


def error(code, message, *, job_id=None, resource_id=None):
    hint = 'Read the same download job before choosing an explicit new retry.'
    if job_id:
        hint = f'Read the same download job {job_id} before choosing an explicit new retry.'
    exc = CivitaiProviderError(code, message, hint=hint)
    exc.job_id = job_id
    exc.resource_id = resource_id
    return exc


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def key_digest(value):
    if value is None:
        return None
    if not isinstance(value, str) or KEY.fullmatch(value) is None:
        raise error('download_invalid_idempotency_key', 'Invalid idempotency key format')
    return digest(value)


def selection_digest(components):
    return digest(sorted(components, key=lambda item: json.dumps(item, sort_keys=True)))


def claim_keys(identity, target):
    # Separate destination and selected identity: neither a new pathname nor a
    # new provider identity can steal an already admitted resource or target.
    selected = {k: identity.get(k) for k in ('provider', 'version_id', 'civitai_file_id')}
    if not selected['civitai_file_id']:
        selected['name'] = Path(target).name
    return ['file:' + digest(selected), 'path:' + digest(os.path.normcase(os.path.abspath(target)))]


@contextmanager
def transaction(db, operation=None):
    """End a caller's read snapshot and acquire the SQLite writer within budget.

    Call only before pending changes or after rollback/commit. A foreign pending
    unit of work is an error, never silently committed or discarded.
    """
    if db.new or db.dirty or db.deleted:
        raise RuntimeError('download transaction requires a clean session')
    db.rollback()
    connection = db.connection()
    previous = connection.exec_driver_sql('PRAGMA busy_timeout').scalar()
    remaining = operation.remaining() if operation is not None else 0.1
    try:
        connection.exec_driver_sql(f'PRAGMA busy_timeout={max(0, int(remaining * 1000))}')
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        if operation is not None:
            operation.remaining()
        yield
        if operation is not None:
            operation.remaining()
        # Restore before commit, which can return the connection to the pool.
        connection.exec_driver_sql(f'PRAGMA busy_timeout={int(previous)}')
        db.commit()
    except OperationalError as exc:
        db.rollback()
        if 'locked' in str(exc).lower() or 'busy' in str(exc).lower():
            if operation is not None:
                operation.remaining()
            raise error('download_database_busy', 'Download admission database is busy') from None
        raise
    except BaseException:
        db.rollback()
        raise
    finally:
        if not connection.closed:
            connection.exec_driver_sql(f'PRAGMA busy_timeout={int(previous)}')


def owner_for(engine, operation=None):
    """Acquire and retain a kernel lock until process exit, then reconcile once.

    In-memory test databases use engine identity. Real SQLite uses its absolute
    path. The sidecar is never unlinked (unlinking would split the lock domain).
    Unsupported engines and uncertain/live ownership refuse before admission.
    """
    if engine.dialect.name != 'sqlite':
        raise error('download_owner_unsupported', 'Download ownership requires the configured SQLite Backend')
    database = engine.url.database
    remaining = operation.remaining() if operation is not None else 0.1
    acquired = _mutex.acquire(timeout=remaining)
    if not acquired:
        if operation is not None:
            operation.remaining()
        raise error('download_owner_busy', 'Download ownership initialization is busy')
    try:
        if operation is not None:
            operation.remaining()
        owners = _memory_owners if database in (None, '', ':memory:') else _owners
        identity = engine if owners is _memory_owners else os.path.abspath(database)
        known = owners.get(identity)
        if known is not None and known['pid'] == os.getpid():
            return known['token']
        handle = None
        if owners is _owners:
            path = identity + '.download-owner.lock'
            try:
                fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                handle = os.fdopen(fd, 'r+b', buffering=0)
                if os.name == 'nt':
                    import msvcrt
                    if os.fstat(fd).st_size == 0:
                        handle.write(b'0')
                    handle.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                if handle is not None:
                    handle.close()
                raise error('download_owner_live_or_uncertain', 'Another Backend owns downloads or exclusive ownership cannot be proven') from None
        token = uuid.uuid4().hex
        owners[identity] = {'pid': os.getpid(), 'token': token, 'handle': handle}
        try:
            from sqlalchemy.orm import Session
            with Session(engine) as db, transaction(db, operation):
                reconcile(db, token)
        except BaseException:
            owners.pop(identity, None)
            if handle is not None:
                handle.close()
            raise
        return token
    finally:
        _mutex.release()


def reconcile(db, token):
    # Called only after exclusive lifetime lock acquisition. No file presence,
    # wall-clock timeout or PID can convert a nonterminal operation to success.
    jobs = db.query(DownloadJob).filter(DownloadJob.status.in_(ACTIVE), DownloadJob.owner_token != token).all()
    for job in jobs:
        reason = {'code': 'download_interrupted', 'message': 'The previous Backend exited before finalizing this download operation.',
                  'hint': f'Read the same download job {job.id}; an explicit new request is required for a retry. No work was replayed.'}
        now = datetime.utcnow()
        for component in db.query(DownloadComponent).filter_by(job_id=job.id).all():
            if component.status in ACTIVE:
                component.status = 'failed'
                component.updated_at = now
                component.error_json = json.dumps(reason)
                owned = db.query(DownloadClaim).filter_by(job_id=job.id, resource_id=component.resource_id).first()
                row = db.get(DownloadedResource, component.resource_id) if owned else None
                if row is not None:
                    row.status = 'failed'
                    publish_download_state(row, 'failed', reason)
        job.status = 'failed'
        job.error_json = json.dumps(reason)
        job.finished_at = job.updated_at = now
        db.execute(delete(DownloadClaim).where(DownloadClaim.job_id == job.id))


def replay(db, selection, key):
    if key is not None:
        known = db.query(DownloadJob).filter_by(idempotency_digest=key).one_or_none()
        if known is not None:
            if known.selection_digest != selection:
                raise error('download_idempotency_conflict', 'The idempotency key is bound to a different selection or destination')
            return known
    return None


def active_claim(db, keys, selection):
    claims = db.query(DownloadClaim).filter(DownloadClaim.claim_key.in_(keys)).all()
    if not claims:
        return None
    ids = {claim.job_id for claim in claims}
    known = db.get(DownloadJob, claims[0].job_id)
    if len(ids) == 1 and known is not None and known.status in ACTIVE and known.selection_digest == selection:
        return known
    raise error('civitai_resource_active', 'A selected resource or destination already has an active owner',
                job_id=claims[0].job_id, resource_id=claims[0].resource_id)


def admit(db, *, selection, key, token, policy, rows):
    """Called inside the same writer transaction that creates/reuses resources."""
    if not 1 <= len(rows) <= MAX_COMPONENTS:
        raise error('download_package_limit', 'Selected package exceeds the bounded component limit')
    now = datetime.utcnow()
    job = DownloadJob(id='dl_' + uuid.uuid4().hex, selection_digest=selection,
        idempotency_digest=key, owner_token=token, status='queued',
        policy_json=json.dumps({'max_bytes': policy.max_bytes, 'free_space_floor_bytes': policy.free_space_floor_bytes}),
        created_at=now, updated_at=now)
    db.add(job)
    db.flush()
    for ordinal, (row, identity, target, ready) in enumerate(rows):
        db.flush()
        component = DownloadComponent(job_id=job.id, ordinal=ordinal, resource_id=row.id,
            selected_size=row.file_size, downloaded_bytes=row.file_size if ready else 0,
            status='completed' if ready else 'queued', updated_at=now,
            result_json=json.dumps({'code': 'verified_existing', 'sha256': row.sha256, 'byte_size': row.file_size}) if ready else None)
        db.add(component)
        for claim in claim_keys(identity, target):
            db.add(DownloadClaim(claim_key=claim, job_id=job.id, resource_id=row.id))
    db.flush()
    finish(db, job)
    return job


def fence(db, job_id, resource_id, token):
    job = db.query(DownloadJob).filter_by(id=job_id, owner_token=token).populate_existing().one_or_none()
    component = db.query(DownloadComponent).filter_by(job_id=job_id, resource_id=resource_id).populate_existing().one_or_none()
    claims = db.query(DownloadClaim).filter_by(job_id=job_id, resource_id=resource_id).count()
    if job is None or job.status not in ACTIVE or component is None or component.status not in ACTIVE or claims != 2:
        raise error('download_stale_owner', 'This callback no longer owns the current download operation', job_id=job_id, resource_id=resource_id)
    return job, component, db.query(DownloadedResource).filter_by(id=resource_id).populate_existing().one()


def begin_component(db, job_id, resource_id, token, operation=None):
    with transaction(db, operation):
        job, component, row = fence(db, job_id, resource_id, token)
        now = datetime.utcnow()
        job.status = component.status = 'running'
        job.started_at = job.started_at or now
        job.updated_at = component.updated_at = now


@contextmanager
def publication(db, job_id, resource_id, token, operation=None):
    with transaction(db, operation):
        job, component, row = fence(db, job_id, resource_id, token)
        yield row, component
        job.updated_at = component.updated_at = datetime.utcnow()


def finish(db, job):
    components = db.query(DownloadComponent).filter_by(job_id=job.id).all()
    if components and all(c.status not in ACTIVE for c in components):
        job.status = 'completed' if all(c.status == 'completed' for c in components) else 'failed'
        job.error_json = next((c.error_json for c in components if c.error_json), None)
        job.finished_at = job.updated_at = datetime.utcnow()
        db.execute(delete(DownloadClaim).where(DownloadClaim.job_id == job.id))


def terminal_component(db, job_id, resource_id, token, *, result=None, reason=None):
    with transaction(db):
        job, component, row = fence(db, job_id, resource_id, token)
        component.status = 'failed' if reason is not None else 'completed'
        component.updated_at = job.updated_at = datetime.utcnow()
        if reason is not None:
            component.error_json = json.dumps(safe_evidence(reason))
            row.status = 'failed'
            publish_download_state(row, 'failed', reason)
        else:
            component.downloaded_bytes = component.selected_size
            component.result_json = json.dumps(safe_evidence(result))
        db.flush()
        finish(db, job)


def fail_unstarted(db, job_id, token, reason):
    with transaction(db):
        job = db.query(DownloadJob).filter_by(id=job_id, owner_token=token).one_or_none()
        if job is None or job.status not in ACTIVE:
            return
        for component in db.query(DownloadComponent).filter_by(job_id=job_id).all():
            if component.status in ACTIVE:
                _, _, row = fence(db, job_id, component.resource_id, token)
                component.status = 'failed'
                component.error_json = json.dumps(safe_evidence(reason))
                component.updated_at = datetime.utcnow()
                row.status = 'failed'
                publish_download_state(row, 'failed', reason)
        db.flush()
        finish(db, job)


def status(db, job_id):
    if not isinstance(job_id, str) or JOB_ID.fullmatch(job_id) is None:
        raise error('download_invalid_job_id', 'Invalid download job ID')
    job = db.get(DownloadJob, job_id)
    if job is None:
        raise error('download_job_not_found', 'Download job was not found', job_id=job_id)
    components = db.query(DownloadComponent).filter_by(job_id=job_id).order_by(DownloadComponent.ordinal).limit(MAX_COMPONENTS + 1).all()
    if len(components) > MAX_COMPONENTS:
        raise error('download_status_invalid', 'Stored download package exceeds the component bound', job_id=job_id)
    def timestamp(value):
        return value.isoformat() + 'Z' if value is not None else None
    return safe_evidence({'job_id': job.id, 'job_domain': 'download', 'status': job.status,
        'resource_ids': [c.resource_id for c in components], 'policy': json.loads(job.policy_json),
        'created_at': timestamp(job.created_at), 'started_at': timestamp(job.started_at),
        'updated_at': timestamp(job.updated_at), 'finished_at': timestamp(job.finished_at),
        'error': json.loads(job.error_json) if job.error_json else None,
        'components': [{'resource_id': c.resource_id, 'status': c.status, 'selected_size': c.selected_size,
            'downloaded_bytes': c.downloaded_bytes, 'updated_at': timestamp(c.updated_at),
            'result': json.loads(c.result_json) if c.result_json else None,
            'error': json.loads(c.error_json) if c.error_json else None} for c in components]})


def resource_link(db, resource_id):
    component = (db.query(DownloadComponent).join(DownloadJob, DownloadJob.id == DownloadComponent.job_id)
                 .filter(DownloadComponent.resource_id == resource_id)
                 .order_by(DownloadJob.created_at.desc(), DownloadJob.id.desc()).limit(1).first())
    if component is None:
        return {'job_id': None, 'job_tracking': 'legacy_untracked',
                'job_hint': 'No durable download attempt was recorded for this resource.'}
    return {'job_id': component.job_id, 'job_tracking': 'durable', 'progress': {
        'downloaded_bytes': component.downloaded_bytes, 'total_bytes': component.selected_size,
        'updated_at': component.updated_at.isoformat() + 'Z'}}
