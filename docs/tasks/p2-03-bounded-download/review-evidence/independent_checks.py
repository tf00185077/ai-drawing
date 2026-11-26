"""AID-209 independent contract checks against the pinned candidate.

Only HTTP I/O, deterministic scheduling, free-space observations and explicit
adverse filesystem/commit events are substituted. Production callers and
configured-file credential resolution remain real.
"""
import hashlib
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from tests.conftest import client, isolated_database, isolated_worker_admission
from tests.test_resource_record_writers import boundary, acquire_http
from tests.test_civitai_download_callers import descriptor
from app.config import get_settings
from app.db import database
from app.db.models import DownloadedResource
from app.services import civitai_provider as provider
from app.services.resource_records import project_resource
from app.services.civitai_safe_download import CivitaiFileMetadata, DownloadResponse, safe_download
from app.services.civitai_download_policy import DownloadPolicy

HTTP_CLIENT = httpx.AsyncClient


def meta(data=b'abcdef'):
    return CivitaiFileMetadata('https://civitai.com/api/download/models/21', hashlib.sha256(data).hexdigest(), len(data), scan_status='clean')


class Transport:
    def __init__(self, body, status=200, headers=None):
        self.body, self.status, self.headers, self.calls = body, status, headers or {}, 0
    def get(self, *a, **kw):
        self.calls += 1
        return DownloadResponse(self.status, self.body, self.headers)


@pytest.fixture
def small_policy(monkeypatch):
    monkeypatch.setenv('CIVITAI_DOWNLOAD_MAX_BYTES', '64')
    monkeypatch.setenv('CIVITAI_DOWNLOAD_FREE_SPACE_FLOOR_BYTES', '10')
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_independent_byte_guard_observes_refusal_before_write(tmp_path, small_policy):
    target = tmp_path/'model'; seen = []
    def body():
        try:
            yield b'ab'
            seen.append((tmp_path/'model.part').read_bytes())
            yield b'cdef!'
            seen.append('overrun')
        finally:
            seen.append('closed')
    result = safe_download(meta(), target, transport=Transport(body()))
    assert result.bytes == 2 and result.diagnostics['code'] == 'civitai_byte_limit_exceeded'
    assert seen == [b'ab', 'closed'] and not target.exists()


def test_independent_space_guard_tracks_destination_and_every_write(tmp_path, monkeypatch, small_policy):
    target = tmp_path/'new'/'model'; observed = []; free = iter([100, 100, 12])
    def space(path):
        observed.append(Path(path))
        return SimpleNamespace(free=next(free))
    monkeypatch.setattr(shutil, 'disk_usage', space)
    result = safe_download(meta(), target, transport=Transport(iter([b'ab', b'cdef'])))
    assert result.bytes == 2 and result.diagnostics['code'] == 'civitai_insufficient_space'
    assert observed == [tmp_path, target.parent, target.parent] and not target.exists()


def prefix(target):
    proof=[]
    association=dict(provider='civitai', model_id='10', version_id='21', file_id='32', resource_id=17, size=6, sha256=meta().sha256)
    def body():
        yield b'ab'
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        safe_download(meta(), target, transport=Transport(body()), association=association, record_partial=proof.append)
    return association, proof[-1]


@pytest.mark.parametrize('header', [None, 'bytes 0-5/6', 'bytes 2-4/6', 'bytes 2-5/7', 'bytes 2-5/*'])
def test_independent_range_guard_retains_owned_prefix(tmp_path, small_policy, header):
    target=tmp_path/'model'; association, proof=prefix(target); part=tmp_path/'model.part'; before=part.stat()
    result=safe_download(meta(), target, transport=Transport(b'cdef', 206, {'Content-Range': header} if header else {}), association=association, resume=proof)
    assert result.status=='failed' and result.diagnostics['code']=='civitai_invalid_range'
    assert part.read_bytes()==b'ab' and part.stat()==before and not target.exists()


@pytest.mark.parametrize('status', [200, 206])
def test_independent_valid_resume_and_restart(tmp_path, small_policy, status):
    target=tmp_path/'model'; association, proof=prefix(target)
    result=safe_download(meta(), target, transport=Transport(b'cdef' if status==206 else b'abcdef', status, {'Content-Range':'bytes 2-5/6'} if status==206 else {}), association=association, resume=proof)
    assert result.status=='completed' and target.read_bytes()==b'abcdef' and result.actual_sha256==meta().sha256


