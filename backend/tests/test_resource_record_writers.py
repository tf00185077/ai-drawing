"""D2: real Settings/file resolver, registered routes, ORM and background work.
Only external HTTP and deterministic thread scheduling are substituted.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from app.config import get_settings
from app.db import database
from app.db.database import get_db
from app.db.models import DownloadedResource
from app.main import app
from app.services import civitai_resource_acquire as acquire
from app.services.resource_records import project_resource


@pytest.fixture
def boundary(client,tmp_path,monkeypatch):
    key=tmp_path/'synthetic-key'; key.write_text('resource-fixture-key')
    monkeypatch.setenv('CIVITAI_API_KEY_FILE',str(key))
    monkeypatch.setenv('COMFYUI_LORAS_DIR',str(tmp_path/'loras'));get_settings.cache_clear()
    def db_dependency():
        with database.SessionLocal() as db: yield db
    app.dependency_overrides[get_db]=db_dependency
    monkeypatch.setattr(acquire,'SessionLocal',database.SessionLocal)
    pending=[]
    class Thread:
        def __init__(self,*,target,**kw): self.target=target
        def start(self): pending.append(self.target)
    monkeypatch.setattr(acquire,'threading',SimpleNamespace(Thread=Thread))
    body=b'selected model bytes'; sha=hashlib.sha256(body).hexdigest()
    file=dict(id=32,name='selected.safetensors',sizeKB=len(body)/1024,hashes={'SHA256':sha},
              downloadUrl='https://civitai.com/api/download/models/21?X-Amz-Signature=SIGNED',
              virusScanResult='Success',primary=True,availability=True,license={'name':'personal'},usage={'personal':True},
              metadata={'format':'SafeTensor'})
    version=dict(id=21,modelId=10,name='chosen',baseModel='Illustrious',trainedWords=[' chosen ','chosen','second'],
                 meta={'steps':27,'cfgScale':6.25},files=[dict(file,id=31,name='first.safetensors',primary=False),file])
    model=dict(id=10,type='LORA',modelVersions=[dict(version,id=20,trainedWords=['WRONG'],files=[]),version],
               allowNoCredit=True,allowCommercialUse=['None'],allowDerivatives=False,allowDifferentLicense=False)
    seen=[]; failure=[False]; original=httpx.AsyncClient
    def wire(request):
        seen.append((request.url.path,request.headers.get('authorization')))
        if '/model-versions/' in request.url.path: return httpx.Response(200,json=version)
        if '/api/v1/models/' in request.url.path: return httpx.Response(200,json=model)
        if failure[0]: return httpx.Response(403)
        return httpx.Response(200,content=body)
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(wire),**kw))
    yield SimpleNamespace(client=client,pending=pending,version=version,model=model,file=file,body=body,sha=sha,seen=seen,failure=failure,tmp=tmp_path)
    app.dependency_overrides.clear();get_settings.cache_clear()


def acquire_http(b):
    return b.client.post('/api/civitai/resources/acquire',json={'locator':'https://civitai.com/models/10?modelVersionId=21'})


def canonical(db,id):
    return project_resource(db.get(DownloadedResource,id)).model_dump()


def assert_selected(value):
    assert value['base_model']=='Illustrious' and value['model_family']=='sdxl'
    assert value['trigger_words']==['chosen','second']
    assert value['recommended_parameters']['steps']=={'value':27,'source_field':'version.meta.steps'}
    assert value['declared_size_bytes']==20
    assert value['license']['values']['allowCommercialUse']==['None']
    assert 'WRONG' not in json.dumps(value) and 'SIGNED' not in json.dumps(value)


def test_registered_acquire_publishes_selected_snapshot_measurements_reuse_and_conflicts(boundary):
    b=boundary; admitted=acquire_http(b); assert admitted.status_code==202,admitted.json()
    id=admitted.json()['resource']['acquisition_id']
    with database.SessionLocal() as db:
        value=canonical(db,id); assert_selected(value)
        assert value['sha256_verified'] is None and value['measured_size_bytes'] is None
    duplicate=acquire_http(b); assert duplicate.json()['resource']['acquisition_id']==id and len(b.pending)==1
    b.pending.pop()()
    with database.SessionLocal() as db:
        value=canonical(db,id); assert_selected(value)
        assert value['sha256_verified'] is True and value['measured_size_bytes']==len(b.body)
        before=db.get(DownloadedResource,id).metadata_json
    status=b.client.get('/api/civitai/resources/status',params={'acquisition_id':id}).json()
    assert status['resources'][0]['status']=='installed'
    assert acquire_http(b).json()['status']=='already_installed' and not b.pending
    ledger=b.client.get('/api/civitai-recipes/local-ledger').json()
    assert ledger['entries'][0]['diagnostics']['resource_record']['resource_id']==id
    assert ledger['entries'][0]['diagnostics']['resource_record']['model_family']=='sdxl'
    # Same version/name with incompatible immutable identity cannot reuse/rebind.
    b.file['id']=999
    response=acquire_http(b); assert response.status_code==422 and response.json()['detail']['code']=='resource_identity_conflict'
    with database.SessionLocal() as db:
        assert db.query(DownloadedResource).count()==1 and db.get(DownloadedResource,id).civitai_file_id=='32'
        assert db.get(DownloadedResource,id).metadata_json==before
    assert all(auth=='Bearer resource-fixture-key' for _,auth in b.seen)


def test_registered_failed_acquire_same_id_truth_and_retry(boundary):
    b=boundary; b.failure[0]=True
    id=acquire_http(b).json()['resource']['acquisition_id']; b.pending.pop()()
    with database.SessionLocal() as db:
        value=canonical(db,id); assert value['status']=='failed' and value['sha256_verified'] is None
    b.failure[0]=False
    assert acquire_http(b).json()['resource']['acquisition_id']==id
    b.pending.pop()()
    with database.SessionLocal() as db:
        assert canonical(db,id)['sha256_verified'] is True and db.query(DownloadedResource).count()==1


def test_registered_inspect_select_install_nonfirst_snapshot_and_shared_ledger(boundary):
    b=boundary
    inspected=b.client.post('/api/civitai-recipes/resource-inspect',json={'locator':'https://civitai.com/models/10?modelVersionId=21'})
    assert inspected.status_code==200,inspected.json()
    selected=b.client.post('/api/civitai-recipes/resource-select',json={'inspect':inspected.json(),'selectors':{'civitai_file_id':32}})
    assert selected.status_code==200,selected.json()
    descriptor=selected.json()['selected']
    assert descriptor['resource_metadata']['trigger_words']==['chosen','second']
    request=dict(selected=descriptor,storage_root='loras')
    installed=b.client.post('/api/civitai-recipes/resource-install',json=request)
    assert installed.status_code==200,installed.json(); id=installed.json()['ledger_id']
    with database.SessionLocal() as db:
        value=canonical(db,id); assert_selected(value); assert value['sha256_verified'] is True
        before=db.get(DownloadedResource,id).metadata_json
    again=b.client.post('/api/civitai-recipes/resource-install',json=request)
    assert again.json()['ledger_id']==id and again.json()['diagnostic']['code']=='adopted_existing'
    # Acquire reuses exactly the same row created through retained install.
    assert acquire_http(b).json()['resource']['acquisition_id']==id and not b.pending
    with database.SessionLocal() as db:
        assert db.query(DownloadedResource).count()==1 and db.get(DownloadedResource,id).metadata_json==before
    assert b.client.get('/api/civitai-recipes/local-ledger').json()['entries'][0]['diagnostics']['resource_record']['trigger_words']==['chosen','second']


def test_legacy_install_descriptor_without_snapshot_stays_unknown(boundary):
    b=boundary
    inspected=b.client.post('/api/civitai-recipes/resource-inspect',json={'locator':'https://civitai.com/models/10?modelVersionId=21'}).json()
    selected=b.client.post('/api/civitai-recipes/resource-select',json={'inspect':inspected,'selectors':{'civitai_file_id':32}}).json()['selected']
    selected.pop('resource_metadata',None)
    installed=b.client.post('/api/civitai-recipes/resource-install',json={'selected':selected,'storage_root':'loras'})
    assert installed.status_code==200,installed.json()
    with database.SessionLocal() as db:
        v=canonical(db,installed.json()['ledger_id']); assert v['trigger_words']==[] and v['recommended_parameters']=={}
        assert v['sha256_verified'] is True


def test_acquire_retains_selected_air_and_install_reuse_preserves_publication_time(boundary):
    b=boundary;b.file['air']='urn:air:sdxl:lora:civitai:10@21'
    inspected=b.client.post('/api/civitai-recipes/resource-inspect',json={'locator':'https://civitai.com/models/10?modelVersionId=21'}).json()
    descriptor=b.client.post('/api/civitai-recipes/resource-select',json={'inspect':inspected,'selectors':{'civitai_file_id':32}}).json()['selected']
    id=acquire_http(b).json()['resource']['acquisition_id'];b.pending.pop()()
    with database.SessionLocal() as db:
        r=db.get(DownloadedResource,id); assert project_resource(r).air==b.file['air']; time=r.downloaded_at
    assert b.client.post('/api/civitai-recipes/resource-install',json={'selected':descriptor,'storage_root':'loras'}).status_code==200
    with database.SessionLocal() as db: assert db.get(DownloadedResource,id).downloaded_at==time
    descriptor['air']='urn:air:sdxl:lora:civitai:999@21'
    refused=b.client.post('/api/civitai-recipes/resource-install',json={'selected':descriptor,'storage_root':'loras'})
    assert refused.status_code==409
    with database.SessionLocal() as db: assert db.get(DownloadedResource,id).air==b.file['air']


def test_background_publication_cannot_rebind_changed_immutable_identity(boundary):
    b=boundary;id=acquire_http(b).json()['resource']['acquisition_id']
    with database.SessionLocal() as db:
        r=db.get(DownloadedResource,id); r.sha256='f'*64;db.commit()
    b.pending.pop()()
    with database.SessionLocal() as db:
        r=db.get(DownloadedResource,id)
        assert r.sha256=='f'*64 and r.status=='failed'
        assert project_resource(r).sha256_verified is None
