"""p2-03: byte, destination-space, range and ownership outcomes on real files.

The transport yields deterministic chunks; disk observations are controlled.
Everything else (open/stat/hash/link/cleanup) uses the real temporary filesystem.
"""
import hashlib
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from app.config import get_settings, Settings
from app.services.civitai_safe_download import CivitaiFileMetadata, DownloadResponse, safe_download


def metadata(data=b'abcdef', **kw):
    values=dict(download_url='https://civitai.com/api/download/models/7', sha256=hashlib.sha256(data).hexdigest(), size=len(data), scan_status='clean')
    return CivitaiFileMetadata(**(values|kw))


class Transport:
    def __init__(self, body, headers=None, status=200):
        self.calls=0; self.body=body; self.headers=headers or {}; self.status=status
    def get(self, *args, **kw):
        self.calls+=1
        return DownloadResponse(self.status,self.body,self.headers)


@pytest.fixture(autouse=True)
def limits(monkeypatch):
    monkeypatch.setenv('CIVITAI_DOWNLOAD_MAX_BYTES','32')
    monkeypatch.setenv('CIVITAI_DOWNLOAD_FREE_SPACE_FLOOR_BYTES','10')
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_actual_chunk_is_refused_before_the_violating_write(tmp_path):
    target=tmp_path/'bounded.safetensors'; observed=[]
    def chunks():
        yield b'ab'
        observed.append(target.with_name(target.name+'.part').read_bytes())
        yield b'cdefg'  # total 7 > declared 6
        observed.append('advanced-past-violation')
    result=safe_download(metadata(),target,transport=Transport(chunks()))
    assert observed==[b'ab']
    assert result.status=='failed' and not target.exists()
    assert result.bytes==2
    assert result.diagnostics['code']=='civitai_byte_limit_exceeded'


def test_space_floor_is_checked_before_each_write(tmp_path,monkeypatch):
    target=tmp_path/'space.safetensors'; observations=iter([100,100,11]); writes=[]
    monkeypatch.setattr(shutil,'disk_usage',lambda path: SimpleNamespace(free=next(observations)))
    def chunks():
        yield b'ab'
        writes.append(target.with_name(target.name+'.part').read_bytes())
        yield b'cdef'
        writes.append('wrote-without-floor')
    result=safe_download(metadata(),target,transport=Transport(chunks()))
    assert result.status=='failed' and result.bytes==2
    assert result.diagnostics['code']=='civitai_insufficient_space'
    assert writes==[b'ab'] and not target.exists()


@pytest.mark.parametrize('free',[15,None,-1,True])
def test_insufficient_or_unknown_space_refuses_before_body_and_partial(tmp_path,monkeypatch,free):
    target=tmp_path/'absent'/'file'; transport=Transport(b'abcdef')
    monkeypatch.setattr(shutil,'disk_usage',lambda path: SimpleNamespace(free=free))
    result=safe_download(metadata(),target,transport=transport)
    assert result.status=='failed'
    assert transport.calls==0 and not target.parent.exists()
    assert result.diagnostics['code'] in {'civitai_insufficient_space','civitai_space_unavailable'}


def test_racing_final_survives_atomic_publication(tmp_path):
    target=tmp_path/'race.safetensors'
    def chunks():
        yield b'abc'
        target.write_bytes(b'other-writer')
        yield b'def'
    result=safe_download(metadata(),target,transport=Transport(chunks()))
    assert result.status=='failed'
    assert target.read_bytes()==b'other-writer'
    assert result.actual_sha256 is None
    assert result.diagnostics['code']=='civitai_target_exists'


@pytest.mark.parametrize('kind',['regular','symlink','hardlink','directory','oversize'])
def test_unassociated_or_unsafe_part_is_retained_without_request(tmp_path,kind):
    target=tmp_path/'file'; part=tmp_path/'file.part'; foreign=tmp_path/'foreign'; foreign.write_bytes(b'ab')
    if kind=='symlink': part.symlink_to(foreign)
    elif kind=='hardlink': os.link(foreign,part)
    elif kind=='directory': part.mkdir()
    else: part.write_bytes(b'oversize!' if kind=='oversize' else b'ab')
    before=os.lstat(part); transport=Transport(b'abcdef')
    result=safe_download(metadata(),target,transport=transport)
    assert result.status=='failed' and transport.calls==0 and not target.exists()
    assert os.lstat(part)==before and foreign.read_bytes()==b'ab'
    if kind!='directory': assert part.read_bytes()==(b'oversize!' if kind=='oversize' else b'ab')