def test_independent_publication_collision_guard(tmp_path, small_policy):
    target=tmp_path/'model'
    def body():
        yield b'ab'
        target.write_bytes(b'concurrent prior data')
        yield b'cdef'
    result=safe_download(meta(), target, transport=Transport(body()))
    assert target.read_bytes()==b'concurrent prior data' and result.actual_sha256 is None
    assert result.status=='failed' and result.diagnostics['code']=='civitai_target_exists'


@pytest.mark.parametrize('body', [b'abcde', b'xxxxxx'])
def test_independent_size_hash_guard(tmp_path, small_policy, body):
    target=tmp_path/'model'
    result=safe_download(meta(), target, transport=Transport(body))
    assert result.status=='failed' and result.diagnostics['code']=='civitai_verification_failed'
    assert result.actual_sha256 is None and not target.exists()


@pytest.mark.parametrize('entry', ['acquire','install'])
@pytest.mark.parametrize('adverse', ['format','oversize','fractional','badsha','space','unknownspace'])
def test_independent_registered_admission_without_side_effects(boundary, monkeypatch, entry, adverse):
    b=boundary; selected=descriptor(b)
    if adverse=='format':
        for f in b.version['files']: f['name']=f['name'].replace('.safetensors','.ckpt')
        selected['name']='selected.ckpt'
    elif adverse=='oversize': monkeypatch.setenv('CIVITAI_DOWNLOAD_MAX_BYTES','1')
    elif adverse=='fractional':
        b.file['size']=1.25; selected['byte_size']=1.25
    elif adverse=='badsha':
        b.file['hashes']['SHA256']='invalid'; selected['sha256']='invalid'
    elif adverse in {'space','unknownspace'}:
        monkeypatch.setattr(shutil,'disk_usage',lambda _:SimpleNamespace(free=0 if adverse=='space' else None))
    get_settings.cache_clear()
    result=acquire_http(b) if entry=='acquire' else b.client.post('/api/civitai-recipes/resource-install',json={'selected':selected,'storage_root':'loras'})
    assert result.status_code in {409,422}, result.text
    assert not b.pending and not (b.tmp/'loras').exists()
    assert not any('/api/download/' in path for path,_ in b.seen)
    with database.SessionLocal() as db: assert db.query(DownloadedResource).count()==0


@pytest.mark.parametrize('entry', ['acquire','install'])
def test_independent_configured_file_rotation_and_origin(boundary, monkeypatch, entry):
    b=boundary; selected=descriptor(b); key=b.tmp/'synthetic-key'; key.write_text('independent-rotated-key')
    monkeypatch.setenv('CIVITAI_AUTHORIZATION','must-never-win')
    get_settings.cache_clear(); seen=[]; closed=[]
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self): yield b.body
        async def aclose(self): closed.append(True)
    def wire(request):
        seen.append((request.url.host, request.url.path, request.headers.get('authorization')))
        if '/api/v1/' in request.url.path:
            return httpx.Response(200,json=b.model if '/models/' in request.url.path else b.version)
        if request.url.host=='civitai.com': return httpx.Response(302,headers={'location':'https://b2.civitai.com/object'})
        return httpx.Response(200,stream=Body())
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:HTTP_CLIENT(transport=httpx.MockTransport(wire),**kw))
    if entry=='acquire':
        result=acquire_http(b); assert result.status_code==202,result.text; b.pending.pop()()
    else:
        result=b.client.post('/api/civitai-recipes/resource-install',json={'selected':selected,'storage_root':'loras'})
        assert result.status_code==200,result.text
    assert closed and all(auth=='Bearer independent-rotated-key' for host,_,auth in seen if host=='civitai.com')
    assert seen[-1]==('b2.civitai.com','/object',None)
    assert (b.tmp/'loras'/selected['name']).read_bytes()==b.body
    assert 'independent-rotated-key' not in result.text and 'must-never-win' not in result.text


