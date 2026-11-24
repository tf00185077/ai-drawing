"""Independent QA expectations for candidate 6f6e1e9; no product code edits."""
import json
from fastapi.testclient import TestClient
from app.main import app
from app.services import lora_trainer, lora_parameters
from tests.test_lora_delivery import isolated_worker
import pytest


def test_aggregate_status_keeps_allocated_names(monkeypatch):
    running={'job_id':'current','folder':'dataset-a','output_name':'水彩 旅人','resolved_output_name':'水彩 旅人_002','output_serial':2,'run_locator':'水彩 旅人_002__20261027T030000Z','output_config_hash':'h','progress':0.5}
    queued=dict(running,job_id='queued',folder='dataset-b',resolved_output_name='水彩 旅人_003',output_serial=3,run_locator='水彩 旅人_003__20261027T030001Z')
    monkeypatch.setattr(lora_trainer,'get_status',lambda:{'status':'running','current_job':running,'queue':[queued],'last_result':None})
    response=TestClient(app).get('/api/lora-train/status')
    assert response.status_code==200
    payload=response.json()
    print('AGGREGATE_OBSERVATION',json.dumps({'current_resolved':payload['current_job']['resolved_output_name'],'queued_resolved':payload['queue'][0]['resolved_output_name'],'current_serial':payload['current_job']['output_serial'],'queued_serial':payload['queue'][0]['output_serial']},ensure_ascii=False))
    assert payload['current_job']['resolved_output_name']==running['resolved_output_name'],payload
    assert payload['queue'][0]['resolved_output_name']==queued['resolved_output_name'],payload
    for key in ('output_name','output_serial','run_locator','output_config_hash'):
        assert payload['current_job'][key]==running[key]
        assert payload['queue'][0][key]==queued[key]


def test_durable_job_http_uses_safe_projection(isolated_worker):
    w=isolated_worker
    # Synthetic privacy marker only; no real secret or file is accessed.
    lora_trainer._update_persistent_job(w.job.job_id,output_path='/private/QA_PRIVATE_SENTINEL/model.safetensors',log_path='/private/QA_PRIVATE_SENTINEL/training.log')
    internal=lora_trainer.get_job_status(w.job.job_id)
    assert 'QA_PRIVATE_SENTINEL' not in json.dumps(lora_parameters.public_job(internal))
    response=TestClient(app).get('/api/lora-train/jobs/'+w.job.job_id)
    assert response.status_code==200
    print('PRIVACY_OBSERVATION',json.dumps({'output_path':response.json()['output_path'],'log_path':response.json()['log_path'],'safe_projection_contains_marker':'QA_PRIVATE_SENTINEL' in json.dumps(lora_parameters.public_job(internal))}))
    assert 'QA_PRIVATE_SENTINEL' not in response.text,response.json()


import pytest
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
from tests.test_lora_delivery import write_lora


def test_http_invalid_names_reject_before_enqueue(monkeypatch):
    calls=[]
    monkeypatch.setattr(lora_trainer,'enqueue',lambda *a,**kw:calls.append((a,kw)))
    client=TestClient(app)
    for name in ['', '..', 'CON', 'LPT9.txt', 'a/b', 'a\\b', '尾 ', '尾.', 'a'*65, '😀'*64]:
        result=client.post('/api/lora-train/start',json={'folder':'fixture','output_name':name,'expected_dataset_hash':'d','expected_profile_hash':'p','recipe':{}})
        assert result.status_code==422,(name,result.status_code)
    assert calls==[]


@pytest.mark.parametrize('family',['sd15','sdxl','anima'])
def test_fake_spawn_family_records_actual_nondefaults(isolated_worker,monkeypatch,family):
    import tomllib
    from tests.test_lora_training_recipe_execution import _compiled
    from tests.test_lora_training_start_safety import _approved_inspection
    from app.services import lora_dataset
    w=isolated_worker
    compiled=_compiled(family,train_text_encoder=False,save_cadence=2)
    caching=compiled.effective.caching.model_copy(update={'cache_to_disk':False,'latent_cache_to_disk':False,'text_encoder_cache_to_disk':False})
    compiled=compiled.model_copy(update={'effective':compiled.effective.model_copy(update={'caching':caching})})
    w.job.recipe=compiled;w.job.model_family=family;w.job.epochs=compiled.effective.optimization.epochs
    inspected=_approved_inspection(w.job.folder)
    inspected=inspected.model_copy(update={'dataset_hash':w.job.dataset_hash,'profile_hash':w.job.profile_hash,'profile':inspected.profile.model_copy(update={'model_family':family})})
    monkeypatch.setattr(lora_dataset,'inspect_dataset',lambda _:inspected)
    lora_trainer._update_persistent_job(w.job.job_id,recipe_json=lora_trainer._recipe_envelope_json(compiled),recipe_hash=compiled.recipe_hash)
    captured=[]
    def spawn(*,argv,sd_scripts_path,run_root):
        snap=json.loads((run_root/'training-parameters.json').read_text(encoding='utf-8'));captured.append(argv)
        md=(run_root/'training-parameters.md').read_text(encoding='utf-8')
        for value in snap.values(): assert json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2) in md
        assert snap['status']=='prepared' and snap['trainer_process']=='not started' and snap['started_utc'] is None
        options=snap['effective_options'];data=tomllib.loads((run_root/'configs/dataset.toml').read_text(encoding='utf-8'))
        assert data['datasets'][0]['batch_size']==options['dataset']['batch_size']==2
        opt=options['optimization']
        for flag,key in [('--max_train_epochs','epochs'),('--learning_rate','learning_rate'),('--gradient_accumulation_steps','gradient_accumulation_steps'),('--optimizer_type','optimizer_type'),('--lr_scheduler','lr_scheduler'),('--mixed_precision','mixed_precision')]:
            assert argv[argv.index(flag)+1]==str(opt[key])
        assert int(argv[argv.index('--seed')+1])==opt['seed']['value']==42
        assert '--cache_latents_to_disk' not in argv and '--cache_text_encoder_outputs_to_disk' not in argv
        assert options['model']['family']==family
        assert argv[argv.index('--network_module')+1]==options['model']['network_module']
        assert Path(argv[argv.index('--output_dir')+1])==run_root/'artifacts'
        if family=='anima':
            assert argv[argv.index('--qwen3')+1]==options['model']['anima']['qwen3']
            assert argv[argv.index('--vae')+1]==options['model']['anima']['vae']
        write_lora(run_root/'artifacts'/(w.job.resolved_output_name+'.safetensors'))
        return SimpleNamespace(stdout=iter([]),returncode=0,wait=lambda:w.event.set())
    monkeypatch.setattr(lora_trainer,'_run_training_subprocess',spawn)
    lora_trainer._queue.append(w.job);lora_trainer._worker_loop()
    result=lora_trainer.get_job_status(w.job.job_id)
    assert len(captured)==1 and result['status']=='completed',result
    assert result['validation_status']=='verified' and result['registration_status']=='registered'
    snapshot=json.loads((w.root/'training-parameters.json').read_text(encoding='utf-8'))
    assert snapshot['status']=='completed' and snapshot['started_utc'] and snapshot['trainer_process']=='spawned'


