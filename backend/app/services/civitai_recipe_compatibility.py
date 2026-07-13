"""CIV-V-E pure, fail-closed compatibility decision; it never compiles or executes."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.schemas.generation_recipe import GenerationRecipe
from app.services.civitai_acquisition import redact_secrets

CONTRACT = "civ-v-e:sdxl-illustrious-comfyui-v1"
_BASE_NODES = {"CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"}
_KIND_NODES = {
    "checkpoint": {"CheckpointLoaderSimple"}, "lora": {"LoraLoader"}, "vae": {"VAELoader"},
    "embedding": {"CLIPTextEncode"}, "controlnet": {"ControlNetLoader", "ControlNetApplyAdvanced", "LoadImage"},
    "upscaler": {"UpscaleModelLoader", "ImageUpscaleWithModel", "ImageScaleBy"},
    "detailer": {"UltralyticsDetectorProvider", "Detailer"},
}
_SUPPORTED_KINDS = frozenset(_KIND_NODES)


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _diag(code: str, field: str, message: str) -> dict[str, str]:
    return {"canonical_field": field, "code": code, "message": message}


def _family(value: Any) -> str | None:
    """Accept only audited family evidence and return its canonical vocabulary value."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    return normalized if normalized in {"sdxl", "illustrious"} else None


def _snapshot_errors(snapshot: Any) -> tuple[list[dict[str, str]], set[str], set[str], set[str], str | None]:
    errors: list[dict[str, str]] = []
    if not isinstance(snapshot, Mapping):
        return [_diag("runtime_snapshot_malformed", "runtime_capabilities", "runtime capability snapshot must be an object")], set(), set(), set(), None
    engine, version = snapshot.get("engine"), snapshot.get("engine_version")
    if engine != "comfyui": errors.append(_diag("runtime_engine_unsupported", "runtime_capabilities.engine", "engine must be comfyui"))
    if not isinstance(version, str) or not version.strip(): errors.append(_diag("runtime_snapshot_malformed", "runtime_capabilities.engine_version", "engine_version must be non-empty"))
    normalized: dict[str, list[str]] = {}
    for field in ("node_types", "sampler_names", "scheduler_names"):
        value = snapshot.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            errors.append(_diag("runtime_snapshot_malformed", f"runtime_capabilities.{field}", f"{field} must be a list of non-empty strings")); normalized[field] = []
        elif value != sorted(set(value)):
            errors.append(_diag("runtime_snapshot_not_canonical", f"runtime_capabilities.{field}", f"{field} must be sorted and unique")); normalized[field] = value
        else: normalized[field] = value
    document = {key: snapshot.get(key) for key in ("engine", "engine_version", "node_types", "sampler_names", "scheduler_names")}
    supplied = snapshot.get("snapshot_sha256")
    digest = hashlib.sha256(_canonical(document).encode()).hexdigest()
    if not isinstance(supplied, str) or supplied != digest:
        errors.append(_diag("runtime_snapshot_hash_mismatch", "runtime_capabilities.snapshot_sha256", "snapshot_sha256 does not match canonical capabilities"))
    return errors, set(normalized["node_types"]), set(normalized["sampler_names"]), set(normalized["scheduler_names"]), supplied if isinstance(supplied, str) else None


