"""Real maintenance handlers, scratch history and bounded synthetic sends only."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from bot.delivery import DeliveryError, DeliveryLedger, ResultDeliveryService
from bot.operator_api import OperatorConfig, OperatorDeliveryServer


@pytest.fixture
def bound(tmp_path):
    path = tmp_path / 'attempts.json'
    DeliveryLedger.provision(path)
    ledger = DeliveryLedger(path)
    api = NS(collect_job_result=AsyncMock(return_value={
        'status': 'completed', 'artifacts': [('one.png', b'synthetic')]}))
    service = ResultDeliveryService(api, ledger)
    server = OperatorDeliveryServer(NS(), service,
        OperatorConfig('synthetic-token', {'art': 5}, 8765), 1)
    try:
        yield service, ledger, path, server
    finally:
        ledger.close()


def request(payload=None, authorized=True):
    return NS(headers={'Authorization': 'Bearer synthetic-token'} if authorized else {},
              json=AsyncMock(return_value={} if payload is None else payload))


def body(response):
    value = json.loads(response.body)
    assert value['schema_version'] == 1
    assert value['legacy_process_certified'] is False
    assert set(value) == {'schema_version', 'owner', 'epoch', 'version',
                          'state', 'active', 'uncertain', 'legacy_process_certified'}
    return value


@pytest.mark.parametrize('damage', ['corrupt', 'missing', 'checkpoint', 'closed',
                                    'unavailable', 'io', 'unexpected'])
async def test_first_close_validates_history_and_never_loses_hold(bound, monkeypatch, damage):
    service, ledger, path, server = bound
    if damage == 'corrupt':
        path.write_text('{')
    elif damage == 'missing':
        path.unlink()
    elif damage == 'checkpoint':
        path.with_name(path.name + '.checkpoint').write_text('{}')
    elif damage == 'closed':
        ledger.close()
    elif damage == 'unavailable':
        service._ledger = None
    elif damage == 'io':
        real_read = Path.read_bytes
        def fail_read(self):
            if self == path:
                raise OSError('synthetic private path /private/not-for-response')
            return real_read(self)
        monkeypatch.setattr(Path, 'read_bytes', fail_read)
    else:
        def fail_check():
            raise RuntimeError('synthetic private credential not-for-response')
        monkeypatch.setattr(ledger, '_check', fail_check)
    # The first receipt itself must know; no status call is allowed to prime it.
    response = await server._handle_close(request({'timeout': 0}))
    assert response.status == 200
    value = body(response)
    assert value['state'] == 'uncertain_closed'
    assert value['active'] == {} and value['uncertain'] == {'ledger': 1}
    assert b'not-for-response' not in response.body
    for route in ('close', 'status', 'close', 'status'):
        later = await getattr(server, '_handle_' + route)(request())
        assert body(later) == value
    send = AsyncMock()
    with pytest.raises(DeliveryError, match='勿盲重送'):
        await service.deliver('late', 'channel:1:5', send, force_resend=True)
    assert send.await_count == 0


async def test_status_unknown_inspection_error_is_sanitized_and_held(bound, monkeypatch):
    service, ledger, path, server = bound
    def fail_check():
        raise RuntimeError('synthetic private path /private/not-for-response')
    monkeypatch.setattr(ledger, '_check', fail_check)
    response = await server._handle_status(request())
    assert body(response)['uncertain'] == {'ledger': 1}
    assert body(response)['state'] == 'uncertain_closed'
    assert b'not-for-response' not in response.body


@pytest.mark.parametrize('history', ['empty', 'complete', 'unfinished'])
@pytest.mark.parametrize('status_first', [False, True])
async def test_clean_and_unfinished_history_close_status_order(bound, history, status_first):
    service, ledger, path, server = bound
    send = AsyncMock(return_value=NS(id=17))
    if history == 'complete':
        await service.deliver('job', 'channel:1:5', send)
    elif history == 'unfinished':
        ledger.begin('channel:1:5:job', job_id='job', destination='channel:1:5', epoch='synthetic')
    before = path.read_bytes()
    if status_first:
        await server._handle_status(request())
    response = await server._handle_close(request({'timeout': 0}))
    value = body(response)
    assert response.status == 200 and value['active'] == {}
    assert value['state'] == ('uncertain_closed' if history == 'unfinished' else 'closed')
    assert value['uncertain'] == ({'delivery_attempt': 1} if history == 'unfinished' else {})
    assert body(await server._handle_status(request())) == value
    assert body(await server._handle_close(request())) == value
    assert path.read_bytes() == before  # inspection never repairs history
    assert send.await_count == (1 if history == 'complete' else 0)


@pytest.mark.parametrize('wait_for_exit', [False, True])
async def test_persistence_failure_with_active_send_and_lock_waiter(bound, wait_for_exit):
    service, ledger, path, server = bound
    entered, release = asyncio.Event(), asyncio.Event()
    effects = []
    async def send(*args, **kwargs):
        effects.append('accepted')
        entered.set()
        await release.wait()
        return NS(id=19)
    first = asyncio.create_task(service.deliver('a', 'channel:1:5', send))
    await asyncio.wait_for(entered.wait(), 1)
    second = asyncio.create_task(service.deliver('b', 'channel:1:5', send))
    await asyncio.sleep(0)  # second is registered while waiting for delivery lock
    path.unlink()
    closing = asyncio.create_task(server._handle_close(request({'timeout': 1 if wait_for_exit else 0})))
    try:
        await asyncio.sleep(0)
        assert service.admission.status()['state'] != 'open'
        if wait_for_exit:
            release.set()
        response = await asyncio.wait_for(closing, 2)
        value = body(response)
        assert response.status == (200 if wait_for_exit else 202)
        assert value['state'] == 'uncertain_closed' and value['uncertain']['ledger'] >= 1
        assert value['active'] == ({} if wait_for_exit else {'delivery': 2})
        if not wait_for_exit:
            assert not first.done() and not second.done()
        with pytest.raises(DeliveryError):
            await service.deliver('c', 'channel:1:5', send, force_resend=True)
    finally:
        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, second, return_exceptions=True), 2)
        await asyncio.wait_for(closing, 2)
    assert all(isinstance(result, Exception) for result in results)
    assert effects == ['accepted']
    for route in ('close', 'status'):
        value = body(await getattr(server, '_handle_' + route)(request()))
        assert value['state'] == 'uncertain_closed' and value['active'] == {}
        assert value['uncertain']['ledger'] >= 1


async def test_clean_active_timeout_is_partial_and_does_not_cancel_send(bound):
    service, ledger, path, server = bound
    entered, release = asyncio.Event(), asyncio.Event()
    async def send(*args, **kwargs):
        entered.set()
        await release.wait()
        return NS(id=23)
    active = asyncio.create_task(service.deliver('a', 'channel:1:5', send))
    await asyncio.wait_for(entered.wait(), 1)
    try:
        response = await server._handle_close(request({'timeout': 0}))
        value = body(response)
        assert response.status == 202 and value['state'] == 'draining'
        assert value['active'] == {'delivery': 1} and value['uncertain'] == {}
        assert not active.done()
    finally:
        release.set()
        receipt = await asyncio.wait_for(active, 1)
    assert receipt.message_ids == ('23',)
    assert body(await server._handle_close(request()))['state'] == 'closed'


@pytest.mark.parametrize('payload', [[], 'bad', {'timeout': True}, {'timeout': -1},
                                     {'timeout': 31}, {'timeout': float('nan')}, {'extra': 1}])
async def test_malformed_body_still_closes_before_parsing(bound, payload):
    service, ledger, path, server = bound
    req = request(payload)
    async def parse():
        assert service.admission.status()['state'] == 'closed'
        return payload
    req.json = parse
    assert (await server._handle_close(req)).status == 400
    assert service.admission.status()['state'] == 'closed'


async def test_slow_body_closes_ingress_before_first_await(bound):
    service, ledger, path, server = bound
    entered, release = asyncio.Event(), asyncio.Event()
    async def parse():
        entered.set()
        await release.wait()
        return {'timeout': 0}
    req = request()
    req.json = parse
    closing = asyncio.create_task(server._handle_close(req))
    await asyncio.wait_for(entered.wait(), 1)
    try:
        assert service.admission.status()['state'] == 'closed'
        send = AsyncMock()
        with pytest.raises(DeliveryError):
            await service.deliver('late', 'channel:1:5', send)
        assert send.await_count == 0
    finally:
        release.set()
        response = await asyncio.wait_for(closing, 1)
    assert response.status == 200 and body(response)['state'] == 'closed'


@pytest.mark.parametrize('route', ['status', 'close', 'delivery'])
async def test_unauthorized_never_inspects_history_or_body(bound, monkeypatch, route):
    service, ledger, path, server = bound
    def forbidden():
        raise AssertionError('unauthorized history inspection')
    monkeypatch.setattr(ledger, '_check', forbidden)
    req = request(authorized=False)
    assert (await getattr(server, '_handle_' + route)(req)).status == 401
    assert req.json.await_count == 0
    assert service.admission.status()['state'] == 'open'
