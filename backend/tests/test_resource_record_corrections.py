"""C1-C4: actual registered writers/background/ORM/HTTP; synthetic wire fixtures only."""
import json
import pytest
from sqlalchemy import event
from app.db import database
from app.db.database import get_db
from app.db.models import DownloadedResource
from app.main import app
from app.schemas.resources import ResourceMetadata
from app.services.resource_records import provider_snapshot, publish_metadata, project_resource
from tests.test_resource_record_writers import boundary, acquire_http

AIR='urn:air:sdxl:lora:civitai:10@21'
ATTACK='https://user:PASS_C1@example.test/proof?X-Amz-Signature=DROP_C1#DROP_C1'


def inspected(b):
    response=b.client.post('/api/civitai-recipes/resource-inspect',json={'locator':'https://civitai.com/models/10?modelVersionId=21'})
    assert response.status_code==200,response.json()
    selected=b.client.post('/api/civitai-recipes/resource-select',json={'inspect':response.json(),'selectors':{'civitai_file_id':32}})
    assert selected.status_code==200,selected.json()
    return selected.json()['selected']


def attack_snapshot():
    snap=provider_snapshot({'baseModel':'Pony','trainedWords':['valid']},None,{}).model_dump()
    snap['trigger_words']+=['Bearer DROP_C1',ATTACK]
    snap['recommended_parameters']={'sampler':{'value':ATTACK,'source_field':ATTACK},ATTACK:{'value':27,'source_field':'version.meta.steps'}}
    snap['license']['values']={'allowNoCredit':True,'file_license':{'proof':ATTACK,'token':'DROP_C1','ordinary_sha256':'a'*64,'text':'password=DROP_C1'}}
    snap['license']['missing_fields']+=[ATTACK]
    snap['source_evidence']={'nested':[{'proof':ATTACK,'safe_hash':'a'*64,'cookie':'DROP_C1'}],ATTACK:ATTACK}
    snap['diagnostics']+=[{'code':ATTACK,'field':ATTACK}]
    return snap


def assert_safe(text):
    for value in ('DROP_C1','PASS_C1','X-Amz-Signature','user:','password='):
        assert value not in text,text


def test_complete_snapshot_normalized_at_publication_and_stored_reads(client):
    data=attack_snapshot()
    with database.SessionLocal() as db:
        row=DownloadedResource(resource_name='safe',resource_type='lora',source_url='unknown',status='planned',sha256='a'*64)
        db.add(row);db.flush();id=row.id
        publish_metadata(row,ResourceMetadata.model_validate(data));db.commit()
        assert_safe(row.metadata_json)
        item=project_resource(row)
        assert item.model_family=='sdxl' and item.sha256=='a'*64 and item.sha256_verified is None
        assert item.license.values['allowNoCredit'] is True
        assert item.license.values['file_license']['ordinary_sha256']=='a'*64
        assert item.trigger_words[0]=='valid' and item.recommended_parameters['sampler'].value=='https://example.test/proof'
        # An unsafe older stored snapshot must remain readable without a repair write.
        data['base_model']=ATTACK
        row.metadata_json=json.dumps(data);before=row.metadata_json;db.commit()
    def dependency():
        with database.SessionLocal() as db:yield db
    app.dependency_overrides[get_db]=dependency
    statements=[]
    def readonly(conn,cursor,sql,*args):
        statements.append(sql)
        assert sql.split()[0].upper() in {'SELECT','PRAGMA'},sql
    event.listen(database.engine,'before_cursor_execute',readonly)
    try:
        for path in ['/api/resources/'+str(id),'/api/resources']:
            response=client.get(path);assert response.status_code==200,response.json();assert_safe(response.text)
        assert statements
    finally:
        event.remove(database.engine,'before_cursor_execute',readonly);app.dependency_overrides.clear()
    with database.SessionLocal() as db:assert db.get(DownloadedResource,id).metadata_json==before


def test_registered_edited_snapshot_normalized_before_install_publication(boundary):
    b=boundary;descriptor=inspected(b);data=attack_snapshot();data['base_model']=descriptor['model_family']
    descriptor['resource_metadata']=data
    result=b.client.post('/api/civitai-recipes/resource-install',json={'selected':descriptor,'storage_root':'loras'})
    assert result.status_code==200,result.json();id=result.json()['ledger_id']
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id);assert_safe(row.metadata_json)
        assert project_resource(row).sha256_verified is True
    for path in ['/api/resources/'+str(id),'/api/resources','/api/civitai-recipes/local-ledger']:
        result=b.client.get(path);assert result.status_code==200,result.json();assert_safe(result.text)


