"""Allowlisted effective-parameter reporting; private environment is never read."""
from __future__ import annotations
import json
import math
import re
from pathlib import Path, PureWindowsPath
from app.services.lora_delivery import DeliveryError, atomic_write, digest, write_json, confined
from app.services.lora_public import failure, public_log_line

_SENSITIVE = re.compile(r'(?:token(?!izer)|password|secret|credential|api.?key|authorization)', re.I)


def _locator(value):
    if not isinstance(value,str): return value
    from urllib.parse import urlsplit
    parsed=urlsplit(value)
    if parsed.scheme in {'http','https'} and (parsed.username or parsed.query):
        return '<redacted credential-bearing locator>'
    if Path(value).is_absolute() or PureWindowsPath(value).is_absolute() or value.startswith('~'):
        return '<redacted private path; see component identity hash>'
    return value


def _safe(value):
    if isinstance(value,dict): return {k:_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_safe(v) for v in value]
    return _locator(value)


def validate_reportable(effective) -> None:
    if effective.caching.latent_cache_to_disk or effective.caching.text_encoder_cache_to_disk:
        raise DeliveryError('run_cache_not_isolatable','this runner writes disk caches beside source images; use memory cache or request a separately approved runner change')
    for arg in (*effective.optimization.optimizer_args, *effective.optimization.lr_scheduler_args):
        key,_,value=arg.partition('=')
        if _SENSITIVE.search(key) or _locator(value) != value:
            raise DeliveryError('unreportable_training_option','optimizer/scheduler arguments must not contain credentials or private path options')


def prepare_parameters(root: Path, *, job, argv, dataset_toml: str, evidence) -> dict:
    effective=job.recipe.effective
    validate_reportable(effective)
    # These model schemas are extra=forbid: this is a field allowlist, never a config/environment dump.
    options={name:getattr(effective,name).model_dump(mode='json') for name in
             ('model','scope','dataset','optimization','caching','execution','server')}
    components={k:{field:getattr(v,field) for field in
                  ('kind','size_bytes','modified_time_ns','sha256','verification_status')}
                for k,v in job.recipe.component_identities.items()}
    for key in components:
        identity=job.recipe.component_identities[key]
        components[key]['requested_locator']=_locator(identity.requested_locator)
        components[key]['resolved_locator']=_locator(identity.resolved_locator)
    # Sanitize known argv path positions plus absolute tokens. Redactions are explicit,
    # not claimed to be the literal command passed to the trainer.
    safe_argv=[_locator(v) for v in argv]
    safe_toml=dataset_toml
    import tomllib
    parsed=tomllib.loads(dataset_toml)
    image_dir=parsed['datasets'][0]['subsets'][0]['image_dir']
    safe_toml=safe_toml.replace(json.dumps(image_dir,ensure_ascii=False),json.dumps('<dataset:'+job.folder+'>',ensure_ascii=False))
    snapshot={
        'schema_version':'lora-actual-parameters/v1', 'job_id':job.job_id,
        'output_name':job.output_name,'resolved_output_name':job.resolved_output_name,
        'output_serial':job.output_serial,'run_locator':job.run_locator,
        'created_utc':job.submitted_at,'started_utc':None,'status':'prepared','trainer_process':'not started',
        'dataset':{'locator':job.folder,'dataset_hash':job.dataset_hash,'profile_hash':job.profile_hash,'version':'hash reference'},
        'effective_options':_safe(options),'step_plan':job.recipe.step_plan.model_dump(mode='json'),
        'components':components,
        'runner':{'sd_scripts_revision':evidence.sd_scripts_revision.value if evidence.sd_scripts_revision and evidence.sd_scripts_revision.status=='verified' else 'unknown',
                  'python_version':evidence.capability.python_version or 'unknown',
                  'torch_version':evidence.capability.torch_version or 'unknown',
                  'accelerate_version':evidence.capability.accelerate_version or 'unknown'},
        'command':{'argv':safe_argv,'redaction_notice':'<redacted ...> values and <dataset:...> are safe references, not literal trainer arguments; exact private command/config remain in run configs and durable internal evidence'},
        'dataset_toml':safe_toml,
        'run_paths':{'artifacts':'artifacts/','config':'configs/dataset.toml','log':'logs/training.log','state':'state/','cache':'cache/'},
        'execution_defaults':{'save_state':False,'max_train_steps':None,'augmentation':'runner defaults; no augmentation flags supplied'},
    }
    write_parameters(root,snapshot)
    return snapshot


