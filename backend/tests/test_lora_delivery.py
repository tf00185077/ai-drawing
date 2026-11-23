"""AID-12 offline regressions: no services, trainer, GPU or network."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.lora_train import TrainStartRequest
from app.core.resources import list_loras
from app.services import lora_trainer


def test_start_roundtrips_readable_product_name():
    request = TrainStartRequest(folder='subject', output_name='水彩 旅人', expected_dataset_hash='d', expected_profile_hash='p', recipe={})
    assert request.output_name == '水彩 旅人'


def test_start_requires_product_name():
    with pytest.raises(ValidationError):
        TrainStartRequest(folder='subject', expected_dataset_hash='d', expected_profile_hash='p', recipe={})


def test_catalog_keeps_managed_relative_locator(tmp_path):
    root = tmp_path / 'loras'
    managed = root / 'AI-Drawing' / '水彩旅人_002__20261027T030000Z'
    managed.mkdir(parents=True)
    (root / 'legacy.safetensors').write_bytes(b'legacy')
    (managed / '水彩旅人_002.safetensors').write_bytes(b'fixture')
    assert list_loras(SimpleNamespace(comfyui_loras_dir=str(root))) == [
        'AI-Drawing/水彩旅人_002__20261027T030000Z/水彩旅人_002.safetensors', 'legacy.safetensors']


def test_registration_never_overwrites_unknown_target(tmp_path, monkeypatch):
    target = tmp_path / 'loras'
    target.mkdir()
    old = target / 'same.safetensors'
    old.write_bytes(b'preserve me')
    source = tmp_path / 'same.safetensors'
    source.write_bytes(b'new')
    monkeypatch.setattr(lora_trainer, 'get_settings', lambda: SimpleNamespace(comfyui_lora_dir=str(target)))
    with pytest.raises(lora_trainer.TrainerServiceError):
        lora_trainer._register_output_lora(source, 'unknown-job')
    assert old.read_bytes() == b'preserve me'


def _delivery():
    from app.services import lora_delivery
    return lora_delivery


@pytest.mark.parametrize('name', ['', '.', '..', 'a/b', 'a\\b', 'con', 'LPT9.txt', '尾 ', '尾.', 'a:bad', 'a\x01', 'a'*65, '字'*65, '😀'*64, '尾\u3000', '\ud800'])
def test_invalid_product_names(name):
    with pytest.raises(ValueError):
        _delivery().validate_output_name(name)


def test_unicode_name_and_preview_identity():
    d = _delivery()
    assert d.validate_output_name('Cafe\u0301 旅人') == 'Café 旅人'
    assert d.output_config_hash('Café', 'r') == d.output_config_hash('Cafe\u0301', 'r')
    assert d.output_config_hash('one', 'r') != d.output_config_hash('two', 'r')


def test_serials_are_durable_concurrent_and_share_resolved_namespace(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.database import Base
    d = _delivery()
    engine = create_engine('sqlite:///'+str(tmp_path/'jobs.db'), connect_args={'check_same_thread':False, 'timeout':30})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    def allocate(i, name='水彩旅人'):
        with sessions() as db:
            result = d.reserve_name(db, job_id=str(i), requested=name, occupied=set(), created_utc='2026-10-27T03:00:00Z')
            db.commit()
            return result
    allocate('explicit', '水彩旅人_002')
    with ThreadPoolExecutor(max_workers=6) as pool:
        values=list(pool.map(allocate, range(12)))
    assert len({v['resolved_output_name'] for v in values}) == 12
    assert {v['output_serial'] for v in values} == {1, *range(3,14)}
    assert allocate(0) == next(v for v in values if v['job_id']=='0')
    engine.dispose()
    assert allocate('after-reopen')['resolved_output_name'] == '水彩旅人_014'
    assert allocate('case','WATER')['resolved_output_name']=='WATER'
    assert allocate('case2','water')['resolved_output_name']=='water_002'
    assert allocate('nfc','Cafe\u0301')['resolved_output_name']=='Café'
    assert allocate('nfc2','Café')['resolved_output_name']=='Café_002'


def test_exact_final_validation_rejects_corrupt_and_symlink(tmp_path):
    d=_delivery()
    artifacts=tmp_path/'artifacts';artifacts.mkdir()
    final=artifacts/'readable.safetensors';final.write_bytes(b'garbage')
    with pytest.raises(ValueError): d.validate_final(final, artifacts)
    final.unlink();outside=tmp_path/'outside.safetensors';write_lora(outside)
    final.symlink_to(outside)
    with pytest.raises(ValueError): d.validate_final(final, artifacts)
    final.unlink();write_lora(final)
    assert len(d.validate_final(final, artifacts))==64


def write_lora(path):
    import json,struct
    header=json.dumps({'lora_unet_test.lora_down.weight':{'dtype':'F32','shape':[1,1],'data_offsets':[0,4]},'lora_unet_test.lora_up.weight':{'dtype':'F32','shape':[1,1],'data_offsets':[4,8]}}).encode()
    header+=b' '*((-len(header))%8)
    path.write_bytes(struct.pack('<Q',len(header))+header+b'\0'*8)


def test_parameters_match_argv_and_toml_without_private_environment(tmp_path, monkeypatch):
    import json
    from tests.test_lora_training_recipe_persistence import _compiled, _job
    d=_delivery()
    from app.services import lora_parameters
    job=_job(_compiled());job.output_name='水彩旅人';job.resolved_output_name='水彩旅人_002';job.output_serial=2;job.run_locator='水彩旅人_002__20261027T030000Z'
    root=tmp_path/job.run_locator;d.create_run(root,job_id=job.job_id)
    argv=lora_trainer.build_training_argv(job.recipe.effective,launcher_argv=('/private/SECRET_SENTINEL/python','-m','accelerate.commands.launch'),sd_scripts_path=tmp_path/'sd',dataset_config_path=root/'configs/dataset.toml',output_dir=root/'artifacts',output_name=job.resolved_output_name)
    toml=lora_trainer.build_dataset_toml(job.recipe.effective,image_dir=Path('/private/SECRET_SENTINEL/images'))
    from app.schemas.lora_train import EvidenceValue
    evidence=lora_trainer.build_execution_evidence(argv=tuple(argv),dataset_config_content=toml,launcher=EvidenceValue(status='unverified'),capability=job.recipe.capability,sd_scripts_revision=EvidenceValue(status='unavailable'))
    monkeypatch.setenv('API_TOKEN','SECRET_SENTINEL')
    snapshot=lora_parameters.prepare_parameters(root,job=job,argv=argv,dataset_toml=toml,evidence=evidence)
    encoded=(root/'training-parameters.json').read_text();md=(root/'training-parameters.md').read_text()
    assert 'SECRET_SENTINEL' not in encoded+md
    assert json.loads(encoded)==snapshot
    assert snapshot['status']=='prepared' and snapshot['started_utc'] is None
    assert snapshot['effective_options']['optimization']['seed']['value']==42
    assert snapshot['effective_options']['dataset']['batch_size']==1
    assert snapshot['command']['argv'][argv.index('--output_name')+1]=='水彩旅人_002'
    assert 'redacted' in encoded and 'not literal' in md
    manifest=json.loads((root/'manifest.json').read_text())
    assert manifest['parameter_files']['training-parameters.md']==d.digest(root/'training-parameters.md')
    lora_parameters.update_phase(root,job_id=job.job_id,status='failed')
    assert json.loads((root/'training-parameters.json').read_text())['trainer_process']=='not started'


@pytest.fixture
def isolated_worker(tmp_path, monkeypatch):
    import threading
    from contextlib import nullcontext
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db import database
    from app.schemas.lora_train import EvidenceValue
    from tests.test_lora_training_recipe_persistence import _compiled, _job
    from tests.test_lora_training_start_safety import _approved_inspection, _approved_validation
    engine=create_engine('sqlite:///'+str(tmp_path/'jobs.db'),connect_args={'check_same_thread':False})
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database,'engine',engine)
    monkeypatch.setattr(database,'SessionLocal',sessionmaker(bind=engine))
    settings=SimpleNamespace(lora_train_dir=str(tmp_path/'train'),comfyui_lora_dir=str(tmp_path/'l'),comfyui_loras_dir=str(tmp_path/'l'),sd_scripts_path=str(tmp_path/'sd'),sd_scripts_python='fake')
    monkeypatch.setattr(lora_trainer,'get_settings',lambda:settings)
    from app.services import lora_dataset
    monkeypatch.setattr(lora_dataset,'get_settings',lambda:settings)
    job=_job(_compiled());job.output_name='旅人';job.output_config_hash=_delivery().output_config_hash(job.output_name,job.recipe.recipe_hash)
    dataset=Path(settings.lora_train_dir)/job.folder;dataset.mkdir(parents=True)
    inspected=_approved_inspection(job.folder).model_copy(update={'dataset_hash':job.dataset_hash,'profile_hash':job.profile_hash})
    validated=_approved_validation(job.folder).model_copy(update={'dataset_hash':job.dataset_hash})
    monkeypatch.setattr(lora_dataset,'inspect_dataset',lambda _:inspected)
    monkeypatch.setattr(lora_dataset,'validate_dataset',lambda *a,**kw:validated)
    monkeypatch.setattr(lora_dataset,'dataset_lock',lambda *a,**kw:nullcontext())
    monkeypatch.setattr(lora_trainer,'select_accelerate_launcher',lambda _: (('fake-python','-m','accelerate.commands.launch'),EvidenceValue(status='unverified')))
    monkeypatch.setattr(lora_trainer,'collect_sd_scripts_revision',lambda _:EvidenceValue(status='unavailable'))
    monkeypatch.setattr(lora_trainer,"inspect_trainer_capability",lambda _:job.recipe.capability)
    event=threading.Event();monkeypatch.setattr(lora_trainer,'_stop_event',event)
    monkeypatch.setattr(lora_trainer,'_queue',[]);monkeypatch.setattr(lora_trainer,'_running',None)
    callbacks=[];monkeypatch.setattr(lora_trainer,'_on_complete_callbacks',[lambda *args:callbacks.append(args)])
    lora_trainer._create_persistent_job(job)
    root=_delivery().run_path(Path(settings.lora_train_dir),job.run_locator)
    _delivery().create_run(root,job_id=job.job_id)
    job.log_path=str(root/'logs/training.log')
    lora_trainer._update_persistent_job(job.job_id,log_path=job.log_path)
    yield SimpleNamespace(job=job,root=root,event=event,callbacks=callbacks,settings=settings)
    engine.dispose()


def test_fake_worker_prepares_parameters_before_spawn_and_registers_exact_final(isolated_worker, monkeypatch):
    import json,tomllib
    w=isolated_worker;captured=[]
    def spawn(*,argv,sd_scripts_path,run_root):
        captured.append(argv)
        snapshot=json.loads((run_root/'training-parameters.json').read_text())
        config=tomllib.loads((run_root/'configs/dataset.toml').read_text())
        assert snapshot['status']=='prepared'
        assert snapshot['effective_options']['dataset']['batch_size']==config['datasets'][0]['batch_size']
        assert snapshot['effective_options']['optimization']['seed']['value']==int(argv[argv.index('--seed')+1])
        assert snapshot['effective_options']['optimization']['learning_rate']==argv[argv.index('--learning_rate')+1]
        assert Path(argv[argv.index('--dataset_config')+1])==run_root/'configs/dataset.toml'
        assert Path(argv[argv.index('--output_dir')+1])==run_root/'artifacts'
        write_lora(run_root/'artifacts'/(w.job.resolved_output_name+'.safetensors'))
        class Process:
            stdout=iter(['epoch 1/1\n']);returncode=0
            def wait(self): w.event.set()
        return Process()
    monkeypatch.setattr(lora_trainer,'_run_training_subprocess',spawn)
    lora_trainer._queue.append(w.job);lora_trainer._worker_loop()
    result=lora_trainer.get_job_status(w.job.job_id)
    assert captured and result['status']=='completed',result
    assert result['registered_lora_name']==f'AI-Drawing/{w.job.run_locator}/旅人.safetensors'
    assert result['validation_status']=='verified' and result['registration_status']=='registered'
    assert w.callbacks
    assert json.loads((w.root/'training-parameters.json').read_text())['status']=='completed'
    # Same-job registration retry is idempotent; changed bytes are rejected.
    source=w.root/'artifacts/旅人.safetensors'
    assert lora_trainer._register_output_lora(source,w.job.job_id)[0]==result['registered_lora_name']
    source.write_bytes(b'corrupt')
    with pytest.raises(lora_trainer.TrainerServiceError): lora_trainer._register_output_lora(source,w.job.job_id)


def test_parameter_write_failure_starts_zero_trainers(isolated_worker, monkeypatch):
    from app.services import lora_parameters
    w=isolated_worker;called=[]
    def fail(*a,**kw):
        w.event.set();raise OSError('disk unavailable')
    monkeypatch.setattr(lora_parameters,'prepare_parameters',fail)
    monkeypatch.setattr(lora_trainer,'_run_training_subprocess',lambda **kw:called.append(kw))
    lora_trainer._queue.append(w.job);lora_trainer._worker_loop()
    result=lora_trainer.get_job_status(w.job.job_id)
    assert not called and result['error_code']=='training_parameters_write_failed'
    assert not w.callbacks


@pytest.mark.parametrize('mode',['spawn_failed','missing_final','registration_conflict'])
def test_failed_delivery_keeps_documents_and_never_calls_success(isolated_worker,monkeypatch,mode):
    import json
    w=isolated_worker
    def spawn(**kw):
        w.event.set()
        if mode=='spawn_failed': raise OSError('fake launch failure')
        if mode=='missing_final': write_lora(w.root/'artifacts/旅人-epoch-0001.safetensors')
        else:
            write_lora(w.root/'artifacts/旅人.safetensors')
            conflict=Path(w.settings.comfyui_lora_dir)/'AI-Drawing'/w.job.run_locator
            conflict.mkdir(parents=True);(conflict/'旅人.safetensors').write_bytes(b'OLD')
        return SimpleNamespace(stdout=iter([]),returncode=0,wait=lambda:None)
    monkeypatch.setattr(lora_trainer,'_run_training_subprocess',spawn)
    lora_trainer._queue.append(w.job);lora_trainer._worker_loop()
    result=lora_trainer.get_job_status(w.job.job_id)
    assert result['status']=='failed' and not w.callbacks,result
    snapshot=json.loads((w.root/'training-parameters.json').read_text())
    assert snapshot['status'] in {'failed','registration_failed'}
    if mode=='spawn_failed': assert snapshot['started_utc'] is None
    if mode=='missing_final': assert result['error_code']=='output_missing'
    if mode=='registration_conflict':
        assert result['stage']=='registration_failed'
        assert (Path(w.settings.comfyui_lora_dir)/'AI-Drawing'/w.job.run_locator/'旅人.safetensors').read_bytes()==b'OLD'


def test_cancelled_allocation_is_not_reused_and_queued_parameters_survive(isolated_worker):
    from dataclasses import replace
    import json
    w=isolated_worker
    lora_trainer._queue.append(w.job)
    lora_trainer.cancel_job(w.job.job_id)
    other=replace(w.job,job_id='next-job',folder='other-dataset',run_locator=None,resolved_output_name=None)
    lora_trainer._create_persistent_job(other)
    assert other.resolved_output_name=='旅人_002'
    assert w.root.exists()


def test_changed_preview_name_is_rejected_before_allocation(isolated_worker,monkeypatch):
    from app.services import lora_training_decision
    w=isolated_worker
    monkeypatch.setattr(lora_training_decision,'build_recipe_compilation_context',lambda *a,**kw:None)
    monkeypatch.setattr(lora_trainer,'compile_training_recipe',lambda *a,**kw:w.job.recipe)
    with pytest.raises(lora_trainer.TrainerServiceError) as error:
        lora_trainer.enqueue(w.job.folder,output_name='changed name',expected_output_config_hash=w.job.output_config_hash,expected_dataset_hash=w.job.dataset_hash,expected_profile_hash=w.job.profile_hash,recipe={})
    assert error.value.code=='output_config_hash_mismatch'
    assert len(list(w.root.parent.iterdir()))==1


def test_nested_managed_output_cannot_be_discovered_or_used_as_dataset(tmp_path,monkeypatch):
    from app.services import lora_dataset
    output=tmp_path/'output/runs/readable/artifacts';output.mkdir(parents=True)
    (output/'a.png').write_bytes(b'fixture');(output/'a.txt').write_text('sks')
    monkeypatch.setattr(lora_dataset,'get_settings',lambda:SimpleNamespace(lora_train_dir=str(tmp_path)))
    assert lora_dataset.list_datasets()==[]
    with pytest.raises(lora_dataset.DatasetServiceError):lora_dataset.resolve_dataset_dir('output/runs/readable/artifacts')


def test_catalog_reports_conflicting_roots_and_does_not_follow_links(tmp_path):
    from app.core.resources import lora_catalog
    roots=[tmp_path/'one',tmp_path/'two']
    for n,root in enumerate(roots):
        folder=root/'AI-Drawing/run';folder.mkdir(parents=True)
        (folder/'model.safetensors').write_bytes(bytes([n]))
    outside=tmp_path/'outside';outside.mkdir();(outside/'escape.safetensors').write_bytes(b'escape')
    (roots[0]/'AI-Drawing/link').symlink_to(outside,target_is_directory=True)
    result=lora_catalog(SimpleNamespace(comfyui_loras_dir=','.join(map(str,roots))))
    assert not result['loras']
    assert result['lora_conflicts'][0]['code']=='lora_locator_conflict'


def test_temp_legacy_schema_additions_preserve_data(tmp_path,monkeypatch):
    from sqlalchemy import create_engine, text, inspect
    from app.db import database
    from app.db.models import LoraTrainingJob
    engine=create_engine('sqlite:///'+str(tmp_path/'legacy.db'))
    added={'output_name','resolved_output_name','output_serial','run_locator','output_config_hash','validation_status','output_sha256','registration_status'}
    cols=[]
    for c in LoraTrainingJob.__table__.columns:
        if c.name not in added: cols.append(c.name+' '+str(c.type)+(' PRIMARY KEY' if c.primary_key else ''))
    with engine.begin() as db:
        db.execute(text('CREATE TABLE lora_training_jobs ('+', '.join(cols)+')'))
        db.execute(text("INSERT INTO lora_training_jobs (id,job_id,folder,status,stage,progress) VALUES (1,'old-job','old-dataset','completed','completed',1)"))
    monkeypatch.setattr(database,'engine',engine)
    database.init_db()
    database.init_db()
    with engine.connect() as db:
        row=db.execute(text('SELECT job_id,folder,output_name,run_locator FROM lora_training_jobs')).one()
    assert tuple(row)==('old-job','old-dataset',None,None)
    assert added.issubset({c['name'] for c in inspect(engine).get_columns('lora_training_jobs')})
    engine.dispose()


def test_graph_and_mock_smoke_preserve_complete_registered_locator(isolated_worker, monkeypatch):
    from app.core.workflow import apply_params
    from app.schemas.lora_train import LoraSmokeTestRequest
    locator='AI-Drawing/水彩旅人_002__20261027T030000Z/水彩旅人_002.safetensors'
    graph=apply_params({'1':{'class_type':'LoraLoader','inputs':{'lora_name':'old','model':['0',0],'clip':['0',1]}}},lora=locator)
    assert graph['1']['inputs']['lora_name']==locator
    job_id=isolated_worker.job.job_id
    lora_trainer._update_persistent_job(job_id,status='completed',stage='completed',registered_lora_name=locator)
    captured=[]
    monkeypatch.setattr(lora_trainer,'submit_generation',lambda p: captured.append(p) or 'mock-id')
    result=lora_trainer.smoke_test_job(job_id,LoraSmokeTestRequest(execution_target='worker'))
    assert result['generation_job_id']=='mock-id' and captured[0]['lora']==locator
    assert lora_trainer.get_job_status(job_id)['smoke_test_job_id']=='mock-id'


def test_public_result_redacts_private_paths_with_explicit_notice():
    from app.services import lora_parameters
    private={'job_id':'x','run_locator':'Readable__20261027T030000Z','resolved_output_name':'Readable','output_path':'/private/SECRET_SENTINEL/model.safetensors','log_path':'/private/SECRET_SENTINEL/log','params':{'checkpoint':'/private/SECRET_SENTINEL/model'},'execution_evidence':{'argv':['/private/SECRET_SENTINEL/python','--output_name','Readable'],'dataset_config_content':'[[datasets]]\nimage_dir = "/private/SECRET_SENTINEL/data"\n','reason':None}}
    result=lora_parameters.public_job(private)
    import json
    assert 'SECRET_SENTINEL' not in json.dumps(result)
    assert 'redacted' in result['execution_evidence']['reason']
    assert private['output_path'].startswith('/private/')


def test_serial_suffix_does_not_truncate_and_extends_past_999(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.database import Base
    from app.db.models import LoraOutputReservation
    d=_delivery();engine=create_engine('sqlite:///'+str(tmp_path/'db'));Base.metadata.create_all(engine);session=sessionmaker(bind=engine)
    with session() as db:
        d.reserve_name(db,job_id='long1',requested='a'*64,occupied=set(),created_utc='2026-10-27T03:00:00Z');db.commit()
    with session() as db:
        with pytest.raises(d.DeliveryError):d.reserve_name(db,job_id='long2',requested='a'*64,occupied=set(),created_utc='2026-10-27T03:00:01Z')
        db.rollback()
        assert db.get(LoraOutputReservation,'long2') is None
        db.add(LoraOutputReservation(job_id='999',requested_name='Travel',request_key='travel',resolved_name='Travel_999',resolved_key='travel_999',serial=999,run_locator='Travel_999__old'));db.commit()
    with session() as db:
        result=d.reserve_name(db,job_id='1000',requested='Travel',occupied=set(),created_utc='2026-10-27T03:00:02Z');db.commit()
        assert result['resolved_output_name']=='Travel_1000'
    engine.dispose()


@pytest.mark.parametrize('family',['sd15','sdxl','anima'])
def test_family_specific_nondefaults_match_parameter_snapshot(tmp_path,family):
    import json,tomllib
    from tests.test_lora_training_recipe_execution import _compiled
    from tests.test_lora_training_recipe_persistence import _job
    from app.services import lora_parameters
    from app.schemas.lora_train import EvidenceValue
    compiled=_compiled(family,train_text_encoder=False,save_cadence=2)
    # Disk cache is an explicitly unsupported launch configuration; exercise memory cache here.
    caching=compiled.effective.caching.model_copy(update={'cache_to_disk':False,'latent_cache_to_disk':False,'text_encoder_cache_to_disk':False})
    compiled=compiled.model_copy(update={'effective':compiled.effective.model_copy(update={'caching':caching})})
    job=_job(compiled);job.output_name='旅人';job.resolved_output_name='旅人_003';job.output_serial=3;job.run_locator='旅人_003__stamp'
    root=tmp_path/family/job.run_locator;_delivery().create_run(root,job_id=job.job_id)
    toml=lora_trainer.build_dataset_toml(compiled.effective,image_dir=tmp_path/'dataset')
    argv=lora_trainer.build_training_argv(compiled.effective,launcher_argv=('fake-python',),sd_scripts_path=tmp_path/'sd',dataset_config_path=root/'configs/dataset.toml',output_dir=root/'artifacts',output_name=job.resolved_output_name)
    evidence=lora_trainer.build_execution_evidence(argv=tuple(argv),dataset_config_content=toml,launcher=EvidenceValue(status='unverified'),capability=compiled.capability,sd_scripts_revision=EvidenceValue(status='unavailable'))
    snapshot=lora_parameters.prepare_parameters(root,job=job,argv=argv,dataset_toml=toml,evidence=evidence)
    options=snapshot['effective_options']
    assert options['model']['family']==family
    assert options['dataset']['batch_size']==tomllib.loads(toml)['datasets'][0]['batch_size']==2
    for flag,key in [('--seed','seed'),('--max_train_epochs','epochs'),('--gradient_accumulation_steps','gradient_accumulation_steps')]:
        value=options['optimization'][key]
        if key=='seed':value=value['value']
        assert int(argv[argv.index(flag)+1])==value
    assert options['optimization']['optimizer_type']=='Lion'
    assert options['model']['network_dim']==int(argv[argv.index('--network_dim')+1])
    assert json.loads((root/'training-parameters.json').read_text())==snapshot
    if family=='anima': assert '--qwen3' in argv and options['model']['anima']['qwen3']


def test_changed_component_bytes_are_rejected_before_launch(tmp_path):
    from tests.test_lora_training_recipe_persistence import _compiled,_job
    from app.schemas.lora_train import ComponentIdentity
    path=tmp_path/'checkpoint.safetensors';path.write_bytes(b'original')
    job=_job(_compiled())
    identity=ComponentIdentity(kind='checkpoint',resolved_locator=str(path),sha256=_delivery().digest(path),verification_status='verified')
    job.recipe=job.recipe.model_copy(update={'component_identities':{'checkpoint':identity}})
    path.write_bytes(b'changed')
    with pytest.raises(lora_trainer.TrainerServiceError) as error:
        lora_trainer._revalidate_launch_components(job,SimpleNamespace(sd_scripts_python=''))
    assert error.value.code=='training_component_changed'


def test_conflicting_legacy_catalog_names_still_occupy_product_namespace(tmp_path,monkeypatch):
    roots=[tmp_path/'one',tmp_path/'two']
    for i,root in enumerate(roots):
        root.mkdir();(root/'旅人.safetensors').write_bytes(bytes([i]))
    monkeypatch.setattr(lora_trainer,'get_settings',lambda:SimpleNamespace(lora_train_dir=str(tmp_path/'train'),comfyui_loras_dir=','.join(map(str,roots))))
    assert '旅人' in lora_trainer._occupied_output_names()


def test_copy_hash_failure_never_publishes_final(isolated_worker,monkeypatch):
    import shutil
    w=isolated_worker
    source=w.root/'artifacts/旅人.safetensors';write_lora(source)
    monkeypatch.setattr(shutil,'copyfileobj',lambda src,dst:dst.write(b'corrupt copy'))
    with pytest.raises(lora_trainer.TrainerServiceError) as error:lora_trainer._register_output_lora(source,w.job.job_id)
    assert error.value.code=='lora_copy_hash_mismatch'
    assert not (Path(w.settings.comfyui_lora_dir)/'AI-Drawing'/w.job.run_locator/source.name).exists()
    assert _delivery().validate_final(source,w.root/'artifacts')


def test_foreign_run_metadata_is_never_changed_by_failure_disposition(isolated_worker):
    import json
    w=isolated_worker
    manifest=w.root/'manifest.json'
    record=json.loads(manifest.read_text());record['job_id']='foreign-job';manifest.write_text(json.dumps(record))
    params=w.root/'training-parameters.json';params.write_text(json.dumps({'job_id':'foreign-job','run_locator':w.job.run_locator,'status':'completed','output_name':'foreign','resolved_output_name':'foreign','output_serial':7}))
    markdown=w.root/'training-parameters.md';markdown.write_text('PRESERVE FOREIGN METADATA')
    before={p:p.read_bytes() for p in (manifest,params,markdown)}
    lora_trainer._update_persistent_job(w.job.job_id,status='failed',stage='run_preparation_failed')
    assert {p:p.read_bytes() for p in before}==before