def test_provider_inspect_select_acquire_normalize_nested_values(boundary):
    b=boundary;b.file['license']={'proof':ATTACK};b.version['trainedWords']=['valid','Bearer DROP_C1',ATTACK]
    b.version['meta'].update(sampler=ATTACK,proof=ATTACK)
    descriptor=inspected(b)
    assert_safe(json.dumps(descriptor['resource_metadata']))
    admitted=acquire_http(b);assert admitted.status_code==202,admitted.json();id=admitted.json()['resource']['acquisition_id']
    b.pending.pop()()
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id);assert_safe(row.metadata_json);assert project_resource(row).sha256_verified is True


@pytest.mark.parametrize('bad',[{'version':999},{'license':{'values':[]}}, {'trigger_words':[{}]},
    {'recommended_parameters':{'steps':{'value':[],'source_field':'version.meta.steps'}}},
    {'verification':{'sha256':'bad'}},{'source_evidence':[]},'bad json',[],None])
def test_family_filters_count_pages_use_typed_validity(client,bad):
    snap=provider_snapshot({'baseModel':'\u2003Pony\u3000'},None,{}).model_dump()
    invalid=json.dumps({**snap,**bad}) if isinstance(bad,dict) else (bad if isinstance(bad,str) else json.dumps(bad))
    ids=[]
    with database.SessionLocal() as db:
        for metadata,notes in [(json.dumps(snap),None),(invalid,json.dumps({'base_model':'Pony'})),
                (None,json.dumps({'base_model':'NoobAI'})),(json.dumps({**snap,'base_model':'Pony extra'}),None),
                (json.dumps(snap),None),(None,'not JSON')]:
            row=DownloadedResource(resource_name='mixed',resource_type='lora',source_url='unknown',status='planned',metadata_json=metadata,notes=notes)
            db.add(row);db.flush();ids.append(row.id)
        db.commit()
    def dependency():
        with database.SessionLocal() as db:yield db
    app.dependency_overrides[get_db]=dependency
    statements=[]
    def readonly(conn,cursor,sql,*args):
        statements.append(sql);assert sql.split()[0].upper() in {'SELECT','PRAGMA'},sql
    event.listen(database.engine,'before_cursor_execute',readonly)
    try:
        detail=client.get('/api/resources/'+str(ids[1])).json();assert detail['model_family'] is None
        pages=[client.get('/api/resources',params={'model_family':'sdxl','limit':1,'offset':i}).json() for i in range(4)]
        assert [p['total'] for p in pages]==[3]*4
        assert [p['items'][0]['resource_id'] for p in pages[:3]]==[ids[0],ids[2],ids[4]]
        assert pages[3]['items']==[]
        assert all(p['items'][0]['model_family']=='sdxl' for p in pages[:3])
        raw=client.get('/api/resources',params={'base_model':'Pony'}).json()
        assert raw['total']==2 and [i['resource_id'] for i in raw['items']]==[ids[0],ids[4]]
        unfiltered=client.get('/api/resources').json();assert unfiltered['total']==6
        assert unfiltered['items'][1]==detail
        ordered=[s for s in statements if 'ORDER BY downloaded_resources.id ASC' in s]
        assert ordered and all('LIMIT' in s and 'OFFSET' in s for s in ordered)
    finally:
        event.remove(database.engine,'before_cursor_execute',readonly);app.dependency_overrides.clear()


@pytest.mark.parametrize('first',['acquire','install'])
@pytest.mark.parametrize('later',['acquire','install'])
@pytest.mark.parametrize('initial,incoming,conflict',[(AIR,None,False),(AIR,AIR,False),(None,AIR,False),(AIR,'urn:air:sdxl:lora:civitai:999@21',True)])
def test_registered_identity_omission_augmentation_and_conflict(boundary,first,later,initial,incoming,conflict):
    b=boundary
    if initial:b.file['air']=initial
    def operate(kind):
        if kind=='acquire':return acquire_http(b)
        return b.client.post('/api/civitai-recipes/resource-install',json={'selected':inspected(b),'storage_root':'loras'})
    created=operate(first);assert created.status_code in {200,202},created.json()
    id=created.json()['resource']['acquisition_id'] if first=='acquire' else created.json()['ledger_id']
    if b.pending:b.pending.pop()()
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id);before=row.metadata_json;sha=row.sha256
        assert project_resource(row).sha256_verified is True
    if incoming:b.file['air']=incoming
    else:b.file.pop('air',None)
    repeated=operate(later)
    if conflict:
        assert repeated.status_code==(422 if later=='acquire' else 409),repeated.json()
    else:
        assert repeated.status_code in {200,202},repeated.json()
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id)
        assert db.query(DownloadedResource).count()==1 and row.air==(initial or incoming)
        assert row.sha256==sha and project_resource(row).sha256_verified is True
        if conflict:assert row.metadata_json==before