@pytest.mark.parametrize('entry', ['acquire','install'])
def test_independent_bad_configured_file_never_falls_back(boundary, monkeypatch, entry):
    b=boundary; selected=descriptor(b); (b.tmp/'synthetic-key').write_text('invalid internal whitespace')
    monkeypatch.setenv('CIVITAI_AUTHORIZATION','fallback-key'); get_settings.cache_clear()
    result=acquire_http(b) if entry=='acquire' else b.client.post('/api/civitai-recipes/resource-install',json={'selected':selected,'storage_root':'loras'})
    assert result.status_code==422 and not b.seen and not b.pending
    with database.SessionLocal() as db: assert db.query(DownloadedResource).count()==0


@pytest.mark.parametrize('adverse', ['deadline','replacement'])
def test_adoption_failure_after_commit_must_publish_current_failure(boundary, monkeypatch, adverse):
    """A real installed-state commit returns, then deadline/path verification fails."""
    b=boundary; selected=descriptor(b); target=b.tmp/'loras'/selected['name']; target.parent.mkdir(); target.write_bytes(b.body)
    raw=' old notes preserved byte for byte '
    with database.SessionLocal() as db:
        row=DownloadedResource(provider='civitai',resource_type='lora',resource_name=selected['name'],status='planned',source_url=selected['download_url_identity'],model_id='10',version_id='21',civitai_file_id='32',sha256=b.sha,file_size=len(b.body),local_path=str(target),storage_root='loras',notes=raw)
        db.add(row);db.commit();rid=row.id
    operations=[]; original_init=provider.ProviderOperation.__init__
    def init(self,*a,**kw): original_init(self,*a,**kw); operations.append(self)
    monkeypatch.setattr(provider.ProviderOperation,'__init__',init)
    cls=database.SessionLocal.class_; commit=cls.commit; fired=[]
    def committed(db):
        changes=[r for r in db.dirty if isinstance(r,DownloadedResource) and r.status=='installed']
        commit(db)
        if changes and not fired:
            fired.append(True)
            if adverse=='deadline':
                for operation in operations: operation.deadline=-1
            else:
                target.rename(target.with_suffix('.original'))
                target.write_bytes(b'foreign replacement during commit')
    monkeypatch.setattr(cls,'commit',committed)
    result=b.client.post('/api/civitai-recipes/resource-install',json={'selected':selected,'storage_root':'loras'})
    status=b.client.get('/api/civitai/resources/status',params={'acquisition_id':rid}).json()['resources'][0]
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid); notes=row.notes; measured=project_resource(row).sha256_verified
    print('QA_ADOPTION_COMMIT='+json.dumps({'adverse':adverse,'http':result.status_code,'body':result.json(),'row_status':status['status'],'error':status.get('error'),'measured':measured,'notes_exact':notes==raw,'event_fired':bool(fired)}))
    assert fired and result.status_code==500 and notes==raw
    if adverse=='replacement': assert target.read_bytes()==b'foreign replacement during commit'
    assert status['status']=='failed', 'post-admission/adoption failure must be current on the same row'
    assert status['error']['code']==('civitai_timeout' if adverse=='deadline' else 'civitai_file_changed')


def test_acquire_then_retained_install_must_not_duplicate_active_body(boundary):
    b=boundary; selected=descriptor(b)
    first=acquire_http(b); assert first.status_code==202,first.text
    rid=first.json()['resource']['acquisition_id']; assert len(b.pending)==1
    second=b.client.post('/api/civitai-recipes/resource-install',json={'selected':selected,'storage_root':'loras'})
    bodies=[path for path,_ in b.seen if '/api/download/' in path]
    during=b.client.get('/api/civitai/resources/status',params={'acquisition_id':rid}).json()['resources'][0]
    b.pending.pop()()
    after=b.client.get('/api/civitai/resources/status',params={'acquisition_id':rid}).json()['resources'][0]
    print('QA_DUPLICATE='+json.dumps({'retained_http':second.status_code,'body_requests':bodies,'original_was_pending':True,'resource_id':rid,'during':during['status'],'after':after['status'],'after_error':after.get('error')}))
    assert bodies==[], 'an already-admitted active resource must not submit another body request'


