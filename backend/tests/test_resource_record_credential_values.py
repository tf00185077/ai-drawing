"""S1-S3 complete-value guards: synthetic credentials; real writers/ORM/HTTP.

The affected string is one safety unit. Neighboring typed data must survive.
Only external HTTP and scheduling are substituted by the retained boundary.
"""
import builtins
import json
from pathlib import Path

import pytest
from sqlalchemy import event
from app.db import database
from app.db.database import get_db
from app.db.models import DownloadedResource
from app.main import app
from app.schemas.resources import ResourceMetadata
from app.services.resource_records import normalize_metadata, provider_snapshot, publish_metadata
from tests.test_resource_record_writers import boundary, acquire_http
from tests.test_resource_record_corrections import inspected

REDACTED = '[redacted credential]'
# Complete affected values, including suffixes after schemes, quotes/delimiters,
# embedded labels, multiple headers, Unicode whitespace and malformed quotes.
ATTACKS = [
    'Authorization: Basic Q29tcGxldGUgdmFsdWU=',
    'Proxy-Authorization: Basic UHJveHkgdmFsdWU=',
    'Cookie: theme=light; session=later-cookie; other=last-cookie',
    'api_key="two word secret"',
    "API-KEY = 'three word secret' trailing text",
    'prefix Authorization:\tBasic\tZGlmZmVyZW50\r\nCookie: a=1; b=2',
    'proxy_authorization = Digest username="name", response="secret", nonce="tail"',
    'Set-Cookie: preference=light; session=second; HttpOnly',
    'password="a;b,c d"; suffix',
    'access_token = "alpha beta"',
    'credential: first second third',
    'signature = value, other=value; tail',
    'token:\u2003first\u3000second',
    'secret="unterminated multi word value',
    '"api_key" : "json style multiword value"',
    'Bearer abc.def+ghi==, next secret',
    'Basic dXNlcjpwYXNz; suffix',
    'X-Api-Key: "compound header value"',
    'proxy authorization: Basic QW5vdGhlcg==',
    'cookie=one=1; two=2; three=3',
]
SAFE_HASH = 'a' * 64


def snapshot_with(text):
    data = provider_snapshot({'baseModel':'Pony','trainedWords':['allowed']},None,{}).model_dump()
    data['trigger_words'] += [text]
    data['recommended_parameters'] = {
        'sampler': {'value': text, 'source_field': text},
        'steps': {'value': 27, 'source_field': 'version.meta.steps'},
        text: {'value': 6.25, 'source_field': 'version.meta.cfgScale'},
    }
    data['license']['values'] = {'allowNoCredit':True, 'file_license':{
        'description':text, 'ordinary_hash':SAFE_HASH, 'permissions':['personal'], text:text}}
    data['license']['missing_fields'] += [text]
    data['source_evidence'] = {'nested':[{'description':text, 'hash':SAFE_HASH}], text:text,
                               'path':'src/tokenizer.py', 'safe':'ordinary evidence'}
    data['diagnostics'].append({'code':text, 'field':text})
    return data


def assert_neighbors(snapshot):
    assert snapshot['license']['values']['allowNoCredit'] is True
    assert snapshot['license']['values']['file_license']['ordinary_hash'] == SAFE_HASH
    assert snapshot['license']['values']['file_license']['permissions'] == ['personal']
    assert snapshot['trigger_words'][0] == 'allowed'
    assert snapshot['recommended_parameters']['steps'] == {'value':27,'source_field':'version.meta.steps'}
    assert snapshot['source_evidence']['path'] == 'src/tokenizer.py'
    assert snapshot['source_evidence']['nested'][0]['hash'] == SAFE_HASH


def assert_complete(snapshot):
    assert_neighbors(snapshot)
    assert snapshot['trigger_words'][1] == REDACTED
    assert snapshot['license']['values']['file_license']['description'] == REDACTED
    assert snapshot['recommended_parameters']['sampler'] == {'value':REDACTED,'source_field':REDACTED}
    assert snapshot['license']['missing_fields'][-1] == REDACTED
    assert snapshot['source_evidence']['nested'][0]['description'] == REDACTED
    assert snapshot['diagnostics'][-1] == {'code':REDACTED,'field':REDACTED}
    # Keys with recognized labels are excluded; standalone schemes are redacted.
    assert set(snapshot['recommended_parameters']) <= {'sampler','steps',REDACTED}
    assert set(snapshot['source_evidence']) <= {'nested','path','safe',REDACTED,'acquisition'}


