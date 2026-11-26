"""Z1: whole acquired ledger, alongside canonical and persisted phase observations.
All inputs are synthetic. Only external HTTP and deterministic scheduling vary.
"""
import json
import sys
from pathlib import Path
import pytest
from sqlalchemy import event
from tests.test_resource_record_writers import boundary, acquire_http
from app.db import database
from app.db.models import DownloadedResource

SECRET = 'QA9 complete raw-identity synthetic value; retained suffix'
PLAIN = '" CIVITAI_API_KEY " = "'+SECRET+'"'
TEXTS = [PLAIN,json.dumps(PLAIN),json.dumps(PLAIN)[1:-1],
         PLAIN.replace(chr(34),chr(39)), 'ordinary "unfinished; '+PLAIN,
         'ordinary "unfinished; HTTP_AUTH"\\u004f"RIZATION = "'+SECRET+'"']

@pytest.mark.parametrize('field',['air','filename'])
@pytest.mark.parametrize('text',TEXTS)
def test_real_acquisition_outer_ledger_complete_trace(boundary,monkeypatch,field,text):
    b = boundary
    if field == 'air': b.file['air'] = text
    else: b.file['name'] = text+'.safetensors'
    response = acquire_http(b)
    if response.status_code == 422:
        # A stable safe refusal with no publication satisfies secrecy.
        body = response.json()
        assert body['detail']['code'] and SECRET not in json.dumps(body)
        with database.SessionLocal() as db:
            assert db.query(DownloadedResource).count() == 0
        assert not b.pending
        return
    assert response.status_code == 202,response.text
    rid = response.json()['resource']['acquisition_id']
    phases = [('admission',response.json())]
    def storage(label):
        with database.SessionLocal() as db:
            row = db.get(DownloadedResource,rid)
            phases.extend([(label+' metadata',json.loads(row.metadata_json)),
                           (label+' notes',json.loads(row.notes))])
            return {c.name:getattr(row,c.name) for c in row.__table__.columns}
    storage('admitted')
    for label,url in [('admitted ledger','/api/civitai-recipes/local-ledger'),
                      ('admitted detail',f'/api/resources/{rid}')]:
        r = b.client.get(url)
        assert r.status_code == 200,r.text
        phases.append((label,r.json()))
    assert len(b.pending) == 1
    b.pending.pop()()
    original = storage('completed')
    assert original['status'] in {'installed','failed'}
    from app.services import resource_records,resource_record_backfill,civitai_provider
    def deny(*a,**kw): raise AssertionError('unexpected completed-read side effect')
    monkeypatch.setattr(resource_records,'publish_metadata',deny)
    monkeypatch.setattr(resource_record_backfill,'backfill_metadata',deny)
    monkeypatch.setattr(civitai_provider,'ProviderOperation',deny)
    old_open = Path.open
    def guarded(p,*a,**kw):
        if str(p) == original['local_path']: return deny()
        return old_open(p,*a,**kw)
    monkeypatch.setattr(Path,'open',guarded)
    def readonly(conn,cursor,sql,*args):
        assert sql.split()[0].upper() in {'SELECT','PRAGMA'},sql
    event.listen(database.engine,'before_cursor_execute',readonly)
    try:
        for label,url in [('status',f'/api/civitai/resources/status?acquisition_id={rid}'),
            ('status list','/api/civitai/resources/status'),('detail',f'/api/resources/{rid}'),
            ('list','/api/resources'),('ledger','/api/civitai-recipes/local-ledger'),
            ('family','/api/resources?model_family=sdxl&limit=1&offset=0')]:
            r = b.client.get(url)
            assert r.status_code == 200,r.text
            phases.append((label,r.json()))
        detail = next(v for p,v in phases if p == 'detail')
        assert detail['resource_id'] == rid and detail['sha256'] == b.sha
        assert detail['trigger_words'] == ['chosen','second']
        print('QA9_OUTER_LEDGER_PHASES='+json.dumps(phases))
        for label,value in phases:
            if label in {'admitted ledger','ledger'}:
                assert SECRET not in json.dumps(value['entries'][0]['diagnostics']['resource_record'])
            else:
                assert SECRET not in json.dumps(value)
        exposed = [label for label,value in phases if SECRET in json.dumps(value)]
        assert not exposed,exposed
        assert 'retained suffix' not in json.dumps(phases)
    finally:
        event.remove(database.engine,'before_cursor_execute',readonly)
        with database.SessionLocal() as db:
            row = db.get(DownloadedResource,rid)
            assert {c.name:getattr(row,c.name) for c in row.__table__.columns} == original
        print('QA9_OUTER_LEDGER_STORAGE_EXACT=true')