@pytest.mark.parametrize('value',[0,-1,True,1.2,None,'bad'])
@pytest.mark.parametrize('field',['civitai_download_max_bytes','civitai_download_free_space_floor_bytes'])
def test_invalid_policy_fails_settings_without_coercion(field,value):
    from pydantic import ValidationError
    with pytest.raises(ValidationError): Settings(_env_file=None,**{field:value})


@pytest.mark.parametrize('size',[0,-1,True,1.25,float('nan'),float('inf'),33,'6'])
def test_invalid_or_oversize_metadata_refuses_without_side_effects(tmp_path,size):
    target=tmp_path/'new'/'file'; transport=Transport(b'abcdef')
    result=safe_download(metadata(size=size),target,transport=transport)
    assert result.status=='failed' and transport.calls==0 and not target.parent.exists()


def test_selected_size_is_exact_and_shared_across_both_callers_and_snapshot():
    from app.services.civitai_resource_acquire import choose_file, AcquireError
    from app.services.civitai_resource_install import inspect_civitai_resource
    from app.services.resource_records import provider_snapshot
    file=dict(id=11,name='a.safetensors',hashes={'SHA256':'a'*64},sizeKB=2.75/1024,downloadUrl='https://civitai.com/api/download/models/7',virusScanResult='clean')
    with pytest.raises(AcquireError): choose_file({'files':[file]})
    assert inspect_civitai_resource({'id':7,'modelId':8,'files':[file]})['candidates'][0]['byte_size'] is None
    assert provider_snapshot({'files':[file]},None,file).declared_size_bytes is None


def associated_part(target, data=b'abcdef'):
    """Real interruption leaves the helper's proof; no test invents its inode/hash."""
    proof=[]; association={'provider':'civitai','model_id':'8','version_id':'7','file_id':'11','resource_id':42,'sha256':metadata(data).sha256,'size':len(data)}
    def interrupted():
        yield data[:2]
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        safe_download(metadata(data),target,transport=Transport(interrupted()),association=association,record_partial=proof.append)
    assert target.with_name(target.name+'.part').read_bytes()==data[:2]
    return association,proof[-1]


@pytest.mark.parametrize('status',[200,206])
def test_verified_association_allows_exact_resume_or_owned_restart(tmp_path,status):
    target=tmp_path/'resume'; association,proof=associated_part(target)
    transport=Transport(b'cdef' if status==206 else b'abcdef',{'Content-Range':'bytes 2-5/6'} if status==206 else {},status)
    result=safe_download(metadata(),target,transport=transport,association=association,resume=proof)
    assert result.status=='completed' and result.resume_used==(status==206)
    assert result.bytes==6 and result.actual_sha256==metadata().sha256 and target.read_bytes()==b'abcdef'
    assert not target.with_name(target.name+'.part').exists()


@pytest.mark.parametrize('header',[None,'bad','bytes 1-5/6','bytes 2-5/7','bytes 2-4/6','bytes 2-6/6','bytes 2-5/*'])
def test_bad_resume_coverage_refuses_before_append_and_closes(tmp_path,header):
    target=tmp_path/'resume'; association,proof=associated_part(target); part=tmp_path/'resume.part'; before=part.stat()
    class Body:
        closed=False
        def __iter__(self): raise AssertionError('must not advance invalid range')
        def close(self): self.closed=True
    body=Body(); result=safe_download(metadata(),target,transport=Transport(body,{'Content-Range':header} if header else {},206),association=association,resume=proof)
    assert result.status=='failed' and result.diagnostics['code']=='civitai_invalid_range'
    assert body.closed and part.stat()==before and part.read_bytes()==b'ab' and not target.exists()


@pytest.mark.parametrize('change',['selected_file','resource','prefix','stat'])
def test_resume_proof_cannot_authorize_a_different_file_or_changed_part(tmp_path,change):
    target=tmp_path/'resume'; association,proof=associated_part(target); part=tmp_path/'resume.part'
    if change=='selected_file': association=association|{'file_id':'12'}
    elif change=='resource': association=association|{'resource_id':43}
    elif change=='prefix': proof=proof|{'prefix_sha256':'f'*64}
    else: part.write_bytes(b'zz')
    before=part.stat(); data=part.read_bytes(); transport=Transport(b'cdef',{'Content-Range':'bytes 2-5/6'},206)
    result=safe_download(metadata(),target,transport=transport,association=association,resume=proof)
    assert result.status=='failed' and transport.calls==0
    assert part.stat()==before and part.read_bytes()==data


