"""Public resource contract at registered HTTP routes; no provider substitutions."""
import json

import pytest
from sqlalchemy import event
from app.db import database
from app.db.database import get_db
from app.db.models import DownloadedResource
from app.main import app
from app.services.resource_records import provider_snapshot


@pytest.fixture
def http_rows(client):
    def dependency():
        with database.SessionLocal() as db:
            yield db
    app.dependency_overrides[get_db] = dependency
    yield client
    app.dependency_overrides.clear()


def seed(metadata, **kw):
    with database.SessionLocal() as db:
        row = DownloadedResource(resource_name='creator\x00 name ' + 'x'*220,
            resource_type='lora', provider='civitai', model_id='10', version_id='21',
            civitai_file_id='32', source_url='https://user:pass@evil.test/wrong?signature=DROP#DROP',
            status='installed', sha256='a'*64, metadata_json=json.dumps(metadata), **kw)
        db.add(row); db.commit()
        return row.id


def test_registered_allowlist_rich_hostile_metadata_and_legacy_storage(http_rows):
    data = provider_snapshot({'baseModel':'Pony','trainedWords':['valid']},None,{}).model_dump()
    data.update(base_model='Po\x00ny', trigger_words=[' Bearer public creator text ', 'word\x00', 'x'*250, '\x00']*40,
        recommended_parameters={
            'steps':{'value':24,'source_field':'https://evil.test/x?signature=DROP'},
            'cfg':{'value':-1,'source_field':'version.meta.cfg'},
            'width':{'value':999999,'source_field':'file.metadata.width'},
            'height':{'value':1024,'source_field':'file.metadata.height'},
            'clip_skip':{'value':2,'source_field':'version.meta.clipSkip'},
            'sampler':{'value':'Euler++ 2M','source_field':'version.meta.sampler'},
            'scheduler':{'value':'<script>','source_field':'version.meta.scheduler'},
            'lora_strength':{'value':0.7,'source_field':'version.meta.strength'}},
        license={'values':{'allowNoCredit':True,'allowCommercialUse':['Sell','RentCivit'],
            'allowDerivatives':{'unknown':'DROP'},'allowDifferentLicense':'unknown',
            'file_license':'DROP'}, 'missing_fields':['hostile field']},
        diagnostics=[{'code':'hostile diagnostic','field':'hostile field'}],
        source_evidence={'acquisition':{'status':'installed','partial':{'internal':'kept'}},'opaque':'DROP'})
    rid = seed(data)
    statements=[]
    def readonly(conn,cursor,sql,*args):
        statements.append(sql)
        assert sql.split()[0].upper() in {'SELECT','PRAGMA'}
    event.listen(database.engine,'before_cursor_execute',readonly)
    try:
        response = http_rows.get(f'/api/resources/{rid}')
        assert response.status_code == 200, response.text
        value = response.json()
        assert 'source_evidence' not in value
        assert value['resource_name'] == ('creator name ' + 'x'*220)[:200]
        assert value['base_model']=='Pony' and value['model_family']=='sdxl'
        assert value['source_url']=='https://civitai.com/models/10?modelVersionId=21'
        assert value['trigger_words']==['Bearer public creator text','word','x'*200]
        assert set(value['recommended_parameters'])=={'steps','height','clip_skip','sampler'}
        assert value['recommended_parameters']['steps']['source_field']=='steps'
        assert value['license']=={'values':{'allowNoCredit':True,'allowCommercialUse':['Sell','RentCivit']},
            'missing_fields':['allowDerivatives','allowDifferentLicense']}
        assert {'invalid_recommendation','invalid_license_field'} <= {d['code'] for d in value['diagnostics']}
        assert all(d['field'] in value for d in value['diagnostics'])
        assert 'hostile' not in json.dumps(value) and 'DROP' not in json.dumps(value)
        listed=http_rows.get('/api/resources',params={'model_family':'sdxl'}).json()
        assert listed['total']==1 and listed['items']==[value]
        schema=http_rows.get('/openapi.json').json()['components']['schemas']['ResourceRecord']
        assert 'source_evidence' not in schema['properties']
    finally:
        event.remove(database.engine,'before_cursor_execute',readonly)
    with database.SessionLocal() as db:
        assert db.get(DownloadedResource,rid).metadata_json==json.dumps(data)


def test_registered_allowlist_caps_words_closed_values_and_invalid_metadata(http_rows):
    data=provider_snapshot({'baseModel':'Pony','trainedWords':[f'word{i}\x01' for i in range(40)]},None,{}).model_dump()
    rid=seed(data)
    value=http_rows.get(f'/api/resources/{rid}').json()
    assert value['trigger_words']==[f'word{i}' for i in range(32)]
    assert value['license']['missing_fields']==['allowNoCredit','allowCommercialUse','allowDerivatives','allowDifferentLicense']
    bad=seed({'version':999,'origin':'civitai_provider','base_model':'Pony'})
    invalid=http_rows.get(f'/api/resources/{bad}').json()
    assert invalid['model_family'] is None and invalid['trigger_words']==[]
    assert 'invalid_metadata' in {d['code'] for d in invalid['diagnostics']}
    assert http_rows.get('/api/resources',params={'model_family':'sdxl'}).json()['total']==1


@pytest.mark.parametrize('name,bad,good',[
    ('steps',151,150),('steps',True,1),('cfg',31,1.0),('cfg',-1,30.0),
    ('width',255,256),('height',2049,2048),('clip_skip',25,24),
    ('steps',10**400,24),('sampler','x'*65,'euler_ancestral'),
    ('scheduler','karras/<script>','normal'),
])
def test_registered_recommendation_bounds(http_rows,name,bad,good):
    data=provider_snapshot({'baseModel':'Pony'},None,{}).model_dump()
    data['recommended_parameters']={name:{'value':bad,'source_field':'version.meta.'+name}}
    rid=seed(data)
    response=http_rows.get(f'/api/resources/{rid}')
    assert response.status_code==200,response.text
    assert response.json()['recommended_parameters']=={}
    data['recommended_parameters'][name]['value']=good
    valid=seed(data)
    value=http_rows.get(f'/api/resources/{valid}').json()
    assert value['recommended_parameters'][name]['value']==good
