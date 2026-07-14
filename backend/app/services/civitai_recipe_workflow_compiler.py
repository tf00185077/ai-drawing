"""CIV-D: pure, fail-closed SDXL/Illustrious recipe-to-ComfyUI compiler.

This module deliberately does not inspect disk, call ComfyUI, access a database, or
submit a job.  Resource paths are accepted only after CIV-C supplied a strict,
hash-verified ``ResourceResolutionReport`` lock.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath
from typing import Any, Mapping, NoReturn, cast

from app.schemas.generation_recipe import GenerationRecipe, ResourceKind, ResourceReference
from app.services.civitai_resource_resolution import ResourceResolutionReport
from app.services.civitai_sampling import runtime_sampler_name



@dataclass(frozen=True)
class RecipeCompileError(Exception):
    """Stable, machine-readable failure with no partially compiled workflow."""

    diagnostic: dict[str, str]
    workflow: None = None

    def __str__(self) -> str:
        return self.diagnostic["message"]


@dataclass(frozen=True)
class CompiledRecipeWorkflow:
    workflow: dict[str, dict[str, Any]]
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"workflow": self.workflow, "manifest": self.manifest}


def _fail(code: str, canonical_field: str, message: str) -> NoReturn:
    raise RecipeCompileError({"code": code, "canonical_field": canonical_field, "message": message})


def _kind(value: ResourceKind | str) -> str:
    return value.value if isinstance(value, ResourceKind) else str(value)


def _reference_matches(resource: Any, reference: ResourceReference | None, kind: str) -> bool:
    if reference is None or _kind(reference.kind) != kind:
        return False
    return all(
        getattr(reference, field) is None or getattr(resource, field) == getattr(reference, field)
        for field in ("sha256", "civitai_model_id", "civitai_model_version_id", "civitai_file_id", "air")
    )


def _required_lock_index(recipe: GenerationRecipe, report: ResourceResolutionReport) -> dict[int, dict[str, Any]]:
    if report.strict is not True:
        _fail("resource_report_not_strict", "resource_report.strict", "resource resolution report must be strict")
    if report.ready is not True:
        _fail("resource_report_not_ready", "resource_report.ready", "resource resolution report must be ready")
    locks: dict[int, dict[str, Any]] = {}
    entries: dict[int, Any] = {}
    for entry in report.entries:
        entry_index = getattr(entry, "index", None)
        if not isinstance(entry_index, int):
            _fail("resource_lock_invalid", "resource_report.entries", "resolution entry must contain an integer index")
        index = cast(int, entry_index)
        if index in entries:
            _fail("resource_lock_duplicate", f"resource_report.entries[{index}]", "resolution entry index must be unique")
        entries[index] = entry
    for lock in report.resource_lock:
        if not isinstance(lock, Mapping) or not isinstance(lock.get("index"), int):
            _fail("resource_lock_invalid", "resource_lock", "resource lock entry must contain an integer index")
        index = lock["index"]
        if index in locks:
            _fail("resource_lock_duplicate", f"resource_lock[{index}]", "resource lock index must be unique")
        locks[index] = dict(lock)
    for index, resource in enumerate(recipe.resources):
        lock = locks.get(index)
        if lock is None:
            _fail("resource_lock_missing", f"resources[{index}]", "every recipe resource requires a verified resource lock")
        if lock.get("kind") != resource.kind.value:
            _fail("resource_lock_kind_mismatch", f"resources[{index}]", "resource lock kind does not match recipe resource")
        if not isinstance(lock.get("local_path"), str) or not lock["local_path"]:
            _fail("resource_lock_missing_local_path", f"resources[{index}]", "resource lock requires local_path")
        if resource.sha256 is None or lock.get("sha256") != resource.sha256:
            _fail("resource_lock_unverified_hash", f"resources[{index}]", "resource lock must contain the recipe's verified sha256")
        entry = entries.get(index)
        if entry is None or getattr(entry, "status", None) != "resolved" or getattr(entry, "hash_verified", None) is not True:
            _fail("resource_lock_unverified_hash", f"resources[{index}]", "resource lock must have a hash-verified resolved entry")
        lock_path = cast(str, lock.get("local_path"))
        if getattr(entry, "local_path", None) != lock_path:
            _fail("resource_lock_unverified_hash", f"resources[{index}]", "resource lock path must match its resolved entry")
        actual_identity = getattr(entry, "actual_identity", None)
        if not isinstance(actual_identity, Mapping) or actual_identity.get("actual_sha256") != resource.sha256:
            _fail("resource_lock_unverified_hash", f"resources[{index}]", "resolved entry must attest the recipe sha256")
    if any(index < 0 or index >= len(recipe.resources) for index in locks):
        _fail("resource_lock_unknown", "resource_lock", "resource lock references an unknown recipe resource")
    return locks


class _Graph:
    def __init__(self) -> None:
        self.workflow: dict[str, dict[str, Any]] = {}
        self.bindings: list[dict[str, Any]] = []
        self.field_bindings: list[dict[str, Any]] = []
        self.input_bindings: list[dict[str, Any]] = []

    def node(self, class_type: str, inputs: Mapping[str, Any]) -> str:
        node_id = str(len(self.workflow) + 1)
        self.workflow[node_id] = {"class_type": class_type, "inputs": dict(inputs)}
        return node_id

    def binding(self, canonical_field: str, node_id: str, input_name: str, lock_index: int) -> None:
        self.bindings.append({
            "canonical_field": canonical_field, "node_id": node_id,
            "input_name": input_name, "resource_lock_index": lock_index,
        })

    def field_binding(self, canonical_field: str, node_id: str, input_name: str, value: Any) -> None:
        self.field_bindings.append({
            "canonical_field": canonical_field, "node_id": node_id,
            "input_name": input_name, "value": value,
        })
    def input_binding(self, canonical_field: str, node_id: str, input_name: str, reference: str, sha256: str) -> None:
        self.input_bindings.append({
            "canonical_field": canonical_field, "node_id": node_id, "input_name": input_name,
            "reference": reference, "sha256": sha256,
        })


def _resource_index(recipe: GenerationRecipe, reference: ResourceReference | None, kind: str, field: str) -> int:
    matches = [
        index for index, resource in enumerate(recipe.resources)
        if resource.kind.value == kind and _reference_matches(resource, reference, kind)
    ]
    if len(matches) != 1:
        _fail("resource_reference_unresolved", field, f"{field} must resolve to exactly one {kind} resource")
    return matches[0]


def _complete_sampling(values: Mapping[str, Any], field: str) -> dict[str, Any]:
    missing = [name for name in ("seed", "steps", "cfg", "sampler", "scheduler", "denoise", "width", "height") if values.get(name) is None]
    if missing:
        _fail("sampling_incomplete", field, "sampling requires " + ", ".join(missing))
    return dict(values)


def _resolve_passes(recipe: GenerationRecipe) -> list[tuple[int, Any, dict[str, Any]]]:
    if recipe.sampling is None:
        _fail("sampling_incomplete", "sampling", "recipe sampling is required")
    if not recipe.passes:
        _fail("passes_missing", "passes", "at least one base pass is required")
    resolved: dict[str, dict[str, Any]] = {}
    result: list[tuple[int, Any, dict[str, Any]]] = []
    names = {item.name for item in recipe.passes}
    for index, item in enumerate(recipe.passes):
        field = f"passes[{index}]"
        parent = item.inherits_from
        if parent == "recipe.sampling":
            inherited = recipe.sampling.model_dump(exclude_none=True)
        elif parent is None:
            inherited = {}
        elif parent not in names:
            _fail("pass_inheritance_unknown", f"{field}.inherits_from", "pass inheritance target is unknown")
        elif parent not in resolved:
            _fail("pass_inheritance_cycle", f"{field}.inherits_from", "pass inheritance must be ordered and acyclic")
        else:
            inherited = resolved[parent]
        values = {**inherited, **item.sampling.model_dump(exclude_none=True)}
        resolved[item.name] = _complete_sampling(values, f"{field}.sampling")
        result.append((index, item, resolved[item.name]))
    return result


def _input_binding(input_bindings: Mapping[str, Any], reference: str, expected_sha: str, field: str) -> str:
    binding = input_bindings.get(reference)
    if binding is None:
        _fail("input_binding_missing", field, "recipe input has no ComfyUI filename binding")
    if isinstance(binding, str):
        _fail("input_binding_sha_missing", field, "input binding must include filename and sha256")
    if not isinstance(binding, Mapping):
        _fail("input_binding_invalid", field, "input binding must be a mapping")
    filename = binding.get("filename")
    if not isinstance(filename, str) or not filename:
        _fail("input_binding_invalid", field, "input binding filename must be non-empty")
    if binding.get("sha256") != expected_sha:
        _fail("input_sha_mismatch", field, "input binding sha256 does not match recipe input")
    return filename


def compile_generation_recipe_workflow(
    recipe: GenerationRecipe,
    resource_report: ResourceResolutionReport,
    *,
    model_family: str,
    input_bindings: Mapping[str, Any],
) -> CompiledRecipeWorkflow:
    """Compile only the explicitly contracted SDXL/Illustrious ComfyUI API graph."""
    if model_family not in {"sdxl", "illustrious"}:
        _fail("unsupported_model_family", "model_family", "only sdxl and illustrious are supported")
    locks = _required_lock_index(recipe, resource_report)
    passes = _resolve_passes(recipe)
    # These source-model labels are schema-valid audit metadata, but this frozen
    # graph contract has no separate node input for them.  The resource reference
    # is the only supported model selector, so never silently discard a label.
    for index, control in enumerate(recipe.controls):
        if control.model is not None:
            _fail("unsupported_operation", f"controls[{index}].model", "control model has no CIV-D node contract")
    for index, detailer in enumerate(recipe.detailers):
        if detailer.model is not None:
            _fail("unsupported_operation", f"detailers[{index}].model", "detailer model has no CIV-D node contract")
    for index, postprocess in enumerate(recipe.postprocess):
        if postprocess.model is not None:
            _fail("unsupported_operation", f"postprocess[{index}].model", "postprocess model has no CIV-D node contract")
    for pass_index, generation_pass, _sampling in passes:
        if generation_pass.upscale_model is not None:
            _fail("unsupported_operation", f"passes[{pass_index}].upscale_model", "upscale_model has no CIV-D node contract")
    checkpoint_indexes = [i for i, r in enumerate(recipe.resources) if r.kind is ResourceKind.CHECKPOINT]
    if len(checkpoint_indexes) != 1:
        _fail("resource_reference_unresolved", "resources", "exactly one checkpoint resource is required")

    graph = _Graph()
    checkpoint_index = checkpoint_indexes[0]
    checkpoint_lock_path = cast(str, locks[checkpoint_index]["local_path"])
    checkpoint_filename = PurePath(checkpoint_lock_path).name
    checkpoint_node = graph.node("CheckpointLoaderSimple", {"ckpt_name": checkpoint_filename})
    graph.binding(f"resources[{checkpoint_index}]", checkpoint_node, "ckpt_name", checkpoint_index)
    model_link: list[Any] = [checkpoint_node, 0]
    clip_link: list[Any] = [checkpoint_node, 1]

    clip_skips = [(index, resource.clip_skip) for index, resource in enumerate(recipe.resources)
                  if resource.kind is ResourceKind.LORA and resource.clip_skip is not None]
    if len({clip_skip for _, clip_skip in clip_skips}) > 1:
        _fail("unsupported_operation", "resources", "multiple distinct clip_skip values cannot be expressed by this contract")
    for resource_index, resource in enumerate(recipe.resources):
        if resource.kind is not ResourceKind.LORA:
            continue
        if resource.strength_model is None or resource.strength_clip is None:
            _fail("unsupported_operation", f"resources[{resource_index}]", "LoRA requires explicit model and clip strengths")
        node = graph.node("LoraLoader", {
            "model": model_link, "clip": clip_link, "lora_name": resource.name,
            "strength_model": resource.strength_model, "strength_clip": resource.strength_clip,
        })
        graph.binding(f"resources[{resource_index}]", node, "lora_name", resource_index)
        model_link, clip_link = [node, 0], [node, 1]
    if clip_skips:
        clip_skip_index, clip_skip = clip_skips[0]
        node = graph.node("CLIPSetLastLayer", {"clip": clip_link, "stop_at_clip_layer": -clip_skip})
        graph.field_binding(f"resources[{clip_skip_index}].clip_skip", node, "stop_at_clip_layer", -clip_skip)
        clip_link = [node, 0]

    positive = recipe.base_prompt
    negative = recipe.negative_prompt
    if not isinstance(positive, str) or not isinstance(negative, str):
        _fail("conditioning_missing", "base_prompt", "positive and negative prompts are required")
    embeddings = [(index, r) for index, r in enumerate(recipe.resources) if r.kind is ResourceKind.EMBEDDING]
    if embeddings:
        tokens = " ".join(f"embedding:{item.name}" for _, item in embeddings)
        positive = f"{positive}, {tokens}"
    positive_node = graph.node("CLIPTextEncode", {"clip": clip_link, "text": positive})
    # Embeddings are ComfyUI prompt tokens, rather than loader nodes.  Their locked
    # resource identity is therefore bound to the exact text-conditioning input.
    for resource_index, _ in embeddings:
        graph.binding(f"resources[{resource_index}]", positive_node, "text", resource_index)
    negative_node = graph.node("CLIPTextEncode", {"clip": clip_link, "text": negative})

    positive_link: list[Any] = [positive_node, 0]
    negative_link: list[Any] = [negative_node, 0]
    inputs_by_reference: dict[str, list[Any]] = {}
    for recipe_input in recipe.inputs:
        inputs_by_reference.setdefault(recipe_input.reference, []).append(recipe_input)
    for index, control in enumerate(recipe.controls):
        field = f"controls[{index}]"
        if control.kind.strip().lower() != "controlnet" or control.resource is None or control.input_ref is None:
            _fail("unsupported_operation", field, "only resource-bound controlnet controls are supported")
        source_matches = inputs_by_reference.get(control.input_ref, [])
        if not source_matches:
            _fail("input_reference_unknown", f"{field}.input_ref", "control input_ref is not declared by recipe.inputs")
        if len(source_matches) != 1:
            _fail("input_reference_unresolved", f"{field}.input_ref", "control input_ref must resolve to exactly one recipe input")
        source = source_matches[0]
        filename = _input_binding(input_bindings, source.reference, source.sha256, f"{field}.input_ref")
        image = graph.node("LoadImage", {"image": filename})
        graph.input_binding(f"{field}.input_ref", image, "image", source.reference, source.sha256)
        image_link: list[Any] = [image, 0]
        if control.preprocessor is not None:
            if control.preprocessor.strip().lower() not in {"dwpreprocessor", "dw_preprocessor"}:
                _fail("unsupported_operation", f"{field}.preprocessor", "preprocessor has no CIV-D node contract")
            prep = graph.node("DWPreprocessor", {"image": image_link, "resolution": 1024, "bbox_detector": "yolo_nas_s_fp16.onnx"})
            image_link = [prep, 0]
        resource_index = _resource_index(recipe, control.resource, "controlnet", f"{field}.resource")
        control_node = graph.node("ControlNetLoader", {"control_net_name": recipe.resources[resource_index].name})
        graph.binding(f"{field}.resource", control_node, "control_net_name", resource_index)
        apply = graph.node("ControlNetApplyAdvanced", {
            "positive": positive_link, "negative": negative_link, "control_net": [control_node, 0], "image": image_link,
            "strength": 1.0 if control.weight is None else control.weight,
            "start_percent": 0.0 if control.start_percent is None else control.start_percent,
            "end_percent": 1.0 if control.end_percent is None else control.end_percent,
        })
        positive_link, negative_link = [apply, 0], [apply, 1]
        for canonical_name, input_name, value in (
            ("weight", "strength", control.weight),
            ("start_percent", "start_percent", control.start_percent),
            ("end_percent", "end_percent", control.end_percent),
        ):
            if value is not None:
                graph.field_binding(f"{field}.{canonical_name}", apply, input_name, value)

    vae_indexes = [i for i, r in enumerate(recipe.resources) if r.kind is ResourceKind.VAE]
    if len(vae_indexes) > 1:
        _fail("resource_reference_unresolved", "resources", "at most one independent VAE is supported")
    vae_link: list[Any] = [checkpoint_node, 2]
    if vae_indexes:
        vae_index = vae_indexes[0]
        vae_node = graph.node("VAELoader", {"vae_name": recipe.resources[vae_index].name})
        graph.binding(f"resources[{vae_index}]", vae_node, "vae_name", vae_index)
        vae_link = [vae_node, 0]

    sampler_link: list[Any] | None = None
    for pass_index, generation_pass, sampling in passes:
        field = f"passes[{pass_index}]"
        if pass_index == 0:
            for unsupported_field in ("scale", "upscale_model", "upscale_resource"):
                if getattr(generation_pass, unsupported_field) is not None:
                    _fail(
                        "unsupported_operation", f"{field}.{unsupported_field}",
                        "base pass upscale fields have no CIV-D node contract",
                    )
        if pass_index == 0:
            latent_node = graph.node("EmptyLatentImage", {"width": sampling["width"], "height": sampling["height"], "batch_size": 1})
            graph.field_binding(f"{field}.sampling.width", latent_node, "width", sampling["width"])
            graph.field_binding(f"{field}.sampling.height", latent_node, "height", sampling["height"])
            latent_link = [latent_node, 0]
        else:
            if sampler_link is None or generation_pass.scale is None or generation_pass.upscale_resource is None:
                _fail("unsupported_operation", field, "follow-up pass requires scale, upscale_resource, and prior pass")
            upscale_index = _resource_index(recipe, generation_pass.upscale_resource, "upscaler", f"{field}.upscale_resource")
            loader = graph.node("UpscaleModelLoader", {"model_name": recipe.resources[upscale_index].name})
            graph.binding(f"{field}.upscale_resource", loader, "model_name", upscale_index)
            decoded_pass = graph.node("VAEDecode", {"samples": sampler_link, "vae": vae_link})
            model_upscale = graph.node("ImageUpscaleWithModel", {
                "upscale_model": [loader, 0], "image": [decoded_pass, 0],
            })
            scaled = graph.node("ImageScaleBy", {
                "image": [model_upscale, 0], "upscale_method": "lanczos", "scale_by": generation_pass.scale,
            })
            graph.field_binding(f"{field}.scale", scaled, "scale_by", generation_pass.scale)
            resized = graph.node("ImageScale", {
                "image": [scaled, 0], "upscale_method": "lanczos", "width": sampling["width"],
                "height": sampling["height"], "crop": "disabled",
            })
            graph.field_binding(f"{field}.sampling.width", resized, "width", sampling["width"])
            graph.field_binding(f"{field}.sampling.height", resized, "height", sampling["height"])
            encoded_pass = graph.node("VAEEncode", {"pixels": [resized, 0], "vae": vae_link})
            latent_link = [encoded_pass, 0]
        runtime_sampler = runtime_sampler_name(sampling["sampler"])
        sampler = graph.node("KSampler", {
            "model": model_link, "positive": positive_link, "negative": negative_link, "latent_image": latent_link,
            "seed": sampling["seed"], "steps": sampling["steps"], "cfg": sampling["cfg"],
            "sampler_name": runtime_sampler, "scheduler": sampling["scheduler"], "denoise": sampling["denoise"],
        })
        sampler_link = [sampler, 0]
        for sampling_field, input_name in (
            ("seed", "seed"), ("steps", "steps"), ("cfg", "cfg"),
            ("sampler", "sampler_name"), ("scheduler", "scheduler"), ("denoise", "denoise"),
        ):
            graph.field_binding(
                f"{field}.sampling.{sampling_field}", sampler, input_name,
                runtime_sampler if sampling_field == "sampler" else sampling[sampling_field]
            )

    assert sampler_link is not None
    decoded = graph.node("VAEDecode", {"samples": sampler_link, "vae": vae_link})
    image_link: list[Any] = [decoded, 0]
    for index, detailer in enumerate(recipe.detailers):
        field = f"detailers[{index}]"
        if detailer.kind.strip().lower() not in {"detailer", "face"} or detailer.resource is None:
            _fail("unsupported_operation", field, "detailer has no CIV-D node contract")
        if detailer.prompt is not None:
            _fail("unsupported_operation", f"{field}.prompt", "detailer prompt has no CIV-D node contract")
        if detailer.negative_prompt is not None:
            _fail("unsupported_operation", f"{field}.negative_prompt", "detailer negative_prompt has no CIV-D node contract")
        resource_index = _resource_index(recipe, detailer.resource, "detailer", f"{field}.resource")
        detector = graph.node("UltralyticsDetectorProvider", {"model_name": recipe.resources[resource_index].name})
        graph.binding(f"{field}.resource", detector, "model_name", resource_index)
        detail = graph.node("Detailer", {"image": image_link, "detector": [detector, 0], "denoise": detailer.denoise if detailer.denoise is not None else 0.5})
        if detailer.denoise is not None:
            graph.field_binding(f"{field}.denoise", detail, "denoise", detailer.denoise)
        image_link = [detail, 0]
    for index, post in enumerate(recipe.postprocess):
        field = f"postprocess[{index}]"
        if post.params:
            _fail("unsupported_operation", f"{field}.params", "postprocess params have no CIV-D node contract")
        normalized = post.kind.strip().lower()
        if normalized == "upscale" and post.resource is not None and post.scale is not None:
            resource_index = _resource_index(recipe, post.resource, "upscaler", f"{field}.resource")
            loader = graph.node("UpscaleModelLoader", {"model_name": recipe.resources[resource_index].name})
            graph.binding(f"{field}.resource", loader, "model_name", resource_index)
            upscale = graph.node("ImageUpscaleWithModel", {"upscale_model": [loader, 0], "image": image_link})
            scaled = graph.node("ImageScaleBy", {
                "image": [upscale, 0], "upscale_method": "lanczos", "scale_by": post.scale,
            })
            graph.field_binding(f"{field}.scale", scaled, "scale_by", post.scale)
            image_link = [scaled, 0]
        elif normalized in {"face_restore", "face-restore"} and post.resource is not None:
            resource_index = _resource_index(recipe, post.resource, "detailer", f"{field}.resource")
            restore = graph.node("FaceRestore", {"image": image_link, "model_name": recipe.resources[resource_index].name})
            graph.binding(f"{field}.resource", restore, "model_name", resource_index)
            image_link = [restore, 0]
        else:
            _fail("unsupported_operation", field, "postprocess has no CIV-D node contract")
    graph.node("SaveImage", {"images": image_link, "filename_prefix": "civitai_recipe"})
    manifest = {
        "model_family": model_family,
        "bindings": graph.bindings,
        "field_bindings": graph.field_bindings,
        "input_bindings": graph.input_bindings,
    }
    return CompiledRecipeWorkflow(workflow=graph.workflow, manifest=manifest)


# Public aliases keep the service discoverable without coupling callers to a short name.
compile_recipe_workflow = compile_generation_recipe_workflow
compile_recipe = compile_generation_recipe_workflow
