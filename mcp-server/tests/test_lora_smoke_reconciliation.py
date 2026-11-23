"""Independent MCP projection through real HttpBackendClient, offline transport."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from mcp_server.client import HttpBackendClient
from mcp_server.tools import lora_train


def invoke(payload, kind):
    def respond(req):
        assert req.method == ('GET' if kind == 'status' else 'POST')
        return httpx.Response(200, json=payload)
    transport = httpx.MockTransport(respond)
    original = httpx.Client
    with patch.object(lora_train, '_get_client', return_value=HttpBackendClient('http://fixture.invalid/api')), patch('httpx.Client', side_effect=lambda **kw: original(transport=transport, **kw)):
        return lora_train.lora_train_job_status('train-1') if kind == 'status' else lora_train.lora_train_smoke_test('train-1')


@pytest.mark.parametrize('kind', ['status','smoke'])
def test_smoke_completion_identity_and_url_survive_client_projection(kind):
    fields = {'artifact':'run/旅人.png','artifact_id':7,'image_id':4,'artifact_url':'/gallery/run/ignored'}
    payload = {'job_id':'train-1', 'smoke_test_status':'completed'}
    payload.update({('smoke_test_'+key if kind=='status' else key):value for key,value in fields.items()})
    payload['smoke_test_job_id' if kind=='status' else 'generation_job_id']='gen-1'
    result=invoke(payload, kind)
    prefix='smoke_test_' if kind=='status' else ''
    assert result['ok'] is True
    assert result[prefix+'artifact_id']==7 and result[prefix+'image_id']==4
    assert result[prefix+'artifact_url']=='/gallery/run/%E6%97%85%E4%BA%BA.png'


@pytest.mark.parametrize('kind', ['status','smoke'])
@pytest.mark.parametrize('bad', ['/private/SECRET_SMOKE.png', '../SECRET_SMOKE.png', 'https://user:SECRET_SMOKE@host/x?token=secret', r'C:\Private\SECRET_SMOKE.png'])
def test_smoke_untrusted_paths_errors_and_unknown_codes_do_not_escape(kind, bad):
    prefix='smoke_test_' if kind=='status' else ''
    payload={'job_id':'train-1','smoke_test_status':'unknown',prefix+'artifact':bad,
             prefix+'artifact_url':'https://SECRET_SMOKE',prefix+'artifact_id':True,
             prefix+'image_id':-4,prefix+'error':'SECRET_SMOKE /private/key',
             prefix+'error_code':'SECRET_SMOKE',prefix+'hint':'SECRET_SMOKE',
             'private_new_field':'SECRET_SMOKE'}
    result=invoke(payload,kind)
    assert result['ok'] is True
    assert 'SECRET_SMOKE' not in json.dumps(result)
    assert result[prefix+'error_code']=='smoke_submission_unknown'
    assert result[prefix+'hint']
    assert result[prefix+'artifact'] is None


@pytest.mark.parametrize('code', ['smoke_generation_failed','smoke_generation_cancelled','smoke_job_missing','smoke_job_unknown','smoke_artifact_unavailable','smoke_submission_unknown','generation_queue_full'])
def test_smoke_known_diagnostics_remain_actionable(code):
    result=invoke({'job_id':'train-1','smoke_test_status':'unknown','smoke_test_error_code':code,'smoke_test_error':'raw private text'},'status')
    assert result['smoke_test_error_code']==code
    assert result['smoke_test_hint'] and result['smoke_test_error']
    assert 'raw private' not in json.dumps(result)


def test_real_backend_http_payloads_in_independent_component_environment():
    path=os.environ.get('SMOKE_HTTP_FIXTURE_OUT')
    if not path:
        pytest.skip('run Backend export first and set SMOKE_HTTP_FIXTURE_OUT for actual HTTP -> independent MCP verification')
    records=json.loads(Path(path).read_text())
    assert records
    for record in records:
        result=invoke(record['payload'],record['kind'])
        assert result['ok'] is True
        assert result['smoke_test_status']==record['state']
        prefix='smoke_test_' if record['kind']=='status' else ''
        if record['state']=='completed':
            assert result[prefix+'artifact']=='run/smoke.png'
            assert result[prefix+'artifact_id']==1 and result[prefix+'image_id']==1
            assert result[prefix+'artifact_url']=='/gallery/run/smoke.png'
        else:
            assert result[prefix+'error_code']==record['code']
            assert result[prefix+'hint']


def test_corrupt_image_recovery_payloads_from_real_backend_http():
    path = os.environ.get('SMOKE_IMAGE_HTTP_FIXTURE_OUT')
    if not path:
        pytest.skip('run Backend image-validation export first and set SMOKE_IMAGE_HTTP_FIXTURE_OUT')
    records = json.loads(Path(path).read_text())
    assert records and {r['state'] for r in records} == {'artifact_unavailable', 'completed'}
    assert {r['kind'] for r in records} == {'status', 'smoke'}
    for record in records:
        result = invoke(record['payload'], record['kind'])
        prefix = 'smoke_test_' if record['kind'] == 'status' else ''
        assert result['ok'] is True
        assert result['smoke_test_status'] == record['state']
        assert result['smoke_test_job_id' if record['kind'] == 'status' else 'generation_job_id'] == 'gen-1'
        assert result['registered_lora_name'] == 'products/旅人_002.safetensors'
        assert result[prefix + 'artifact'] == record['artifact']
        assert result[prefix + 'image_id'] == record['image_id']
        assert result[prefix + 'artifact_id'] == record['artifact_id']
        if record['state'] == 'completed':
            assert record['gallery_sha256']  # Backend retrieved and decoded these bytes.
            assert result[prefix + 'artifact_url'] == '/gallery/' + record['artifact']
            assert result[prefix + 'error_code'] is None
        else:
            assert result[prefix + 'artifact_url'] is None
            assert result[prefix + 'error_code'] == 'smoke_artifact_unavailable'
            assert result[prefix + 'error'] and result[prefix + 'hint']
