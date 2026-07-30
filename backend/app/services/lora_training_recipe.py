"""Canonical LoRA training recipe parsing and compilation."""
from __future__ import annotations

import difflib
import hashlib
import json
import math
import re
import secrets
import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import ValidationError

from app.schemas.lora_train import RequestedTrainingRecipeV1
from app.schemas.lora_train import (
    ComponentIdentity,
    EffectiveAnimaRecipe,
    EffectiveCachingRecipe,
    EffectiveDatasetRecipe,
    EffectiveExecutionRecipe,
    EffectiveModelRecipe,
    EffectiveOptimizationRecipe,
    EffectiveScopeRecipe,
    EffectiveServerRecipe,
    EffectiveTrainingRecipeV1,
    EffectiveWarmup,
    ExecutionEvidence,
    RecipeCompilationContext,
    RecipeCompilationResult,
    RecipeFieldSource,
    TrainingStepPlan,
)


PolicySource = Literal["preflight_policy", "server_policy"]


class RecipeError(ValueError):
    """Repair-guided, redacted recipe contract error."""

    def __init__(
        self,
        code: str,
        message: str,
        hint: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.details = details or {}


@dataclass(frozen=True)
class NormalizedRecipeInput:
    """Canonical requested recipe plus the leaves explicitly supplied by a caller."""

    requested: RequestedTrainingRecipeV1
    provided_fields: frozenset[str]
    scalar_fields: frozenset[str]


@dataclass(frozen=True)
class _AliasRule:
    path: str
    form: str = "value"


@dataclass(frozen=True)
class _SeedIntent:
    mode: Literal["fixed", "random"]
    value: int | None
    source: Literal["caller", "preflight_policy", "server_policy"]


class _InvalidValue(ValueError):
    pass


_ROOT_CONTAINERS = {
    "model": "model",
    "scope": "scope",
    "dataset": "dataset",
    "optimization": "optimization",
    "caching": "caching",
    "execution": "execution",
}

_NESTED_CONTAINERS = {
    "model": {"anima": "model.anima"},
}


def _rules(*entries: tuple[str, str] | tuple[str, str, str]) -> dict[str, _AliasRule]:
    result: dict[str, _AliasRule] = {}
    for entry in entries:
        alias, path, *form = entry
        result[alias] = _AliasRule(path=path, form=form[0] if form else "value")
    return result


_ALIASES: dict[str, dict[str, _AliasRule]] = {
    "": _rules(
        ("schema_version", "schema_version"),
        ("schemaVersion", "schema_version"),
        ("version", "schema_version"),
        ("expected_recipe_hash", "expected_recipe_hash"),
        ("expectedRecipeHash", "expected_recipe_hash"),
        ("family", "model.family"),
        ("model_family", "model.family"),
        ("modelFamily", "model.family"),
        ("checkpoint", "model.checkpoint"),
        ("allow_unverified_checkpoint", "model.allow_unverified_checkpoint"),
        ("allowUnverifiedCheckpoint", "model.allow_unverified_checkpoint"),
        ("network_module", "model.network_module"),
        ("networkModule", "model.network_module"),
        ("network_dim", "model.network_dim"),
        ("networkDim", "model.network_dim"),
        ("network_alpha", "model.network_alpha"),
        ("networkAlpha", "model.network_alpha"),
        ("qwen3", "model.anima.qwen3"),
        ("anima_qwen3", "model.anima.qwen3"),
        ("animaQwen3", "model.anima.qwen3"),
        ("vae", "model.anima.vae"),
        ("anima_vae", "model.anima.vae"),
        ("animaVae", "model.anima.vae"),
        ("t5_tokenizer_path", "model.anima.t5_tokenizer_path"),
        ("anima_t5_tokenizer_path", "model.anima.t5_tokenizer_path"),
        ("animaT5TokenizerPath", "model.anima.t5_tokenizer_path"),
        ("train_text_encoder", "scope.train_text_encoder"),
        ("trainTextEncoder", "scope.train_text_encoder"),
        ("trainable_scope", "scope.train_text_encoder", "scope"),
        ("trainableScope", "scope.train_text_encoder", "scope"),
        ("trigger_token", "dataset.trigger_token"),
        ("triggerToken", "dataset.trigger_token"),
        ("class_tokens", "dataset.trigger_token"),
        ("classTokens", "dataset.trigger_token"),
        ("instance_token", "dataset.trigger_token"),
        ("instanceToken", "dataset.trigger_token"),
        ("resolution", "dataset.resolution"),
        ("batch", "dataset.batch_size"),
        ("batchSize", "dataset.batch_size"),
        ("batch_size", "dataset.batch_size"),
        ("keep_tokens", "dataset.keep_tokens"),
        ("keepTokens", "dataset.keep_tokens"),
        ("shuffle_caption", "dataset.shuffle_caption"),
        ("shuffleCaption", "dataset.shuffle_caption"),
        ("num_repeats", "dataset.num_repeats"),
        ("numRepeats", "dataset.num_repeats"),
        ("enable_bucket", "dataset.enable_bucket"),
        ("enableBucket", "dataset.enable_bucket"),
        ("bucket_no_upscale", "dataset.bucket_no_upscale"),
        ("bucketNoUpscale", "dataset.bucket_no_upscale"),
        ("min_bucket_reso", "dataset.min_bucket_reso"),
        ("minBucketReso", "dataset.min_bucket_reso"),
        ("max_bucket_reso", "dataset.max_bucket_reso"),
        ("maxBucketReso", "dataset.max_bucket_reso"),
        ("bucket_reso_steps", "dataset.bucket_reso_steps"),
        ("bucketResoSteps", "dataset.bucket_reso_steps"),
        ("epochs", "optimization.epochs"),
        ("learning_rate", "optimization.learning_rate"),
        ("learningRate", "optimization.learning_rate"),
        ("denoiser_learning_rate", "optimization.denoiser_learning_rate"),
        ("denoiserLearningRate", "optimization.denoiser_learning_rate"),
        ("unet_lr", "optimization.denoiser_learning_rate"),
        ("dit_lr", "optimization.denoiser_learning_rate"),
        ("text_encoder_learning_rates", "optimization.text_encoder_learning_rates"),
        ("textEncoderLearningRates", "optimization.text_encoder_learning_rates"),
        ("text_encoder_lr", "optimization.text_encoder_learning_rates"),
        ("textEncoderLr", "optimization.text_encoder_learning_rates"),
        ("gradient_accumulation_steps", "optimization.gradient_accumulation_steps"),
        ("gradient_accumulation", "optimization.gradient_accumulation_steps"),
        ("gradientAccumulationSteps", "optimization.gradient_accumulation_steps"),
        ("gradientAccumulation", "optimization.gradient_accumulation_steps"),
        ("optimizer_type", "optimization.optimizer_type"),
        ("optimizerType", "optimization.optimizer_type"),
        ("optimizer", "optimization.optimizer_type"),
        ("optimizer_args", "optimization.optimizer_args"),
        ("optimizerArgs", "optimization.optimizer_args"),
        ("lr_scheduler", "optimization.lr_scheduler"),
        ("lrScheduler", "optimization.lr_scheduler"),
        ("scheduler", "optimization.lr_scheduler"),
        ("lr_scheduler_args", "optimization.lr_scheduler_args"),
        ("lrSchedulerArgs", "optimization.lr_scheduler_args"),
        ("scheduler_args", "optimization.lr_scheduler_args"),
        ("schedulerArgs", "optimization.lr_scheduler_args"),
        ("warmup", "optimization.warmup"),
        ("lr_warmup_steps", "optimization.warmup", "warmup_steps"),
        ("lrWarmupSteps", "optimization.warmup", "warmup_steps"),
        ("warmup_ratio", "optimization.warmup", "warmup_ratio"),
        ("warmupRatio", "optimization.warmup", "warmup_ratio"),
        ("seed", "optimization.seed"),
        ("mixed_precision", "optimization.mixed_precision"),
        ("mixedPrecision", "optimization.mixed_precision"),
        ("precision", "optimization.mixed_precision"),
        ("cache_latents", "caching.cache_latents"),
        ("cacheLatents", "caching.cache_latents"),
        (
            "cache_text_encoder_outputs",
            "caching.cache_text_encoder_outputs",
        ),
        ("cacheTextEncoderOutputs", "caching.cache_text_encoder_outputs"),
        ("cache_to_disk", "caching.cache_to_disk"),
        ("cacheToDisk", "caching.cache_to_disk"),
        ("max_data_loader_n_workers", "execution.max_data_loader_n_workers"),
        ("maxDataLoaderNWorkers", "execution.max_data_loader_n_workers"),
        ("workers", "execution.max_data_loader_n_workers"),
        (
            "persistent_data_loader_workers",
            "execution.persistent_data_loader_workers",
        ),
        ("persistentDataLoaderWorkers", "execution.persistent_data_loader_workers"),
        ("persistentWorkers", "execution.persistent_data_loader_workers"),
        ("save_every_n_epochs", "execution.save_every_n_epochs"),
        ("saveEveryNEpochs", "execution.save_every_n_epochs"),
        ("save_cadence", "execution.save_every_n_epochs"),
        ("saveCadence", "execution.save_every_n_epochs"),
    ),
    "model": _rules(
        ("family", "model.family"),
        ("model_family", "model.family"),
        ("modelFamily", "model.family"),
        ("checkpoint", "model.checkpoint"),
        ("allow_unverified_checkpoint", "model.allow_unverified_checkpoint"),
        ("allowUnverifiedCheckpoint", "model.allow_unverified_checkpoint"),
        ("network_module", "model.network_module"),
        ("networkModule", "model.network_module"),
        ("network_dim", "model.network_dim"),
        ("networkDim", "model.network_dim"),
        ("network_alpha", "model.network_alpha"),
        ("networkAlpha", "model.network_alpha"),
        ("qwen3", "model.anima.qwen3"),
        ("vae", "model.anima.vae"),
        ("t5_tokenizer_path", "model.anima.t5_tokenizer_path"),
        ("t5TokenizerPath", "model.anima.t5_tokenizer_path"),
    ),
    "model.anima": _rules(
        ("qwen3", "model.anima.qwen3"),
        ("vae", "model.anima.vae"),
        ("t5_tokenizer_path", "model.anima.t5_tokenizer_path"),
        ("t5TokenizerPath", "model.anima.t5_tokenizer_path"),
    ),
    "scope": _rules(
        ("train_text_encoder", "scope.train_text_encoder"),
        ("trainTextEncoder", "scope.train_text_encoder"),
        ("trainable_scope", "scope.train_text_encoder", "scope"),
        ("trainableScope", "scope.train_text_encoder", "scope"),
    ),
    "dataset": _rules(
        ("trigger_token", "dataset.trigger_token"),
        ("triggerToken", "dataset.trigger_token"),
        ("class_tokens", "dataset.trigger_token"),
        ("classTokens", "dataset.trigger_token"),
        ("instance_token", "dataset.trigger_token"),
        ("instanceToken", "dataset.trigger_token"),
        ("resolution", "dataset.resolution"),
        ("batch", "dataset.batch_size"),
        ("batchSize", "dataset.batch_size"),
        ("batch_size", "dataset.batch_size"),
        ("keep_tokens", "dataset.keep_tokens"),
        ("keepTokens", "dataset.keep_tokens"),
        ("shuffle_caption", "dataset.shuffle_caption"),
        ("shuffleCaption", "dataset.shuffle_caption"),
        ("num_repeats", "dataset.num_repeats"),
        ("numRepeats", "dataset.num_repeats"),
        ("enable_bucket", "dataset.enable_bucket"),
        ("enableBucket", "dataset.enable_bucket"),
        ("bucket_no_upscale", "dataset.bucket_no_upscale"),
        ("bucketNoUpscale", "dataset.bucket_no_upscale"),
        ("min_bucket_reso", "dataset.min_bucket_reso"),
        ("minBucketReso", "dataset.min_bucket_reso"),
        ("max_bucket_reso", "dataset.max_bucket_reso"),
        ("maxBucketReso", "dataset.max_bucket_reso"),
        ("bucket_reso_steps", "dataset.bucket_reso_steps"),
        ("bucketResoSteps", "dataset.bucket_reso_steps"),
    ),
    "optimization": _rules(
        ("epochs", "optimization.epochs"),
        ("learning_rate", "optimization.learning_rate"),
        ("learningRate", "optimization.learning_rate"),
        ("denoiser_learning_rate", "optimization.denoiser_learning_rate"),
        ("denoiserLearningRate", "optimization.denoiser_learning_rate"),
        ("unet_lr", "optimization.denoiser_learning_rate"),
        ("dit_lr", "optimization.denoiser_learning_rate"),
        ("text_encoder_learning_rates", "optimization.text_encoder_learning_rates"),
        ("textEncoderLearningRates", "optimization.text_encoder_learning_rates"),
        ("text_encoder_lr", "optimization.text_encoder_learning_rates"),
        ("textEncoderLr", "optimization.text_encoder_learning_rates"),
        ("gradient_accumulation_steps", "optimization.gradient_accumulation_steps"),
        ("gradient_accumulation", "optimization.gradient_accumulation_steps"),
        ("gradientAccumulationSteps", "optimization.gradient_accumulation_steps"),
        ("gradientAccumulation", "optimization.gradient_accumulation_steps"),
        ("optimizer_type", "optimization.optimizer_type"),
        ("optimizerType", "optimization.optimizer_type"),
        ("optimizer", "optimization.optimizer_type"),
        ("optimizer_args", "optimization.optimizer_args"),
        ("optimizerArgs", "optimization.optimizer_args"),
        ("lr_scheduler", "optimization.lr_scheduler"),
        ("lrScheduler", "optimization.lr_scheduler"),
        ("scheduler", "optimization.lr_scheduler"),
        ("lr_scheduler_args", "optimization.lr_scheduler_args"),
        ("lrSchedulerArgs", "optimization.lr_scheduler_args"),
        ("scheduler_args", "optimization.lr_scheduler_args"),
        ("schedulerArgs", "optimization.lr_scheduler_args"),
        ("warmup", "optimization.warmup"),
        ("lr_warmup_steps", "optimization.warmup", "warmup_steps"),
        ("lrWarmupSteps", "optimization.warmup", "warmup_steps"),
        ("warmup_ratio", "optimization.warmup", "warmup_ratio"),
        ("warmupRatio", "optimization.warmup", "warmup_ratio"),
        ("seed", "optimization.seed"),
        ("mixed_precision", "optimization.mixed_precision"),
        ("mixedPrecision", "optimization.mixed_precision"),
        ("precision", "optimization.mixed_precision"),
    ),
    "caching": _rules(
        ("cache_latents", "caching.cache_latents"),
        ("cacheLatents", "caching.cache_latents"),
        (
            "cache_text_encoder_outputs",
            "caching.cache_text_encoder_outputs",
        ),
        ("cacheTextEncoderOutputs", "caching.cache_text_encoder_outputs"),
        ("cache_to_disk", "caching.cache_to_disk"),
        ("cacheToDisk", "caching.cache_to_disk"),
    ),
    "execution": _rules(
        ("max_data_loader_n_workers", "execution.max_data_loader_n_workers"),
        ("maxDataLoaderNWorkers", "execution.max_data_loader_n_workers"),
        ("workers", "execution.max_data_loader_n_workers"),
        (
            "persistent_data_loader_workers",
            "execution.persistent_data_loader_workers",
        ),
        ("persistentDataLoaderWorkers", "execution.persistent_data_loader_workers"),
        ("persistentWorkers", "execution.persistent_data_loader_workers"),
        ("save_every_n_epochs", "execution.save_every_n_epochs"),
        ("saveEveryNEpochs", "execution.save_every_n_epochs"),
        ("save_cadence", "execution.save_every_n_epochs"),
        ("saveCadence", "execution.save_every_n_epochs"),
    ),
}


_INTEGER_PATHS = {
    "model.network_dim",
    "model.network_alpha",
    "dataset.resolution",
    "dataset.batch_size",
    "dataset.keep_tokens",
    "dataset.num_repeats",
    "dataset.min_bucket_reso",
    "dataset.max_bucket_reso",
    "dataset.bucket_reso_steps",
    "optimization.epochs",
    "optimization.gradient_accumulation_steps",
    "execution.max_data_loader_n_workers",
    "execution.save_every_n_epochs",
}

_BOOLEAN_PATHS = {
    "model.allow_unverified_checkpoint",
    "scope.train_text_encoder",
    "dataset.shuffle_caption",
    "dataset.enable_bucket",
    "dataset.bucket_no_upscale",
    "caching.cache_latents",
    "caching.cache_text_encoder_outputs",
    "caching.cache_to_disk",
    "execution.persistent_data_loader_workers",
}

_TEXT_PATHS = {
    "model.checkpoint",
    "model.network_module",
    "model.anima.qwen3",
    "model.anima.vae",
    "model.anima.t5_tokenizer_path",
    "dataset.trigger_token",
    "optimization.optimizer_type",
    "optimization.lr_scheduler",
}

_RATE_PATHS = {
    "optimization.learning_rate",
    "optimization.denoiser_learning_rate",
}


def _recipe_error(
    issues: list[dict[str, Any]],
    *,
    hint: str = "apply the suggested field correction and retry",
) -> RecipeError:
    return RecipeError(
        "recipe_validation_failed",
        "training recipe is invalid",
        hint,
        {"issues": issues},
    )


def _parse_transport(raw: object) -> Mapping[str, object]:
    parsed = raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise _recipe_error(
                [
                    {
                        "location": "recipe",
                        "type": "invalid_json",
                        "accepted_forms": ["JSON object", "JSON-object string"],
                    }
                ]
            ) from None
    if not isinstance(parsed, Mapping):
        raise _recipe_error(
            [
                {
                    "location": "recipe",
                    "type": "object_required",
                    "accepted_forms": ["JSON object", "JSON-object string"],
                }
            ]
        )
    return parsed


def _accepted_forms_for_path(path: str) -> list[str]:
    forms = {
        alias
        for aliases in _ALIASES.values()
        for alias, rule in aliases.items()
        if rule.path == path
    }
    return sorted(forms)


def _accepted_forms_for_context(context: str) -> list[str]:
    forms = set(_ALIASES[context])
    if context == "":
        forms.update(_ROOT_CONTAINERS)
    forms.update(_NESTED_CONTAINERS.get(context, {}))
    return sorted(forms)


def _unknown_issue(context: str, key: object) -> dict[str, Any]:
    safe_key = (
        key
        if isinstance(key, str)
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", key)
        else "<unknown>"
    )
    location = f"{context}.{safe_key}" if context else str(safe_key)
    candidates = _accepted_forms_for_context(context)
    match = difflib.get_close_matches(str(safe_key), candidates, n=1, cutoff=0.6)
    issue: dict[str, Any] = {
        "location": location,
        "type": "unknown_field",
    }
    if match:
        matching_rule = _ALIASES[context].get(match[0])
        issue["suggestion"] = (
            matching_rule.path.rsplit(".", 1)[-1]
            if matching_rule is not None
            else match[0]
        )
    issue["accepted_forms"] = candidates
    return issue


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        raise _InvalidValue
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
        return int(value.strip())
    raise _InvalidValue


def _coerce_float(value: object) -> float:
    if isinstance(value, bool):
        raise _InvalidValue
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            raise _InvalidValue from None
    else:
        raise _InvalidValue
    if not math.isfinite(number):
        raise _InvalidValue
    return number


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
    raise _InvalidValue


def _coerce_optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _InvalidValue
    normalized = value.strip()
    if not normalized:
        raise _InvalidValue
    return normalized


def _coerce_schema_version(value: object) -> str:
    if isinstance(value, bool):
        raise _InvalidValue
    if value == 1:
        return "lora-training-recipe/v1"
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "v1", "lora-training-recipe/v1"}:
            return "lora-training-recipe/v1"
    raise _InvalidValue


