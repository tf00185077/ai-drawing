"""p2-03 production row/notes/publication outcomes; no alternate downloader."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest

_HTTPClient = httpx.AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import database
from app.db.models import DownloadedResource
from app.services import civitai_resource_install as install
from app.services.civitai_safe_download import DownloadResponse
from app.services.resource_records import project_resource, download_context
from tests.test_resource_record_writers import boundary, acquire_http


def descriptor(b):
    from app.services.civitai_resource_install import inspect_civitai_resource, select_civitai_resource
    return select_civitai_resource(inspect_civitai_resource(b.model),{'civitai_file_id':32})['selected']


@pytest.mark.parametrize('entry',['acquire','install'])
@pytest.mark.parametrize('fault',['bytes','space','hash','collision','body_error','unauthorized'])
def test_admitted_failure_keeps_same_row_notes_identity_and_closes(boundary,monkeypatch,entry,fault):
    import shutil
    b=boundary; selected=descriptor(b); target=b.tmp/'loras'/'selected.safetensors'
    raw=' \n'+json.dumps({'old':'historical note','error':{'code':'old'}})+' \t'
    with database.SessionLocal() as db:
        row=DownloadedResource(provider='civitai',resource_type='lora',resource_name=selected['name'],status='planned',source_url=selected['download_url_identity'],
            model_id='10',version_id='21',civitai_file_id='32',sha256=b.sha,file_size=len(b.body),local_path=str(target),storage_root='loras',notes=raw)
        db.add(row);db.commit();rid=row.id
    seen=[]; streams=[]; original=_HTTPClient
    class Body(httpx.AsyncByteStream):
        closed=False
        async def __aiter__(self):
            if fault=='collision': target.write_bytes(b'foreign racing final')
            if fault=='space': monkeypatch.setattr(shutil,'disk_usage',lambda _:SimpleNamespace(free=0))
            if fault=='body_error': raise httpx.ReadError('synthetic; do not serialize secrets')
            yield b.body+b'!' if fault=='bytes' else b'X'*len(b.body) if fault=='hash' else b.body
        async def aclose(self): self.closed=True
    def handler(request):
        seen.append(request)
        if '/api/v1/' in request.url.path:return httpx.Response(200,json=b.model if '/models/' in request.url.path else b.version)
        stream=Body();streams.append(stream);return httpx.Response(403 if fault=='unauthorized' else 200,stream=stream)
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw: original(transport=httpx.MockTransport(handler),**kw))
    if entry=='acquire':
        admitted=acquire_http(b);assert admitted.status_code==202,admitted.text
        assert admitted.json()['resource']['acquisition_id']==rid
        b.pending.pop()()
    else:
        response=b.client.post('/api/civitai-recipes/resource-install',json={'selected':selected,'storage_root':'loras'})
        assert response.status_code==500,response.text
        assert response.json()['detail']['diagnostic']['resource_id']==rid
    status=b.client.get('/api/civitai/resources/status',params={'acquisition_id':rid}).json()['resources'][0]
    assert status['status']=='failed' and status['acquisition_id']==rid and status['error']!= {'code':'old'}
    expected={'bytes':'civitai_byte_limit_exceeded','space':'civitai_insufficient_space','hash':'civitai_verification_failed','collision':'civitai_target_exists','body_error':'civitai_network_error','unauthorized':'unauthorized'}[fault]
    assert status['error']['code']==expected,status
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        assert row.notes==raw and row.sha256==b.sha and row.civitai_file_id=='32'
        assert db.query(DownloadedResource).count()==1 and project_resource(row).sha256_verified is None
    assert len(streams)==1 and all(s.closed for s in streams)
    if fault=='collision':assert target.read_bytes()==b'foreign racing final'
    else:assert not target.exists()
    assert all(r.headers.get('Authorization')=='Bearer resource-fixture-key' for r in seen)
    print('P203_ROW_TRACE='+json.dumps({'entry':entry,'fault':fault,'resource_id':rid,'status':status['status'],'code':status['error']['code'],'old_notes_sha256':hashlib.sha256(raw.encode()).hexdigest(),'old_notes_exact':row.notes==raw,'selected_sha256':b.sha,'body_requests':len(streams),'all_bodies_closed':all(s.closed for s in streams),'final_exists':target.exists()}))


@pytest.mark.parametrize('replace_final',[False,True])
def test_retained_commit_compensation_checks_the_actual_publication(boundary,monkeypatch,replace_final):
    b=boundary; selected=descriptor(b); target=b.tmp/'loras'/selected['name']; original=install._persist_ledger_identity
    def reject(*args,**kw):
        assert target.read_bytes()==b.body
        if replace_final:
            target.rename(target.with_suffix('.owned'))
            target.write_bytes(b'foreign replacement')
        raise RuntimeError('synthetic commit failure')
    monkeypatch.setattr(install,'_persist_ledger_identity',reject)
    with database.SessionLocal() as db:
        response=install.install_civitai_resource(selected,'loras',db=db,storage_roots={'loras':target.parent},transport=SimpleNamespace(get=lambda *a,**kw: DownloadResponse(200,b.body)))
        row=db.query(DownloadedResource).one()
        assert row.status=='failed' and row.id==response['ledger_id']
        assert project_resource(row).sha256_verified is None
    assert response['status']=='failed' and response['diagnostic']['code']=='ledger_persistence_failed'
    if replace_final: assert target.read_bytes()==b'foreign replacement' and target.with_suffix('.owned').read_bytes()==b.body
    else: assert not target.exists()
    print('P203_COMPENSATION_TRACE='+json.dumps({'replaced':replace_final,'status':response['status'],'resource_id':response['ledger_id'],'final_exists':target.exists(),'replacement_preserved':target.read_bytes()==b'foreign replacement' if replace_final else None}))


@pytest.mark.parametrize('entry',['acquire','install'])
@pytest.mark.parametrize('response_status',[200,206,'bad206'])
def test_real_row_resume_association_survives_interruption_and_retries_same_id(boundary,monkeypatch,entry,response_status):
    b=boundary; selected=descriptor(b); target=b.tmp/'loras'/selected['name']; requests=[]; original=_HTTPClient; interrupted=[True]
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            if interrupted[0]:
                # Production transport emits 1 MiB chunks, so interrupt after one full chunk.
                yield b.body[:1024*1024]
                raise KeyboardInterrupt()
            yield b.body[1024*1024:] if response_status==206 else b.body
        async def aclose(self): pass
    # A complete retained prefix is safe for a bounded 200 restart; body closure
    # and partial proof are established by the actual helper/ORM callback.
    def handler(request):
        requests.append(request)
        if '/api/v1/' in request.url.path:return httpx.Response(200,json=b.model if '/models/' in request.url.path else b.version)
        return httpx.Response(200 if interrupted[0] else 206 if response_status=='bad206' else response_status,stream=Body(), headers={"Content-Range": f"bytes 1048576-{len(b.body)-1}/{len(b.body)+(1 if response_status=='bad206' else 0)}"} if response_status in {206,'bad206'} and not interrupted[0] else {})
    # Make the interrupted chunk exactly the provider's production chunk size.
    b.body=b'a'*(2*1024*1024);b.sha=hashlib.sha256(b.body).hexdigest();b.file['sizeKB']=2048;b.file['hashes']['SHA256']=b.sha
    selected=descriptor(b)
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    if entry=='acquire':
        rid=acquire_http(b).json()['resource']['acquisition_id']
        with pytest.raises(KeyboardInterrupt): b.pending.pop()()
    else:
        # Existing authority can have unknown model/version columns; admission
        # must fill them from this selected identity before binding a partial.
        with database.SessionLocal() as db:
            db.add(DownloadedResource(provider='civitai',resource_type='lora',resource_name=selected['name'],
                source_url=selected['download_url_identity'],civitai_file_id='32',status='planned',notes=' old notes '))
            db.commit()
        with database.SessionLocal() as db:
            from app.services.civitai_provider import ProviderOperation, ProviderDownloadTransport
            with ProviderOperation('download') as operation:
                with pytest.raises(KeyboardInterrupt):
                    install.install_civitai_resource(selected,'loras',db=db,storage_roots={'loras':target.parent},transport=ProviderDownloadTransport(operation),operation=operation)
        with database.SessionLocal() as db:rid=db.query(DownloadedResource).one().id
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid);association,proof=download_context(row,len(b.body),b.sha)
        print('P203_ASSOCIATION_TRACE='+json.dumps({'entry':entry,'response':response_status,'association':association,'proof':proof,'current_status':row.status}))
        assert proof['association']==association and proof['identity']['size']==1024*1024
        assert row.status=='failed'
    interrupted[0]=False
    if entry=='acquire':
        assert acquire_http(b).json()['resource']['acquisition_id']==rid;b.pending.pop()()
    else:
        result=b.client.post('/api/civitai-recipes/resource-install',json={'selected':selected,'storage_root':'loras'})
        assert result.status_code==(500 if response_status=='bad206' else 200),result.text
        if response_status!='bad206': assert result.json()['ledger_id']==rid
    if response_status=='bad206':
        assert not target.exists() and Path(str(target)+'.part').read_bytes()==b.body[:1024*1024]
        with database.SessionLocal() as db:
            row=db.get(DownloadedResource,rid)
            assert row.status=='failed' and project_resource(row).sha256_verified is None
            assert json.loads(row.metadata_json)['source_evidence']['acquisition']['error']['code']=='civitai_invalid_range'
        return
    assert target.read_bytes()==b.body and not Path(str(target)+'.part').exists()
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid); assert row.status=='installed' and project_resource(row).sha256_verified is True
    assert requests[-1].headers['Range']=='bytes=1048576-'
    print('P203_RESUME_TRACE='+json.dumps({'entry':entry,'response':response_status,'range':requests[-1].headers['Range'],'resource_id':rid,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'status':row.status}))


def test_background_must_not_adopt_a_collision_created_after_admission(boundary):
    b=boundary; admitted=acquire_http(b);rid=admitted.json()['resource']['acquisition_id']
    target=b.tmp/'loras'/b.file['name'];target.parent.mkdir();target.write_bytes(b.body)
    before=target.stat();b.pending.pop()()
    status=b.client.get('/api/civitai/resources/status',params={'acquisition_id':rid}).json()['resources'][0]
    assert status['status']=='failed' and status['error']['code']=='civitai_target_exists'
    assert target.read_bytes()==b.body and target.stat()==before
    with database.SessionLocal() as db: assert project_resource(db.get(DownloadedResource,rid)).sha256_verified is None


@pytest.mark.parametrize('state',['installed','failed'])
def test_acquisition_retains_known_storage_when_configured_root_changes(boundary,monkeypatch,state):
    from app.config import get_settings
    b=boundary;rid=acquire_http(b).json()['resource']['acquisition_id'];b.pending.pop()()
    old=b.tmp/'loras'/b.file['name'];old_info=old.stat()
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid);row.status=state;db.commit()
    new=b.tmp/'new-root';new.mkdir();foreign=new/b.file['name'];foreign.write_bytes(b'foreign model at new root');before=foreign.stat()
    monkeypatch.setenv('COMFYUI_LORAS_DIR',str(new));get_settings.cache_clear()
    response=acquire_http(b);assert response.status_code==202,response.text
    assert response.json()['resource']['acquisition_id']==rid
    if b.pending:b.pending.pop()()
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        assert row.status=='installed' and row.local_path==str(old)
        assert project_resource(row).sha256_verified is True
    assert old.read_bytes()==b.body and old.stat()==old_info
    assert foreign.read_bytes()==b'foreign model at new root' and foreign.stat()==before
