"""Y2-Y3: new notes and legacy summaries share complete-value normalization.
Real Settings/provider/registered admission/background/ORM and read-only HTTP.
Only external HTTP and deterministic thread scheduling are substituted.
"""
import json
from pathlib import Path
import pytest
from sqlalchemy import event
from app.db import database
from app.db.models import DownloadedResource
from app.services import resource_records, resource_record_backfill, civitai_provider
from tests.test_resource_record_writers import boundary, acquire_http

SECRET = 'SIGNED_NOTES'
TEXTS = ['https://user:password@example.test/proof?signature='+SECRET+'#fragment']
AIR = 'urn:air:sdxl:lora:civitai:10@21'

def assert_excluded(value):
    # Whole affected values, not merely the first token, must be absent.
    assert SECRET not in json.dumps(value, ensure_ascii=False)


def views(b, rid):
    observed = []
    for phase, url in [('status','/api/civitai/resources/status?acquisition_id='+str(rid)),
        ('status-list','/api/civitai/resources/status'), ('detail','/api/resources/'+str(rid)),
        ('list','/api/resources'), ('ledger','/api/civitai-recipes/local-ledger'),
        ('family','/api/resources?model_family=sdxl&limit=1')]:
        response=b.client.get(url)
        assert response.status_code==200, response.text
        observed.append({'phase':phase,'value':response.json()})
    return observed


@pytest.mark.parametrize('outcome', ['success','refused','exception'])
@pytest.mark.parametrize('field', ['base_model','version_name','model_name','license'])
@pytest.mark.parametrize('text', TEXTS)
def test_new_notes_admission_background_and_all_public_phases(boundary, outcome, field, text):
    b=boundary; b.file['air']=AIR
    if field=='base_model': b.version['baseModel']=text
    elif field=='version_name': b.version['name']=text
    elif field=='model_name': b.model['name']=text
    else: b.model['allowCommercialUse']=['None',text]
    admitted=acquire_http(b); assert admitted.status_code==202, admitted.text
    rid=admitted.json()['resource']['acquisition_id']
    phases=[{'phase':'admission','value':admitted.json()}]
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        phases += [{'phase':'admitted notes','value':json.loads(row.notes)},
                   {'phase':'admitted metadata','value':json.loads(row.metadata_json)}]
        assert row.air==AIR and row.sha256==b.sha
    phases += views(b,rid)
    assert len(b.pending)==1
    if outcome=='refused': b.failure[0]=True
    if outcome=='exception': (b.tmp/'synthetic-key').write_text('')
    b.pending.pop()()
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        phases += [{'phase':'completed notes','value':json.loads(row.notes)},
                   {'phase':'completed metadata','value':json.loads(row.metadata_json)}]
        original_notes=row.notes
        assert row.air==AIR and row.sha256==b.sha
        record=resource_records.project_resource(row)
        assert record.sha256_verified is (True if outcome=='success' else None)
    phases += views(b,rid)
    print('NEW_NOTES_PHASES_JSON='+json.dumps(phases))
    # Typed metadata and DTOs must stay safe independently of note persistence.
    for phase in phases:
        if 'notes' not in phase['phase']: assert_excluded(phase)
    for phase in phases: assert_excluded(phase)
    notes=next(p['value'] for p in phases if p['phase']=='admitted notes')
    assert notes['expected_size_bytes']==len(b.body)
    assert notes['license']['allowCommercialUse'][0]=='None'
    if field!='base_model': assert notes['base_model']=='Illustrious'
    status=phases[-6]['value']['resources'][0]
    assert status['status']==('installed' if outcome=='success' else 'failed')
    if outcome=='success': assert status['error'] is None
    else: assert status['error']['code'] and status['error']['message'] and status['error']['hint']
    # A retry retains the entire first operation's note body and same identity.
    b.failure[0]=False; (b.tmp/'synthetic-key').write_text('resource-fixture-key')
    again=acquire_http(b); assert again.json()['resource']['acquisition_id']==rid
    if b.pending: b.pending.pop()()
    assert_excluded(again.json())
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        assert db.query(DownloadedResource).count()==1 and row.notes==original_notes
        assert row.air==AIR and row.sha256==b.sha
        assert resource_records.project_resource(row).sha256_verified is True
    for phase in views(b,rid): assert_excluded(phase)