@pytest.mark.parametrize('outcome',['success','refused','exception'])
@pytest.mark.parametrize('notes',['  {"base_model":"Illustrious", "unknown":{"history":"PRESERVE_ME"}, "error":"old"} \n','bad old evidence\t', '',None])
def test_retained_background_notes_exact_and_current_error_truth(boundary,outcome,notes):
    b=boundary
    with database.SessionLocal() as db:
        row=DownloadedResource(resource_name='selected.safetensors',resource_type='lora',provider='civitai',source_url='unknown',
            model_id='10',version_id='21',civitai_file_id='32',sha256=b.sha,status='failed',notes=notes)
        db.add(row);db.commit();id=row.id
    admitted=acquire_http(b);assert admitted.status_code==202,admitted.json();assert admitted.json()['resource']['acquisition_id']==id
    # Real provider refusal or real credential file failure; actual background target runs.
    if outcome=='refused':b.failure[0]=True
    if outcome=='exception':(b.tmp/'synthetic-key').write_text('')
    b.pending.pop()()
    response=b.client.get('/api/civitai/resources/status',params={'acquisition_id':id})
    assert response.status_code==200,response.json();summary=response.json()['resources'][0]
    assert summary['status']==('installed' if outcome=='success' else 'failed')
    if outcome=='success':
        assert summary['error'] is None
    else:
        assert isinstance(summary['error'],dict),summary
        assert summary['error']['code']==('unauthorized' if outcome=='refused' else 'civitai_credentials_unavailable')
        assert summary['error']['message'] and summary['error']['hint']
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id);assert row.notes==notes
        assert db.query(DownloadedResource).count()==1
        record=project_resource(row);op=record.source_evidence['acquisition']
        assert op['status']==summary['status'] and op['error']==summary['error']
        assert record.sha256_verified is (True if outcome=='success' else None)
        assert 'resource-fixture-key' not in record.model_dump_json()


@pytest.mark.parametrize('outcome',['success','refused','exception'])
def test_new_row_outcomes_and_same_id_retry_clear_current_error(boundary,outcome):
    b=boundary;admitted=acquire_http(b);assert admitted.status_code==202,admitted.json()
    id=admitted.json()['resource']['acquisition_id']
    if outcome=='refused':b.failure[0]=True
    if outcome=='exception':(b.tmp/'synthetic-key').write_text('')
    b.pending.pop()()
    first=b.client.get('/api/civitai/resources/status',params={'acquisition_id':id}).json()['resources'][0]
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id);original=row.notes
        legacy=json.loads(original)
        if outcome=='success':assert 'file_identity' in legacy and first['error'] is None
        else:assert legacy['error']==first['error'] and first['error']['hint']
    b.failure[0]=False;(b.tmp/'synthetic-key').write_text('resource-fixture-key')
    again=acquire_http(b);assert again.json()['resource']['acquisition_id']==id
    if b.pending:b.pending.pop()()
    final=b.client.get('/api/civitai/resources/status',params={'acquisition_id':id}).json()['resources'][0]
    assert final['status']=='installed' and final['error'] is None
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id)
        assert db.query(DownloadedResource).count()==1 and row.notes==original
        assert project_resource(row).source_evidence['acquisition']=={'status':'installed','error':None}


def test_supplied_operation_cannot_replace_current_retry_diagnostics(boundary):
    b=boundary;b.failure[0]=True
    id=acquire_http(b).json()['resource']['acquisition_id'];b.pending.pop()()
    before=b.client.get('/api/civitai/resources/status',params={'acquisition_id':id}).json()['resources'][0]['error']
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id)
        supplied=provider_snapshot({'baseModel':'Pony'},None,{})
        supplied.source_evidence['acquisition']={'status':'failed','error':None}
        publish_metadata(row,supplied);db.commit()
    after=b.client.get('/api/civitai/resources/status',params={'acquisition_id':id}).json()['resources'][0]['error']
    assert before==after and after['code']=='unauthorized'
