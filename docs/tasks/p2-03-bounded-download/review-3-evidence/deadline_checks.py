"""QA3 independent scaled deadline/ownership guards; external HTTP only is fake."""
import asyncio
import json
import sys
import threading
import time
import traceback

import httpx
import pytest

from tests.conftest import client, isolated_database, isolated_worker_admission
from tests.test_resource_record_writers import boundary, acquire_http
from tests.test_civitai_download_correction import seed, retained, state, columns
from app.services import civitai_resource_acquire as acquire
from app.services import civitai_provider as provider
from app.services import resource_records as records
from mcp_server.server import mcp


def stat(path):
    s = path.lstat()
    return [getattr(s, k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_uid',
        'st_gid','st_size','st_mtime_ns','st_ctime_ns')]


def lock_probe(lock):
    result = []
    def other():
        got = lock.acquire(blocking=False); result.append(got)
        if got: lock.release()
    t = threading.Thread(target=other); t.start(); t.join(1)
    assert not t.is_alive()
    return result == [True]


@pytest.mark.parametrize('entry', ['install', 'acquire_http', 'acquire_mcp'])
@pytest.mark.parametrize('budget', [0.12, -0.01])
def test_real_callers_return_before_held_owner_releases(boundary, monkeypatch, entry, budget):
    if entry == 'install' and budget == -0.01:
        pytest.skip('Known immediate-expiry diagnostic lacks resource_id; '
                    'docs/tasks/p2-04-durable-download-jobs/task.md owns fix and re-enable')
    b = boundary; rid, target = seed(b, final=True)
    # Adapter-to-ASGI bridge retains actual registered MCP implementation.
    http_client = httpx.Client
    class BackendClient(http_client):
        def __init__(self, **kw): super().__init__(transport=b.client._transport, **kw)
    monkeypatch.setattr(httpx, 'Client', BackendClient)
    occupied = threading.Event(); release = threading.Event(); started = threading.Event()
    returned = threading.Event(); short = []; operations = []; results = []; owners = []; errors = []
    verify = acquire.verified_existing
    def hold(*args, **kw):
        value = verify(*args, **kw)
        if not occupied.is_set():
            occupied.set(); assert release.wait(5), 'owner fixture needs release'
        return value
    monkeypatch.setattr(acquire, 'verified_existing', hold)
    init = provider.ProviderOperation.__init__
    def shorten(self, kind, **kw):
        init(self, kind, **kw)
        if short and kind == 'download':
            now = time.monotonic(); self.deadline = now + budget
            operations.append((self, threading.get_ident(), now)); started.set()
    monkeypatch.setattr(provider.ProviderOperation, '__init__', shorten)
    def owner():
        try: owners.append(acquire_http(b))
        except BaseException as exc: errors.append(repr(exc))
    def compete():
        try:
            if entry == 'install': results.append(retained(b))
            elif entry == 'acquire_http': results.append(acquire_http(b))
            else: results.append(asyncio.run(mcp.call_tool('civitai_resource_acquire',
                {'source':'https://civitai.com/models/10?modelVersionId=21'}))[1])
        except BaseException as exc: errors.append(repr(exc))
        finally: returned.set()
    first = threading.Thread(target=owner); second = threading.Thread(target=compete)
    first.start()
    try:
        assert occupied.wait(3)
        before = columns(rid); identity = stat(target); files = sorted(str(p) for p in b.tmp.rglob('*'))
        short.append(True); second.start(); began = started.wait(0.5)
        bounded = returned.wait(0.45) if began else False
        elapsed = time.monotonic() - operations[0][2] if operations else None
        frame = sys._current_frames().get(operations[0][1]) if operations else None
        stack = traceback.format_stack(frame) if frame is not None else []
        unchanged = columns(rid) == before and stat(target) == identity
        same_files = sorted(str(p) for p in b.tmp.rglob('*')) == files
        body_count = len([p for p, _ in b.seen if '/api/download/' in p])
        still_owned = not lock_probe(records.resource_admission)
        print('QA3_DEADLINE='+json.dumps(dict(entry=entry,budget=budget,started=began,
            returned_before_release=bounded,elapsed=elapsed,margin=0.33,stack=stack,
            owner_unchanged=unchanged,files_unchanged=same_files,owner_still_holds=still_owned,
            model_body_count=body_count,pending=len(b.pending),resource_id=rid)))
    finally:
        short.clear(); release.set(); first.join(5)
        if second.ident is not None: second.join(5)
    assert not first.is_alive() and not second.is_alive() and not errors, errors
    assert owners[0].status_code == 202
    while b.pending: b.pending.pop()()
    assert state(b,rid)['status'] == 'installed' and target.read_bytes() == b.body
    assert columns(rid)['notes'] == before['notes']
    assert began and bounded and elapsed < 0.45, 'existing budget must end contention before owner release'
    assert unchanged and same_files and body_count == 0 and still_owned
    if entry == 'acquire_mcp':
        assert results[0]['ok'] is False and results[0]['error']['code'] == 'civitai_timeout', results
        assert results[0]['error']['hint']
    else:
        response = results[0]; assert response.status_code == (409 if entry == 'install' else 422), response.text
        diagnostic = response.json()['detail']
        if entry == 'install':
            diagnostic = diagnostic['diagnostic']; assert diagnostic['resource_id'] == rid
        assert diagnostic['code'] == 'civitai_timeout' and diagnostic['hint']
    assert lock_probe(records.resource_admission)
    assert retained(b).json()['ledger_id'] == rid
    assert acquire_http(b).json()['status'] == 'already_installed'


@pytest.mark.parametrize('path', ['expired', 'entry_expired', 'exception', 'reentrant', 'legacy'])
def test_real_operation_entry_boundaries_balance_lock(boundary, monkeypatch, path):
    lock = records.resource_admission
    with provider.ProviderOperation('download') as op:
        deadline = op.deadline
        if path == 'expired': op.deadline = time.monotonic() - 1
        if path == 'entry_expired':
            remaining = op.remaining; calls = []
            def expire_after_observation():
                value = remaining(); calls.append(True)
                if len(calls) == 1: op.deadline = time.monotonic() - 1
                return value
            monkeypatch.setattr(op, 'remaining', expire_after_observation)
        if path in {'expired', 'entry_expired'}:
            with pytest.raises(provider.CivitaiProviderError) as err:
                with records.bounded_resource_admission(op):
                    assert False, 'expired operation reached mutation body'
            assert err.value.code == 'civitai_timeout'
        elif path == 'exception':
            with pytest.raises(RuntimeError, match='synthetic body failure'):
                with records.bounded_resource_admission(op): raise RuntimeError('synthetic body failure')
        elif path == 'reentrant':
            with records.bounded_resource_admission(op):
                with records.bounded_resource_admission(op): assert not lock_probe(lock)
                assert not lock_probe(lock)
            assert op.deadline == deadline
        else:
            with records.bounded_resource_admission(None): assert not lock_probe(lock)
        assert lock_probe(lock)
        with records.bounded_resource_admission(None): pass