@pytest.mark.parametrize('state',['installed','downloading','failed'])
@pytest.mark.parametrize('field',['base_model','model_family','license','error'])
@pytest.mark.parametrize('text',TEXTS)
def test_old_notes_public_summary_readonly_exact_storage(boundary,monkeypatch,state,field,text):
    b=boundary
    notes={'base_model':'Illustrious','model_family':'illustrious',
           'license':{'allowCommercialUse':['None']}, 'expected_size_bytes':len(b.body),
           'error':{'code':'historical','message':'old','hint':'Inspect this ID.'}}
    notes[field]={'description':text,'allowCommercialUse':['None']} if field=='license' else text
    raw='  '+json.dumps(notes,ensure_ascii=False)+' \n'
    path=b.tmp/'old.safetensors'; path.write_bytes(b.body)
    Path(str(path)+'.part').write_bytes(b.body[:5])
    snap=resource_records.provider_snapshot({'baseModel':'Illustrious','trainedWords':['chosen']},None,{}).model_dump_json()
    with database.SessionLocal() as db:
        row=DownloadedResource(resource_name='selected.safetensors',resource_type='lora',provider='civitai',
            source_url='unknown',local_path=str(path),storage_root='loras',status=state,
            model_id='10',version_id='21',civitai_file_id='32',air=AIR,sha256=b.sha,
            file_size=len(b.body),notes=raw,metadata_json=snap)
        db.add(row); db.commit(); rid=row.id
        original={c.name:getattr(row,c.name) for c in row.__table__.columns}
    def deny(*args,**kwargs): raise AssertionError('unexpected old-summary side effect')
    monkeypatch.setattr(resource_records,'publish_metadata',deny)
    monkeypatch.setattr(resource_record_backfill,'backfill_metadata',deny)
    monkeypatch.setattr(civitai_provider,'ProviderOperation',deny)
    original_open=Path.open
    def guarded(p,*a,**kw):
        if p==path: return deny()
        return original_open(p,*a,**kw)
    monkeypatch.setattr(Path,'open',guarded)
    def readonly(conn,cursor,sql,*args): assert sql.split()[0].upper() in {'SELECT','PRAGMA'},sql
    event.listen(database.engine,'before_cursor_execute',readonly)
    try:
        phases=views(b,rid)
        print('OLD_NOTES_PHASES_JSON='+json.dumps(phases))
        for phase in phases: assert_excluded(phase)
        summary=phases[0]['value']['resources'][0]
        assert summary['acquisition_id']==rid and summary['sha256']==b.sha and summary['status']==state
        if state=='downloading':
            assert summary['progress'] is None and summary['job_tracking']=='legacy_untracked'
        if field!='license': assert summary['license']['allowCommercialUse']==['None']
    finally:
        event.remove(database.engine,'before_cursor_execute',readonly)
        with database.SessionLocal() as db:
            row=db.get(DownloadedResource,rid)
            assert {c.name:getattr(row,c.name) for c in row.__table__.columns}==original
        print('OLD_NOTES_STORAGE_EXACT=true')

@pytest.mark.parametrize('state',['installed','downloading','failed'])
@pytest.mark.parametrize('outcome',['success','refused','exception'])
@pytest.mark.parametrize('text',TEXTS)
def test_retained_adverse_notes_acquisition_reuse_and_retry_exact(boundary,state,outcome,text):
    b=boundary;b.file['air']=AIR
    rid=acquire_http(b).json()['resource']['acquisition_id'];b.pending.pop()()
    raw='  '+json.dumps({'base_model':text,'license':{'allowCommercialUse':['None',text]},
        'error':{'code':'old','message':text,'hint':'Inspect the same ID.'}},ensure_ascii=False)+' \n'
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid);row.status=state;row.notes=raw;db.commit()
        before_hash=row.sha256;before_air=row.air
        before_verification=json.loads(row.metadata_json)['verification']
    admitted=acquire_http(b)
    if state=='downloading':
        assert admitted.status_code==409,admitted.text
        assert admitted.json()['detail']['code']=='download_legacy_untracked'
        assert not b.pending
        with database.SessionLocal() as db:
            row=db.get(DownloadedResource,rid)
            assert row.notes==raw and row.status==state and row.sha256==before_hash and row.air==before_air
            assert json.loads(row.metadata_json)['verification']==before_verification
        return
    assert admitted.status_code==202,admitted.text
    assert admitted.json()['resource']['acquisition_id']==rid
    assert len(b.pending)==(1 if state=='failed' else 0)
    phases=[{'phase':'retained admission','value':admitted.json()}]
    if b.pending:
        if outcome=='refused':b.failure[0]=True
        if outcome=='exception':(b.tmp/'synthetic-key').write_text('')
        b.pending.pop()()
    phases += views(b,rid)
    print('RETAINED_NOTES_PHASES_JSON='+json.dumps(phases))
    for phase in phases:assert_excluded(phase)
    summary=phases[1]['value']['resources'][0]
    # Exact retained finals are now explicitly rehashed/adopted without a body request.
    expected=state if state!='failed' else 'installed' if outcome!='exception' else 'failed'
    assert summary['status']==expected
    if state=='failed':
        if outcome!='exception':assert summary['error'] is None
        else:assert summary['error']['code'] and summary['error']['message'] and summary['error']['hint']
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        assert db.query(DownloadedResource).count()==1 and row.notes==raw
        assert row.sha256==before_hash and row.air==before_air and row.id==rid
        verification=json.loads(row.metadata_json)['verification']
        assert verification['sha256']==before_verification['sha256']==b.sha
        assert verification['size_bytes']==before_verification['size_bytes']==len(b.body)
        assert verification['method']==before_verification['method']
        if state=='failed' and outcome=='success':
            stat=Path(row.local_path).stat()
            assert (verification['inode'],verification['mtime_ns'])==(stat.st_ino,stat.st_mtime_ns)
            assert resource_records.project_resource(row).sha256_verified is True
        else:assert verification==before_verification