@pytest.mark.parametrize('entry',['acquire','install'])
@pytest.mark.parametrize('fault',['cap','space','hash','collision','network','denied','latehash','latepublication'])
def test_independent_real_provider_closure_and_same_id_failure(boundary, monkeypatch, entry, fault):
    from app.services import civitai_safe_download as download
    b=boundary; selected=descriptor(b); target=b.tmp/'loras'/selected['name']; streams=[]; seen=[]
    monkeypatch.setenv('CIVITAI_DOWNLOAD_MAX_BYTES','64')
    monkeypatch.setenv('CIVITAI_DOWNLOAD_FREE_SPACE_FLOOR_BYTES','10');get_settings.cache_clear()
    raw=' original notes with Authorization: Bearer historical-secret '
    with database.SessionLocal() as db:
        row=DownloadedResource(provider='civitai',resource_type='lora',resource_name=selected['name'],status='failed',source_url=selected['download_url_identity'],model_id='10',version_id='21',civitai_file_id='32',sha256=b.sha,file_size=len(b.body),local_path=str(target),storage_root='loras',notes=raw)
        db.add(row);db.commit();rid=row.id
    operations=[]; original_init=provider.ProviderOperation.__init__
    def init(self,*a,**kw): original_init(self,*a,**kw); operations.append(self)
    monkeypatch.setattr(provider.ProviderOperation,'__init__',init)
    if fault=='latehash':
        digest=download._digest
        def late(stream,operation):
            value=digest(stream,operation)
            if os.fstat(stream.fileno()).st_size==len(b.body): operation.deadline=-1
            return value
        monkeypatch.setattr(download,'_digest',late)
    if fault=='latepublication':
        link=os.link
        def late_link(*a,**kw):
            link(*a,**kw)
            for operation in operations: operation.deadline=-1
        monkeypatch.setattr(os,'link',late_link)
    class Body(httpx.AsyncByteStream):
        closed=False
        async def __aiter__(self):
            if fault=='space': monkeypatch.setattr(shutil,'disk_usage',lambda _:SimpleNamespace(free=10))
            if fault=='collision': target.write_bytes(b'concurrent foreign model')
            if fault=='network': raise httpx.ReadError('Authorization: Bearer synthetic-no-public')
            yield b.body+b'!' if fault=='cap' else b'X'*len(b.body) if fault=='hash' else b.body
        async def aclose(self): self.closed=True
    def wire(request):
        seen.append(request)
        if '/api/v1/' in request.url.path: return httpx.Response(200,json=b.model if '/models/' in request.url.path else b.version)
        stream=Body();streams.append(stream)
        return httpx.Response(403 if fault=='denied' else 200,stream=stream)
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:HTTP_CLIENT(transport=httpx.MockTransport(wire),**kw))
    if entry=='acquire':
        response=acquire_http(b); assert response.status_code==202,response.text
        assert response.json()['resource']['acquisition_id']==rid; b.pending.pop()()
    else:
        response=b.client.post('/api/civitai-recipes/resource-install',json={'selected':selected,'storage_root':'loras'})
        assert response.status_code==500,response.text
    public=b.client.get('/api/civitai/resources/status',params={'acquisition_id':rid})
    status=public.json()['resources'][0]
    expected={'cap':'civitai_byte_limit_exceeded','space':'civitai_insufficient_space','hash':'civitai_verification_failed','collision':'civitai_target_exists','network':'civitai_network_error','denied':'unauthorized','latehash':'civitai_timeout','latepublication':'civitai_timeout'}[fault]
    assert status['status']=='failed' and status['error']['code']==expected
    assert len(streams)==1 and streams[0].closed
    assert 'historical-secret' not in public.text and 'synthetic-no-public' not in public.text
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        assert db.query(DownloadedResource).count()==1 and row.notes==raw and row.sha256==b.sha
        assert project_resource(row).sha256_verified is None
    if fault=='collision': assert target.read_bytes()==b'concurrent foreign model'
    print('QA_PROVIDER_EXIT='+json.dumps({'entry':entry,'fault':fault,'code':status['error']['code'],'resource_id':rid,'closed':streams[0].closed,'body_requests':len(streams),'notes_exact':row.notes==raw,'final_exists':target.exists()}))
