"""Canonical row identity/metadata. Deliberate faults are exercised at delivery."""
import hashlib
import json
from pathlib import Path

import pytest
from app.db import database
from app.db.models import DownloadedResource


def row(db, **kw):
    values = dict(resource_name='selected.safetensors', resource_type='lora', provider='civitai',
                  source_url='https://civitai.com/models/10?modelVersionId=21&token=SYNTHETIC',
                  model_id='10', version_id='21', civitai_file_id='32', sha256='a'*64,
                  file_size=99, status='installed')
    values.update(kw)
    result=DownloadedResource(**values); db.add(result); db.commit(); return result


def snapshot(base=' Illustrious ', **kw):
    from app.services.resource_records import provider_snapshot
    version=dict(id=21, modelId=10, baseModel=base, trainedWords=[' a ', 'a', '', 7, 'B'],
                 meta={'steps':24, 'cfgScale':5.5, 'sampler':' Euler ', 'scheduler':'normal',
                       'width':1024,'height':True,'strength':0.7,'mystery':'safe',
                       'url':'https://example.test/x?signature=DROP','token':'DROP'},
                 images=[{'meta':{'steps':88,'height':999}}])
    version.update(kw)
    return provider_snapshot(version, {'allowNoCredit':True}, {'id':32, 'sizeKB':99/1024, 'metadata':{'format':'SafeTensor'}})


@pytest.mark.parametrize('label,expected',[(x,'sdxl') for x in ['SDXL 1.0',' illustrious ','PONY','NoobAI']]+[
    (x,None) for x in [None,{},7,'sdxl','SDXL 1.0 extra','Ponyish','foo Illustrious','anima','urn:air:sdxl','NoobAI.safetensors','']])
def test_exact_phase2_mapping_orm(label,expected):
    from app.services.resource_records import publish_metadata, project_resource
    with database.SessionLocal() as db:
        r=row(db); publish_metadata(r,snapshot(label)); db.commit(); db.expire_all()
        item=project_resource(db.get(DownloadedResource,r.id))
        assert item.resource_id==r.id and item.model_family==expected
        assert item.base_model==(label if isinstance(label,str) else None)
        assert ('no_matching_workflow' in [d.code for d in item.diagnostics]) == (expected is None)


def test_snapshot_types_missing_evidence_and_safe_opaque_roundtrip():
    from app.services.resource_records import publish_metadata, project_resource
    with database.SessionLocal() as db:
        r=row(db); publish_metadata(r,snapshot()); db.commit(); db.expire_all()
        item=project_resource(db.get(DownloadedResource,r.id)); value=item.model_dump()
        assert item.trigger_words==['a','B']
        assert value['recommended_parameters']=={
            'steps':{'value':24,'source_field':'version.meta.steps'},
            'cfg':{'value':5.5,'source_field':'version.meta.cfgScale'},
            'sampler':{'value':'Euler','source_field':'version.meta.sampler'},
            'scheduler':{'value':'normal','source_field':'version.meta.scheduler'},
            'width':{'value':1024,'source_field':'version.meta.width'}}
        assert item.declared_size_bytes==99 and item.measured_size_bytes is None and item.sha256_verified is None
        assert value['license']['missing_fields']==['allowCommercialUse','allowDerivatives','allowDifferentLicense']
        codes={d.code for d in item.diagnostics}; assert {'invalid_trigger_word','invalid_recommendation','license_incomplete'}<=codes
        assert item.metadata_origin=='civitai_provider' and item.metadata_version==1
        text=json.dumps(value); assert 'SYNTHETIC' not in text and 'signature' not in text and 'DROP' not in text
        assert 'source_evidence' not in value
        assert 'mystery' in r.metadata_json and 'format' in r.metadata_json and '999' not in text