def _coerce_family(value: object) -> str:
    if not isinstance(value, str):
        raise _InvalidValue
    normalized = value.strip().lower().replace("_", "").replace("-", "")
    aliases = {
        "sd1": "sd15",
        "sd1.5": "sd15",
        "sd15": "sd15",
        "sdxl": "sdxl",
        "xl": "sdxl",
        "anima": "anima",
    }
    try:
        return aliases[normalized]
    except KeyError:
        raise _InvalidValue from None


def _coerce_rate(value: object) -> str:
    if isinstance(value, bool):
        raise _InvalidValue
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            raise _InvalidValue
        rendered = normalized
    elif isinstance(value, int):
        rendered = str(value)
    elif isinstance(value, float) and math.isfinite(value):
        rendered = format(value, ".15g")
    else:
        raise _InvalidValue
    try:
        number = Decimal(rendered)
    except InvalidOperation:
        raise _InvalidValue from None
    if not number.is_finite() or number <= 0:
        raise _InvalidValue
    return format(number.normalize(), "f")


def _coerce_rate_list(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        if not value:
            raise _InvalidValue
        return tuple(_coerce_rate(item) for item in value)
    return (_coerce_rate(value),)


def _render_arg_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            raise _InvalidValue
        return normalized
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return format(value, ".15g")
    raise _InvalidValue


_ARG_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")


def _validate_and_sort_args(items: list[str]) -> tuple[str, ...]:
    by_key: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise _InvalidValue
        key, raw_value = item.split("=", 1)
        if (
            not _ARG_KEY_RE.fullmatch(key)
            or not raw_value
            or any(character.isspace() for character in raw_value)
            or key in by_key
        ):
            raise _InvalidValue
        by_key[key] = f"{key}={raw_value}"
    return tuple(by_key[key] for key in sorted(by_key))


def _coerce_args(value: object) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        rendered: list[str] = []
        for key in sorted(value):
            if not isinstance(key, str) or not _ARG_KEY_RE.fullmatch(key):
                raise _InvalidValue
            rendered.append(f"{key}={_render_arg_scalar(value[key])}")
        return _validate_and_sort_args(rendered)
    if isinstance(value, (list, tuple)):
        result: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise _InvalidValue
            result.append(item.strip())
        return _validate_and_sort_args(result)
    if isinstance(value, str):
        try:
            return _validate_and_sort_args(shlex.split(value, posix=True))
        except ValueError:
            raise _InvalidValue from None
    raise _InvalidValue


def _coerce_scope(value: object, form: str) -> bool:
    if form != "scope":
        return _coerce_bool(value)
    if not isinstance(value, str):
        raise _InvalidValue
    normalized = value.strip().lower()
    if normalized == "denoiser_only":
        return False
    if normalized == "denoiser_and_text_encoder":
        return True
    raise _InvalidValue


def _coerce_warmup(value: object, form: str) -> dict[str, int | float]:
    if form == "warmup_steps":
        return {"mode": "steps", "value": _coerce_int(value)}
    if form == "warmup_ratio":
        return {"mode": "ratio", "value": _coerce_float(value)}
    if isinstance(value, Mapping):
        if set(value) - {"mode", "value"} or "mode" not in value or "value" not in value:
            raise _InvalidValue
        mode = value["mode"]
        if not isinstance(mode, str):
            raise _InvalidValue
        normalized_mode = mode.strip().lower()
        if normalized_mode == "steps":
            return {"mode": "steps", "value": _coerce_int(value["value"])}
        if normalized_mode == "ratio":
            return {"mode": "ratio", "value": _coerce_float(value["value"])}
        raise _InvalidValue
    return {"mode": "steps", "value": _coerce_int(value)}


def _coerce_seed(
    value: object,
    *,
    explicit_source: Literal["caller", "preflight_policy", "server_policy"],
    accept_materialized_policy_source: bool,
) -> _SeedIntent:
    if value is None:
        return _SeedIntent("random", None, explicit_source)
    if isinstance(value, str) and value.strip().lower() == "random":
        return _SeedIntent("random", None, explicit_source)
    if isinstance(value, Mapping):
        if set(value) - {"mode", "value", "source"}:
            raise _InvalidValue
        mode = value.get("mode")
        if not isinstance(mode, str):
            raise _InvalidValue
        normalized_mode = mode.strip().lower()
        supplied_source = value.get("source", explicit_source)
        if supplied_source not in {"caller", "preflight_policy", "server_policy"}:
            raise _InvalidValue
        source = (
            supplied_source
            if accept_materialized_policy_source
            else explicit_source
        )
        raw_seed = value.get("value")
        if normalized_mode == "fixed":
            if raw_seed is None:
                raise _InvalidValue
            seed = _coerce_int(raw_seed)
            _validate_seed_range(seed)
            return _SeedIntent("fixed", seed, source)
        if normalized_mode == "random":
            if raw_seed is None:
                return _SeedIntent("random", None, source)
            seed = _coerce_int(raw_seed)
            _validate_seed_range(seed)
            return _SeedIntent("random", seed, source)
        raise _InvalidValue
    seed = _coerce_int(value)
    _validate_seed_range(seed)
    return _SeedIntent("fixed", seed, explicit_source)


def _validate_seed_range(seed: int) -> None:
    if seed < 0 or seed > 2**32 - 1:
        raise _InvalidValue


def _coerce_mixed_precision(value: object) -> str:
    if not isinstance(value, str):
        raise _InvalidValue
    normalized = value.strip().lower()
    if normalized == "fp32":
        return "no"
    if normalized in {"no", "fp16", "bf16"}:
        return normalized
    raise _InvalidValue


def _coerce_expected_hash(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _InvalidValue
    normalized = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise _InvalidValue
    return normalized


def _coerce_value(
    rule: _AliasRule,
    value: object,
) -> object:
    path = rule.path
    if path == "schema_version":
        return _coerce_schema_version(value)
    if path == "expected_recipe_hash":
        return _coerce_expected_hash(value)
    if path == "model.family":
        return _coerce_family(value)
    if path in _INTEGER_PATHS:
        return _coerce_int(value)
    if path in _BOOLEAN_PATHS:
        if path == "scope.train_text_encoder":
            return _coerce_scope(value, rule.form)
        return _coerce_bool(value)
    if path in _TEXT_PATHS:
        return _coerce_optional_text(value)
    if path in _RATE_PATHS:
        return _coerce_rate(value)
    if path == "optimization.text_encoder_learning_rates":
        return _coerce_rate_list(value)
    if path in {"optimization.optimizer_args", "optimization.lr_scheduler_args"}:
        return _coerce_args(value)
    if path == "optimization.warmup":
        return _coerce_warmup(value, rule.form)
    if path == "optimization.mixed_precision":
        return _coerce_mixed_precision(value)
    raise RuntimeError(f"missing canonical recipe coercer for {path}")


def _set_nested(target: dict[str, Any], path: str, value: object) -> None:
    parts = path.split(".")
    cursor = target
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = value


def normalize_recipe_input(
    raw: object,
    *,
    policy_source: PolicySource = "server_policy",
    seed_factory: Callable[[], int] | None = None,
    accept_materialized_policy_seed: bool = False,
) -> NormalizedRecipeInput:
    """Normalize broad recipe transport into its canonical requested shape."""
    source = policy_source
    if source not in {"preflight_policy", "server_policy"}:
        raise ValueError("unsupported recipe policy source")
    parsed = _parse_transport(raw)
    values: dict[str, object] = {}
    provided_fields: set[str] = set()
    scalar_fields: set[str] = set()
    collection_fields: set[str] = set()
    conflicts: set[str] = set()
    issues: list[dict[str, Any]] = []

    def record(rule: _AliasRule, value: object) -> None:
        try:
                canonical = (
                _coerce_seed(
                    value,
                    explicit_source="caller",
                    accept_materialized_policy_source=accept_materialized_policy_seed,
                )
                if rule.path == "optimization.seed"
                else _coerce_value(rule, value)
            )
        except (_InvalidValue, TypeError, ValueError):
            issues.append(
                {
                    "location": rule.path,
                    "type": "invalid_value",
                    "accepted_forms": _accepted_forms_for_path(rule.path),
                }
            )
            return
        if rule.path in values and values[rule.path] != canonical:
            conflicts.add(rule.path)
            return
        values[rule.path] = canonical
        provided_fields.add(rule.path)
        if rule.path == "optimization.text_encoder_learning_rates":
            if isinstance(value, (list, tuple)):
                collection_fields.add(rule.path)
            else:
                scalar_fields.add(rule.path)

    def visit(mapping: Mapping[object, object], context: str) -> None:
        rules = _ALIASES[context]
        containers = (
            _ROOT_CONTAINERS if context == "" else _NESTED_CONTAINERS.get(context, {})
        )
        for key, value in mapping.items():
            if key in containers:
                if value is None:
                    continue
                if not isinstance(value, Mapping):
                    location = f"{context}.{key}" if context else str(key)
                    issues.append(
                        {
                            "location": location,
                            "type": "object_required",
                            "accepted_forms": ["JSON object"],
                        }
                    )
                    continue
                visit(value, containers[key])
                continue
            rule = rules.get(key) if isinstance(key, str) else None
            if rule is None:
                issues.append(_unknown_issue(context, key))
                continue
            if value is None and rule.path != "optimization.seed":
                continue
            record(rule, value)

    visit(parsed, "")

    if conflicts:
        raise RecipeError(
            "recipe_field_conflict",
            "training recipe contains conflicting aliases",
            "remove one conflicting alias and retry",
            {
                "issues": [
                    {
                        "location": path,
                        "type": "alias_conflict",
                        "accepted_forms": _accepted_forms_for_path(path),
                    }
                    for path in sorted(conflicts)
                ]
            },
        )
    if issues:
        raise _recipe_error(issues)

    seed_intent = values.get("optimization.seed")
    if seed_intent is None:
        seed_intent = _SeedIntent("random", None, source)
    assert isinstance(seed_intent, _SeedIntent)
    if seed_intent.value is None:
        draw_seed = seed_factory or (lambda: secrets.randbelow(2**32))
        try:
            materialized_seed = _coerce_int(draw_seed())
            _validate_seed_range(materialized_seed)
        except (_InvalidValue, TypeError, ValueError):
            raise RuntimeError("seed factory returned an invalid seed") from None
        seed_intent = _SeedIntent(
            seed_intent.mode,
            materialized_seed,
            seed_intent.source,
        )
    values["optimization.seed"] = {
        "mode": seed_intent.mode,
        "value": seed_intent.value,
        "source": seed_intent.source,
    }

    canonical: dict[str, Any] = {
        "schema_version": values.pop(
            "schema_version",
            "lora-training-recipe/v1",
        )
    }
    for path, value in values.items():
        _set_nested(canonical, path, value)
    try:
        requested = RequestedTrainingRecipeV1.model_validate(canonical)
    except ValidationError as exc:
        validation_issues = []
        for error in exc.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        ):
            validation_issues.append(
                {
                    "location": ".".join(str(part) for part in error["loc"]),
                    "type": "invalid_value",
                }
            )
        raise _recipe_error(validation_issues) from None

    return NormalizedRecipeInput(
        requested=requested,
        provided_fields=frozenset(provided_fields),
        scalar_fields=frozenset(scalar_fields - collection_fields),
    )


_TRUSTED_NETWORK_MODULES: dict[str, tuple[str, ...]] = {
    "sd15": ("networks.lora",),
    "sdxl": ("networks.lora",),
    "anima": ("networks.lora_anima",),
}

_NETWORK_MODULE_DEFAULTS = {
    family: modules[0] for family, modules in _TRUSTED_NETWORK_MODULES.items()
}


def _cross_field_error(
    code: str,
    message: str,
    hint: str,
    locations: tuple[str, ...],
) -> RecipeError:
    return RecipeError(
        code,
        message,
        hint,
        {
            "issues": [
                {"location": location, "type": "incompatible_value"}
                for location in locations
            ]
        },
    )


def _default_epochs(family: str, image_count: int) -> int:
    if family == "anima":
        return 8
    if image_count < 12:
        return 12
    if image_count <= 40:
        return 10
    return 8


def calculate_step_plan(
    *,
    image_count: int,
    num_repeats: int,
    batch_size: int,
    gradient_accumulation_steps: int,
    epochs: int,
    warmup_mode: Literal["steps", "ratio"],
    warmup_value: int | float,
) -> TrainingStepPlan:
    """Calculate the documented single-process optimizer-step relationship."""
    if min(
        image_count,
        num_repeats,
        batch_size,
        gradient_accumulation_steps,
        epochs,
    ) <= 0:
        raise _recipe_error(
            [
                {
                    "location": "step_plan",
                    "type": "invalid_value",
                }
            ]
        )
    train_examples = image_count * num_repeats
    batches_per_epoch = math.ceil(train_examples / batch_size)
    optimizer_steps_per_epoch = math.ceil(
        batches_per_epoch / gradient_accumulation_steps
    )
    total_optimizer_steps = optimizer_steps_per_epoch * epochs
    if warmup_mode == "steps":
        if isinstance(warmup_value, bool) or int(warmup_value) != warmup_value:
            raise _recipe_error(
                [
                    {
                        "location": "optimization.warmup.value",
                        "type": "invalid_value",
                    }
                ]
            )
        warmup_steps = int(warmup_value)
    elif warmup_mode == "ratio":
        ratio = float(warmup_value)
        if not math.isfinite(ratio) or ratio < 0 or ratio > 1:
            raise _recipe_error(
                [
                    {
                        "location": "optimization.warmup.value",
                        "type": "invalid_value",
                        "accepted_range": [0, 1],
                    }
                ]
            )
        warmup_steps = math.ceil(total_optimizer_steps * ratio)
    else:
        raise _recipe_error(
            [
                {
                    "location": "optimization.warmup.mode",
                    "type": "invalid_value",
                }
            ]
        )
    return TrainingStepPlan(
        image_count=image_count,
        num_repeats=num_repeats,
        train_examples=train_examples,
        batch_size=batch_size,
        batches_per_epoch=batches_per_epoch,
        gradient_accumulation_steps=gradient_accumulation_steps,
        optimizer_steps_per_epoch=optimizer_steps_per_epoch,
        epochs=epochs,
        total_optimizer_steps=total_optimizer_steps,
        warmup_steps=warmup_steps,
        process_count=1,
    )


def canonical_recipe_hash(
    effective: EffectiveTrainingRecipeV1,
    *,
    dataset_hash: str,
    profile_hash: str,
    component_identities: Mapping[str, ComponentIdentity],
) -> str:
    """Hash semantic training identity using canonical UTF-8 JSON."""
    document = {
        "schema_version": effective.schema_version,
        "dataset_hash": dataset_hash,
        "profile_hash": profile_hash,
        "effective_recipe": effective.model_dump(mode="json"),
        "component_identities": {
            name: identity.model_dump(mode="json")
            for name, identity in sorted(component_identities.items())
        },
    }
    canonical = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _effective_leaf_paths(value: object, prefix: str = "") -> set[str]:
    if isinstance(value, dict):
        result: set[str] = set()
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if item is not None:
                result.update(_effective_leaf_paths(item, path))
        return result
    return {prefix}


def compile_training_recipe(
    raw: object,
    *,
    context: RecipeCompilationContext,
    policy_source: PolicySource = "server_policy",
    seed_factory: Callable[[], int] | None = None,
    accept_materialized_policy_seed: bool = False,
) -> RecipeCompilationResult:
    """Compile broad requested input into one complete immutable v1 recipe."""
    normalized = (
        raw
        if isinstance(raw, NormalizedRecipeInput)
        else normalize_recipe_input(
            raw,
            policy_source=policy_source,
            seed_factory=seed_factory,
            accept_materialized_policy_seed=accept_materialized_policy_seed,
        )
    )
    requested = normalized.requested
    provided = normalized.provided_fields
    sources: dict[str, RecipeFieldSource] = {
        "schema_version": "server_policy",
    }

    def resolved_component_value(
        identity_name: str,
        requested_locator: str | None,
    ) -> str | None:
        identity = context.component_identities.get(identity_name)
        if (
            requested_locator
            and identity is not None
            and identity.requested_locator == requested_locator
            and identity.verification_status == "verified"
            and identity.resolved_locator
        ):
            return identity.resolved_locator
        return requested_locator

    def choose(
        path: str,
        requested_value: Any,
        default_value: Any,
        *,
        default_source: RecipeFieldSource = policy_source,
    ) -> Any:
        if path in provided and requested_value is not None:
            sources[path] = "caller"
            return requested_value
        sources[path] = default_source
        return default_value

    requested_model = requested.model
    caller_family = requested_model.family if requested_model is not None else None
    family = choose(
        "model.family",
        caller_family,
        context.profile_model_family,
        default_source="derived",
    )
    if family != context.profile_model_family:
        raise _cross_field_error(
            "model_family_mismatch",
            "recipe model family does not match the approved dataset profile",
            "use the dataset profile model family and rerun preflight",
            ("model.family",),
        )

    checkpoint = choose(
        "model.checkpoint",
        requested_model.checkpoint if requested_model is not None else None,
        context.policy.default_checkpoint,
    )
    if not checkpoint:
        raise _recipe_error(
            [
                {
                    "location": "model.checkpoint",
                    "type": "required_value",
                }
            ],
            hint="configure or provide a checkpoint locator and rerun preflight",
        )
    resolved_checkpoint = resolved_component_value("checkpoint", checkpoint)
    if resolved_checkpoint != checkpoint:
        checkpoint = resolved_checkpoint
        sources["model.checkpoint"] = "derived"
    allow_unverified = choose(
        "model.allow_unverified_checkpoint",
        (
            requested_model.allow_unverified_checkpoint
            if requested_model is not None
            else None
        ),
        False,
    )
    requested_module = (
        requested_model.network_module if requested_model is not None else None
    )
    network_module = choose(
        "model.network_module",
        requested_module,
        _NETWORK_MODULE_DEFAULTS[family],
    )
    allowed_modules = _TRUSTED_NETWORK_MODULES[family]
    if network_module not in allowed_modules:
        raise RecipeError(
            "unsupported_network_module",
            "network module is not trusted for the selected model family",
            "use one of the allowed network module identifiers",
            {
                "family": family,
                "allowed_identifiers": list(allowed_modules),
            },
        )
    network_dim = choose(
        "model.network_dim",
        requested_model.network_dim if requested_model is not None else None,
        context.policy.network_dim,
    )
    network_alpha = choose(
        "model.network_alpha",
        requested_model.network_alpha if requested_model is not None else None,
        context.policy.network_alpha,
    )

    anima: EffectiveAnimaRecipe | None = None
    if family == "anima":
        requested_anima = requested_model.anima if requested_model is not None else None
        qwen3 = choose(
            "model.anima.qwen3",
            requested_anima.qwen3 if requested_anima is not None else None,
            context.policy.default_anima_qwen3,
        )
        if not qwen3:
            raise _recipe_error(
                [
                    {
                        "location": "model.anima.qwen3",
                        "type": "required_value",
                    }
                ],
                hint="configure or provide the Anima Qwen3 locator and rerun preflight",
            )
        resolved_qwen3 = resolved_component_value("text_encoder", qwen3)
        if resolved_qwen3 != qwen3:
            qwen3 = resolved_qwen3
            sources["model.anima.qwen3"] = "derived"
        vae = choose(
            "model.anima.vae",
            requested_anima.vae if requested_anima is not None else None,
            context.policy.default_anima_vae,
        )
        tokenizer = choose(
            "model.anima.t5_tokenizer_path",
            (
                requested_anima.t5_tokenizer_path
                if requested_anima is not None
                else None
            ),
            context.policy.default_anima_t5_tokenizer_path,
        )
        resolved_vae = resolved_component_value("vae", vae)
        if resolved_vae != vae:
            vae = resolved_vae
            sources["model.anima.vae"] = "derived"
        resolved_tokenizer = resolved_component_value(
            "tokenizer",
            tokenizer,
        )
        if resolved_tokenizer != tokenizer:
            tokenizer = resolved_tokenizer
            sources["model.anima.t5_tokenizer_path"] = "derived"
        if vae is None:
            sources.pop("model.anima.vae")
        if tokenizer is None:
            sources.pop("model.anima.t5_tokenizer_path")
        anima = EffectiveAnimaRecipe(
            qwen3=qwen3,
            vae=vae,
            t5_tokenizer_path=tokenizer,
        )

    requested_scope = requested.scope
    train_text_encoder = choose(
        "scope.train_text_encoder",
        (
            requested_scope.train_text_encoder
            if requested_scope is not None
            else None
        ),
        False,
    )
    denoiser_kind = "dit" if family == "anima" else "unet"
    sources.update(
        {
            "scope.denoiser_kind": "derived",
            "scope.train_denoiser": "server_policy",
            "scope.verification_status": "server_policy",
        }
    )
    if not train_text_encoder:
        sources["scope.native_scope_flag"] = "derived"

    requested_dataset = requested.dataset
    requested_token = (
        requested_dataset.trigger_token if requested_dataset is not None else None
    )
    trigger_token = choose(
        "dataset.trigger_token",
        requested_token,
        context.approved_trigger_token,
        default_source="derived",
    )
    if trigger_token != context.approved_trigger_token:
        raise _cross_field_error(
            "trigger_token_mismatch",
            "recipe trigger token does not match the approved dataset token",
            "use the approved normalized trigger token and rerun preflight",
            ("dataset.trigger_token",),
        )
    sources["dataset.class_tokens"] = "derived"
    resolution = choose(
        "dataset.resolution",
        requested_dataset.resolution if requested_dataset is not None else None,
        context.policy.resolution,
    )
    requested_batch = (
        requested_dataset.batch_size if requested_dataset is not None else None
    )
    if "dataset.batch_size" in provided and requested_batch is not None:
        batch_size = requested_batch
        sources["dataset.batch_size"] = "caller"
    else:
        capability = context.capability
        use_configured_batch = (
            family == "sd15"
            and resolution < 1024
            and capability.platform == "cuda"
            and capability.status == "verified"
        )
        batch_size = context.policy.batch_size if use_configured_batch else 1
        sources["dataset.batch_size"] = policy_source
    keep_tokens = choose(
        "dataset.keep_tokens",
        requested_dataset.keep_tokens if requested_dataset is not None else None,
        context.policy.keep_tokens,
    )
    default_repeats = 8 if family == "anima" else context.policy.num_repeats
    num_repeats = choose(
        "dataset.num_repeats",
        requested_dataset.num_repeats if requested_dataset is not None else None,
        default_repeats,
    )
    enable_bucket = choose(
        "dataset.enable_bucket",
        requested_dataset.enable_bucket if requested_dataset is not None else None,
        True,
    )
    bucket_no_upscale = choose(
        "dataset.bucket_no_upscale",
        (
            requested_dataset.bucket_no_upscale
            if requested_dataset is not None
            else None
        ),
        True,
    )
    min_bucket_reso = choose(
        "dataset.min_bucket_reso",
        requested_dataset.min_bucket_reso if requested_dataset is not None else None,
        256,
    )
    max_bucket_reso = choose(
        "dataset.max_bucket_reso",
        requested_dataset.max_bucket_reso if requested_dataset is not None else None,
        max(1024, resolution * 2),
    )
    bucket_reso_steps = choose(
        "dataset.bucket_reso_steps",
        requested_dataset.bucket_reso_steps if requested_dataset is not None else None,
        64,
    )
    bucket_issue_locations: list[str] = []
    if min_bucket_reso > max_bucket_reso:
        bucket_issue_locations.extend(
            ("dataset.min_bucket_reso", "dataset.max_bucket_reso")
        )
    if min_bucket_reso % bucket_reso_steps:
        bucket_issue_locations.append("dataset.min_bucket_reso")
    if max_bucket_reso % bucket_reso_steps:
        bucket_issue_locations.append("dataset.max_bucket_reso")
    if enable_bucket and resolution % bucket_reso_steps:
        bucket_issue_locations.append("dataset.resolution")
    if enable_bucket and not (min_bucket_reso <= resolution <= max_bucket_reso):
        bucket_issue_locations.append("dataset.resolution")
    if bucket_issue_locations:
        raise _recipe_error(
            [
                {
                    "location": location,
                    "type": "bucket_invariant",
                }
                for location in dict.fromkeys(bucket_issue_locations)
            ]
        )

    requested_optimization = requested.optimization
    epochs = choose(
        "optimization.epochs",
        (
            requested_optimization.epochs
            if requested_optimization is not None
            else None
        ),
        _default_epochs(family, context.image_count),
    )
    try:
        policy_learning_rate = _coerce_rate(context.policy.learning_rate)
    except _InvalidValue:
        raise RecipeError(
            "server_recipe_policy_invalid",
            "server LoRA recipe policy is invalid",
            "correct the server learning-rate policy",
            {"issues": [{"location": "policy.learning_rate", "type": "invalid_value"}]},
        ) from None
    learning_rate = choose(
        "optimization.learning_rate",
        (
            requested_optimization.learning_rate
            if requested_optimization is not None
            else None
        ),
        policy_learning_rate,
    )
    denoiser_learning_rate = choose(
        "optimization.denoiser_learning_rate",
        (
            requested_optimization.denoiser_learning_rate
            if requested_optimization is not None
            else None
        ),
        learning_rate,
        default_source="derived",
    )
    requested_text_rates = (
        requested_optimization.text_encoder_learning_rates
        if requested_optimization is not None
        else None
    )
    expected_text_rate_count = 2 if family == "sdxl" else 1
    if not train_text_encoder:
        if "optimization.text_encoder_learning_rates" in provided:
            raise _cross_field_error(
                "incompatible_training_recipe",
                "Text Encoder learning rates require Text Encoder training",
                "enable Text Encoder training or remove its learning rates",
                (
                    "scope.train_text_encoder",
                    "optimization.text_encoder_learning_rates",
                ),
            )
        text_encoder_learning_rates: tuple[str, ...] = ()
        sources["optimization.text_encoder_learning_rates"] = "derived"
    elif requested_text_rates is None:
        text_encoder_learning_rates = (learning_rate,) * expected_text_rate_count
        sources["optimization.text_encoder_learning_rates"] = "derived"
    elif (
        len(requested_text_rates) == 1
        and "optimization.text_encoder_learning_rates" in normalized.scalar_fields
    ):
        text_encoder_learning_rates = (
            requested_text_rates[0],
        ) * expected_text_rate_count
        sources["optimization.text_encoder_learning_rates"] = "caller"
    elif len(requested_text_rates) != expected_text_rate_count:
        raise _recipe_error(
            [
                {
                    "location": "optimization.text_encoder_learning_rates",
                    "type": "invalid_count",
                    "expected_count": expected_text_rate_count,
                }
            ]
        )
    else:
        text_encoder_learning_rates = tuple(requested_text_rates)
        sources["optimization.text_encoder_learning_rates"] = "caller"

    gradient_accumulation_steps = choose(
        "optimization.gradient_accumulation_steps",
        (
            requested_optimization.gradient_accumulation_steps
            if requested_optimization is not None
            else None
        ),
        1,
    )
    optimizer_type = choose(
        "optimization.optimizer_type",
        (
            requested_optimization.optimizer_type
            if requested_optimization is not None
            else None
        ),
        "AdamW",
    )
    optimizer_args = choose(
        "optimization.optimizer_args",
        (
            requested_optimization.optimizer_args
            if requested_optimization is not None
            else None
        ),
        (),
    )
    lr_scheduler = choose(
        "optimization.lr_scheduler",
        (
            requested_optimization.lr_scheduler
            if requested_optimization is not None
            else None
        ),
        "constant",
    )
    lr_scheduler_args = choose(
        "optimization.lr_scheduler_args",
        (
            requested_optimization.lr_scheduler_args
            if requested_optimization is not None
            else None
        ),
        (),
    )
    requested_warmup = (
        requested_optimization.warmup
        if requested_optimization is not None
        else None
    )
    if requested_warmup is None:
        warmup_mode: Literal["steps", "ratio"] = "steps"
        warmup_value: int | float = 0
        warmup_source: RecipeFieldSource = policy_source
    else:
        warmup_mode = requested_warmup.mode
        warmup_value = requested_warmup.value
        warmup_source = "caller"
    sources["optimization.warmup.mode"] = warmup_source
    sources["optimization.warmup.value"] = warmup_source
    sources["optimization.warmup.resolved_steps"] = "derived"

    seed = requested_optimization.seed if requested_optimization is not None else None
    if seed is None:
        raise RuntimeError("normalized recipe did not materialize a seed")
    seed_source: RecipeFieldSource = seed.source
    sources.update(
        {
            "optimization.seed.mode": seed_source,
            "optimization.seed.value": seed_source,
            "optimization.seed.source": seed_source,
        }
    )
    requested_precision = (
        requested_optimization.mixed_precision
        if requested_optimization is not None
        else None
    )
    if "optimization.mixed_precision" in provided and requested_precision is not None:
        if (
            requested_precision != "no"
            and (
                context.capability.status != "verified"
                or requested_precision
                not in context.capability.supported_mixed_precision
            )
        ):
            raise RecipeError(
                "unsupported_runtime_precision",
                "requested mixed precision is not verified for this trainer runtime",
                "use mixed_precision=no or verify trainer capability",
                {
                    "issues": [
                        {
                            "location": "optimization.mixed_precision",
                            "type": "unsupported_capability",
                        }
                    ]
                },
            )
        mixed_precision = requested_precision
        sources["optimization.mixed_precision"] = "caller"
    else:
        configured_precision = context.policy.mixed_precision
        if (
            context.capability.platform == "cuda"
            and context.capability.status == "verified"
            and configured_precision in context.capability.supported_mixed_precision
        ):
            mixed_precision = configured_precision
        else:
            mixed_precision = "no"
        sources["optimization.mixed_precision"] = policy_source

    requested_caching = requested.caching
    cache_latents = choose(
        "caching.cache_latents",
        requested_caching.cache_latents if requested_caching is not None else None,
        True,
    )
    cache_text_encoder_outputs = choose(
        "caching.cache_text_encoder_outputs",
        (
            requested_caching.cache_text_encoder_outputs
            if requested_caching is not None
            else None
        ),
        (not train_text_encoder and family in {"sdxl", "anima"}),
    )
    cache_to_disk = choose(
        "caching.cache_to_disk",
        requested_caching.cache_to_disk if requested_caching is not None else None,
        True,
    )
    if train_text_encoder and cache_text_encoder_outputs:
        raise _cross_field_error(
            "incompatible_training_recipe",
            "Text Encoder output caching cannot be used while training Text Encoder modules",
            "disable cache_text_encoder_outputs or disable Text Encoder training",
            (
                "scope.train_text_encoder",
                "caching.cache_text_encoder_outputs",
            ),
        )
    requested_shuffle_caption = (
        requested_dataset.shuffle_caption if requested_dataset is not None else None
    )
    if (
        "dataset.shuffle_caption" in provided
        and requested_shuffle_caption is not None
    ):
        shuffle_caption = requested_shuffle_caption
        shuffle_caption_source: RecipeFieldSource = "caller"
    elif cache_text_encoder_outputs:
        # sd-scripts cannot cache Text Encoder outputs when captions are mutated.
        shuffle_caption = False
        shuffle_caption_source = "derived"
    else:
        shuffle_caption = True
        shuffle_caption_source = "server_policy"
    if cache_text_encoder_outputs and shuffle_caption:
        raise _cross_field_error(
            "incompatible_training_recipe",
            "Text Encoder output caching cannot be combined with caption shuffling",
            "set dataset.shuffle_caption=false or disable cache_text_encoder_outputs",
            (
                "dataset.shuffle_caption",
                "caching.cache_text_encoder_outputs",
            ),
        )
    latent_cache_to_disk = cache_to_disk and cache_latents
    text_encoder_cache_to_disk = cache_to_disk and cache_text_encoder_outputs
    sources["caching.latent_cache_to_disk"] = "derived"
    sources["caching.text_encoder_cache_to_disk"] = "derived"

    requested_execution = requested.execution
    workers = choose(
        "execution.max_data_loader_n_workers",
        (
            requested_execution.max_data_loader_n_workers
            if requested_execution is not None
            else None
        ),
        0,
    )
    persistent_workers = choose(
        "execution.persistent_data_loader_workers",
        (
            requested_execution.persistent_data_loader_workers
            if requested_execution is not None
            else None
        ),
        False,
    )
    if persistent_workers and workers == 0:
        raise _cross_field_error(
            "incompatible_training_recipe",
            "persistent data-loader workers require a positive worker count",
            "set workers above zero or disable persistent workers",
            (
                "execution.max_data_loader_n_workers",
                "execution.persistent_data_loader_workers",
            ),
        )
    save_every_n_epochs = choose(
        "execution.save_every_n_epochs",
        (
            requested_execution.save_every_n_epochs
            if requested_execution is not None
            else None
        ),
        1,
    )
    final_only = save_every_n_epochs == 0
    sources["execution.final_only"] = "derived"

    step_plan = calculate_step_plan(
        image_count=context.image_count,
        num_repeats=num_repeats,
        batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        epochs=epochs,
        warmup_mode=warmup_mode,
        warmup_value=warmup_value,
    )

    server = EffectiveServerRecipe(
        gradient_checkpointing=True,
        caption_extension=".txt",
        shuffle_caption=shuffle_caption,
        save_model_as="safetensors",
        launcher_num_cpu_threads_per_process=1,
    )
    sources.update(
        {
            "server.gradient_checkpointing": "server_policy",
            "server.caption_extension": "server_policy",
            "server.shuffle_caption": shuffle_caption_source,
            "server.save_model_as": "server_policy",
            "server.launcher_num_cpu_threads_per_process": "server_policy",
        }
    )
    effective = EffectiveTrainingRecipeV1(
        model=EffectiveModelRecipe(
            family=family,
            checkpoint=checkpoint,
            allow_unverified_checkpoint=allow_unverified,
            network_module=network_module,
            network_dim=network_dim,
            network_alpha=network_alpha,
            anima=anima,
        ),
        scope=EffectiveScopeRecipe(
            denoiser_kind=denoiser_kind,
            train_denoiser=True,
            train_text_encoder=train_text_encoder,
            native_scope_flag=(
                None if train_text_encoder else "--network_train_unet_only"
            ),
            verification_status="source_contract",
        ),
        dataset=EffectiveDatasetRecipe(
            trigger_token=trigger_token,
            class_tokens=trigger_token,
            resolution=resolution,
            batch_size=batch_size,
            keep_tokens=keep_tokens,
            num_repeats=num_repeats,
            enable_bucket=enable_bucket,
            bucket_no_upscale=bucket_no_upscale,
            min_bucket_reso=min_bucket_reso,
            max_bucket_reso=max_bucket_reso,
            bucket_reso_steps=bucket_reso_steps,
        ),
        optimization=EffectiveOptimizationRecipe(
            epochs=epochs,
            learning_rate=learning_rate,
            denoiser_learning_rate=denoiser_learning_rate,
            text_encoder_learning_rates=text_encoder_learning_rates,
            gradient_accumulation_steps=gradient_accumulation_steps,
            optimizer_type=optimizer_type,
            optimizer_args=tuple(optimizer_args),
            lr_scheduler=lr_scheduler,
            lr_scheduler_args=tuple(lr_scheduler_args),
            warmup=EffectiveWarmup(
                mode=warmup_mode,
                value=warmup_value,
                resolved_steps=step_plan.warmup_steps,
            ),
            seed=seed,
            mixed_precision=mixed_precision,
        ),
        caching=EffectiveCachingRecipe(
            cache_latents=cache_latents,
            cache_text_encoder_outputs=cache_text_encoder_outputs,
            cache_to_disk=cache_to_disk,
            latent_cache_to_disk=latent_cache_to_disk,
            text_encoder_cache_to_disk=text_encoder_cache_to_disk,
        ),
        execution=EffectiveExecutionRecipe(
            max_data_loader_n_workers=workers,
            persistent_data_loader_workers=persistent_workers,
            save_every_n_epochs=save_every_n_epochs,
            final_only=final_only,
        ),
        server=server,
    )
    effective_paths = _effective_leaf_paths(
        effective.model_dump(mode="json", exclude_none=True)
    )
    if set(sources) != effective_paths:
        raise RuntimeError(
            "recipe compiler field-source coverage drift: "
            f"missing={sorted(effective_paths - set(sources))}, "
            f"extra={sorted(set(sources) - effective_paths)}"
        )

    identities = dict(context.component_identities)
    recipe_hash = canonical_recipe_hash(
        effective,
        dataset_hash=context.dataset_hash,
        profile_hash=context.profile_hash,
        component_identities=identities,
    )
    expected_hash = requested.expected_recipe_hash
    if expected_hash is not None and expected_hash != recipe_hash:
        raise RecipeError(
            "recipe_hash_mismatch",
            "training recipe no longer matches its preflight preview",
            "rerun decision preflight and submit its exact start_payload",
            {
                "expected_recipe_hash": expected_hash,
                "current_recipe_hash": recipe_hash,
            },
        )
    evidence = ExecutionEvidence(
        status="unverified",
        reason="source contract only; bounded trainer probe is deferred",
        capability=context.capability,
    )
    return RecipeCompilationResult(
        requested=requested,
        effective=effective,
        field_sources=sources,
        component_identities=identities,
        capability=context.capability,
        step_plan=step_plan,
        recipe_hash=recipe_hash,
        execution_evidence=evidence,
    )