def test_changed_part_is_neither_written_nor_removed(tmp_path):
    target=tmp_path/'changed'; part=tmp_path/'changed.part'; saved=tmp_path/'owned-prefix'
    def chunks():
        yield b'ab'
        part.rename(saved); part.write_bytes(b'foreign')
        yield b'cdef'
    result=safe_download(metadata(),target,transport=Transport(chunks()))
    assert result.status=='failed' and result.diagnostics['code']=='civitai_file_changed'
    assert part.read_bytes()==b'foreign' and saved.read_bytes()==b'ab' and not target.exists()


def test_deadline_covers_disk_hash_and_final_publication(tmp_path,monkeypatch):
    from app.services.civitai_provider import ProviderOperation
    from app.services import civitai_safe_download as download
    key=tmp_path/'key';key.write_text('synthetic')
    settings=SimpleNamespace(civitai_api_key_file=str(key))
    with ProviderOperation('download',settings=settings) as operation:
        original=download._digest
        def late_hash(*args):
            digest=original(*args)
            operation.deadline=0
            return digest
        monkeypatch.setattr(download,'_digest',late_hash)
        result=safe_download(metadata(),tmp_path/'late',transport=Transport(b'abcdef'),operation=operation)
    assert result.status=='failed' and result.diagnostics['code']=='civitai_timeout'
    assert not (tmp_path/'late').exists()


def test_part_created_after_preflight_is_preserved_without_network_retry(tmp_path):
    target=tmp_path/'race-part';part=tmp_path/'race-part.part'
    class Racing(Transport):
        def get(self,*args,**kw):
            part.write_bytes(b'foreign')
            return super().get(*args,**kw)
    transport=Racing(b'abcdef')
    result=safe_download(metadata(),target,transport=transport)
    assert result.status=='failed' and transport.calls==1
    assert part.read_bytes()==b'foreign' and not target.exists()


def test_configured_environment_supplies_exact_effective_positive_policy(monkeypatch):
    from app.services.civitai_download_policy import DownloadPolicy
    assert DownloadPolicy.from_settings()==DownloadPolicy(32,10)
    monkeypatch.delenv('CIVITAI_DOWNLOAD_MAX_BYTES');monkeypatch.delenv('CIVITAI_DOWNLOAD_FREE_SPACE_FLOOR_BYTES');get_settings.cache_clear()
    assert DownloadPolicy.from_settings()==DownloadPolicy(8589934592,21474836480)
    from app.services.civitai_provider import CivitaiProviderError
    with pytest.raises(CivitaiProviderError) as error:DownloadPolicy.from_settings(SimpleNamespace())
    assert error.value.code=='civitai_download_policy_unavailable'


@pytest.mark.parametrize('kind',['checkpoint','lora'])
def test_production_selection_prefers_safetensors_over_pickle_primary(kind):
    from app.services.civitai_resource_acquire import choose_file
    file={'id':11,'name':'pickle.ckpt','primary':True,'sizeKB':6/1024,'hashes':{'SHA256':metadata().sha256},'virusScanResult':'clean','downloadUrl':metadata().download_url}
    chosen=choose_file({'files':[file,file|{'id':12,'name':'safe.SAFETENSORS','primary':False}]},safetensors_only=True)
    assert chosen['civitai_file_id']==12 and chosen['name']=='safe.SAFETENSORS'


@pytest.mark.parametrize('failure',['short','long','invalid_length'])
def test_range_body_coverage_is_exact_including_retained_prefix(tmp_path,failure):
    target=tmp_path/'resume';association,proof=associated_part(target)
    headers={'Content-Range':'bytes 2-5/6'}
    if failure=='invalid_length':headers['Content-Length']='3'
    result=safe_download(metadata(),target,transport=Transport(b'cde' if failure=='short' else b'cdefg',headers,206),association=association,resume=proof)
    assert result.status=='failed' and result.actual_sha256 is None and not target.exists()
    assert (tmp_path/'resume.part').read_bytes()==(b'abcde' if failure=='short' else b'ab')


def test_resume_proof_also_binds_the_supplied_metadata(tmp_path):
    target=tmp_path/'resume';association,proof=associated_part(target);transport=Transport(b'cdef',{'Content-Range':'bytes 2-5/6'},206)
    result=safe_download(metadata(sha256=hashlib.sha256(b'abxxxx').hexdigest()),target,transport=transport,association=association,resume=proof)
    assert result.status=='failed' and transport.calls==0 and (tmp_path/'resume.part').read_bytes()==b'ab'


def test_failed_space_observation_is_an_actionable_refusal(tmp_path,monkeypatch):
    def broken(_):raise RuntimeError('synthetic observer failure')
    monkeypatch.setattr(shutil,'disk_usage',broken)
    result=safe_download(metadata(),tmp_path/'file',transport=Transport(b'abcdef'))
    assert result.status=='failed' and result.diagnostics['code']=='civitai_space_unavailable'
