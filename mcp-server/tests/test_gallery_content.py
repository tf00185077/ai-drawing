"""Canonical PNG contract through actual registered wrappers and HTTP client.

Faults caught: content omitted/rewritten; selector coercion; unsafe or raced
opening; shallow PNG checks; unbounded reads; wrong error/state. Only HTTP
transport and selected OS/storage faults are replaced.
"""
import base64
import hashlib
import io
import json
import os
import struct
import zlib
from pathlib import Path

import httpx
import pytest
from PIL import Image

from mcp_server.config import get_mcp_settings
from mcp_server.server import mcp


def png(size=(8, 9), color='red', **kwargs):
    out = io.BytesIO()
    Image.new('RGB', size, color).save(out, format='PNG', **kwargs)
    return out.getvalue()


@pytest.fixture
def content_backend(tmp_path, monkeypatch):
    root = tmp_path / 'host' / 'gallery'
    root.mkdir(parents=True)
    path = root / 'nested' / '杯 子.png'
    path.parent.mkdir()
    body = png()
    path.write_bytes(body)
    record = {'id': 73, 'artifact_type': 'image', 'mime_type': 'image/png',
              'gallery_path': 'nested/杯 子.png', 'artifact_url': '/gallery/nested/杯%20子.png',
              'local_path': str(path), 'file_size': len(body), 'job_id': 'job-73',
              'width': 8, 'height': 9, 'revision_context': {'request_ref': 'cup'},
              'revision_context_error': None}
    requests = []
    response = {'status': 200, 'body': record}
    def respond(req):
        requests.append((req.method, req.url.path))
        assert req.method == 'GET'  # no writes/submission is part of the read
        return httpx.Response(response['status'], json=response['body'])
    real = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: real(transport=httpx.MockTransport(respond), **kw))
    monkeypatch.setenv('MCP_BACKEND_API_URL', 'http://backend.invalid')
    monkeypatch.setenv('MCP_GALLERY_DIR', str(root))
    get_mcp_settings.cache_clear()
    yield root, path, record, body, requests, response
    get_mcp_settings.cache_clear()


async def read(**args):
    blocks, result = await mcp.call_tool('gallery_get', args)
    assert json.loads(blocks[0].text) == result
    return result


def error(result, code):
    assert result['ok'] is False, result
    assert set(result) == {'ok', 'error'}
    assert result['error']['code'] == code
    if code.startswith('artifact_content'):
        assert result['error']['details']['artifact_id'] == 73
        assert 'metadata' in result['error']['hint'].lower()
        assert 'base64' not in json.dumps(result)
        assert not any(s in result['error']['hint'].lower() for s in ('resubmit', 'regenerat', 'cancel'))


async def test_exact_png_metadata_default_and_root_symlink(content_backend, monkeypatch):
    root, path, record, body, requests, _ = content_backend
    metadata = await read(artifact_id=73)
    assert metadata['ok'] and 'content' not in metadata['data']
    alias = root.parent / 'alias'
    alias.symlink_to(root, target_is_directory=True)
    monkeypatch.setenv('MCP_GALLERY_DIR', str(alias))
    get_mcp_settings.cache_clear()
    result = await read(artifact_id=73, include_content=True)
    assert result['ok'], result
    assert {k:v for k,v in result['data'].items() if k != 'content'} == metadata['data']
    assert result['data']['content'] == {'encoding': 'base64', 'mime_type': 'image/png',
        'byte_length': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
        'width': 8, 'height': 9, 'base64': base64.b64encode(body).decode('ascii')}
    assert requests == [('GET', '/api/gallery/artifacts/73')] * 2
    assert path.read_bytes() == body


@pytest.mark.parametrize('args', [
    {}, {'image_id': 3}, {'image_id': 3, 'artifact_id': 73},
    *[{'artifact_id': x} for x in (0, -1, True, 73.0, '73', [], {})],
    {'artifact_id':73, 'include_content': 'true'},
    {'artifact_id':73, 'path':'private'},
])
async def test_selectors_rejected_before_backend_or_open(content_backend, monkeypatch, args):
    _, _, _, _, requests, _ = content_backend
    args = {'include_content': True, **args}
    def forbidden(*a, **k):
        pytest.fail('invalid selection opened storage')
    monkeypatch.setattr(os, 'open', forbidden)
    error(await read(**args), 'request_validation_failed')
    assert requests == []


