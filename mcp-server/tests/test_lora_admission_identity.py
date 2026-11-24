"""Independent MCP client projection, including real Backend HTTP export."""
import json, os, sys
from pathlib import Path
from unittest.mock import patch
import httpx
import pytest
from mcp_server.client import HttpBackendClient
from mcp_server.tools import lora_train
from mcp_server.server import mcp
import asyncio

@pytest.mark.parametrize('malformed',[False,True])
def test_uncertain_admission_has_safe_identity_and_no_retry_hint(malformed):
    payload={'detail':{'code':'admission_uncertain','job_id':'bad/PRIVATE_SENTINEL' if malformed else 'canonical-123','hint':'PRIVATE_SENTINEL','message':'PRIVATE_SENTINEL','details':{'anything':'PRIVATE_SENTINEL'}}}
    transport=httpx.MockTransport(lambda req:httpx.Response(503,json=payload))
    original=httpx.Client
    with patch.object(lora_train,'_get_client',return_value=HttpBackendClient('http://fixture.invalid/api')),patch('httpx.Client',side_effect=lambda **kw:original(transport=transport,**kw)):
        result=lora_train.lora_train_start('x','x',expected_dataset_hash='d',expected_profile_hash='p',recipe={})
    assert result['error']['code']=='admission_uncertain'
    if not malformed:assert result['job_id']==result['error']['job_id']=='canonical-123'
    else:assert result.get('job_id') is None
    assert 'do not resubmit' in result['error']['hint']
    assert 'PRIVATE_SENTINEL' not in json.dumps(result)

def test_real_backend_http_export_survives_independent_client():
    file=os.environ.get('LORA_LIFECYCLE_HTTP_FIXTURE')
    if not file:pytest.skip('run verify_offline lifecycle-export first; supply exact export path')
    rows=json.loads(Path(file).read_text())
    original=httpx.Client
    for row in rows:
        calls=[]
        def handle(req):
            calls.append(str(req.url));return httpx.Response(row['http_status'],json=row['body'])
        with patch.object(lora_train,'_get_client',return_value=HttpBackendClient('http://fixture.invalid/api')),patch('httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(handle),**kw)):
            result=asyncio.run(mcp.call_tool('lora_train_start', {'folder': 'x', 'output_name': 'x', 'expected_dataset_hash': 'd', 'expected_profile_hash': 'p', 'recipe': {}}))[1]
        assert len(calls)==1 and result['error']['details']['job_id']==row['body']['detail']['job_id']
        assert result['error']['code']=='admission_uncertain' and 'SECRET_SENTINEL' not in json.dumps(result)
    assert not any(k.startswith('app.') for k in sys.modules)
