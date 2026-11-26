"""D4 registered HTTP/OpenAPI/ORM behavior with denied writes and body reads."""
import builtins
import json
import socket
from pathlib import Path
import pytest
from sqlalchemy import event
from app.db import database
from app.db.database import get_db
from app.db.models import DownloadedResource
from app.main import app
from app.services.resource_records import provider_snapshot,publish_metadata


@pytest.fixture
def reads(client,tmp_path):
    path=tmp_path/'do-not-read.safetensors';path.write_bytes(b'no model IO in reads')
    ids=[]
    with database.SessionLocal() as db:
        for n in range(131):
            r=DownloadedResource(resource_name='row-'+str(n),resource_type='lora' if n%2 else 'checkpoint',
                provider='civitai' if n%3 else 'other',source_url='https://civitai.com/models/10?token=PRIVATE_SENTINEL&X-Amz-Signature=SIGNED_SENTINEL',
                local_path=str(path),sha256=('a' if n%2 else 'b')*64,status='installed' if n%2 else 'planned',
                notes=json.dumps({'base_model':'Pony' if n%2 else 'SD 1.5','trainedWords':['old']}))
            db.add(r);db.flush()
            if n%2:
                publish_metadata(r,provider_snapshot({'baseModel':'Pony','trainedWords':['new']},None,{}))
            ids.append(r.id)
        db.commit()
    def dependency():
        with database.SessionLocal() as db: yield db
    app.dependency_overrides[get_db]=dependency
    yield client,ids,path
    app.dependency_overrides.clear()


def test_registered_pagination_filtered_totals_same_detail_and_openapi(reads):
    client,ids,path=reads
    r=client.get('/api/resources'); assert r.status_code==200,r.json()
    value=r.json();assert set(value)=={'items','total','limit','offset'}
    assert value['total']==131 and value['limit']==25 and value['offset']==0
    assert [x['resource_id'] for x in value['items']]==ids[:25]
    maxed=client.get('/api/resources',params={'limit':100,'offset':30}).json()
    assert len(maxed['items'])==100 and maxed['total']==131
    assert client.get('/api/resources',params={'offset':999}).json()['items']==[]
    for params,expected in [({'resource_type':' lora '},65),({'provider':' civitai '},87),
            ({'base_model':' Pony '},65),({'model_family':' sdxl '},65),({'status':'installed'},65),
            ({'sha256':'A'*64},65),({'provider':'unmatched'},0),({'base_model':'pony'},0),
            ({'status':'installed','resource_type':'checkpoint'},0)]:
        response=client.get('/api/resources',params={**params,'limit':3,'offset':1})
        assert response.status_code==200,response.json()
        body=response.json(); assert body['total']==expected,params
        assert len(body['items'])==min(3,max(0,expected-1))
    item=value['items'][0]
    assert client.get('/api/resources/'+str(item['resource_id'])).json()==item
    text=json.dumps(value); assert 'PRIVATE_SENTINEL' not in text and 'SIGNED_SENTINEL' not in text and 'token=' not in text
    api=client.get('/openapi.json').json()
    assert api['paths']['/api/resources']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/ResourceList')
    params={p['name']:p for p in api['paths']['/api/resources']['get']['parameters']}
    assert set(params)=={'limit','offset','resource_type','provider','base_model','model_family','status','sha256'}
    assert params['limit']['schema']['maximum']==100 and params['limit']['schema']['minimum']==1 and params['limit']['schema']['default']==25
    assert params['offset']['schema']['minimum']==0
    assert client.get('/api/resources/9999').json()['detail']['code']=='resource_not_found'
    assert client.get('/api/resources/9999').status_code==404
    assert client.get('/api/resources/9999').json()['detail']['hint']


@pytest.mark.parametrize('params',[{'limit':x} for x in ['0','101','-1','bad','1.0','1e1']]+[
    {'offset':x} for x in ['-1','no','1.1']]+[{'model_family':x} for x in ['illustrious','SDXL','']]+[
    {'sha256':x} for x in ['f'*63,'g'*64,'https://x.test/?token=SECRET']]+[
    {'provider':' '},{'resource_type':''},{'base_model':''},{'name':'fuzzy'}])
def test_invalid_query_is_422_without_echoing_private_input(reads,params):
    client,_,_=reads;r=client.get('/api/resources',params=params)
    assert r.status_code==422,r.json();assert 'SECRET' not in r.text


@pytest.mark.parametrize('id',['0','-1','1.2','abc'])
def test_invalid_detail_ids(reads,id):
    assert reads[0].get('/api/resources/'+id).status_code==422


def test_reads_deny_sql_writes_provider_body_reads_and_metadata_repair(reads,monkeypatch):
    client,ids,path=reads
    def deny(*a,**k): raise AssertionError('read side effect')
    from app.services import civitai_provider,resource_records,resource_record_backfill
    monkeypatch.setattr(civitai_provider,'ProviderOperation',deny)
    monkeypatch.setattr(resource_record_backfill,'backfill_metadata',deny)
    monkeypatch.setattr(resource_records,'publish_metadata',deny)
    monkeypatch.setattr(socket,'create_connection',deny)
    original=builtins.open; pathopen=Path.open
    def guarded(p,*a,**kw):
        if str(p)==str(path): return deny()
        return original(p,*a,**kw)
    def pathguard(p,*a,**kw):
        if p==path: return deny()
        return pathopen(p,*a,**kw)
    monkeypatch.setattr(builtins,'open',guarded);monkeypatch.setattr(Path,'open',pathguard)
    statements=[]
    def sql(conn,cursor,statement,params,context,many):
        statements.append(statement)
        if statement.split()[0].upper() not in {'SELECT','PRAGMA'}: deny()
    event.listen(database.engine,'before_cursor_execute',sql)
    try:
        for params in [{},{'limit':1,'offset':50},{'model_family':'sdxl'}]:
            assert client.get('/api/resources',params=params).status_code==200
        assert client.get('/api/resources/'+str(ids[0])).status_code==200
        assert client.get('/api/resources/999').status_code==404
        page_queries=[s for s in statements if 'ORDER BY downloaded_resources.id ASC' in s]
        assert page_queries and all('LIMIT' in s for s in page_queries),page_queries
    finally: event.remove(database.engine,'before_cursor_execute',sql)
    with database.SessionLocal() as db:
        assert db.get(DownloadedResource,ids[0]).metadata_json is None


def test_registered_family_filter_matches_exact_projection_for_whitespace_and_bad_legacy_labels(reads):
    client,ids,path=reads
    labels=['\tSDXL 1.0\n',' Illustrious ','PONY','\u2003NoobAI\u3000','Pony extra','file.safetensors',None,17,{},'sdxl']
    added=[]
    with database.SessionLocal() as db:
        for label in labels:
            r=DownloadedResource(resource_name='label',resource_type='lora',provider='civitai',source_url='https://civitai.com/models/1',status='planned',
                notes=json.dumps({'base_model':label}))
            db.add(r);db.flush();added.append(r.id)
        bad=DownloadedResource(resource_name='bad',resource_type='lora',source_url='unknown',status='planned',notes='invalid TOKEN_SENTINEL')
        db.add(bad);db.commit()
    result=client.get('/api/resources',params={'model_family':'sdxl','limit':100}).json()
    assert [v['resource_id'] for v in result['items'] if v['resource_id'] in added]==added[:4]
    raw=client.get('/api/resources',params={'base_model':'\t SDXL 1.0 \n'}).json()
    assert raw['total']==1 and raw['items'][0]['base_model']=='\tSDXL 1.0\n'