def preflight_recipe_compatibility(recipe: GenerationRecipe, resource_report: Mapping[str, Any], *, requested_model_family: str, runtime_capabilities: Mapping[str, Any]) -> dict[str, Any]:
    """Return structured compatibility data only; no IO, compiler, queue, DB, or mutation."""
    diagnostics: list[dict[str, str]] = []
    if requested_model_family not in {"sdxl", "illustrious"}:
        diagnostics.append(_diag("unsupported_model_family", "model_family", "only sdxl and illustrious are supported"))
    snapshot_errors, node_types, samplers, schedulers, snapshot_digest = _snapshot_errors(runtime_capabilities)
    diagnostics.extend(snapshot_errors)
    report = resource_report if isinstance(resource_report, Mapping) else {}
    if report.get("strict") is not True: diagnostics.append(_diag("resource_report_not_strict", "resource_report.strict", "report.strict must be true"))
    if report.get("ready") is not True: diagnostics.append(_diag("resource_report_not_ready", "resource_report.ready", "report.ready must be true"))
    raw_entries, raw_locks = report.get("entries"), report.get("resource_lock")
    entries = raw_entries if isinstance(raw_entries, list) else []
    locks = raw_locks if isinstance(raw_locks, list) else []
    if not isinstance(raw_entries, list): diagnostics.append(_diag("resolution_entries_malformed", "resource_report.entries", "entries must be a list"))
    if not isinstance(raw_locks, list): diagnostics.append(_diag("resource_locks_malformed", "resource_report.resource_lock", "resource_lock must be a list"))
    entry_by_index: dict[int, Mapping[str, Any]] = {}
    lock_by_index: dict[int, Mapping[str, Any]] = {}
    for collection, destination, duplicate_code, field in ((entries, entry_by_index, "resolution_entry_duplicate", "resource_report.entries"), (locks, lock_by_index, "resource_lock_duplicate", "resource_report.resource_lock")):
        for item in collection:
            index = item.get("index") if isinstance(item, Mapping) else None
            if not isinstance(index, int): diagnostics.append(_diag("resolution_item_malformed", field, "every item requires integer index")); continue
            if index in destination: diagnostics.append(_diag(duplicate_code, f"{field}[{index}]", "resource index must be unique")); continue
            destination[index] = item
    decisions: list[dict[str, Any]] = []
    checkpoint_indices = []
    required_nodes = set(_BASE_NODES)
    lora_clip_skips = {
        resource.clip_skip for resource in recipe.resources
        if resource.kind.value == "lora" and resource.clip_skip is not None
    }
    for index, resource in enumerate(recipe.resources):
        kind, sha = resource.kind.value, resource.sha256
        if kind == "checkpoint": checkpoint_indices.append(index)
        required = sorted(_KIND_NODES.get(kind, set()))
        required_nodes.update(required)
        entry, lock = entry_by_index.get(index), lock_by_index.get(index)
        reasons: list[dict[str, str]] = []
        if kind not in _SUPPORTED_KINDS: reasons.append(_diag("unsupported_resource_kind", f"resources[{index}].kind", "resource kind is not expressible by compiler"))
        if kind == "lora" and (resource.strength_model is None or resource.strength_clip is None):
            reasons.append(_diag("unsupported_operation", f"resources[{index}]", "LoRA requires explicit model and clip strengths"))
        if entry is None:
            reasons.append(_diag("resource_entry_missing", f"resources[{index}]", "matching entry is required"))
        else:
            if entry.get("index") != index:
                reasons.append(_diag("resource_entry_index_mismatch", f"resources[{index}]", "entry index must match recipe"))
            if entry.get("expected_identity", {}).get("sha256") != sha:
                reasons.append(_diag("resource_entry_sha_mismatch", f"resources[{index}]", "entry sha256 must match recipe"))
            if not isinstance(entry.get("local_path"), str) or not entry.get("local_path"):
                reasons.append(_diag("resource_entry_path_missing", f"resources[{index}]", "entry local_path is required"))
        if lock is None:
            reasons.append(_diag("resource_lock_missing", f"resources[{index}]", "matching lock is required"))
        else:
            if lock.get("kind") != kind:
                reasons.append(_diag("resource_lock_kind_mismatch", f"resources[{index}]", "lock kind must match recipe"))
            if lock.get("sha256") != sha or not isinstance(sha, str):
                reasons.append(_diag("resource_lock_sha_mismatch", f"resources[{index}]", "lock sha256 must match recipe"))
            if not isinstance(lock.get("local_path"), str) or not lock.get("local_path"):
                reasons.append(_diag("resource_lock_path_missing", f"resources[{index}]", "lock local_path is required"))
            if entry is not None and lock.get("local_path") != entry.get("local_path"):
                reasons.append(_diag("resource_lock_path_mismatch", f"resources[{index}]", "lock and entry local_path must match"))
        if entry is not None and (entry.get("status") != "resolved" or entry.get("hash_verified") is not True or not isinstance(entry.get("actual_identity"), Mapping) or entry["actual_identity"].get("actual_sha256") != sha):
            reasons.append(_diag("resource_entry_unverified", f"resources[{index}]", "entry must be hash-verified resolved identity"))
        # Family evidence can only originate in the verified resolution record/lock;
        # display names and recipe paths are never evidence.  Canonicalize every
        # supplied audited assertion before checking disagreement.
        raw_families = [lock.get("model_family")] if lock is not None else []
        if entry is not None and isinstance(entry.get("actual_identity"), Mapping):
            raw_families.append(entry["actual_identity"].get("model_family"))
        supplied_families = [value for value in raw_families if value is not None]
        normalized_families = [_family(value) for value in supplied_families]
        normalized_family = None
        if any(value is None for value in normalized_families):
            reasons.append(_diag("unknown_model_family", f"resources[{index}]", "audited checkpoint/LoRA family evidence is unrecognized"))
        elif normalized_families and len(set(normalized_families)) != 1:
            reasons.append(_diag("model_family_conflict", f"resources[{index}]", "audited family evidence conflicts"))
        elif normalized_families:
            normalized_family = normalized_families[0]
        if kind in {"checkpoint", "lora"} and normalized_family is None and not any(reason["code"] == "unknown_model_family" for reason in reasons):
            reasons.append(_diag("unknown_model_family", f"resources[{index}]", "audited checkpoint/LoRA family evidence is required"))
        if kind in {"checkpoint", "lora"} and normalized_family is not None and normalized_family != requested_model_family: reasons.append(_diag("model_family_mismatch", f"resources[{index}]", "audited family must equal requested family"))
        local_path = lock.get("local_path") if isinstance(lock, Mapping) else None
        decisions.append({"recipe_index": index, "kind": kind, "sha256": sha, "resolved_local_identity": {"local_path": local_path}, "declared_model_family": normalized_family or "unknown", "required_node_types": required, "compatible": not reasons, "diagnostics": reasons})
        diagnostics.extend(reasons)
    if len(lora_clip_skips) > 1:
        clip_skip_diagnostic = _diag("unsupported_operation", "resources", "multiple distinct clip_skip values cannot be expressed by this contract")
        diagnostics.append(clip_skip_diagnostic)
        for decision in decisions:
            if decision["kind"] == "lora" and recipe.resources[decision["recipe_index"]].clip_skip is not None:
                decision["compatible"] = False
                decision["diagnostics"].append(clip_skip_diagnostic)
    if lora_clip_skips:
        required_nodes.add("CLIPSetLastLayer")
    if len(checkpoint_indices) != 1: diagnostics.append(_diag("checkpoint_cardinality", "resources", "exactly one checkpoint is required"))
    if sum(resource.kind.value == "vae" for resource in recipe.resources) > 1:
        diagnostics.append(_diag("resource_cardinality", "resources", "at most one VAE is expressible by compiler contract"))
    for index in set(entry_by_index) | set(lock_by_index):
        if index < 0 or index >= len(recipe.resources): diagnostics.append(_diag("resource_report_unknown_index", "resource_report", "report may not contain extra resource indexes"))
    # Compiler graph features that are present in the canonical recipe add their node contracts.
    if recipe.controls: required_nodes.update({"ControlNetLoader", "ControlNetApplyAdvanced", "LoadImage"})
    if recipe.detailers: required_nodes.update({"UltralyticsDetectorProvider", "Detailer"})
    if len(recipe.passes) > 1:
        required_nodes.update({"UpscaleModelLoader", "ImageUpscaleWithModel", "ImageScaleBy", "ImageScale", "VAEEncode"})
    for index, control in enumerate(recipe.controls):
        if control.kind.strip().casefold() != "controlnet" or control.resource is None or control.input_ref is None:
            diagnostics.append(_diag("unsupported_operation", f"controls[{index}]", "only resource-bound controlnet is expressible"))
        if control.model is not None:
            diagnostics.append(_diag("unsupported_operation", f"controls[{index}].model", "control model has no compiler node contract"))
        if control.preprocessor is not None and control.preprocessor.strip().casefold() not in {"dwpreprocessor", "dw_preprocessor"}:
            diagnostics.append(_diag("unsupported_operation", f"controls[{index}].preprocessor", "preprocessor has no compiler node contract"))
        if control.preprocessor is not None and control.preprocessor.strip().casefold() in {"dwpreprocessor", "dw_preprocessor"}:
            required_nodes.add("DWPreprocessor")
    for index, detailer in enumerate(recipe.detailers):
        if detailer.kind.strip().casefold() not in {"detailer", "face"} or detailer.resource is None or detailer.prompt is not None or detailer.negative_prompt is not None:
            diagnostics.append(_diag("unsupported_operation", f"detailers[{index}]", "detailer operation has no complete compiler contract"))
        if detailer.model is not None:
            diagnostics.append(_diag("unsupported_operation", f"detailers[{index}].model", "detailer model has no compiler node contract"))
    for index, post in enumerate(recipe.postprocess):
        normalized = post.kind.strip().casefold()
        if post.params or not ((normalized == "upscale" and post.resource is not None and post.scale is not None) or (normalized in {"face_restore", "face-restore"} and post.resource is not None)):
            diagnostics.append(_diag("unsupported_operation", f"postprocess[{index}]", "postprocess has no compiler node contract"))
        if post.model is not None:
            diagnostics.append(_diag("unsupported_operation", f"postprocess[{index}].model", "postprocess model has no compiler node contract"))
        if normalized == "upscale" and post.resource is not None and post.scale is not None:
            required_nodes.update({"UpscaleModelLoader", "ImageUpscaleWithModel", "ImageScaleBy"})
        if normalized in {"face_restore", "face-restore"} and post.resource is not None:
            required_nodes.add("FaceRestore")
    resolved_sampling: dict[str, Mapping[str, Any]] = {}
    recipe_sampling = recipe.sampling.model_dump(exclude_none=True) if recipe.sampling is not None else {}
    if recipe.sampling is None:
        diagnostics.append(_diag("sampling_incomplete", "sampling", "recipe sampling is required"))
    if not recipe.passes:
        diagnostics.append(_diag("passes_missing", "passes", "at least one base pass is required"))
    pass_names = {item.name for item in recipe.passes}
    for pass_index, generation_pass in enumerate(recipe.passes):
        if generation_pass.upscale_model is not None:
            diagnostics.append(_diag("unsupported_operation", f"passes[{pass_index}].upscale_model", "upscale_model has no CIV-D node contract"))
        if pass_index == 0:
            for field in ("scale", "upscale_model", "upscale_resource"):
                if getattr(generation_pass, field) is not None:
                    diagnostics.append(_diag("unsupported_operation", f"passes[{pass_index}].{field}", "base pass upscale fields have no CIV-D node contract"))
        parent = generation_pass.inherits_from
        if parent == "recipe.sampling": inherited = recipe_sampling
        elif parent is None: inherited = {}
        elif parent not in pass_names or parent not in resolved_sampling:
            diagnostics.append(_diag("unsupported_operation", f"passes[{pass_index}].inherits_from", "pass inheritance must be ordered and resolvable")); inherited = {}
        else: inherited = resolved_sampling[parent]
        values = {**inherited, **generation_pass.sampling.model_dump(exclude_none=True)}
        resolved_sampling[generation_pass.name] = values
        sampler, scheduler = values.get("sampler"), values.get("scheduler")
        if not isinstance(sampler, str) or sampler not in samplers: diagnostics.append(_diag("runtime_sampler_missing", f"passes[{pass_index}].sampling.sampler", "sampler is not in runtime snapshot"))
        if not isinstance(scheduler, str) or scheduler not in schedulers: diagnostics.append(_diag("runtime_scheduler_missing", f"passes[{pass_index}].sampling.scheduler", "scheduler is not in runtime snapshot"))
    for node in sorted(required_nodes - node_types): diagnostics.append(_diag("runtime_node_missing", "runtime_capabilities.node_types", f"required node type missing: {node}"))
    diagnostics = sorted(redact_secrets(diagnostics), key=lambda item: (item["canonical_field"], item["code"], item["message"]))
    for decision in decisions: decision["diagnostics"] = sorted(redact_secrets(decision["diagnostics"]), key=lambda item: (item["canonical_field"], item["code"], item["message"]))
    compatible = not diagnostics
    return redact_secrets({"status": "compatible" if compatible else "incompatible", "compatible": compatible, "requested_model_family": requested_model_family, "compiler_contract": CONTRACT, "runtime_snapshot_sha256": snapshot_digest, "resources": decisions, "diagnostics": diagnostics})