@pytest.mark.timeout(3)
@pytest.mark.parametrize('quote',['"',"'"])
@pytest.mark.parametrize('representation',['literal','serialized','escaped'])
def test_long_new_notes_and_summary_keep_full_safe_content(boundary,quote,representation):
    b=boundary
    raw=('\\'+quote+'ordinary description ')*4000+'\\'
    assert len(raw)==92001
    encoded=json.dumps(raw)
    text=raw if representation=='literal' else encoded if representation=='serialized' else encoded[1:-1]
    b.version['baseModel']=text
    admitted=acquire_http(b);assert admitted.status_code==202,admitted.text
    rid=admitted.json()['resource']['acquisition_id'];b.pending.pop()()
    with database.SessionLocal() as db:
        row=db.get(DownloadedResource,rid)
        assert json.loads(row.notes)['base_model']==text
        assert json.loads(row.metadata_json)['base_model']==resource_records.public_name(text)
    assert b.client.get('/api/civitai/resources/status',params={'acquisition_id':rid}).json()['resources'][0]['base_model']==text

@pytest.mark.parametrize('field',['model_type','scan_status','filename'])
@pytest.mark.parametrize('text',TEXTS)
def test_acquisition_refusal_diagnostics_exclude_complete_source_values(boundary,field,text):
    b=boundary
    if field=='model_type':b.model['type']=text
    elif field=='scan_status':b.file['virusScanResult']=text
    else:b.file['name']=text
    response=acquire_http(b)
    assert response.status_code==422,response.text
    detail=response.json()['detail']
    assert detail['code'] in {'unsupported_model_type','virus_scan_not_clean','unsafe_filename'}
    assert detail['message']
    assert_excluded(response.json())
    assert not b.pending
    with database.SessionLocal() as db:assert db.query(DownloadedResource).count()==0

@pytest.mark.parametrize('text',TEXTS)
def test_source_derived_package_warnings_use_complete_policy(boundary,monkeypatch,text):
    from app.config import get_settings
    b=boundary;b.model['type']='Checkpoint';b.version['baseModel']='Anima'
    b.version['files'][0]['name']=text+'.txt'
    monkeypatch.setenv('COMFYUI_DIFFUSION_MODELS_DIR',str(b.tmp/'diffusion'))
    get_settings.cache_clear()
    admitted=acquire_http(b);assert admitted.status_code==202,admitted.text
    assert admitted.json()['warnings']
    assert_excluded(admitted.json())
    rid=admitted.json()['resource']['acquisition_id']
    b.pending.pop()()
    for phase in views(b,rid):assert_excluded(phase)

@pytest.mark.parametrize('text',TEXTS)
def test_selected_provider_legacy_license_snapshot_contract(boundary,text):
    # This retained adapter is independently safe even though persistence and
    # public DTO normalization now also protect its downstream consumers.
    from app.services.civitai_resource_acquire import resolve_version_metadata,license_snapshot
    b=boundary;b.model['allowCommercialUse']=['None',text]
    resolved=resolve_version_metadata('https://civitai.com/models/10?modelVersionId=21')
    snapshot,warnings=license_snapshot(resolved['model'])
    assert snapshot['allowCommercialUse'][0]=='None'
    assert snapshot['license_verified'] is True and warnings==[]
    assert_excluded(snapshot)
    assert b.seen and all(auth=='Bearer resource-fixture-key' for _,auth in b.seen)
