"""Public LoRA client projection, also safe against older Backend result shapes.

No Backend imports: MCP has an independent Python environment and deployment.
"""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit, quote


ERROR_CODES = frozenset('admission_uncertain dataset_not_found invalid_dataset_folder dataset_locked dataset_hash_mismatch profile_hash_mismatch dataset_validation_failed dataset_profile_invalid model_family_mismatch missing_caption empty_caption trigger_token_missing backup_not_found ai_cleanup_not_configured recipe_missing recipe_validation_failed recipe_hash_mismatch recipe_field_conflict recipe_context_unavailable server_recipe_policy_invalid unsupported_network_module unsupported_model_family unsupported_mixed_precision unsupported_runtime_precision invalid_output_name output_config_hash_mismatch unreportable_training_option run_cache_not_isolatable legacy_output_unknown output_allocation_conflict output_path_too_long unsafe_run_path output_ownership_mismatch sd_scripts_path_missing sd_scripts_path_not_directory train_script_missing checkpoint_not_found training_component_changed trainer_capability_changed training_parameters_write_failed run_preparation_failed duplicate_folder output_missing invalid_lora_output output_hash_changed lora_registration_not_configured lora_registration_conflict lora_copy_hash_mismatch lora_registration_failed job_not_found job_not_cancellable job_cancel_failed log_not_found log_read_failed smoke_test_precondition_failed smoke_test_submit_failed generation_queue_full completion_callback_failed unexpected_error kohya_failed cancelled legacy_training_fields_removed request_validation_failed recipe_required unsupported_recipe_schema_version'.split())
_PARAMS = frozenset('checkpoint model_family trainer_script sdxl epochs resolution batch_size learning_rate class_tokens keep_tokens num_repeats mixed_precision kohya_mixed_precision network_module network_dim network_alpha anima_qwen3 anima_vae anima_t5_tokenizer_path dataset_hash profile_hash'.split())
_PHASES = frozenset('request queued preflight prepared training registering registration_failed completed failed cancelled unknown'.split())
_EVENTS = frozenset('queued dequeued started progress cancelled cancellation_requested registered completed failed callback_failed cleanup_failed'.split())


def locator(value):
    if not isinstance(value, str): return value
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute() or value.startswith('~'):
        return '<redacted private path>'
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {'http', 'https'} and (parsed.username or parsed.query):
            return '<redacted credential-bearing locator>'
    except ValueError:
        return '<redacted invalid locator>'
    return value


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


def evidence(value):
    if isinstance(value, dict):
        return {key: _public_option_args(item) if key in {'optimizer_args', 'lr_scheduler_args'} else
                '<redacted internal diagnostic>' if key == 'reason' and item else
                ['<redacted internal argv; see training-parameters.json>'] if key == 'argv' and item is not None else
                '<redacted internal dataset TOML; see training-parameters.json>' if key == 'dataset_config_content' and item is not None else evidence(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [evidence(item) for item in value]
    return locator(value)


def status(payload):
    result = copy.deepcopy(payload)
    for key in ('requested_recipe', 'effective_recipe', 'component_identities', 'capability', 'execution_evidence'):
        if key in result: result[key] = evidence(result[key])
    if isinstance(result.get('params'), dict):
        result['params'] = {key: evidence(item) for key, item in result['params'].items() if key in _PARAMS}
    for key in ('output_path', 'log_path', 'registered_lora_name'):
        if result.get(key): result[key] = locator(result[key])
    if result.get('error_code') or result.get('error_message') or result.get('error_details'):
        code = result.get('error_code')
        code = code if isinstance(code, str) and code in ERROR_CODES else 'unexpected_error'
        details = result.get('error_details')
        phase = details.get('phase') if isinstance(details, dict) else result.get('stage')
        hint = 'check the safe failure code and job state; reconcile before retrying'
        result.update(error_code=code, error_message=f'Backend reported a LoRA job failure ({code})', error_details={
            'classification': 'backend_job_failure', 'phase': phase if isinstance(phase, str) and phase in _PHASES else 'unknown', 'hint': hint,
        })
    for key in ('registration_error', 'smoke_test_error'):
        if result.get(key): result[key] = 'Backend reported a LoRA operation failure; check the safe job failure code'
    return smoke(result, prefix='smoke_test_')


_SMOKE_CODES = frozenset('smoke_generation_failed smoke_generation_cancelled smoke_job_missing smoke_job_unknown smoke_artifact_unavailable smoke_submission_unknown generation_queue_full'.split())
_SMOKE_STATES = frozenset('submitted submitting queued running completed failed cancelled unknown artifact_unavailable submission_unknown'.split())


def smoke(payload, *, prefix=''):
    """Closed smoke projection for current and independently deployed older Backends."""
    result = copy.deepcopy(payload)
    state = result.get('smoke_test_status')
    if state is not None and (not isinstance(state, str) or state not in _SMOKE_STATES):
        result['smoke_test_status'] = 'unknown'
    path = result.get(prefix+'artifact')
    if path is not None:
        safe = (isinstance(path,str) and bool(path) and not PurePosixPath(path).is_absolute()
                and not PureWindowsPath(path).drive and not any(c in path for c in '\\:%?#\r\n\x00')
                and all(part not in {'','.','..'} for part in path.split('/')))
        result[prefix+'artifact'] = path if safe else None
        result[prefix+'artifact_url'] = '/gallery/'+quote(path,safe='/') if safe else None
    elif prefix+'artifact_url' in result:
        result[prefix+'artifact_url'] = None
    for key in ('artifact_id','image_id'):
        if prefix+key in result:
            value=result[prefix+key]
            result[prefix+key] = value if type(value) is int and value>0 else None
    if result.get(prefix+'error') or result.get(prefix+'error_code'):
        code=result.get(prefix+'error_code')
        code=code if isinstance(code,str) and code in _SMOKE_CODES else 'smoke_submission_unknown'
        hint=('Restore the Gallery image for the recorded job and refresh status.' if code=='smoke_artifact_unavailable' else
              'Queue rejected this submission; an explicit request may retry when capacity is available.' if code=='generation_queue_full' else
              'Reconcile the recorded generation job and Backend submission evidence; automatic resubmission is disabled.')
        result.update({prefix+'error_code':code, prefix+'error':f'Backend smoke diagnostic ({code})', prefix+'hint':hint})
    elif prefix+'hint' in result:
        result[prefix+'hint'] = None
    return result


def log_line(line):
    prefix = '[lora-event] '
    if isinstance(line, str) and line.startswith(prefix):
        try:
            value = json.loads(line[len(prefix):])
            if isinstance(value, dict) and value.get('event') in _EVENTS:
                safe = {'event': value['event']}
                if value.get('code') in ERROR_CODES: safe['code'] = value['code']
                if value['event'] == 'progress':
                    for key in ('progress', 'epoch', 'total_epochs'):
                        item = value.get(key)
                        if isinstance(item, (float, int)) and math.isfinite(item) and 0 <= item <= 1_000_000_000: safe[key] = item
                return prefix + json.dumps(safe, sort_keys=True)
        except (TypeError, ValueError):
            pass
    return '<redacted unstructured trainer/legacy log line>'


def logs(payload):
    result = status(payload)
    result['lines'] = [log_line(line) for line in payload.get('lines', [])]
    return result
