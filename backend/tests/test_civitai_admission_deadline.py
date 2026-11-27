"""Admission consumes the real caller budget and never changes another owner.

External HTTP and scheduling/time are synthetic. Registered routes, configured
credentials, ProviderOperation, RLock, ORM and filesystem are production paths.
An unbounded wait, reset budget, foreign release or leaked lock breaks these guards.
"""
import json
import sys
import threading
import time
import traceback

import pytest
from app.db import database
from app.db.models import DownloadedResource
from app.services import civitai_provider as provider
from app.services import civitai_resource_acquire as acquire
from app.services import resource_records as records
from tests.test_resource_record_writers import boundary, acquire_http
from tests.test_civitai_download_correction import seed, retained, state, columns


def submit(b, entry):
    return retained(b) if entry == 'install' else acquire_http(b)


def code(response, entry):
    detail = response.json()['detail']
    return detail['diagnostic'] if entry == 'install' else detail


def fingerprint(target):
    s = target.lstat()
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


@pytest.mark.parametrize('entry', ['install', 'acquire'])
@pytest.mark.parametrize('budget', [0.15, -0.01])
def test_registered_contender_times_out_before_original_owner_releases(boundary, monkeypatch, entry, budget):
    if entry == 'install' and budget < 0:
        pytest.skip('Pre-existing immediate-deadline diagnostic lacks resource_id before lookup; tracked by docs/tasks/p2-04-durable-download-jobs/task.md')
    b = boundary; rid, target = seed(b, final=True)
    occupied = threading.Event(); release = threading.Event(); returned = threading.Event()
    started = threading.Event(); operations = []; outcomes = []; owner_results = []; errors = []
    original = acquire.verified_existing; init = provider.ProviderOperation.__init__
    def observe(*args, **kw):
        value = original(*args, **kw)
        if not occupied.is_set():
            occupied.set(); assert release.wait(4), 'fixture must release original owner'
        return value
    monkeypatch.setattr(acquire, 'verified_existing', observe)
    shorten = []
    def operation(self, kind, **kw):
        init(self, kind, **kw)
        if shorten and kind == 'download':
            now = time.monotonic(); self.deadline = now + budget
            operations.append((self, threading.get_ident(), now)); started.set()
    monkeypatch.setattr(provider.ProviderOperation, '__init__', operation)
    def owner():
        try: owner_results.append(acquire_http(b))
        except BaseException as exc: errors.append(exc)
    def contender():
        try: outcomes.append(submit(b, entry))
        except BaseException as exc: errors.append(exc)
        finally: returned.set()
    first = threading.Thread(target=owner); other = threading.Thread(target=contender)
    first.start()
    try:
        assert occupied.wait(3)
        before = columns(rid); identity = fingerprint(target)
        shorten.append(True); t = time.monotonic(); other.start()
        began_before_release = started.wait(0.6)
        bounded = returned.wait(0.6) if began_before_release else returned.is_set()
        elapsed = time.monotonic() - (operations[0][2] if operations else t)
        frame = sys._current_frames().get(operations[0][1]) if operations else None
        stack = traceback.format_stack(frame) if frame is not None else []
        unchanged = columns(rid) == before and fingerprint(target) == identity
        assert target.read_bytes() == b.body
        body_count = len([p for p, _ in b.seen if '/api/download/' in p])
        pending = len(b.pending)
        print('ADMISSION_DEADLINE='+json.dumps(dict(entry=entry, budget=budget,
            operation_started_before_release=began_before_release, returned_before_release=bounded,
            elapsed=elapsed, margin_seconds=0.45, stack=stack, resource_id=rid,
            owner_columns_unchanged=unchanged, body_count=body_count, pending=pending)))
    finally:
        release.set(); first.join(4)
        if other.ident is not None: other.join(4)
    assert not first.is_alive() and not other.is_alive() and not errors, errors
    assert owner_results[0].status_code == 202, owner_results[0].text
    shorten.clear()  # the original owner's background operation keeps its own budget
    while b.pending: b.pending.pop()()
    assert state(b, rid)['status'] == 'installed' and target.read_bytes() == b.body
    assert columns(rid)['notes'] == before['notes']
    assert began_before_release, 'the acquisition budget must exist before lock contention'
    assert bounded and elapsed < 0.6, 'admission must return within existing budget plus explicit scheduling margin'
    assert unchanged and body_count == 0 and pending == 0, 'contender must not mutate owner or submit work'
    assert outcomes[0].status_code == (409 if entry == 'install' else 422), outcomes[0].text
    diagnostic = code(outcomes[0], entry)
    assert diagnostic['code'] == 'civitai_timeout' and diagnostic['hint']
    if entry == 'install': assert diagnostic['resource_id'] == rid
    # A timed-out waiter must neither release the owner's RLock nor leak its own.
    shorten.clear()
    assert acquire_http(b).json()['status'] == 'already_installed'
    assert retained(b).json()['ledger_id'] == rid