@pytest.mark.parametrize('field',['air','filename'])
def test_safe_identity_outer_ledger_remains_useful(boundary,field):
    b = boundary
    air = 'urn:air:sdxl:lora:civitai:10@21'
    b.file['air'] = air
    if field == 'filename': b.file['name'] = 'useful tokenizer ordinary.safetensors'
    admitted = acquire_http(b)
    assert admitted.status_code == 202,admitted.text
    rid = admitted.json()['resource']['acquisition_id']
    b.pending.pop()()
    response = b.client.get('/api/civitai-recipes/local-ledger')
    assert response.status_code == 200,response.text
    entry = response.json()['entries'][0]
    record = entry['diagnostics']['resource_record']
    assert record['resource_id'] == rid and record['sha256_verified'] is True
    assert entry['air'] == record['air'] == air
    assert entry['local_path'] == record['local_path']
    assert entry['local_path'].endswith(b.file['name'])
    assert entry['sha256'] == record['sha256'] == b.sha

from app.services.civitai_local_identity_ledger import local_identity_ledger, ledger_payload
from app.services.resource_records import provider_snapshot
from app.services.civitai_resource_resolution import resolve_recipe_resources
from app.schemas.generation_recipe import GenerationRecipe
from tests.test_civitai_local_identity_ledger import _recipe


def seed(b, field, text, state='installed',kind='lora'):
    path=b.tmp/'legacy.safetensors'; path.write_bytes(b.body)
    values=dict(resource_name='legacy.safetensors',resource_type=kind,provider='civitai',
        source_url='unknown',local_path=str(path),storage_root='loras',status=state,
        model_id='10',version_id='20',civitai_file_id='30',air='urn:air:sd1:lora:civitai:10@20',
        sha256=b.sha,file_size=len(b.body),notes='  {"legacy": "unchanged"} \n',
        metadata_json=provider_snapshot({'baseModel':'SDXL 1.0' if kind=='checkpoint' else 'Illustrious','trainedWords':['chosen']},None,{}).model_dump_json())
    if field=='local_path':
        path=b.tmp/(text+'.safetensors'); path.write_bytes(b.body); values[field]=str(path)
    elif field=='notes': values[field]='  '+json.dumps({'source':text})+' \n'
    else: values[field]=text
    with database.SessionLocal() as db:
        row=DownloadedResource(**values);db.add(row);db.commit();rid=row.id
        original={c.name:getattr(row,c.name) for c in row.__table__.columns}
    return rid,original,path


@pytest.mark.parametrize('state',['installed','downloading','failed','incomplete'])
@pytest.mark.parametrize('field',['air','local_path','resource_type','sha256','status','resource_name','source_url','notes'])
@pytest.mark.parametrize('text',TEXTS)
def test_seeded_old_whole_ledger_readonly_exact_columns(boundary,monkeypatch,state,field,text):
    b=boundary;rid,original,path=seed(b,field,text,state)
    from app.services import resource_records,resource_record_backfill,civitai_provider
    def deny(*a,**kw): raise AssertionError('unexpected ordinary-read side effect')
    monkeypatch.setattr(resource_records,'publish_metadata',deny)
    monkeypatch.setattr(resource_record_backfill,'backfill_metadata',deny)
    monkeypatch.setattr(civitai_provider,'ProviderOperation',deny)
    old_open=Path.open
    def guarded(p,*a,**kw):
        if p==path:return deny()
        return old_open(p,*a,**kw)
    monkeypatch.setattr(Path,'open',guarded)
    def readonly(conn,cursor,sql,*args):assert sql.split()[0].upper() in {'SELECT','PRAGMA'},sql
    event.listen(database.engine,'before_cursor_execute',readonly)
    try:
        phases=[]
        with database.SessionLocal() as db:
            raw=local_identity_ledger(db)
            entry=raw.entries[0]
            assert entry.air==original['air'] and str(entry.local_path)==original['local_path']
            phases.append(('direct public serializer',ledger_payload(raw)))
            assert local_identity_ledger(db,air=original['air']).metadata['row_count']==1
            assert local_identity_ledger(db,air='different').metadata['row_count']==0
        for label,url,params in [('ledger','/api/civitai-recipes/local-ledger',{}),
            ('exact raw filter','/api/civitai-recipes/local-ledger',{'air':original['air']}),
            ('detail',f'/api/resources/{rid}',{}),('list','/api/resources',{}),
            ('family','/api/resources',{'model_family':'sdxl','limit':1,'offset':0})]:
            r=b.client.get(url,params=params);assert r.status_code==200,r.text
            phases.append((label,r.json()))
        print('OLD_LEDGER_PHASES='+json.dumps(phases))
        assert phases[1][1]['snapshot']['row_count']==1
        assert phases[-1][1]['total']==1
        record=phases[1][1]['entries'][0]['diagnostics']['resource_record']
        assert record['resource_id']==rid and record['trigger_words']==['chosen']
        assert 'retained suffix' not in json.dumps(phases)
        assert SECRET not in json.dumps(phases)
    finally:
        event.remove(database.engine,'before_cursor_execute',readonly)
        with database.SessionLocal() as db:
            row=db.get(DownloadedResource,rid)
            assert {c.name:getattr(row,c.name) for c in row.__table__.columns}==original
        print('OLD_LEDGER_ALL_COLUMNS_EXACT=true')