def write_parameters(root: Path, snapshot: dict) -> None:
    try:
        confined(root/'training-parameters.json',root)
        manifest=json.loads(confined(root/'manifest.json',root).read_text(encoding='utf-8'))
        if manifest.get('job_id') != snapshot.get('job_id') or manifest.get('run_locator') != snapshot.get('run_locator'):
            raise DeliveryError('output_ownership_mismatch','parameter documents do not belong to this job/run')
        content=json.dumps(snapshot,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
        md=['# Actual training parameters / 實際訓練參數','',
            'Readable names identify the product. Serials count allocations, including failed/cancelled jobs.',
            'Paths marked redacted are safe references, not literal trainer arguments.','']
        for key,value in snapshot.items():
            md.extend(['## '+key.replace('_',' '),'',
                       '```json\n'+json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n```',''])
        markdown='\n'.join(md)
        atomic_write(root/'training-parameters.json',content.encode('utf-8'))
        atomic_write(root/'training-parameters.md',markdown.encode('utf-8'))
        if json.loads((root/'training-parameters.json').read_text(encoding='utf-8')) != snapshot or (root/'training-parameters.md').read_text(encoding='utf-8') != markdown:
            raise ValueError('parameter readback differs')
        manifest.update({k:snapshot[k] for k in ('job_id','output_name','resolved_output_name','output_serial','run_locator','status')})
        manifest['parameter_files']={name:digest(root/name) for name in ('training-parameters.json','training-parameters.md')}
        write_json(root/'manifest.json',manifest)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise DeliveryError('training_parameters_write_failed','unable to safely write and verify actual parameter documents') from exc


def update_phase(root: Path, *, job_id: str, status: str, started_utc: str | None = None, **fields) -> None:
    """Retain documents on every outcome; absent files mean trainer never prepared."""
    path=confined(root/'training-parameters.json',root)
    if not path.exists(): return
    snapshot=json.loads(path.read_text(encoding='utf-8'))
    if snapshot.get('job_id') != job_id:
        raise DeliveryError('output_ownership_mismatch','cannot update another job’s parameter documents')
    snapshot['status']=status
    if started_utc:
        snapshot['started_utc']=started_utc;snapshot['trainer_process']='spawned'
    snapshot.update(fields)
    write_parameters(root,snapshot)


def queued_parameters(root: Path, job) -> None:
    """A cancelled queued run still records known options without claiming launch."""
    options={name:getattr(job.recipe.effective,name).model_dump(mode='json') for name in
             ('model','scope','dataset','optimization','caching','execution','server')}
    write_parameters(root,{
        'schema_version':'lora-actual-parameters/v1','job_id':job.job_id,
        'output_name':job.output_name,'resolved_output_name':job.resolved_output_name,
        'output_serial':job.output_serial,'run_locator':job.run_locator,
        'created_utc':job.submitted_at,'started_utc':None,'status':'queued',
        'trainer_process':'not started','effective_options':_safe(options),
        'dataset':{'locator':job.folder,'dataset_hash':job.dataset_hash,'profile_hash':job.profile_hash},
        'step_plan':job.recipe.step_plan.model_dump(mode='json'),
        'command':{'status':'not prepared; revalidated at launch'},'dataset_toml':None,
        'runner':{'version':'unknown until launch preparation'},
    })


_PUBLIC_PARAMS = frozenset('checkpoint model_family trainer_script sdxl epochs resolution batch_size learning_rate class_tokens keep_tokens num_repeats mixed_precision kohya_mixed_precision network_module network_dim network_alpha anima_qwen3 anima_vae anima_t5_tokenizer_path dataset_hash profile_hash'.split())


# Closed display semantics for legacy free-form optimizer/scheduler arguments.
# This is deliberately independent of input normalization and execution bytes.
_OPTION_NUMBERS = frozenset('weight_decay eps lr d0 growth_rate clip_threshold decay_rate momentum beta1 beta2 num_cycles power factor patience cooldown min_lr threshold'.split())
_OPTION_BOOLEANS = frozenset('decouple relative_step scale_parameter warmup_init amsgrad foreach fused correct_bias safeguard_warmup use_bias_correction'.split())
_OPTION_ENUMS = {'mode': frozenset({'min', 'max'}), 'threshold_mode': frozenset({'rel', 'abs'}), 'anneal_strategy': frozenset({'cos', 'linear'})}
_OPTION_REDACTED = '<redacted unknown or unsafe legacy option>'


def _public_option_args(value):
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        return [_OPTION_REDACTED]
    result = []
    for item in value:
        safe = False
        if isinstance(item, str) and '=' in item:
            key, raw = (part.strip() for part in item.split('=', 1))
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
                raw = raw[1:-1]
            if key in _OPTION_BOOLEANS:
                safe = raw in {'true', 'false', 'True', 'False'}
            elif key in _OPTION_ENUMS:
                safe = raw in _OPTION_ENUMS[key]
            elif key in _OPTION_NUMBERS or key == 'betas':
                parts = raw.split(',') if key == 'betas' else [raw]
                safe = len(parts) == (2 if key == 'betas' else 1)
                for part in parts:
                    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', part.strip()):
                        safe = False
                        break
                    number = float(part)
                    if not math.isfinite(number) or not (0 <= number <= 1 if key == 'betas' else abs(number) <= 1_000_000_000):
                        safe = False
                        break
        result.append(item if safe else _OPTION_REDACTED)
    return result


def _public_evidence(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in {'optimizer_args', 'lr_scheduler_args'}:
                result[key] = _public_option_args(item)
            elif key == 'reason':
                result[key] = '<redacted internal diagnostic>' if item else item
            elif key == 'argv':
                result[key] = ['<redacted internal argv; see training-parameters.json>'] if item is not None else None
            elif key == 'dataset_config_content':
                result[key] = '<redacted internal dataset TOML; see training-parameters.json>' if item is not None else None
            else:
                result[key] = _public_evidence(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_public_evidence(item) for item in value]
    return _locator(value)


def public_job(job: dict) -> dict:
    """All public jobs, including legacy rows; never mutate internal execution evidence."""
    import copy
    result=copy.deepcopy(job)
    for field in ('requested_recipe','effective_recipe','component_identities','capability','execution_evidence'):
        if field in result: result[field]=_public_evidence(result[field])
    if isinstance(result.get('params'), dict):
        result['params'] = {key: _public_evidence(value) for key, value in result['params'].items() if key in _PUBLIC_PARAMS}
    evidence=result.get('execution_evidence')
    if evidence:
        evidence['reason']='safe public projection: private paths are redacted, not literal trainer arguments; config hash identifies the internal unredacted config'
    run = job.get('run_locator')
    name = job.get('resolved_output_name')
    root = 'output/runs/' + run if isinstance(run, str) and run not in {'.', '..'} and not any(c in run for c in '/\\\r\n') else None
    if result.get('output_path'):
        result['output_path'] = root+'/artifacts/'+name+'.safetensors' if root and isinstance(name, str) and not any(c in name for c in '/\\\r\n') else '<redacted private path; legacy run unknown>'
    if result.get('log_path'):
        result['log_path'] = root+'/logs/training.log' if root else '<redacted private path; legacy run unknown>'
    for field in ('registered_lora_name', 'smoke_test_artifact'):
        if result.get(field): result[field] = _locator(result[field])
    if result.get('error_code') or result.get('error_message') or result.get('error_details'):
        detail = result.get('error_details')
        detail = detail if isinstance(detail, dict) else {}
        safe = failure(result.get('error_code'), phase=detail.get('phase', result.get('stage', 'unknown')), details=detail)
        result.update(error_code=safe['code'], error_message=safe['message'], error_details=safe['details'])
    for field, code in (('registration_error', 'lora_registration_failed'),):
        if result.get(field): result[field] = failure(code)['message']
    from app.services.lora_smoke import diagnostic
    if result.get('smoke_test_error') or result.get('smoke_test_error_code'):
        code, message, hint = diagnostic(result.get('smoke_test_error_code') or result.get('smoke_test_error'))
        result.update(smoke_test_error_code=code, smoke_test_error=message, smoke_test_hint=hint)
    return result


def public_last_result(last: dict | None) -> dict | None:
    if last is None: return None
    result = dict(last)
    if result.get('path'):
        projected = public_job({**result, 'output_path': result['path']})
        result['path'] = projected['output_path']
    if result.get('error'):
        detail = result.get('error_details')
        detail = detail if isinstance(detail, dict) else {}
        safe = failure(result.get('error_code') or ('cancelled' if result['error'] == 'cancelled' else None), phase=detail.get('phase', result.get('stage', 'unknown')), details=detail)
        result.update(error=safe['message'], error_code=safe['code'], error_details=safe['details'])
    return result


def public_logs(result: dict) -> dict:
    projected = public_job(result)
    projected['lines'] = [public_log_line(line) for line in result.get('lines', [])]
    return projected