@pytest.mark.parametrize('text', ATTACKS)
def test_complete_value_direct_publication_commit_reload_and_idempotence(client,text):
    data=snapshot_with(text)
    with database.SessionLocal() as db:
        row=DownloadedResource(resource_name='direct',resource_type='lora',provider='civitai',source_url='unknown',status='planned',sha256=SAFE_HASH)
        db.add(row);db.flush();id=row.id
        publish_metadata(row,ResourceMetadata.model_validate(data));db.commit();db.expire_all()
        row=db.get(DownloadedResource,id);before=row.metadata_json
        snapshot=ResourceMetadata.model_validate_json(before)
        assert_complete(snapshot.model_dump())
        assert normalize_metadata(snapshot).model_dump_json() == before
        publish_metadata(row,snapshot);db.commit();db.expire_all()
        assert db.get(DownloadedResource,id).metadata_json == before
        assert db.query(DownloadedResource).count() == 1


FIELDS = ['license','license_key','missing_field','diagnostic_code','diagnostic_field','trigger',
          'recommendation_value','recommendation_origin','recommendation_key','evidence','evidence_key','base_model']


def put_field(data,field,text):
    if field=='license': data['license']['values']['description']=text
    elif field=='license_key': data['license']['values'][text]='untrusted value'
    elif field=='missing_field': data['license']['missing_fields'].append(text)
    elif field=='diagnostic_code': data['diagnostics'].append({'code':text,'field':'provider_note'})
    elif field=='diagnostic_field': data['diagnostics'].append({'code':'provider_note','field':text})
    elif field=='trigger': data['trigger_words'].append(text)
    elif field=='recommendation_value': data['recommended_parameters']['sampler']={'value':text,'source_field':'version.meta.sampler'}
    elif field=='recommendation_origin': data['recommended_parameters']['sampler']={'value':'Euler','source_field':text}
    elif field=='recommendation_key': data['recommended_parameters'][text]={'value':27,'source_field':'version.meta.steps'}
    elif field=='evidence': data['source_evidence']['nested']=[{'description':text}]
    elif field=='evidence_key': data['source_evidence'][text]='untrusted value'
    elif field=='base_model': data['base_model']=text


@pytest.mark.parametrize('text',ATTACKS[:4])
@pytest.mark.parametrize('field',FIELDS)
def test_complete_value_old_storage_detail_list_ledger_readonly(client,tmp_path,monkeypatch,field,text):
    data=provider_snapshot({'baseModel':'Pony','trainedWords':['allowed']},None,{}).model_dump()
    data['license']['values']={'allowNoCredit':True,'hash':SAFE_HASH}
    data['source_evidence']={'path':'src/tokenizer.py'}
    put_field(data,field,text)
    model=tmp_path/'unread.safetensors';model.write_bytes(b'synthetic stored bytes')
    notes='  {"historical":"exact evidence"} \n'
    with database.SessionLocal() as db:
        row=DownloadedResource(resource_name='old',resource_type='lora',provider='civitai',source_url='unknown',
            status='installed',local_path=str(model),sha256=SAFE_HASH,metadata_json=json.dumps(data),notes=notes)
        db.add(row);db.commit();id=row.id;before=row.metadata_json
    def dependency():
        with database.SessionLocal() as db: yield db
    app.dependency_overrides[get_db]=dependency
    def deny(*a,**k): raise AssertionError('stored read side effect')
    from app.services import civitai_provider,resource_records,resource_record_backfill
    monkeypatch.setattr(civitai_provider,'ProviderOperation',deny)
    monkeypatch.setattr(resource_record_backfill,'backfill_metadata',deny)
    monkeypatch.setattr(resource_records,'publish_metadata',deny)
    original=builtins.open;pathopen=Path.open
    def guarded(p,*a,**kw):
        if str(p)==str(model): return deny()
        return original(p,*a,**kw)
    def pathguard(p,*a,**kw):
        if p==model: return deny()
        return pathopen(p,*a,**kw)
    monkeypatch.setattr(builtins,'open',guarded);monkeypatch.setattr(Path,'open',pathguard)
    statements=[]
    def readonly(conn,cursor,sql,*args):
        statements.append(sql); assert sql.split()[0].upper() in {'SELECT','PRAGMA'},sql
    event.listen(database.engine,'before_cursor_execute',readonly)
    try:
        detail=client.get('/api/resources/'+str(id));assert detail.status_code==200,detail.text
        page=client.get('/api/resources');assert page.status_code==200,page.text
        ledger=client.get('/api/civitai-recipes/local-ledger');assert ledger.status_code==200,ledger.text
        item=detail.json()
        assert page.json()['items']==[item] and page.json()['total']==1
        assert ledger.json()['entries'][0]['diagnostics']['resource_record']==item
        expected=ResourceMetadata.model_validate(data).model_dump()
        # Exact complete redaction, not absence of a hand-picked marker/suffix.
        if field.endswith('_key'):
            for container in [item['license']['values'],item['recommended_parameters'],item['source_evidence']]:
                assert text not in container
        elif field=='base_model': assert item['base_model']==REDACTED
        elif field=='license': assert item['license']['values']['description']==REDACTED
        elif field=='missing_field': assert item['license']['missing_fields'][-1]==REDACTED
        elif field=='diagnostic_code': assert {'code':REDACTED,'field':'provider_note'} in item['diagnostics']
        elif field=='diagnostic_field': assert {'code':'provider_note','field':REDACTED} in item['diagnostics']
        elif field=='trigger': assert item['trigger_words'][-1]==REDACTED
        elif field=='recommendation_value': assert item['recommended_parameters']['sampler']['value']==REDACTED
        elif field=='recommendation_origin': assert item['recommended_parameters']['sampler']['source_field']==REDACTED
        elif field=='evidence': assert item['source_evidence']['nested'][0]['description']==REDACTED
        assert item['resource_id']==id and item['sha256']==SAFE_HASH
        assert item['license']['values']['hash']==SAFE_HASH and item['license']['values']['allowNoCredit'] is True
        assert item['trigger_words'][0]=='allowed' and item['source_evidence']['path']=='src/tokenizer.py'
        family=client.get('/api/resources',params={'model_family':'sdxl','limit':1}).json()
        assert family['total']==(0 if field=='base_model' else 1)
        assert family['items']==([] if field=='base_model' else [item])
        assert any('LIMIT' in s and 'OFFSET' in s for s in statements)
    finally:
        event.remove(database.engine,'before_cursor_execute',readonly);app.dependency_overrides.clear()
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id);assert row.metadata_json==before and row.notes==notes