@pytest.mark.parametrize('field',['air','local_path'])
@pytest.mark.parametrize('state',['installed','downloading','failed'])
@pytest.mark.parametrize('text',TEXTS)
def test_raw_internal_resolution_public_refusal_and_failure(boundary,field,state,text):
    b=boundary;rid,original,path=seed(b,field,text,state)
    recipe=_recipe(b.sha);recipe['resources'][0]['air']=original['air']
    model=GenerationRecipe.model_validate(recipe)
    try:
        with database.SessionLocal() as db:
            snapshot=local_identity_ledger(db)
            raw=resolve_recipe_resources(model.resources,snapshot.entries,strict=True)
            entry=raw.entries[0]
            assert entry.local_path==str(path) and entry.actual_identity['air']==original['air']
            assert entry.status==('resolved' if state=='installed' else 'unavailable')
            if state=='installed':
                assert raw.ready and raw.resource_lock[0]['local_path']==str(path)
                assert raw.resource_lock[0]['air']==original['air']
            assert ledger_payload(snapshot)['snapshot']['row_count']==1
        public_entry={key:getattr(snapshot.entries[0],key) for key in ['kind','local_path','sha256','civitai_model_id','civitai_model_version_id','civitai_file_id','air','availability','diagnostics']}
        for endpoint,payload in [('resolve-local',{'recipe':recipe}),
                ('resolve',{'recipe':recipe,'ledger':[public_entry],'strict':True})]:
            response=b.client.post('/api/civitai-recipes/'+endpoint,json=payload)
            assert 'retained suffix' not in response.text
            if state=='installed':
                # A public executable lock cannot contain a projected fake locator.
                assert response.status_code==422,response.text
                assert response.json()['detail']['code']=='unsafe_resource_projection'
                assert 'Inspect' in response.json()['detail']['hint']
                assert 'resource_lock' not in response.json()['detail']
            else:
                assert response.status_code==409,response.text
                report=response.json()['detail']['report']
                assert report['ready'] is False and report['entries'][0]['status']==entry.status

    finally:
        with database.SessionLocal() as db:
            row=db.get(DownloadedResource,rid)
            assert {c.name:getattr(row,c.name) for c in row.__table__.columns}==original

@pytest.mark.parametrize('field',['air','local_path'])
@pytest.mark.parametrize('text',TEXTS+['safe original'])
def test_variant_raw_report_refused_before_build_or_queue(boundary,monkeypatch,field,text):
    from tests.test_civitai_recipe_variant_facade import body,canonical
    from app.services import civitai_recipe_variants as variants
    b=boundary;rid,original,path=seed(b,field,text,kind='checkpoint')
    request=body();recipe=_recipe(b.sha);recipe['resources'][0]['kind']='checkpoint';recipe['resources'][0]['air']=original['air']
    request['parent_recipe']=recipe
    request['parent_recipe_sha256']=canonical(GenerationRecipe.model_validate(recipe).model_dump(mode='json',exclude_none=True))
    submissions=[]
    # Only deterministic queue scheduling is substituted; derive/resolve/compiler/provenance are real.
    monkeypatch.setattr(variants,'submit_audited_recipe',lambda params,job_id:submissions.append(params) or job_id)
    response=b.client.post('/api/civitai-recipes/variants/generate-one',json=request)
    assert 'retained suffix' not in response.text
    if text=='safe original':
        assert response.status_code==202,response.text
        assert len(submissions)==1
        assert response.json()['provenance_components']['strict_resolution_snapshot']['report']['resource_lock'][0]['local_path']==str(path)
    else:
        assert response.status_code==422,response.text
        assert response.json()['detail']['code']=='unsafe_resource_projection',response.text
        assert 'Inspect' in response.json()['detail']['message']
        assert not submissions
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        assert {c.name:getattr(row,c.name) for c in row.__table__.columns}==original


