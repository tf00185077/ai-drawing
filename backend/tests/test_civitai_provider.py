"""Private configuration and actual HTTP boundary contracts for p2-01."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def private_config(monkeypatch):
    monkeypatch.setenv('CIVITAI_API_KEY_FILE', '')
    monkeypatch.setenv('CIVITAI_AUTHORIZATION', '')
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def configure(monkeypatch, path='', legacy=''):
    monkeypatch.setenv('CIVITAI_API_KEY_FILE', str(path))
    monkeypatch.setenv('CIVITAI_AUTHORIZATION', legacy)
    get_settings.cache_clear()


def test_file_precedence_trim_and_rotation_without_settings_patch(tmp_path, monkeypatch):
    from app.services.civitai_resource_acquire import _auth_headers
    key = tmp_path/'key'
    key.write_text('  file-sentinel\n', encoding='utf-8')
    configure(monkeypatch, key, 'legacy-sentinel')
    assert _auth_headers() == {'Authorization': 'Bearer file-sentinel'}
    key.write_text('rotated-sentinel')
    assert _auth_headers() == {'Authorization': 'Bearer rotated-sentinel'}


@pytest.mark.parametrize('legacy,want', [('', {}), (' raw-sentinel ', {'Authorization': 'Bearer raw-sentinel'}), ('Bearer prefixed', {'Authorization': 'Bearer prefixed'}), ('bearer prefixed', {'Authorization': 'bearer prefixed'})])
def test_blank_file_legacy_and_anonymous(monkeypatch, legacy, want):
    from app.services.civitai_resource_acquire import _auth_headers
    configure(monkeypatch, '  ', legacy)
    assert _auth_headers() == want


@pytest.mark.parametrize('kind', ['missing', 'directory', 'fifo', 'empty', 'unicode', 'oversized', 'control', 'header', 'json'])
def test_configured_bad_file_fails_before_provider_traffic(tmp_path, monkeypatch, kind):
    from app.services.civitai_resource_acquire import resolve_version_metadata
    key = tmp_path/'key'
    if kind == 'directory': key.mkdir()
    elif kind == 'fifo': os.mkfifo(key)
    elif kind != 'missing':
        key.write_bytes({'empty': b' \n', 'unicode': b'\xff', 'oversized': b'a'*65537, 'control': b'abc\x00def', 'header': b'Authorization: sentinel', 'json': b'{"key":"sentinel"}'}[kind])
    configure(monkeypatch, key, 'fallback-must-not-be-used')
    calls = []
    class NoTraffic:
        def get_json(self, *a, **kw):
            calls.append(a)
            return 200, {'id': 7}
    with pytest.raises(Exception) as error:
        resolve_version_metadata('7', transport=NoTraffic())
    assert error.value.code == 'civitai_credentials_unavailable'
    assert 'CIVITAI_API_KEY_FILE' in error.value.hint
    assert not calls
    assert 'fallback-must-not-be-used' not in str(error.value)

@pytest.fixture
def wire(monkeypatch):
    """Keep the real HTTP client/factories; replace only external HTTP I/O."""
    original = httpx.AsyncClient
    def bind(handler):
        class WiredClient(original):
            def __init__(self, **kw): super().__init__(transport=httpx.MockTransport(handler), **kw)
        monkeypatch.setattr(httpx, 'AsyncClient', WiredClient)
    return bind


class Stream(httpx.AsyncByteStream):
    def __init__(self, parts=(b'abc', b'def'), *, advance=None, fail=None):
        self.parts, self.advance, self.fail, self.closed = parts, advance, fail, False
    async def __aiter__(self):
        for part in self.parts:
            if self.advance: self.advance()
            yield part
        if self.fail: raise self.fail
    async def aclose(self):
        self.closed = True


def test_redirect_origin_headers_bytes_and_unconsumed_close(wire, tmp_path, monkeypatch):
    from app.services.civitai_provider import ProviderOperation, ProviderDownloadTransport
    key=tmp_path/'key'; key.write_text('wire-sentinel'); configure(monkeypatch, key)
    seen=[]; streams=[]
    def handle(request):
        seen.append(request)
        stream=Stream(); streams.append(stream)
        if request.url.host == 'civitai.com':
            return httpx.Response(307, headers={'Location':'https://www.civitai.com/next'}, stream=stream)
        if request.url.host == 'www.civitai.com':
            return httpx.Response(302, headers={'Location':'https://b2.civitai.com/file?X-Amz-Signature=SIGNED_SENTINEL'}, stream=stream)
        return httpx.Response(200, stream=stream)
    wire(handle)
    with ProviderOperation('download') as op:
        response=ProviderDownloadTransport(op).get('https://civitai.com/start')
        assert b''.join(response.body) == b'abcdef'
    assert [r.headers.get('authorization') for r in seen] == ['Bearer wire-sentinel', None, None]
    assert all(s.closed for s in streams)
    assert all(0 < r.extensions['timeout']['read'] <= 30 for r in seen)
    with ProviderOperation('download') as op:
        response=ProviderDownloadTransport(op).get('https://b2.civitai.com/direct')
        response.close()  # must close even before the first next()
        assert streams[-1].closed
    with ProviderOperation('download') as op:
        ProviderDownloadTransport(op).get('https://b2.civitai.com/unconsumed')
    assert streams[-1].closed


@pytest.mark.parametrize('url', ['http://civitai.com/a','https://civitai.com.evil/a','https://evilcivitai.com/a','https://civitai.com:444/a','https://user@civitai.com/a','https://b2.civitai.com:80/a','file:///tmp/a'])
@pytest.mark.parametrize('redirect', [False, True])
def test_initial_and_redirect_destinations_fail_closed(wire, url, redirect):
    from app.services.civitai_provider import ProviderOperation, CivitaiProviderError
    seen=[]; streams=[]
    def handle(request):
        seen.append(request); stream=Stream(); streams.append(stream)
        return httpx.Response(307, headers={'location':url}, stream=stream)
    wire(handle)
    with ProviderOperation('metadata') as op:
        with pytest.raises(CivitaiProviderError) as error:
            op.get_json('https://civitai.com/start' if redirect else url)
    assert error.value.code == 'civitai_redirect_blocked'
    assert len(seen) == int(redirect)
    assert all(s.closed for s in streams)


def test_five_redirects_maximum_and_no_reauthentication_after_return(wire, monkeypatch):
    from app.services.civitai_provider import ProviderOperation, CivitaiProviderError
    configure(monkeypatch, legacy='legacy-sentinel')
    seen=[]; streams=[]
    def handle(request):
        seen.append(request); stream=Stream(); streams.append(stream)
        destination='https://b2.civitai.com/next' if len(seen)==1 else 'https://civitai.com/loop'
        return httpx.Response(307, headers={'location':destination}, stream=stream)
    wire(handle)
    with ProviderOperation('metadata') as op:
        with pytest.raises(CivitaiProviderError) as error: op.get_json('https://civitai.com/start')
    assert error.value.code == 'civitai_redirect_blocked'
    assert len(seen) == 6
    assert [r.headers.get('authorization') for r in seen] == ['Bearer legacy-sentinel'] + [None]*5
    assert all(s.closed for s in streams)


def test_nested_metadata_snapshot_and_absolute_deadline(wire, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.services import civitai_provider as provider
    from app.services.civitai_resource_acquire import resolve_version_metadata
    key=tmp_path/'key'; key.write_text('first-sentinel'); configure(monkeypatch, key)
    clock=[0.0]; seen=[]; streams=[]
    monkeypatch.setattr(provider, 'time', SimpleNamespace(monotonic=lambda:clock[0]))
    def handle(request):
        seen.append(request)
        key.write_text('rotated-sentinel')
        clock[0] += 11
        payload={'id':7, 'modelId':8} if '/model-versions/' in str(request.url) else {'id':8,'modelVersions':[{'id':7}]}
        stream=Stream((json.dumps(payload).encode(),)); streams.append(stream)
        return httpx.Response(200, stream=stream)
    wire(handle)
    with pytest.raises(provider.CivitaiProviderError) as error: resolve_version_metadata('7')
    assert error.value.code == 'civitai_timeout'
    assert [r.headers.get('authorization') for r in seen] == ['Bearer first-sentinel']*2
    assert all(s.closed for s in streams)
    assert all(0 < r.extensions['timeout']['read'] <= 10 and 0 < r.extensions['timeout']['connect'] <= 5 for r in seen)
    resolve_version_metadata('https://civitai.com/models/8')
    assert seen[-1].headers['authorization'] == 'Bearer rotated-sentinel'


def test_download_total_spans_retries_backoff_and_keeps_snapshot(wire, tmp_path, monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from app.services import civitai_provider as provider
    from app.services.civitai_safe_download import safe_download, CivitaiFileMetadata
    key=tmp_path/'key'; key.write_text('retry-sentinel'); configure(monkeypatch, key)
    clock=[0.0]; seen=[]; streams=[]
    monkeypatch.setattr(provider,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def handle(request):
        seen.append(request); key.write_text('rotated-sentinel'); clock[0]+=300
        stream=Stream(); streams.append(stream)
        return httpx.Response(429, stream=stream)
    wire(handle)
    def sleep(seconds): clock[0]+=seconds
    metadata=CivitaiFileMetadata('https://civitai.com/file',hashlib.sha256(b'abcdef').hexdigest(),6,scan_status='clean')
    with provider.ProviderOperation('download') as op:
        result=safe_download(metadata,tmp_path/'file',transport=provider.ProviderDownloadTransport(op),operation=op,backoff=lambda *_:200,sleep=sleep)
    assert result.status == 'failed'
    assert result.diagnostics['code'] == 'civitai_timeout'
    assert len(seen) == 2
    assert [r.headers['authorization'] for r in seen] == ['Bearer retry-sentinel']*2
    assert all(s.closed for s in streams)
    assert not (tmp_path/'file').exists()


def test_slow_drip_is_cancelled_by_total_deadline_and_closes(wire, tmp_path):
    import hashlib,time
    from app.services.civitai_provider import ProviderOperation, ProviderDownloadTransport
    from app.services.civitai_safe_download import safe_download, CivitaiFileMetadata
    class Slow(Stream):
        async def __aiter__(self):
            for _ in range(10):
                await asyncio.sleep(.015)
                yield b'x'
    stream=Slow()
    wire(lambda request:httpx.Response(200,stream=stream))
    metadata=CivitaiFileMetadata('https://civitai.com/file',hashlib.sha256(b'x'*10).hexdigest(),10,scan_status='clean')
    with ProviderOperation('download') as op:
        op.deadline=time.monotonic()+.05
        result=safe_download(metadata,tmp_path/'file',transport=ProviderDownloadTransport(op),operation=op)
    assert result.diagnostics['code'] == 'civitai_timeout'
    assert stream.closed
    assert not (tmp_path/'file').exists()


@pytest.mark.parametrize('status,code,attempts',[(401,'unauthorized',1),(403,'unauthorized',1),(429,'civitai_api_error',3),(503,'civitai_api_error',3)])
def test_provider_failures_are_truthful_closed_and_sanitized(wire,tmp_path,status,code,attempts):
    from app.services.civitai_provider import ProviderOperation,ProviderDownloadTransport
    from app.services.civitai_safe_download import safe_download,CivitaiFileMetadata
    streams=[]
    def handle(request):
        stream=Stream(); streams.append(stream)
        return httpx.Response(status,headers={'location':'https://b2.civitai.com/f?X-Amz-Signature=SIGNED_SENTINEL'},stream=stream)
    wire(handle)
    with ProviderOperation('download') as op:
        result=safe_download(CivitaiFileMetadata('https://civitai.com/f','a'*64,6,scan_status='clean'),tmp_path/'f',transport=ProviderDownloadTransport(op),operation=op)
    assert result.status == 'failed' and result.diagnostics['code'] == code
    assert len(streams) == attempts and all(s.closed for s in streams)
    assert 'SIGNED_SENTINEL' not in json.dumps(result.to_dict())


def test_network_failures_retry_without_exception_url_or_key(wire,tmp_path,monkeypatch):
    from app.services.civitai_provider import ProviderOperation,ProviderDownloadTransport
    from app.services.civitai_safe_download import safe_download,CivitaiFileMetadata
    configure(monkeypatch, legacy='network-sentinel'); calls=[]
    def handle(request):
        calls.append(request)
        raise httpx.ConnectError('network-sentinel https://civitai.com/f?X-Amz-Signature=SIGNED_SENTINEL',request=request)
    wire(handle)
    with ProviderOperation('download') as op:
        result=safe_download(CivitaiFileMetadata('https://civitai.com/f','a'*64,6,scan_status='clean'),tmp_path/'f',transport=ProviderDownloadTransport(op),operation=op)
    assert result.diagnostics['code'] == 'civitai_network_error'
    assert len(calls) == 3
    assert 'network-sentinel' not in json.dumps(result.to_dict())
    assert 'SIGNED_SENTINEL' not in json.dumps(result.to_dict())


def test_signed_query_redaction_retains_tokenizer_and_source_hashes():
    from app.services.civitai_acquisition import redact_secrets
    data={'tokenizer/path.py':{'sha256':'a'*64},'url':'https://b2.civitai.com/f?type=Model&X-Amz-Credential=PRIVATE&X-Amz-Signature=SIGNED&Policy=POLICY&Key-Pair-Id=PAIR&Expires=123&token=TOKEN'}
    result=redact_secrets(data)
    assert result['tokenizer/path.py']['sha256'] == 'a'*64
    assert 'type=Model' in result['url']
    for value in ('PRIVATE','SIGNED','POLICY','PAIR','123','TOKEN'): assert value not in result['url']


def test_http_logs_exclude_signed_queries_and_credentials(wire, monkeypatch, caplog):
    import logging
    from app.services.civitai_provider import ProviderOperation
    configure(monkeypatch, legacy='log-sentinel')
    def handle(request):
        logging.getLogger('httpcore.http11').debug('headers %s location https://b2.civitai.com/f?X-Amz-Signature=SIGNED_SENTINEL', request.headers.get('authorization'))
        return httpx.Response(200,json={'ok':True})
    wire(handle)
    with caplog.at_level(logging.DEBUG):
        with ProviderOperation('metadata') as op:
            op.get_json('https://civitai.com/f?X-Amz-Signature=SIGNED_SENTINEL&token=OTHER_SENTINEL')
    assert 'SIGNED_SENTINEL' not in caplog.text
    assert 'log-sentinel' not in caplog.text
    assert 'OTHER_SENTINEL' not in caplog.text


def test_interruption_closes_response_and_preserves_partial_truth(wire,tmp_path):
    from app.services.civitai_provider import ProviderOperation,ProviderDownloadTransport
    from app.services.civitai_safe_download import safe_download,CivitaiFileMetadata
    stream=Stream((b'x'*1048576,),fail=KeyboardInterrupt())
    wire(lambda request:httpx.Response(200,stream=stream))
    with ProviderOperation('download') as op:
        with pytest.raises(KeyboardInterrupt):
            safe_download(CivitaiFileMetadata('https://civitai.com/f','a'*64,2000000,scan_status='clean'),tmp_path/'f',transport=ProviderDownloadTransport(op),operation=op)
    assert stream.closed
    assert not (tmp_path/'f').exists()
    assert (tmp_path/'f.part').stat().st_size == 1048576


def test_unreadable_file_and_exact_64k_boundary(tmp_path, monkeypatch):
    from app.services.civitai_resource_acquire import _auth_headers
    from app.services import civitai_provider as provider
    key=tmp_path/'key'; key.write_bytes(b'a'*65536); configure(monkeypatch,key)
    assert _auth_headers()['Authorization'] == 'Bearer '+('a'*65536)
    def denied(*args,**kwargs): raise PermissionError('private path must not escape')
    monkeypatch.setattr(provider.os,'open',denied)
    with pytest.raises(provider.CivitaiProviderError) as error: _auth_headers()
    assert error.value.code == 'civitai_credentials_unavailable'
    assert 'private path must not escape' not in str(error.value)


@pytest.fixture
def production_routes(monkeypatch, client):
    """Real Backend routes/ORM and MCP HTTP adapter, with isolated DB and HTTP."""
    from app.db import database
    from app.services import civitai_resource_acquire as acquire
    from app.main import app
    from app.db.database import get_db
    original=httpx.Client
    class BackendClient(original):
        def __init__(self, **kw): super().__init__(transport=client._transport,**kw)
    monkeypatch.setattr(httpx,'Client',BackendClient)
    monkeypatch.setattr(acquire,'SessionLocal',database.SessionLocal)
    def db_dependency():
        with database.SessionLocal() as db: yield db
    app.dependency_overrides[get_db]=db_dependency
    pending=[]
    class Thread:
        def __init__(self, *, target, **kwargs): self.target=target
        def start(self): pending.append(self.target)
    # Preserve the actual default thread path and background _run/_run_one;
    # defer scheduling only so admission/rotation/status checks are deterministic.
    from types import SimpleNamespace
    monkeypatch.setattr(acquire,'threading',SimpleNamespace(Thread=Thread))
    yield client,pending
    app.dependency_overrides.clear()


def resource_payload(body=b'abcdef'):
    import hashlib
    file={'id':11,'name':'fixture.safetensors','sizeKB':len(body)/1024,'hashes':{'SHA256':hashlib.sha256(body).hexdigest()},'downloadUrl':'https://civitai.com/api/download/models/7?type=Model&X-Amz-Signature=SIGNED_SENTINEL','virusScanResult':'Success','primary':True,'availability':True,'license':{'name':'test'},'usage':{'personal':True}}
    version={'id':7,'modelId':8,'name':'v1','baseModel':'SDXL 1.0','files':[file],'model':{'id':8,'type':'LORA'}}
    model={'id':8,'type':'LORA','name':'fixture','modelVersions':[version],'allowNoCredit':True,'allowCommercialUse':['Image'],'allowDerivatives':True,'allowDifferentLicense':True}
    return version,model


def call_mcp(name,args):
    from mcp_server.server import mcp
    return asyncio.run(mcp.call_tool(name,args))[1]


def test_registered_mcp_admission_background_rotation_status_and_reuse(production_routes,wire,tmp_path,monkeypatch):
    from app.db import database
    from app.db.models import DownloadedResource
    client,pending=production_routes
    key=tmp_path/'key'; key.write_text('metadata-sentinel'); configure(monkeypatch,key,'fallback-sentinel')
    # Private environment config, no settings object/credential/transport patch.
    monkeypatch.setenv('COMFYUI_LORAS_DIR',str(tmp_path/'loras')); get_settings.cache_clear()
    version,model=resource_payload(); seen=[]; streams=[]
    def handle(request):
        seen.append(request)
        if '/model-versions/' in request.url.path:
            key.write_text('download-sentinel')
            return httpx.Response(200,json=version)
        if '/api/v1/models/' in request.url.path: return httpx.Response(200,json=model)
        stream=Stream(); streams.append(stream)
        if request.url.host=='civitai.com': return httpx.Response(307,headers={'location':'https://b2.civitai.com/f?X-Amz-Signature=SIGNED_SENTINEL'},stream=stream)
        return httpx.Response(200,stream=stream)
    wire(handle)
    admitted=call_mcp('civitai_resource_acquire',{'source':'7'})
    assert admitted['ok'] is True
    resource=admitted['data']['resource']; acquisition_id=resource['acquisition_id']
    assert resource['status']=='downloading' and len(pending)==1
    duplicate=call_mcp('civitai_resource_acquire',{'source':'7'})
    assert duplicate['data']['resource']['acquisition_id']==acquisition_id and len(pending)==1
    # The duplicate is another metadata operation; the original nested reads
    # still used the first immutable snapshot.
    assert [r.headers['authorization'] for r in seen[:2]]==['Bearer metadata-sentinel']*2
    pending.pop()()
    status=call_mcp('civitai_resource_status',{'acquisition_id':acquisition_id})
    assert status['data']['resources'][0]['status']=='installed'
    assert [r.headers.get('authorization') for r in seen[-2:]]==['Bearer download-sentinel',None]
    assert Path(status['data']['resources'][0]['local_path']).read_bytes()==b'abcdef'
    reused=call_mcp('civitai_resource_acquire',{'source':'7'})
    assert reused['data']['status']=='already_installed' and not pending
    with database.SessionLocal() as db:
        rows=db.query(DownloadedResource).all(); assert len(rows)==1
        assert rows[0].id==acquisition_id and rows[0].civitai_file_id=='11'
        stored=json.dumps({c.name:getattr(rows[0],c.name) for c in DownloadedResource.__table__.columns},default=str)
    for private in ('metadata-sentinel','download-sentinel','fallback-sentinel','SIGNED_SENTINEL'):
        assert private not in stored+json.dumps(admitted)+json.dumps(status)
    assert all(s.closed for s in streams)


@pytest.mark.parametrize('failure', ['bad_file','redirect','timeout','unauthorized','network'])
def test_registered_errors_survive_metadata_and_background_status(production_routes,wire,tmp_path,monkeypatch,failure):
    from app.services import civitai_provider as provider
    from types import SimpleNamespace
    client,pending=production_routes
    key=tmp_path/'key'; key.write_text('error-sentinel'); configure(monkeypatch,key)
    monkeypatch.setenv('COMFYUI_LORAS_DIR',str(tmp_path/'loras'));get_settings.cache_clear()
    version,model=resource_payload(); clock=[0.0]; seen=[]
    monkeypatch.setattr(provider,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def handle(request):
        seen.append(request)
        if '/model-versions/' in request.url.path: return httpx.Response(200,json=version)
        if '/api/v1/models/' in request.url.path: return httpx.Response(200,json=model)
        if failure=='redirect': return httpx.Response(307,headers={'location':'https://evil.example/f?token=SIGNED_SENTINEL'})
        if failure=='timeout': clock[0]+=901;return httpx.Response(200,content=b'abcdef')
        if failure=='unauthorized': return httpx.Response(403)
        raise httpx.ConnectError('error-sentinel SIGNED_SENTINEL',request=request)
    wire(handle)
    expected={'bad_file':'civitai_credentials_unavailable','redirect':'civitai_redirect_blocked','timeout':'civitai_timeout','unauthorized':'unauthorized','network':'civitai_network_error'}[failure]
    if failure=='bad_file':
        key.write_text('')
        result=call_mcp('civitai_resource_acquire',{'source':'7'})
        assert not result['ok'] and result['error']['code']==expected
        assert 'CIVITAI_API_KEY_FILE' in result['error']['hint']
        assert not seen and not pending
        return
    admitted=call_mcp('civitai_resource_acquire',{'source':'7'})
    acquisition_id=admitted['data']['resource']['acquisition_id']
    pending.pop()()
    status=call_mcp('civitai_resource_status',{'acquisition_id':acquisition_id})
    resource=status['data']['resources'][0]
    assert resource['status']=='failed' and resource['error']['code']==expected and resource['error']['hint']
    assert 'error-sentinel' not in json.dumps(status) and 'SIGNED_SENTINEL' not in json.dumps(status)
    assert not (tmp_path/'loras/fixture.safetensors').exists()


def test_retained_inspect_install_routes_use_private_file_and_preserve_identity(production_routes,wire,tmp_path,monkeypatch):
    from app.db import database
    from app.db.models import DownloadedResource
    client,_=production_routes
    key=tmp_path/'key';key.write_text('inspect-sentinel');configure(monkeypatch,key)
    monkeypatch.setenv('COMFYUI_LORAS_DIR',str(tmp_path/'loras'));get_settings.cache_clear()
    version,model=resource_payload();seen=[];streams=[]
    def handle(request):
        seen.append(request)
        if '/api/v1/models/' in request.url.path: return httpx.Response(200,json=model)
        stream=Stream();streams.append(stream)
        if request.url.host=='civitai.com': return httpx.Response(307,headers={'location':'https://b2.civitai.com/f'},stream=stream)
        return httpx.Response(200,stream=stream)
    wire(handle)
    inspected=client.post('/api/civitai-recipes/resource-inspect',json={'locator':'https://civitai.com/models/8?modelVersionId=7'})
    assert inspected.status_code==200, inspected.json()
    selected=client.post('/api/civitai-recipes/resource-select',json={'inspect':inspected.json(),'selectors':{'civitai_file_id':11}})
    assert selected.status_code==200, selected.json()
    key.write_text('install-sentinel')
    installed=client.post('/api/civitai-recipes/resource-install',json={'selected':selected.json()['selected'],'storage_root':'loras'})
    assert installed.status_code==200, installed.json()
    assert [r.headers.get('authorization') for r in seen]==['Bearer inspect-sentinel','Bearer install-sentinel',None]
    with database.SessionLocal() as db:
        row=db.query(DownloadedResource).one()
        assert row.id==installed.json()['ledger_id'] and row.civitai_file_id=='11' and row.version_id=='7'
    key.write_text('')
    for route,body in [('resource-inspect',{'locator':'https://civitai.com/models/8'}),('resource-install',{'selected':selected.json()['selected'],'storage_root':'loras'})]:
        response=client.post('/api/civitai-recipes/'+route,json=body)
        assert response.json()['detail']['code']=='civitai_credentials_unavailable'
        assert response.json()['detail']['hint']
    assert len(seen)==3 and all(s.closed for s in streams)


@pytest.mark.parametrize('status,code', [(401,'unauthorized'),(403,'unauthorized'),(429,'civitai_api_error'),(503,'civitai_api_error')])
def test_registered_metadata_refusal_keeps_status_hint(production_routes,wire,status,code):
    _,pending=production_routes
    wire(lambda request:httpx.Response(status,json={'message':'https://b2.civitai.com/f?X-Amz-Signature=SIGNED_SENTINEL'}))
    result=call_mcp('civitai_resource_acquire',{'source':'7'})
    assert not result['ok'] and result['error']['code']==code
    assert str(status) in result['error']['message'] and result['error']['hint']
    assert 'SIGNED_SENTINEL' not in json.dumps(result) and not pending


def test_encoded_and_other_signed_query_keys_are_redacted():
    from app.services.civitai_acquisition import redact_secrets
    url='https://b2.civitai.com/f?%58-Amz-Signature=SIGNED&sig=PRIVATE&X-Bz-Authorization=AUTH&AWSAccessKeyId=IDENTITY&type=Model'
    result=redact_secrets(url)
    for value in ('SIGNED','PRIVATE','AUTH','IDENTITY'): assert value not in result
    assert 'type=Model' in result


def test_metadata_sanitizes_provider_echoes_but_keeps_ephemeral_signed_locator(wire,tmp_path,monkeypatch):
    from app.services.civitai_resource_acquire import resolve_version_metadata
    key=tmp_path/'key';key.write_text('echo-sentinel');configure(monkeypatch,key)
    version,model=resource_payload()
    model.update(name='echo-sentinel',authorization={'raw':'anything-private'},token='other-private')
    wire(lambda request:httpx.Response(200,json=version if '/model-versions/' in request.url.path else model))
    resolved=resolve_version_metadata('7')
    assert resolved['model']['name']=='[REDACTED]'
    assert resolved['model']['authorization']=='[REDACTED]' and resolved['model']['token']=='[REDACTED]'
    assert 'SIGNED_SENTINEL' in resolved['version']['files'][0]['downloadUrl']


@pytest.mark.parametrize('scope', [
    'Domain=.civitai.com; Path=/; Secure',
    'Domain=civitai.com; Path=/files; Secure',
    'Path=/; Secure',
    'Domain=.civitai.com; Path=/',
])
def test_provider_cookie_credentials_never_replay_on_same_cross_or_return_hops(wire, tmp_path, monkeypatch, scope):
    """Removing stateless cookie protection must expose a final wire credential."""
    from app.services.civitai_provider import ProviderOperation, ProviderDownloadTransport
    key=tmp_path/'key'; key.write_text('cookie-file-sentinel'); configure(monkeypatch,key)
    seen=[]; streams=[]
    destinations=[
        'https://civitai.com/files/same', 'https://www.civitai.com/files/www',
        'https://b2.civitai.com/files/cdn', 'https://civitai.com/files/return',
        'https://civitai.com/files/end',
    ]
    def handle(request):
        seen.append(request); stream=Stream(); streams.append(stream)
        headers={'set-cookie':'session=cookie-file-sentinel; '+scope}
        if len(seen)<=len(destinations):
            headers['location']=destinations[len(seen)-1]
            return httpx.Response(307,headers=headers,stream=stream)
        return httpx.Response(200,headers=headers,stream=stream)
    wire(handle)
    with ProviderOperation('download') as op:
        response=ProviderDownloadTransport(op).get('https://civitai.com/files/start')
        assert b''.join(response.body)==b'abcdef'
        # Another request in the same operation gets its allowed Authorization,
        # without accepting any earlier cookie, even after a return hop.
        response=ProviderDownloadTransport(op).get('https://civitai.com/files/repeated')
        assert b''.join(response.body)==b'abcdef'
    assert [r.headers.get('authorization') for r in seen]==['Bearer cookie-file-sentinel']*2+[None]*4+['Bearer cookie-file-sentinel']
    for request in seen:
        assert 'cookie' not in request.headers
        assert 'proxy-authorization' not in request.headers
        assert 'cookie-file-sentinel' not in str(request.url)
        assert all('cookie-file-sentinel' not in v for k,v in request.headers.multi_items() if k!='authorization')
    assert all(s.closed for s in streams)


def test_final_prepared_request_strips_implicit_and_caller_credential_headers(tmp_path,monkeypatch):
    """A filter before build_request cannot stop implicit client credential state."""
    from app.services.civitai_provider import ProviderOperation
    key=tmp_path/'key'; key.write_text('prepared-file-sentinel'); configure(monkeypatch,key)
    original=httpx.AsyncClient; seen=[]
    def handle(request):
        seen.append(request)
        return httpx.Response(200,json={'ok':True})
    class ImplicitClient(original):
        def __init__(self,**kwargs):
            super().__init__(transport=httpx.MockTransport(handle),headers={
                'Cookie':'session=implicit-sentinel','Proxy-Authorization':'Basic implicit-sentinel',
                'Authorization':'Bearer implicit-sentinel'},**kwargs)
            self.cookies.set('implicit','cookie-jar-sentinel',domain='.civitai.com')
    monkeypatch.setattr(httpx,'AsyncClient',ImplicitClient)
    with ProviderOperation('metadata') as op:
        for host in ('civitai.com','www.civitai.com','b2.civitai.com'):
            with op.request('HEAD','https://'+host+'/files',headers={
                    'cOoKiE':'caller-sentinel','pRoXy-AuThOrIzAtIoN':'caller-sentinel',
                    'aUtHoRiZaTiOn':'caller-sentinel','Accept':'application/json'}) as response:
                assert response.status_code==200
    assert [r.headers.get('authorization') for r in seen]==['Bearer prepared-file-sentinel',None,None]
    for request in seen:
        assert request.headers['accept']=='application/json'
        assert 'cookie' not in request.headers
        assert 'proxy-authorization' not in request.headers
        assert all('implicit-sentinel' not in v and 'caller-sentinel' not in v for v in request.headers.values())


@pytest.mark.parametrize('cdn',['b2.civitai.com','www.civitai.com'])
def test_registered_cookie_responses_install_without_replaying_credentials(production_routes,wire,tmp_path,monkeypatch,cdn):
    """Old cookie replay must fail at the registered MCP/Backend/background wire."""
    from app.db import database
    from app.db.models import DownloadedResource
    _,pending=production_routes
    key=tmp_path/'key';key.write_text('registered-cookie-sentinel');configure(monkeypatch,key)
    monkeypatch.setenv('COMFYUI_LORAS_DIR',str(tmp_path/'loras'));get_settings.cache_clear()
    version,model=resource_payload();seen=[];streams=[];downloads=[]
    def handle(request):
        seen.append(request);stream=Stream();streams.append(stream)
        headers={'set-cookie':'session=registered-cookie-sentinel; Domain=.civitai.com; Path=/; Secure'}
        if '/model-versions/' in request.url.path:return httpx.Response(200,json=version,headers=headers)
        if '/api/v1/models/' in request.url.path:return httpx.Response(200,json=model,headers=headers)
        downloads.append(request)
        if len(downloads)==1:
            headers['location']='https://'+cdn+'/file'
            return httpx.Response(307,headers=headers,stream=stream)
        if len(downloads)==2:
            headers['location']='https://civitai.com/return'
            return httpx.Response(307,headers=headers,stream=stream)
        return httpx.Response(200,headers=headers,stream=stream)
    wire(handle)
    admitted=call_mcp('civitai_resource_acquire',{'source':'7'});assert admitted['ok']
    identity=admitted['data']['resource']['acquisition_id'];assert len(pending)==1
    pending.pop()()
    status=call_mcp('civitai_resource_status',{'acquisition_id':identity})
    row=status['data']['resources'][0]
    assert row['status']=='installed' and row['acquisition_id']==identity
    assert Path(row['local_path']).read_bytes()==b'abcdef'
    assert [r.headers.get('authorization') for r in downloads]==['Bearer registered-cookie-sentinel',None,None]
    for request in seen:
        assert 'cookie' not in request.headers
        assert 'proxy-authorization' not in request.headers
        assert all('registered-cookie-sentinel' not in v for k,v in request.headers.multi_items() if k!='authorization')
    # Only download responses use the explicit streams above.
    assert all(s.closed for s in streams[2:])
    with database.SessionLocal() as db:
        stored=db.query(DownloadedResource).one()
        assert stored.id==identity and stored.civitai_file_id=='11'
        durable=json.dumps({c.name:getattr(stored,c.name) for c in DownloadedResource.__table__.columns},default=str)
    assert 'registered-cookie-sentinel' not in durable+json.dumps(admitted)+json.dumps(status)


@pytest.mark.parametrize('entry',['acquire','install'])
@pytest.mark.parametrize('bad',['format','oversize','fractional','sha','space','unknown_space'])
def test_p203_production_admission_gates_have_no_body_partial_or_row(production_routes,wire,tmp_path,monkeypatch,entry,bad):
    from app.db import database
    from app.db.models import DownloadedResource
    import shutil
    client,pending=production_routes
    key=tmp_path/'key';key.write_text('synthetic-p203');configure(monkeypatch,key)
    monkeypatch.setenv('COMFYUI_LORAS_DIR',str(tmp_path/'loras'))
    monkeypatch.setenv('CIVITAI_DOWNLOAD_MAX_BYTES','8')
    monkeypatch.setenv('CIVITAI_DOWNLOAD_FREE_SPACE_FLOOR_BYTES','10');get_settings.cache_clear()
    version,model=resource_payload(); file=version['files'][0]; requests=[]
    if bad=='format': file['name']='fixture.ckpt'
    elif bad=='oversize': file['sizeKB']=9/1024
    elif bad=='fractional': file['sizeKB']=2.75/1024
    elif bad=='sha': file['hashes']['SHA256']='invalid'
    elif bad=='space': monkeypatch.setattr(shutil,'disk_usage',lambda _: type('Space',(),{'free':15})())
    elif bad=='unknown_space': monkeypatch.setattr(shutil,'disk_usage',lambda _: type('Space',(),{'free':None})())
    def handler(request):
        requests.append(request.url.path)
        if '/model-versions/' in request.url.path:return httpx.Response(200,json=version)
        if '/api/v1/models/' in request.url.path:return httpx.Response(200,json=model)
        raise AssertionError('pre-admission body traffic')
    wire(handler)
    if entry=='acquire':
        response=call_mcp('civitai_resource_acquire',{'source':'7'})
        assert response['ok'] is False
    else:
        inspected=client.post('/api/civitai-recipes/resource-inspect',json={'locator':'https://civitai.com/models/8'})
        selection=client.post('/api/civitai-recipes/resource-select',json={'inspect':inspected.json(),'selectors':{'civitai_file_id':11}})
        if selection.status_code==200:
            response=client.post('/api/civitai-recipes/resource-install',json={'selected':selection.json()['selected'],'storage_root':'loras'})
            assert response.status_code in {409,422}
        else: assert selection.status_code in {409,422}
    with database.SessionLocal() as db: assert db.query(DownloadedResource).count()==0
    assert not pending and not (tmp_path/'loras').exists()
    assert all('/api/download/' not in path for path in requests)
