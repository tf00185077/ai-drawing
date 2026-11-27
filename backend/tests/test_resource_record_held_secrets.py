"""D2 real configured-file/provider/acquisition/storage/read paths; synthetic key only."""
import json
import logging
from urllib.parse import quote

from app.db import database
from app.db.models import DownloadedResource
from tests.test_resource_record_writers import boundary, acquire_http


def test_acquisition_held_key_signed_urls_transport_absent_every_phase(boundary, caplog, monkeypatch):
    b=boundary
    key='synthetic-held+/=key'
    encoded=quote(key,safe='')
    (b.tmp/'synthetic-key').write_text(key)
    signed='https://user:password@example.test/proof?X-Amz-Signature=SIGNED_QUERY#fragment'
    b.version['trainedWords']=['creator token=public text',key,encoded,signed]
    b.version['name']=key+' '+encoded+' '+signed
    b.model['name']=b.version['name']
    b.version['meta'].update(proof=key+' '+encoded+' '+signed,
        Authorization='Bearer '+key, COOKIE='private cookie', api_key=key)
    b.file['metadata'].update(proof=b.version['meta']['proof'], **{'X-API-Key':encoded})
    b.file['downloadUrl']='https://civitai.com/api/download/models/21?ticket=SIGNED_DOWNLOAD'
    caplog.set_level(logging.DEBUG,logger='httpx')
    caplog.set_level(logging.DEBUG,logger='httpcore.http11')
    import httpx
    original_send=httpx._client.AsyncClient.send
    async def send(self,request,**kwargs):
        logging.getLogger('httpcore.http11').debug('headers %r location %s',
            [(b'set-cookie',b'private cookie'),(b'authorization',request.headers.get('authorization'))],
            'https://b2.civitai.com/file?ticket=SIGNED_QUERY')
        return await original_send(self,request,**kwargs)
    # External HTTP is already mocked by boundary; only add received-header traces.
    monkeypatch.setattr(httpx._client.AsyncClient,'send',send)
    observations=[]
    def observe(rid):
        with database.SessionLocal() as db:
            row=db.get(DownloadedResource,rid)
            observations.append(json.dumps({c.name:str(getattr(row,c.name)) for c in row.__table__.columns}))
        for path in ['/api/resources',f'/api/resources/{rid}',
            '/api/civitai/resources/status',f'/api/civitai/resources/status?acquisition_id={rid}',
            '/api/civitai-recipes/local-ledger']:
            response=b.client.get(path)
            assert response.status_code==200,response.text
            observations.append(response.text)
    admitted=acquire_http(b)
    assert admitted.status_code==202,admitted.text
    rid=admitted.json()['resource']['acquisition_id']; observations.append(admitted.text)
    observe(rid)
    b.pending.pop()()
    observe(rid)
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        assert row.status=='installed'
        assert json.loads(row.metadata_json)['source_evidence']['acquisition']['status']=='installed'
    text='\n'.join(observations)+caplog.text
    for forbidden in (key,encoded,'SIGNED_QUERY','SIGNED_DOWNLOAD','private cookie','user:password'):
        assert forbidden not in text
    assert 'creator token=public text' in text


def test_shared_filter_only_urls_exact_transport_keys_and_held_secrets(boundary):
    from app.services.resource_records import safe_evidence
    key='synthetic-held+/=key'; (boundary.tmp/'synthetic-key').write_text(key)
    text='Bearer public value; api_key=creator text; Basic dXNlcjpwYXNz'
    raw={name:'transport secret' for name in ['Authorization','PROXY-AUTHORIZATION','Cookie','Set-Cookie','token','api_key','apikey','x-api-key']}
    raw.update(password=text, access_token=text, ordinary={'nested':[float('inf'),key,quote(key,safe='')]},
        url='https://user:pass@example.test/path?arbitrary=SIGNED#fragment',
        **{key:'key name',quote(key,safe=''):'encoded key name'})
    result=safe_evidence(raw)
    assert result['password']==result['access_token']==text
    assert set(result)=={'password','access_token','ordinary','url','[REDACTED]'}
    assert result['ordinary']['nested']==[None,'[REDACTED]','[REDACTED]']
    assert result['url']=='https://example.test/path'