@pytest.mark.parametrize('change,code', [
    ({'id':74}, 'artifact_content_unavailable'),
    ({'id':True}, 'artifact_content_unavailable'),
    ({'artifact_type':'video'}, 'artifact_content_invalid'),
    ({'mime_type':'image/jpeg'}, 'artifact_content_invalid'),
    ({'mime_type':None}, 'artifact_content_invalid'),
    ({'gallery_path':'../secret.png'}, 'artifact_content_unavailable'),
    ({'artifact_url':'http://remote.invalid/secret.png'}, 'artifact_content_unavailable'),
    ({'artifact_url':'/gallery/other.png'}, 'artifact_content_unavailable'),
    ({'local_path':'CONFLICT'}, 'artifact_content_unavailable'),
    ({'gallery_path':'/data/gallery/cup.png', 'artifact_url':None, 'local_path':None}, 'artifact_content_unavailable'),
    ({'gallery_path':None, 'artifact_url':None, 'local_path':None}, 'artifact_content_unavailable'),
])
async def test_identity_mime_and_locator_fail_closed(content_backend, change, code):
    root, path, record, _, _, _ = content_backend
    if change.get('local_path') == 'CONFLICT':
        change = {**change, 'local_path':str(root/'other.png')}
    record.update(change)
    result = await read(artifact_id=73, include_content=True)
    error(result, code)
    assert 'secret' not in json.dumps(result) and '/data/gallery' not in json.dumps(result)
    assert str(root) not in json.dumps(result) if code == 'artifact_content_unavailable' else True


@pytest.mark.parametrize('case,code', [
    ('missing','unavailable'), ('directory','unavailable'), ('fifo','unavailable'),
    ('unreadable','unavailable'), ('empty','invalid'), ('corrupt','invalid'),
    ('truncated','invalid'), ('jpeg','invalid'), ('animated','invalid'),
    ('oversize','too_large'), ('wide','too_large'), ('tall','too_large'),
])
async def test_content_failures(content_backend, monkeypatch, case, code):
    root, path, record, body, _, _ = content_backend
    if case in ('missing', 'directory', 'fifo'):
        path.unlink()
        if case == 'directory': path.mkdir()
        if case == 'fifo': os.mkfifo(path)
    elif case == 'unreadable':
        real_open = os.open
        def denied(name,*a,**kw):
            if str(name) == str(path): raise PermissionError('private path must not leak')
            return real_open(name,*a,**kw)
        monkeypatch.setattr(os, 'open', denied)
    elif case == 'empty': path.write_bytes(b'')
    elif case == 'corrupt': path.write_bytes(b'\x89PNG\r\n\x1a\ncorrupt')
    elif case == 'truncated': path.write_bytes(body[:-20])
    elif case == 'jpeg':
        out=io.BytesIO(); Image.new('RGB',(8,9)).save(out,format='JPEG'); path.write_bytes(out.getvalue())
    elif case == 'animated':
        out=io.BytesIO(); Image.new('RGB',(8,9),'red').save(out,format='PNG',save_all=True,
            append_images=[Image.new('RGB',(8,9),'blue')]); path.write_bytes(out.getvalue())
    elif case == 'oversize': path.write_bytes(body + b'x' * 2097152)
    else:
        path.write_bytes(png((2049, 1) if case == 'wide' else (1, 2049)))
        monkeypatch.setattr(Image.Image, 'load', lambda *a,**kw: pytest.fail('decoded before dimension guard'))
    result = await read(artifact_id=73, include_content=True)
    error(result, 'artifact_content_'+code)
    assert 'private path' not in json.dumps(result)
    assert record['job_id'] == 'job-73'


async def test_opened_file_race_and_symlink_escape(content_backend, monkeypatch, tmp_path):
    root, path, record, body, _, _ = content_backend
    outside=tmp_path/'private.png'; outside.write_bytes(body)
    real_open=os.open
    def race(name,*a,**kw):
        if str(name) == str(path):
            path.unlink(); path.symlink_to(outside)
        return real_open(name,*a,**kw)
    monkeypatch.setattr(os,'open',race)
    error(await read(artifact_id=73, include_content=True), 'artifact_content_unavailable')
    assert outside.read_bytes() == body