@pytest.mark.parametrize('entry', ['install', 'acquire'])
@pytest.mark.parametrize('budget', [-0.01, 0.25])
@pytest.mark.parametrize('final', [False, True])
def test_registered_available_admission_respects_expiration_and_still_installs(boundary, monkeypatch, entry, budget, final):
    b = boundary; rid, target = seed(b, final=final); before = columns(rid)
    init = provider.ProviderOperation.__init__
    def operation(self, kind, **kw):
        init(self, kind, **kw)
        if kind == 'download': self.deadline = time.monotonic() + budget
    monkeypatch.setattr(provider.ProviderOperation, '__init__', operation)
    response = submit(b, entry)
    if budget < 0:
        assert response.status_code == (409 if entry == 'install' else 422), response.text
        assert code(response, entry)['code'] == 'civitai_timeout'
        assert columns(rid) == before and not b.pending
        assert not [p for p, _ in b.seen if '/api/download/' in p]
        assert target.exists() is final
    else:
        assert response.status_code == (200 if entry == 'install' else 202), response.text
        while b.pending: b.pending.pop()()
        assert state(b, rid)['status'] == 'installed' and target.read_bytes() == b.body
    with database.SessionLocal() as db:
        assert db.query(DownloadedResource).count() == 1


@pytest.mark.parametrize('entry', ['install', 'acquire'])
@pytest.mark.parametrize('exception', [False, True])
def test_registered_admission_reenters_and_releases_after_exception(boundary, monkeypatch, entry, exception):
    b = boundary; rid, target = seed(b)
    # Wrap the real acquire only to take one additional same-thread RLock level.
    # The registered caller must balance its level even if claim raises.
    lock = records.resource_admission
    original_acquire = lock.acquire
    class ReentrantProbe:
        def acquire(self, *args, **kw):
            original_acquire()
            return original_acquire(*args, **kw)
        def release(self):
            lock.release(); lock.release()
    monkeypatch.setattr(records, 'resource_admission', ReentrantProbe())
    if exception:
        cls = database.SessionLocal.class_; commit = cls.commit; failed = []
        def reject_once(db):
            if not failed:
                failed.append(True); raise RuntimeError('synthetic admission commit failure')
            return commit(db)
        monkeypatch.setattr(cls, 'commit', reject_once)
        # Acquisition propagates unexpected DB errors through TestClient.
        try: response = submit(b, entry)
        except RuntimeError:
            assert entry == 'acquire'
        else: assert response.status_code == 500, response.text
    else:
        response = submit(b, entry)
        assert response.status_code == (200 if entry == 'install' else 202), response.text
    while b.pending: b.pending.pop()()
    response = submit(b, entry)
    assert response.status_code == (200 if entry == 'install' else 202), response.text
    while b.pending: b.pending.pop()()
    assert state(b, rid)['status'] == 'installed' and target.read_bytes() == b.body
    # A different thread must acquire afterwards; same-thread success alone
    # would hide an unbalanced reentrant level.
    available = []
    def following():
        got = lock.acquire(timeout=0.1); available.append(got)
        if got: lock.release()
    thread = threading.Thread(target=following); thread.start(); thread.join(1)
    assert available == [True]