@pytest.mark.parametrize('endpoint',['source-info','generate-like'])
@pytest.mark.parametrize('text',TEXTS)
def test_easy_public_plan_copy_preserves_raw_internal_match(boundary,monkeypatch,text,endpoint):
    import httpx
    from app.config import get_settings
    from app.services.civitai_easy import plan_generation
    b=boundary;rid,original,path=seed(b,'local_path',text)
    monkeypatch.setenv('COMFYUI_LORAS_DIR',str(b.tmp))
    cp=b.tmp/'checkpoints';cp.mkdir();(cp/'base.safetensors').write_bytes(b'synthetic checkpoint')
    monkeypatch.setenv('COMFYUI_CHECKPOINTS_DIR',str(cp));get_settings.cache_clear()
    image={'id':123,'meta':{'prompt':'useful prompt','negativePrompt':'bad',
        'resources':[{'type':'lora','name':'remote.safetensors','modelId':10,'modelVersionId':20,
                      'hash':b.sha,'weight':0.7}], 'seed':42,'steps':20,'cfgScale':7,'sampler':'Euler','Size':'512x512'}}
    def wire(url,**kw):
        payload={'items':[image]} if '/images' in str(url) else {'id':20,'modelId':10,'name':'safe','baseModel':'Illustrious',
            'model':{'id':10,'type':'LORA'},'files':[{'id':30,'name':'remote.safetensors','primary':True,'hashes':{'SHA256':b.sha}}]}
        return httpx.Response(200,json=payload,request=httpx.Request('GET',url))
    monkeypatch.setattr(httpx,'get',wire)
    with database.SessionLocal() as db:
        plan=plan_generation({'resources':[{'kind':'lora','name':'remote.safetensors','civitai_model_version_id':20}]},db=db)
        assert plan['loras'][0]['name']==path.name
    submissions=[]
    from app.services import civitai_easy as easy
    monkeypatch.setattr(easy,'queue_submit',lambda params:submissions.append(params) or 'synthetic-job')
    if endpoint=='source-info':
        response=b.client.get('/api/civitai/source-info',params={'locator':'123'})
        assert response.status_code==200,response.text
        assert response.json()['local_plan']['loras'],response.text
        assert response.json()['prompt']=='useful prompt'
        assert not submissions
    else:
        response=b.client.post('/api/civitai/generate-like',json={'locator':'123','download_missing':False})
        assert response.status_code==202,response.text
        assert len(submissions)==1
        assert submissions[0]['loras'][0]['name']==path.name
        assert response.json()['job_id']=='synthetic-job'
    assert 'retained suffix' not in response.text
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        assert {c.name:getattr(row,c.name) for c in row.__table__.columns}==original


def test_safe_mixed_ledger_order_filters_and_counts(boundary):
    b=boundary; originals=[]
    for state in ['installed','downloading','failed','incomplete']:
        rid,row,path=seed(b,'air','urn:air:sdxl:lora:civitai:10@'+str(len(originals)+1),state)
        originals.append((rid,row))
    try:
        response=b.client.get('/api/civitai-recipes/local-ledger'); assert response.status_code==200
        payload=response.json()
        assert [e['diagnostics']['database_id'] for e in payload['entries']]==[i for i,_ in originals]
        assert payload['snapshot']['row_count']==4
        for (rid,row),entry in zip(originals,payload['entries']):
            assert entry['air']==row['air'] and entry['local_path']==row['local_path'] and entry['sha256']==row['sha256']
        with database.SessionLocal() as db:
            assert len(local_identity_ledger(db,availability=True).entries)==1
            assert len(local_identity_ledger(db,availability=False).entries)==3
        for rid,row in originals:
            r=b.client.get('/api/civitai-recipes/local-ledger',params={'air':row['air'],'civitai_file_id':30,'kind':'lora','sha256':b.sha.upper()})
            assert r.json()['snapshot']['row_count']==1
            assert r.json()['entries'][0]['diagnostics']['database_id']==rid
        family=b.client.get('/api/resources',params={'model_family':'sdxl','limit':2,'offset':1}).json()
        assert family['total']==4 and [r['resource_id'] for r in family['items']]==[i for i,_ in originals][1:3]
    finally:
        with database.SessionLocal() as db:
            for rid,row in originals:
                current=db.get(DownloadedResource,rid)
                assert {c.name:getattr(current,c.name) for c in current.__table__.columns}==row
