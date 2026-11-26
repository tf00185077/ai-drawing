"""T1-T3: reverting shared label recognition exposes values at real boundaries.

Only external HTTP/scheduling are substituted by the retained fixtures. Expected
redaction and safe neighbors are literal; no expectation calls the recognizer.
"""
import json

import pytest
from app.db import database
from app.db.models import DownloadedResource
from app.schemas.resources import ResourceMetadata
from app.services.resource_records import normalize_metadata, provider_snapshot, publish_metadata
from tests.test_resource_record_writers import boundary
from tests import test_resource_record_credential_values as values

# Prefixes are identifier parts, including joined/camelCase, numeric components,
# Unicode identifiers, mixed case, separators and quoted header/assignment labels.
LABELS = [
    'CIVITAI_API_KEY', 'HTTP_AUTHORIZATION', 'provider_api_key',
    'X-Api-Key', 'provider.api.key', 'provider api key', 'providerApiKey',
    'providerapikey', 'HTTP_PROXY_AUTHORIZATION', 'httpAuthorization',
    'SERVICE_ACCESS_TOKEN', 'serviceAccessToken', 'app2_token', 'APP_SECRET',
    'vendorPassword', 'X-Credential', 'remote.signature', 'HTTP_COOKIE',
    'HTTP_SET_COOKIE', '服务_API_KEY', 'ENV__API__KEY', 'v2.AUTHORIZATION',
]
ASSIGNMENTS = [
    'CIVITAI_API_KEY="QA3 ENV MULTI WORD VALUE"',
    'HTTP_AUTHORIZATION=Basic UUEzX0VOVl9WQUxVRQ==',
] + [f'{label} = "synthetic full value; later suffix"' for label in LABELS[2:]] + [
    '"CIVITAI_API_KEY" : "quoted label full value"',
    "'HTTP_AUTHORIZATION' = Basic b3BhcXVl",  # explicitly labelled: no colon decoding requirement
    '"provider api key"\u2003=\u3000"unicode whitespace full value"',
    'context: ordinary; providerApiKey="all of this value"; trailing safe prose',
]


@pytest.mark.parametrize('text', ASSIGNMENTS)
def test_prefixed_direct_publication_commit_reload_idempotent(client, text):
    values.test_complete_value_direct_publication_commit_reload_and_idempotence(client, text)


@pytest.mark.parametrize('text', ASSIGNMENTS)
def test_prefixed_registered_edited_install(boundary, text):
    values.test_complete_value_registered_edited_install_publication(boundary, text)


@pytest.mark.parametrize('text', ASSIGNMENTS)
def test_prefixed_provider_inspect_select_acquire_background(boundary, text):
    values.test_complete_value_real_provider_inspect_select_acquire_background(boundary, text)


@pytest.mark.parametrize('text', ASSIGNMENTS)
@pytest.mark.parametrize('field', values.FIELDS)
def test_prefixed_old_storage_all_fields_readonly(client, tmp_path, monkeypatch, field, text):
    values.test_complete_value_old_storage_detail_list_ledger_readonly(client, tmp_path, monkeypatch, field, text)


@pytest.mark.parametrize('label', LABELS)
def test_credential_dictionary_keys_share_assignment_policy(client, tmp_path, label):
    data = provider_snapshot({'baseModel':'Pony','trainedWords':['allowed']},None,{}).model_dump()
    data['source_evidence'] = {'nested':[{label:'synthetic full value', 'tokenizer':'retained', 'hash':values.SAFE_HASH}]}
    data['license']['values'] = {label:'synthetic full value','allowNoCredit':True}
    data['recommended_parameters'] = {label:{'value':27,'source_field':'version.meta.steps'}}
    model=tmp_path/'key-label.safetensors';model.write_bytes(b'synthetic key fixture')
    with database.SessionLocal() as db:
        row = DownloadedResource(resource_name='key-label',resource_type='lora',provider='civitai',source_url='unknown',status='installed',local_path=str(model))
        db.add(row);db.flush();id=row.id
        publish_metadata(row,ResourceMetadata.model_validate(data));db.commit();db.expire_all()
        observed = json.loads(db.get(DownloadedResource,id).metadata_json)
    assert observed['source_evidence']['nested'] == [{'tokenizer':'retained','hash':values.SAFE_HASH}]
    assert observed['license']['values'] == {'allowNoCredit':True}
    assert observed['recommended_parameters'] == {}
    for url in ['/api/resources/'+str(id),'/api/resources','/api/civitai-recipes/local-ledger']:
        response=client.get(url);assert response.status_code==200,response.text
        assert 'synthetic full value' not in response.text and values.SAFE_HASH in response.text


SAFE = ['tokenizer','tokenization','api_keyboard','api_keynote','secretariat','passwordless',
        'authorizations','cookiecutter','credentialed','signaturelike','api_version','ordinary_hash',
        'API_KEY documentation without assignment','secret garden','src/tokenizer.py',values.SAFE_HASH]


@pytest.mark.parametrize('safe', SAFE)
def test_near_neighbor_metadata_and_keys_remain_useful(client, safe):
    data=provider_snapshot({'baseModel':'Pony','trainedWords':['allowed',safe]},None,{}).model_dump()
    # Prose/path examples are values; identifier examples also exercise safe keys.
    evidence={'description':safe,'hash':values.SAFE_HASH}
    if safe in SAFE[:12]: evidence[safe]='ordinary value'
    data['source_evidence']=evidence
    with database.SessionLocal() as db:
        row=DownloadedResource(resource_name='neighbor',resource_type='lora',source_url='unknown',status='planned')
        db.add(row);db.flush();id=row.id;publish_metadata(row,ResourceMetadata.model_validate(data));db.commit()
        before=row.metadata_json
    item=client.get('/api/resources/'+str(id)).json()
    assert item['trigger_words']==['allowed',safe]
    assert item['source_evidence']==evidence
    assert normalize_metadata(ResourceMetadata.model_validate_json(before)).model_dump_json()==before


@pytest.mark.parametrize('label', LABELS)
@pytest.mark.parametrize('field', ['license_key','recommendation_key','evidence_key'])
def test_prefixed_label_keys_in_old_storage_readonly(client, tmp_path, monkeypatch, field, label):
    values.test_complete_value_old_storage_detail_list_ledger_readonly(client, tmp_path, monkeypatch, field, label)