async def test_intermediate_directory_swap_detects_actual_open(content_backend, monkeypatch, tmp_path):
    root, path, record, body, _, _ = content_backend
    outside=tmp_path/'outside'; outside.mkdir(); (outside/path.name).write_bytes(body)
    real_open=os.open
    def race(name,*a,**kw):
        if str(name) == str(path):
            path.parent.rename(root/'old'); (root/'nested').symlink_to(outside, target_is_directory=True)
        return real_open(name,*a,**kw)
    monkeypatch.setattr(os,'open',race)
    result=await read(artifact_id=73, include_content=True)
    error(result,'artifact_content_unavailable')
    assert str(outside) not in json.dumps(result)


async def test_byte_boundary_streaming_and_metadata_compatibility(content_backend, monkeypatch):
    root, path, record, body, requests, response=content_backend
    # Valid ancillary chunk fills exact 2 MiB; bytes must survive unchanged.
    filler=b'x'*(2097152-len(body)-12)
    chunk=b'tEXt'+filler
    padded=body[:-12]+struct.pack('>I',len(filler))+chunk+struct.pack('>I',zlib.crc32(chunk))+body[-12:]
    assert len(padded)==2097152
    path.write_bytes(padded)
    result=await read(artifact_id=73,include_content=True)
    assert result['ok'], result
    assert base64.b64decode(result['data']['content']['base64']) == padded
    # Metadata reads preserve video and legacy paths, and never open them.
    record.update(artifact_type='video', mime_type='video/mp4', gallery_path='/outside/video.mp4')
    def forbidden(*a,**kw): pytest.fail('metadata read opened content')
    monkeypatch.setattr(os,'open',forbidden)
    result=await read(artifact_id=73)
    assert result['ok'] and result['data']['artifact_type']=='video' and 'content' not in result['data']
    record.update(id=900, image_path='legacy.png')
    result=await read(image_id=900)
    assert result['ok'] and result['data']['image_id']==900 and 'content' not in result['data']
    response.update(status=404,body={'detail':{'error':'artifact_not_found','artifact_id':73}})
    result=await read(artifact_id=73,include_content=True)
    assert result['ok'] is False and result['error']['code'] != 'artifact_content_unavailable'


async def test_read_has_one_bounded_request_not_unbounded_or_size_trust(content_backend, monkeypatch):
    root,path,record,body,_,_=content_backend
    path.write_bytes(body+b'x'*2097152)
    record['file_size']=1  # stale metadata must not bypass actual byte limit
    original=os.fdopen
    amounts=[]
    class BoundedStream:
        def __init__(self,*a,**kw): self.stream=original(*a,**kw)
        def __enter__(self): return self
        def __exit__(self,*a): self.stream.close()
        def read(self,amount=-1):
            amounts.append(amount)
            assert amount==2097153
            return self.stream.read(amount)
    monkeypatch.setattr(os,'fdopen',BoundedStream)
    error(await read(artifact_id=73,include_content=True),'artifact_content_too_large')
    assert amounts==[2097153]


async def test_invalid_backend_identity_shape_and_outside_conflicting_local_path(content_backend):
    root,path,record,body,_,response=content_backend
    response['body']=[]
    error(await read(artifact_id=73,include_content=True),'artifact_content_unavailable')
    response['body']=record
    record['local_path']=str(root.parent/'unrelated.png')
    error(await read(artifact_id=73,include_content=True),'artifact_content_unavailable')


async def test_documented_container_mapping_needs_canonical_relative_identity(content_backend):
    root,path,record,body,_,_=content_backend
    record['local_path']='/data/gallery/nested/杯 子.png'
    result=await read(artifact_id=73,include_content=True)
    assert result['ok'] and base64.b64decode(result['data']['content']['base64'])==body
    record['local_path']='/data/gallery/other.png'
    error(await read(artifact_id=73,include_content=True),'artifact_content_unavailable')
