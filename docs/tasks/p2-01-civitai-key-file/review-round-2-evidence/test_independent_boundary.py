"""Additional QA HTTP observations; every credential here is synthetic."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'backend/tests'))
from conftest import client, isolated_database, isolated_worker_admission
from test_civitai_provider import (private_config, wire, production_routes,
                                  configure, Stream, resource_payload, call_mcp)

def check_cross_origin_cookie_credential_excluded(wire, tmp_path, monkeypatch):
    """A canonical response must not echo the configured credential via a cookie."""
    from app.services.civitai_provider import ProviderOperation
    key=tmp_path/'key'; key.write_text('qa-file-sentinel'); configure(monkeypatch,key)
    seen=[]; streams=[]
    def handle(request):
        seen.append(request)
        if len(seen)==1:
            stream=Stream(); streams.append(stream)
            return httpx.Response(307,headers={
                'location':'https://b2.civitai.com/file',
                'set-cookie':'session=qa-file-sentinel; Domain=.civitai.com; Path=/; Secure',
            },stream=stream)
        return httpx.Response(200,json={'ok':True})
    wire(handle)
    with ProviderOperation('metadata') as op: assert op.get_json('https://civitai.com/file')[0]==200
    assert seen[0].headers['authorization']=='Bearer qa-file-sentinel'
    assert 'authorization' not in seen[1].headers
    assert 'cookie' not in seen[1].headers
    assert all(s.closed for s in streams)

def test_cookie_boundary_credential_excluded(wire,tmp_path,monkeypatch):
    """Positive security guard; historical adverse record remains unchanged."""
    check_cross_origin_cookie_credential_excluded(wire,tmp_path,monkeypatch)

def test_registered_download_cookie_credentials_excluded(production_routes,wire,tmp_path,monkeypatch):
    """Positive registered/background security guard after R1 correction."""
    from app.config import get_settings
    client,pending=production_routes
    key=tmp_path/'key';key.write_text('qa-registered-sentinel');configure(monkeypatch,key)
    monkeypatch.setenv('COMFYUI_LORAS_DIR',str(tmp_path/'loras'));get_settings.cache_clear()
    version,model=resource_payload();seen=[];streams=[]
    def handle(request):
        seen.append(request)
        if '/model-versions/' in request.url.path:return httpx.Response(200,json=version)
        if '/api/v1/models/' in request.url.path:return httpx.Response(200,json=model)
        stream=Stream();streams.append(stream)
        if request.url.host=='civitai.com':
            return httpx.Response(307,headers={'location':'https://b2.civitai.com/file',
                'set-cookie':'session=qa-registered-sentinel; Domain=.civitai.com; Path=/; Secure'},stream=stream)
        return httpx.Response(200,stream=stream)
    wire(handle)
    admitted=call_mcp('civitai_resource_acquire',{'source':'7'});assert admitted['ok']
    pending.pop()()
    result=call_mcp('civitai_resource_status',{'acquisition_id':admitted['data']['resource']['acquisition_id']})
    assert result['data']['resources'][0]['status']=='installed'
    assert seen[-1].url.host=='b2.civitai.com'
    assert seen[-1].headers.get('authorization') is None
    assert 'cookie' not in seen[-1].headers
    assert all('cookie' not in r.headers and 'proxy-authorization' not in r.headers for r in seen)
    assert all(s.closed for s in streams)

@pytest.mark.parametrize('url',[
    'https://civitai.com./f','https://user:pass@b2.civitai.com/f',
    'https://civitai.com:443.evil/f','https://civitai.com\\@b2.civitai.com/f',
    'https://b2.civitai.com:444/f','https://civitai.com/f\nheader',
])
def test_additional_url_rejections_precede_io(wire,url):
    from app.services.civitai_provider import ProviderOperation,CivitaiProviderError
    seen=[]
    wire(lambda request:seen.append(request))
    with ProviderOperation('metadata') as op:
        with pytest.raises(CivitaiProviderError) as error: op.get_json(url)
    assert error.value.code=='civitai_redirect_blocked' and not seen

def test_exact_default_port_allows_auth_and_www_does_not(wire,monkeypatch):
    from app.services.civitai_provider import ProviderOperation
    configure(monkeypatch,legacy='qa-auth-sentinel'); seen=[]
    def handle(request): seen.append(request); return httpx.Response(200,json={})
    wire(handle)
    for url in ('https://civitai.com:443/f','https://www.civitai.com:443/f'):
        with ProviderOperation('metadata') as op: op.get_json(url)
    assert [r.headers.get('authorization') for r in seen]==['Bearer qa-auth-sentinel',None]

def test_actual_async_nested_metadata_total_and_close(wire,tmp_path,monkeypatch):
    from app.services.civitai_provider import ProviderOperation,CivitaiProviderError
    from app.services.civitai_resource_acquire import _JsonTransport,_resolve_version_metadata
    configure(monkeypatch); streams=[];seen=[]
    class Drip(Stream):
        async def __aiter__(self):
            for b in json.dumps({'id':7,'modelId':8}).encode():
                await asyncio.sleep(.004)
                yield bytes([b])
    def handle(request):
        seen.append(request); s=Drip();streams.append(s);return httpx.Response(200,stream=s)
    wire(handle); started=time.monotonic()
    with ProviderOperation('metadata') as op:
        op.deadline=time.monotonic()+.03
        with pytest.raises(CivitaiProviderError) as error:
            _resolve_version_metadata('7',transport=_JsonTransport(op),headers=op.headers)
    assert error.value.code=='civitai_timeout'
    assert time.monotonic()-started<.5
    assert len(seen)==1 and all(s.closed for s in streams)

def test_rotated_invalid_download_file_reports_same_id_without_io(production_routes,wire,tmp_path,monkeypatch):
    from app.config import get_settings
    client,pending=production_routes
    key=tmp_path/'key';key.write_text('qa-good-sentinel');configure(monkeypatch,key,'qa-legacy-sentinel')
    monkeypatch.setenv('COMFYUI_LORAS_DIR',str(tmp_path/'loras'));get_settings.cache_clear()
    version,model=resource_payload();seen=[]
    def handle(request):
        seen.append(request)
        return httpx.Response(200,json=version if '/model-versions/' in request.url.path else model)
    wire(handle)
    admitted=call_mcp('civitai_resource_acquire',{'source':'7'});assert admitted['ok']
    identity=admitted['data']['resource']['acquisition_id'];key.write_text('')
    pending.pop()()
    result=call_mcp('civitai_resource_status',{'acquisition_id':identity})
    row=result['data']['resources'][0]
    assert row['acquisition_id']==identity and row['status']=='failed'
    assert row['error']['code']=='civitai_credentials_unavailable'
    assert 'CIVITAI_API_KEY_FILE' in row['error']['hint']
    assert len(seen)==2 and not (tmp_path/'loras/fixture.safetensors').exists()


@pytest.mark.parametrize('kind',['metadata','download'])
@pytest.mark.parametrize('scope',[
    'Domain=.civitai.com; Path=/; Secure',
    'Domain=civitai.com; Path=/files; Secure',
    'Path=/; Secure',
    'Domain=.civitai.com; Path=/',
])
def test_cookie_acceptance_and_replay_are_both_disabled(tmp_path,monkeypatch,kind,scope):
    """Observe final wire channels, client retention, byte flow and closure."""
    from app.services.civitai_provider import ProviderOperation,ProviderDownloadTransport
    key=tmp_path/'key';key.write_text('qa-round2-cookie-sentinel');configure(monkeypatch,key)
    original=httpx.AsyncClient;clients=[];seen=[];streams=[]
    destinations=['https://civitai.com/files/same','https://b2.civitai.com/files/cdn',
                  'https://civitai.com/files/return']
    def handle(request):
        seen.append(request)
        headers={'set-cookie':'session=qa-round2-cookie-sentinel; '+scope}
        if len(seen)<=len(destinations):
            headers['location']=destinations[len(seen)-1]
            stream=Stream();streams.append(stream)
            return httpx.Response(307,headers=headers,stream=stream)
        if kind=='metadata':return httpx.Response(200,json={'ok':True},headers=headers)
        stream=Stream();streams.append(stream)
        return httpx.Response(200,stream=stream,headers=headers)
    class ObservedClient(original):
        def __init__(self,**kwargs):
            super().__init__(transport=httpx.MockTransport(handle),**kwargs)
            clients.append(self)
    monkeypatch.setattr(httpx,'AsyncClient',ObservedClient)
    with ProviderOperation(kind) as op:
        for route in ('start','again'):
            url='https://civitai.com/files/'+route
            if kind=='metadata':assert op.get_json(url)==(200,{'ok':True})
            else:
                response=ProviderDownloadTransport(op).get(url)
                assert response.status_code==200
                assert b''.join(response.body)==b'abcdef'
    assert [r.headers.get('authorization') for r in seen]==[
        'Bearer qa-round2-cookie-sentinel','Bearer qa-round2-cookie-sentinel',None,None,
        'Bearer qa-round2-cookie-sentinel']
    for request in seen:
        assert 'cookie' not in request.headers
        assert 'proxy-authorization' not in request.headers
        assert 'qa-round2-cookie-sentinel' not in str(request.url)
        assert all('qa-round2-cookie-sentinel' not in v for k,v in request.headers.multi_items() if k!='authorization')
    # Replay stripping alone would hide a retained authentication cookie. The
    # stateless requirement also forbids accepting it into the client's state.
    assert all(not list(client.cookies.jar) for client in clients)
    assert all(client.is_closed for client in clients)
    assert all(stream.closed for stream in streams)