@pytest.mark.parametrize('text',ATTACKS)
def test_complete_value_registered_edited_install_publication(boundary,text):
    b=boundary;selected=inspected(b);data=snapshot_with(text);data['base_model']=selected['model_family']
    selected['resource_metadata']=data
    selected['license']={'description':text,'hash':SAFE_HASH}
    selected['usage_restrictions']={'description':text,'personal':True}
    installed=b.client.post('/api/civitai-recipes/resource-install',json={'selected':selected,'storage_root':'loras'})
    assert installed.status_code==200,installed.json();id=installed.json()['ledger_id']
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id);assert_complete(json.loads(row.metadata_json))
        assert json.loads(row.notes)['license']['description']==REDACTED
    for url in ['/api/resources/'+str(id),'/api/resources','/api/civitai-recipes/local-ledger']:
        result=b.client.get(url);assert result.status_code==200,result.json()
        assert text not in result.text


@pytest.mark.parametrize('text',ATTACKS)
def test_complete_value_real_provider_inspect_select_acquire_background(boundary,text):
    b=boundary
    b.file['license']={'description':text,'hash':SAFE_HASH}
    b.file['usage']={'description':text,'personal':True}
    b.version['trainedWords']=['allowed',text]
    b.version['meta'].update(sampler=text,description=text)
    # These model permission strings also appear in legacy acquisition status.
    b.model['allowCommercialUse']=['None',text]
    selected=inspected(b)
    assert selected['license']['description']==REDACTED
    assert selected['usage_restrictions']['description']==REDACTED
    assert selected['resource_metadata']['trigger_words']==['allowed',REDACTED]
    assert selected['resource_metadata']['recommended_parameters']['sampler']['value']==REDACTED
    assert selected['resource_metadata']['source_evidence']['version.meta']['description']==REDACTED
    admitted=acquire_http(b);assert admitted.status_code==202,admitted.json();id=admitted.json()['resource']['acquisition_id']
    assert admitted.json()['resource']['license']['allowCommercialUse']==['None',REDACTED]
    with database.SessionLocal() as db:
        assert json.loads(db.get(DownloadedResource,id).metadata_json)['license']['values']['file_license']['description']==REDACTED
    b.pending.pop()()
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,id);snapshot=json.loads(row.metadata_json)
        assert snapshot['trigger_words']==['allowed',REDACTED]
        assert snapshot['verification']['sha256']==b.sha
        assert snapshot['license']['values']['file_license']=={'description':REDACTED,'hash':SAFE_HASH}
        assert row.sha256==b.sha and db.query(DownloadedResource).count()==1
    status=b.client.get('/api/civitai/resources/status',params={'acquisition_id':id})
    assert status.status_code==200,status.json()
    assert status.json()['resources'][0]['license']['allowCommercialUse']==['None',REDACTED]


@pytest.mark.parametrize('safe',['ordinary permissions','a'*64,'src/tokenizer.py','secret garden','cookie cutter',
    'basic painting','bearer of news?','sampler: Euler','https://example.test/file?token=remove#secret'])
def test_safe_neighbors_retain_meaning(client,safe):
    from app.services.resource_records import safe_text
    expected='https://example.test/file' if safe.startswith('https://') else (REDACTED if safe=='bearer of news?' else safe)
    assert safe_text(safe)==expected