def test_publication_identity_idempotence_and_measured_facts(tmp_path):
    from app.services.resource_records import publish_metadata, project_resource, measured_evidence, ResourceIdentityConflict
    path=tmp_path/'selected.safetensors'; path.write_bytes(b'test'); sha=hashlib.sha256(b'test').hexdigest()
    with database.SessionLocal() as db:
        r=row(db,sha256=sha,local_path=str(path),file_size=4)
        snap=snapshot(); evidence=measured_evidence(path,4,sha)
        publish_metadata(r,snap,identity={'civitai_file_id':'32','sha256':sha},measured=evidence); db.commit()
        first=r.metadata_json
        publish_metadata(r,snap,identity={'civitai_file_id':'32','sha256':sha},measured=evidence); db.commit()
        assert r.metadata_json==first and db.query(DownloadedResource).count()==1
        item=project_resource(r); assert item.sha256_verified is True and item.measured_size_bytes==4 and item.path_available is True
        for identity in [{'civitai_file_id':'999'}, {'sha256':'f'*64}, {'model_id':'999'}]:
            with pytest.raises(ResourceIdentityConflict): publish_metadata(r,snap,identity=identity)
            assert r.metadata_json==first and r.civitai_file_id=='32' and r.sha256==sha
        r.sha256='b'*64; assert project_resource(r).sha256_verified is None
        r.sha256=sha; path.write_bytes(b'changed'); assert project_resource(r).sha256_verified is None


def test_legacy_incomplete_or_invalid_never_verified_and_read_does_not_repair():
    from app.services.resource_records import project_resource
    with database.SessionLocal() as db:
        for notes in [None,'broken SECRET','[]',json.dumps({'model_family':'sdxl','file_identity':{'size':99}})]:
            r=row(db,notes=notes); item=project_resource(r)
            assert item.sha256_verified is None and item.metadata_origin in {None,'legacy_notes'}
            assert r.metadata_json is None and r.notes==notes
            assert 'SECRET' not in item.model_dump_json()


@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,'24',[],None])
def test_bad_recommendations_stay_absent(value):
    s=snapshot(meta={'steps':value,'cfgScale':value,'width':value})
    assert s.recommended_parameters=={}


def test_recommendation_conflicts_are_not_applied_and_nonfinite_source_is_diagnosed():
    from app.services.resource_records import provider_snapshot
    s=provider_snapshot({'baseModel':'Pony','trainedWords':[],
                        'meta':{'cfgScale':5,'cfg':6,'strength':0.1,'loraStrength':0.2}},None,
                       {'metadata':{'cfgScale':7,'strength':0.3},'sizeKB':float('inf')})
    assert s.recommended_parameters=={}
    assert s.declared_size_bytes is None
    assert {'conflicting_recommendation','invalid_declared_size'}<={d.code for d in s.diagnostics}


def test_publication_can_fill_missing_identity_but_never_partial_rebind():
    from app.services.resource_records import publish_metadata, ResourceIdentityConflict
    with database.SessionLocal() as db:
        r=row(db,civitai_file_id=None,air=None)
        publish_metadata(r,snapshot(),identity={'civitai_file_id':'32','air':'urn:air:sdxl:lora:civitai:10@21'})
        assert r.civitai_file_id=='32' and r.air=='urn:air:sdxl:lora:civitai:10@21'
        with pytest.raises(ResourceIdentityConflict):
            publish_metadata(r,snapshot(),identity={'model_id':'999','air':'different'})
        assert r.model_id=='10' and r.air=='urn:air:sdxl:lora:civitai:10@21'


def test_legacy_conflicting_metadata_is_explicit_and_invalid_typed_storage_is_readable():
    from app.services.resource_records import project_resource
    with database.SessionLocal() as db:
        r=row(db,notes=json.dumps({'base_model':'Pony','model_family':'anima'}))
        assert 'conflicting_legacy_metadata' in {d.code for d in project_resource(r).diagnostics}
        r.metadata_json='invalid TOKEN_SENTINEL'
        item=project_resource(r)
        assert item.model_family is None and item.sha256_verified is None
        assert 'invalid_metadata' in {d.code for d in item.diagnostics}
        assert 'TOKEN_SENTINEL' not in item.model_dump_json()


def test_invalid_provider_identity_and_license_are_unknown_not_fabricated():
    from app.services.resource_records import provider_snapshot,project_resource,publish_metadata
    with database.SessionLocal() as db:
        r=row(db,model_id='bad',version_id='0',civitai_file_id='-3')
        snap=provider_snapshot({'trainedWords':[]},{'allowNoCredit':'true','allowCommercialUse':[7]}, {})
        publish_metadata(r,snap);db.commit()
        v=project_resource(r)
        assert v.model_id is None and v.version_id is None and v.civitai_file_id is None
        assert 'invalid_provider_identity' in {d.code for d in v.diagnostics}
        assert 'invalid_license_field' in {d.code for d in v.diagnostics}
        assert v.license.values=={} and v.license.missing_fields==['allowNoCredit','allowCommercialUse','allowDerivatives','allowDifferentLicense']
