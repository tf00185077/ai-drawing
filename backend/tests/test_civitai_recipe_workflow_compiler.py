"""CIV-D pure, deterministic Civitai recipe workflow compiler contract tests."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app.schemas.generation_recipe import GenerationRecipe
from app.services.civitai_resource_resolution import ResolutionEntry, ResourceResolutionReport
from app.services.civitai_recipe_workflow_compiler import (
    RecipeCompileError,
    compile_generation_recipe_workflow,
)

SHA = {name: name * 64 for name in "abcdef"}


def _recipe(*, extras: bool = False) -> GenerationRecipe:
    resources = [
        {"kind": "checkpoint", "name": "base.safetensors", "sha256": SHA["a"]},
    ]
    payload: dict = {
        "source": {"image_id": 1},
        "base_prompt": "positive",
        "negative_prompt": "negative",
        "resources": resources,
        "sampling": {
            "seed": 42, "steps": 30, "cfg": 6.5, "sampler": "euler",
            "scheduler": "normal", "denoise": 1.0, "width": 1024, "height": 768,
        },
        "passes": [{"name": "base", "inherits_from": "recipe.sampling"}],
    }
    if extras:
        resources.extend([
            {"kind": "vae", "name": "clearvae.safetensors", "sha256": SHA["b"]},
            {"kind": "embedding", "name": "badhand.pt", "sha256": SHA["c"]},
            {"kind": "lora", "name": "one.safetensors", "sha256": SHA["d"], "strength_model": .7, "strength_clip": .4, "clip_skip": 2},
            {"kind": "lora", "name": "two.safetensors", "sha256": SHA["e"], "strength_model": .8, "strength_clip": .5},
            {"kind": "lora", "name": "three.safetensors", "sha256": SHA["f"], "strength_model": .9, "strength_clip": .6},
        ])
        payload["passes"].append({
            "name": "hires", "inherits_from": "base", "scale": 1.5,
            "sampling": {"steps": 12, "denoise": .35, "width": 1536, "height": 1152},
            "upscale_resource": {"kind": "upscaler", "sha256": "1" * 64},
        })
        resources.append({"kind": "upscaler", "name": "4x.pth", "sha256": "1" * 64})
    return GenerationRecipe.model_validate(payload)


def _report(recipe: GenerationRecipe, *, strict: bool = True, ready: bool = True) -> ResourceResolutionReport:
    locks = [
        {"index": index, "kind": item.kind.value, "local_path": f"/models/{item.name}", "sha256": item.sha256}
        for index, item in enumerate(recipe.resources)
    ]
    return ResourceResolutionReport(
        strict=strict,
        ready=ready,
        entries=[
            ResolutionEntry(
                index=lock["index"], status="resolved", matched_by=["sha256"],
                expected_identity={"sha256": lock["sha256"]},
                actual_identity={"actual_sha256": lock["sha256"]},
                local_path=lock["local_path"], diagnostics={"hash_verified": True}, hash_verified=True,
            )
            for lock in locks
        ],
        resource_lock=locks,
    )


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _node_id(nodes: dict[str, dict], class_type: str) -> str:
    return next(node_id for node_id, node in nodes.items() if node["class_type"] == class_type)


def _ancestors(nodes: dict[str, dict], node_id: str) -> set[str]:
    """Return every node reachable upstream through ComfyUI API links."""
    result: set[str] = set()
    pending = [node_id]
    while pending:
        current = pending.pop()
        for value in nodes[current]["inputs"].values():
            if not (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)):
                continue
            parent = value[0]
            if parent not in result:
                result.add(parent)
                pending.append(parent)
    return result


@pytest.mark.parametrize("model_family", ["sdxl", "illustrious"])
def test_base_graph_is_a_serializable_checkpoint_conditioning_sample_decode_save_path(model_family: str) -> None:
    recipe = _recipe()
    result = compile_generation_recipe_workflow(recipe, _report(recipe), model_family=model_family, input_bindings={})

    assert json.loads(json.dumps(result.workflow)) == result.workflow
    classes = [node["class_type"] for node in result.workflow.values()]
    assert classes == ["CheckpointLoaderSimple", "CLIPTextEncode", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"]
    sampler = next(node for node in result.workflow.values() if node["class_type"] == "KSampler")
    assert sampler["inputs"] == {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": 42, "steps": 30, "cfg": 6.5, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}
    assert result.manifest["bindings"][0] == {"canonical_field": "resources[0]", "node_id": "1", "input_name": "ckpt_name", "resource_lock_index": 0}
    expected_sampling_bindings = {
        ("passes[0].sampling.seed", "5", "seed", 42),
        ("passes[0].sampling.steps", "5", "steps", 30),
        ("passes[0].sampling.cfg", "5", "cfg", 6.5),
        ("passes[0].sampling.sampler", "5", "sampler_name", "euler"),
        ("passes[0].sampling.scheduler", "5", "scheduler", "normal"),
        ("passes[0].sampling.denoise", "5", "denoise", 1.0),
        ("passes[0].sampling.width", "4", "width", 1024),
        ("passes[0].sampling.height", "4", "height", 768),
    }
    actual_sampling_bindings = {
        (item["canonical_field"], item["node_id"], item["input_name"], item["value"])
        for item in result.manifest["field_bindings"]
    }
    assert expected_sampling_bindings <= actual_sampling_bindings


def test_compilation_is_deterministic_and_does_not_mutate_inputs() -> None:
    recipe = _recipe(extras=True)
    report = _report(recipe)
    recipe_before, report_before = deepcopy(recipe), deepcopy(report)
    first = compile_generation_recipe_workflow(recipe, report, model_family="sdxl", input_bindings={})
    second = compile_generation_recipe_workflow(recipe, report, model_family="sdxl", input_bindings={})

    assert _canonical(first.workflow) == _canonical(second.workflow)
    assert _canonical(first.manifest) == _canonical(second.manifest)
    assert recipe == recipe_before and report == report_before


def test_clip_skip_embedding_ordered_dual_weight_loras_and_hires_are_explicit() -> None:
    recipe = _recipe(extras=True)
    result = compile_generation_recipe_workflow(recipe, _report(recipe), model_family="sdxl", input_bindings={})
    nodes = result.workflow
    loras = [(node_id, node) for node_id, node in nodes.items() if node["class_type"] == "LoraLoader"]

    assert [node["inputs"]["lora_name"] for _, node in loras] == ["one.safetensors", "two.safetensors", "three.safetensors"]
    assert [(node["inputs"]["strength_model"], node["inputs"]["strength_clip"]) for _, node in loras] == [(.7, .4), (.8, .5), (.9, .6)]
    clip_skip_id = _node_id(nodes, "CLIPSetLastLayer")
    assert {"canonical_field": "resources[3].clip_skip", "node_id": clip_skip_id,
            "input_name": "stop_at_clip_layer", "value": -2} in result.manifest["field_bindings"]
    assert any("badhand.pt" in node["inputs"].get("text", "") for node in nodes.values())
    samplers = [node for node in nodes.values() if node["class_type"] == "KSampler"]
    assert len(samplers) == 2
    encode_id = _node_id(nodes, "VAEEncode")
    scaled_id = _node_id(nodes, "ImageScaleBy")
    image_upscale_id = _node_id(nodes, "ImageUpscaleWithModel")
    loader_id = _node_id(nodes, "UpscaleModelLoader")
    first_sampler_id = next(node_id for node_id, node in nodes.items() if node["class_type"] == "KSampler")
    second_sampler_id = next(
        node_id for node_id, node in nodes.items()
        if node["class_type"] == "KSampler" and node_id != first_sampler_id
    )
    decode_id = next(node_id for node_id, node in nodes.items() if node["class_type"] == "VAEDecode")
    assert samplers[1]["inputs"]["latent_image"] == [encode_id, 0]
    assert nodes[second_sampler_id]["inputs"]["latent_image"] == [encode_id, 0]
    assert nodes[scaled_id]["inputs"] == {"image": [image_upscale_id, 0], "upscale_method": "lanczos", "scale_by": 1.5}
    assert nodes[image_upscale_id]["inputs"]["image"] == [decode_id, 0]
    assert nodes[image_upscale_id]["inputs"]["upscale_model"] == [loader_id, 0]
    assert nodes[decode_id]["inputs"]["samples"] == [first_sampler_id, 0]
    assert {"canonical_field": "passes[1].scale", "node_id": scaled_id, "input_name": "scale_by", "value": 1.5} in result.manifest["field_bindings"]
    assert {"canonical_field": "passes[1].upscale_resource", "node_id": loader_id, "input_name": "model_name", "resource_lock_index": 6} in result.manifest["bindings"]

    # A model upscaler can produce its own native dimensions.  The recipe's resolved
    # hires dimensions must therefore be re-bound explicitly before VAEEncode rather
    # than merely assumed from the factor.
    resize_id = next(
        node_id for node_id, node in nodes.items()
        if node["class_type"] == "ImageScale" and node["inputs"].get("width") == 1536
    )
    assert nodes[encode_id]["inputs"]["pixels"] == [resize_id, 0]
    assert {first_sampler_id, decode_id, loader_id, image_upscale_id, scaled_id, resize_id, encode_id} <= _ancestors(nodes, second_sampler_id)
    assert nodes[resize_id]["inputs"] == {
        "image": [scaled_id, 0], "upscale_method": "lanczos", "width": 1536,
        "height": 1152, "crop": "disabled",
    }
    assert {"canonical_field": "passes[1].sampling.width", "node_id": resize_id, "input_name": "width", "value": 1536} in result.manifest["field_bindings"]
    assert {"canonical_field": "passes[1].sampling.height", "node_id": resize_id, "input_name": "height", "value": 1152} in result.manifest["field_bindings"]


@pytest.mark.parametrize(
    "strict,ready,model_family,code,field",
    [(False, True, "sdxl", "resource_report_not_strict", "resource_report.strict"), (True, False, "sdxl", "resource_report_not_ready", "resource_report.ready"), (True, True, "flux", "unsupported_model_family", "model_family")],
)
def test_report_and_target_fail_closed(strict: bool, ready: bool, model_family: str, code: str, field: str) -> None:
    recipe = _recipe()
    with pytest.raises(RecipeCompileError) as raised:
        compile_generation_recipe_workflow(recipe, _report(recipe, strict=strict, ready=ready), model_family=model_family, input_bindings={})
    assert raised.value.diagnostic == {"code": code, "canonical_field": field, "message": raised.value.diagnostic["message"]}
    assert raised.value.workflow is None


def test_missing_or_duplicate_or_wrong_resource_lock_fails_closed() -> None:
    recipe = _recipe()
    for mutate, code in (
        (lambda report: report.resource_lock.clear(), "resource_lock_missing"),
        (lambda report: report.resource_lock.append(deepcopy(report.resource_lock[0])), "resource_lock_duplicate"),
        (lambda report: report.resource_lock.__setitem__(0, {**report.resource_lock[0], "kind": "lora"}), "resource_lock_kind_mismatch"),
    ):
        report = _report(recipe)
        mutate(report)
        with pytest.raises(RecipeCompileError) as raised:
            compile_generation_recipe_workflow(recipe, report, model_family="sdxl", input_bindings={})
        assert raised.value.diagnostic["code"] == code


def test_control_detailer_and_postprocess_chain_are_explicit_and_binding_checked() -> None:
    recipe = _recipe()
    recipe = recipe.model_copy(update={
        "resources": recipe.resources + [
            recipe.resources[0].model_copy(update={"kind": "controlnet", "name": "pose.safetensors", "sha256": "b" * 64}),
            recipe.resources[0].model_copy(update={"kind": "detailer", "name": "face.onnx", "sha256": "c" * 64}),
            recipe.resources[0].model_copy(update={"kind": "upscaler", "name": "4x.pth", "sha256": "d" * 64}),
        ],
    })
    recipe = GenerationRecipe.model_validate({
        **recipe.model_dump(), "inputs": [{"reference": "pose.png", "sha256": "e" * 64, "kind": "image"}],
        "controls": [{"kind": "controlnet", "input_ref": "pose.png", "resource": {"kind": "controlnet", "sha256": "b" * 64}, "weight": .8, "start_percent": .1, "end_percent": .9}],
        "detailers": [{"kind": "detailer", "resource": {"kind": "detailer", "sha256": "c" * 64}, "denoise": .2}],
        "postprocess": [{"kind": "upscale", "resource": {"kind": "upscaler", "sha256": "d" * 64}, "scale": 2}, {"kind": "face_restore", "resource": {"kind": "detailer", "sha256": "c" * 64}}],
    })
    result = compile_generation_recipe_workflow(recipe, _report(recipe), model_family="sdxl", input_bindings={"pose.png": {"filename": "pose.png", "sha256": "e" * 64}})
    classes = [node["class_type"] for node in result.workflow.values()]
    assert classes.index("LoadImage") < classes.index("ControlNetLoader") < classes.index("ControlNetApplyAdvanced")
    assert "Detailer" in classes and "ImageUpscaleWithModel" in classes and "FaceRestore" in classes
    nodes = result.workflow
    save_id = _node_id(nodes, "SaveImage")
    restore_id = _node_id(nodes, "FaceRestore")
    scaled_id = _node_id(nodes, "ImageScaleBy")
    upscale_id = _node_id(nodes, "ImageUpscaleWithModel")
    loader_ids = [node_id for node_id, node in nodes.items() if node["class_type"] == "UpscaleModelLoader"]
    assert nodes[save_id]["inputs"]["images"] == [restore_id, 0]
    assert nodes[restore_id]["inputs"]["image"] == [scaled_id, 0]
    assert nodes[scaled_id]["inputs"] == {"image": [upscale_id, 0], "upscale_method": "lanczos", "scale_by": 2}
    assert nodes[upscale_id]["inputs"]["upscale_model"] == [loader_ids[-1], 0]
    assert {"canonical_field": "postprocess[0].scale", "node_id": scaled_id, "input_name": "scale_by", "value": 2} in result.manifest["field_bindings"]
    assert {"canonical_field": "postprocess[0].resource", "node_id": loader_ids[-1], "input_name": "model_name", "resource_lock_index": 3} in result.manifest["bindings"]
    apply_id = _node_id(nodes, "ControlNetApplyAdvanced")
    detailer_id = _node_id(nodes, "Detailer")
    assert {
        ("controls[0].weight", apply_id, "strength", .8),
        ("controls[0].start_percent", apply_id, "start_percent", .1),
        ("controls[0].end_percent", apply_id, "end_percent", .9),
        ("detailers[0].denoise", detailer_id, "denoise", .2),
    } <= {
        (item["canonical_field"], item["node_id"], item["input_name"], item["value"])
        for item in result.manifest["field_bindings"]
    }


@pytest.mark.parametrize("field,value", [("scale", 2), ("upscale_model", "ignored.pth"), ("upscale_resource", {"kind": "upscaler", "sha256": "b" * 64})])
def test_base_pass_unexpressible_upscale_fields_fail_closed(field: str, value: object) -> None:
    payload = _recipe().model_dump()
    payload["passes"][0][field] = value
    if field == "upscale_resource":
        payload["resources"].append({"kind": "upscaler", "name": "ignored.pth", "sha256": "b" * 64})
    recipe = GenerationRecipe.model_validate(payload)

    with pytest.raises(RecipeCompileError) as raised:
        compile_generation_recipe_workflow(recipe, _report(recipe), model_family="sdxl", input_bindings={})

    assert raised.value.diagnostic["code"] == "unsupported_operation"
    assert raised.value.diagnostic["canonical_field"] == f"passes[0].{field}"
    assert raised.value.workflow is None


def test_duplicate_control_input_reference_fails_closed_instead_of_selecting_one() -> None:
    payload = _recipe().model_dump()
    payload["resources"].append({"kind": "controlnet", "name": "pose.safetensors", "sha256": "b" * 64})
    payload["inputs"] = [
        {"reference": "pose.png", "sha256": "c" * 64, "kind": "image"},
        {"reference": "pose.png", "sha256": "d" * 64, "kind": "image"},
    ]
    payload["controls"] = [{"kind": "controlnet", "input_ref": "pose.png", "resource": {"kind": "controlnet", "sha256": "b" * 64}}]
    recipe = GenerationRecipe.model_validate(payload)

    with pytest.raises(RecipeCompileError) as raised:
        compile_generation_recipe_workflow(recipe, _report(recipe), model_family="sdxl", input_bindings={})

    assert raised.value.diagnostic["code"] == "input_reference_unresolved"
    assert raised.value.diagnostic["canonical_field"] == "controls[0].input_ref"
    assert raised.value.workflow is None


@pytest.mark.parametrize(
    "case,expected_code,expected_field",
    [
        ("inheritance_cycle", "pass_inheritance_cycle", "passes[0].inherits_from"),
        ("unknown_control", "unsupported_operation", "controls[0]"),
        ("postprocess_params", "unsupported_operation", "postprocess[0].params"),
    ],
)
def test_explicitly_unsupported_recipe_operations_fail_closed(case: str, expected_code: str, expected_field: str) -> None:
    payload = _recipe().model_dump()
    if case == "inheritance_cycle":
        payload["passes"] = [
            {"name": "base", "inherits_from": "hires"},
            {"name": "hires", "inherits_from": "base"},
        ]
    elif case == "unknown_control":
        payload["controls"] = [{"kind": "ip_adapter"}]
    else:
        payload["resources"].append({"kind": "upscaler", "name": "4x.pth", "sha256": "b" * 64})
        payload["postprocess"] = [{"kind": "upscale", "resource": {"kind": "upscaler", "sha256": "b" * 64}, "scale": 2, "params": {"tile": 64}}]
    recipe = GenerationRecipe.model_validate(payload)

    with pytest.raises(RecipeCompileError) as raised:
        compile_generation_recipe_workflow(recipe, _report(recipe), model_family="sdxl", input_bindings={})

    assert raised.value.diagnostic["code"] == expected_code
    assert raised.value.diagnostic["canonical_field"] == expected_field
    assert raised.value.workflow is None


@pytest.mark.parametrize("field", ["prompt", "negative_prompt"])
def test_detailer_prompt_fields_fail_closed_instead_of_being_dropped(field: str) -> None:
    recipe = _recipe()
    recipe = GenerationRecipe.model_validate({
        **recipe.model_dump(),
        "resources": recipe.model_dump()["resources"] + [{"kind": "detailer", "name": "face.onnx", "sha256": "c" * 64}],
        "detailers": [{"kind": "detailer", "resource": {"kind": "detailer", "sha256": "c" * 64}, field: "must not disappear"}],
    })
    with pytest.raises(RecipeCompileError) as raised:
        compile_generation_recipe_workflow(recipe, _report(recipe), model_family="sdxl", input_bindings={})
    assert raised.value.diagnostic["code"] == "unsupported_operation"
    assert raised.value.diagnostic["canonical_field"] == f"detailers[0].{field}"
    assert raised.value.workflow is None


def test_forged_ready_report_without_hash_verified_entries_fails_closed() -> None:
    recipe = _recipe()
    report = _report(recipe)
    report.entries[0].hash_verified = False
    report.entries[0].diagnostics["hash_verified"] = False

    with pytest.raises(RecipeCompileError) as raised:
        compile_generation_recipe_workflow(recipe, report, model_family="sdxl", input_bindings={})

    assert raised.value.diagnostic["code"] == "resource_lock_unverified_hash"
    assert raised.value.diagnostic["canonical_field"] == "resources[0]"
    assert raised.value.workflow is None


def test_control_input_hash_is_explicit_in_manifest() -> None:
    recipe = GenerationRecipe.model_validate({
        **_recipe().model_dump(),
        "resources": _recipe().model_dump()["resources"] + [
            {"kind": "controlnet", "name": "pose.safetensors", "sha256": "b" * 64},
        ],
        "inputs": [{"reference": "pose.png", "sha256": "e" * 64, "kind": "image"}],
        "controls": [{"kind": "controlnet", "input_ref": "pose.png", "resource": {"kind": "controlnet", "sha256": "b" * 64}}],
    })
    result = compile_generation_recipe_workflow(
        recipe, _report(recipe), model_family="sdxl",
        input_bindings={"pose.png": {"filename": "pose.png", "sha256": "e" * 64}},
    )
    load_id = _node_id(result.workflow, "LoadImage")

    assert {"canonical_field": "controls[0].input_ref", "node_id": load_id,
            "input_name": "image", "reference": "pose.png", "sha256": "e" * 64} in result.manifest["input_bindings"]


def test_input_binding_sha_and_unknown_operation_fail_closed() -> None:
    recipe = _recipe()
    recipe = GenerationRecipe.model_validate({
        **recipe.model_dump(),
        "resources": recipe.model_dump()["resources"] + [{"kind": "controlnet", "name": "pose.safetensors", "sha256": "b" * 64}],
        "inputs": [{"reference": "pose.png", "sha256": "e" * 64, "kind": "image"}],
        "controls": [{"kind": "controlnet", "input_ref": "pose.png", "resource": {"kind": "controlnet", "sha256": "b" * 64}}],
    })
    with pytest.raises(RecipeCompileError) as missing:
        compile_generation_recipe_workflow(recipe, _report(recipe), model_family="sdxl", input_bindings={})
    assert missing.value.diagnostic["code"] == "input_binding_missing"
    with pytest.raises(RecipeCompileError) as mismatch:
        compile_generation_recipe_workflow(recipe, _report(recipe), model_family="sdxl", input_bindings={"pose.png": {"filename": "pose.png", "sha256": "f" * 64}})
    assert mismatch.value.diagnostic["code"] == "input_sha_mismatch"


@pytest.mark.parametrize(
    "operation,canonical_field",
    [
        ("control", "controls[0].model"),
        ("detailer", "detailers[0].model"),
        ("postprocess", "postprocess[0].model"),
        ("followup_pass", "passes[1].upscale_model"),
    ],
)
def test_unrepresented_operation_model_fields_fail_closed(
    operation: str, canonical_field: str,
) -> None:
    """CIV-D-AC7: model labels cannot silently select a different graph input."""
    payload = _recipe(extras=True).model_dump()
    if operation == "control":
        payload["resources"].append({"kind": "controlnet", "name": "pose.safetensors", "sha256": "2" * 64})
        payload["inputs"] = [{"reference": "pose.png", "sha256": "3" * 64, "kind": "image"}]
        payload["controls"] = [{
            "kind": "controlnet", "input_ref": "pose.png", "model": "pose.safetensors",
            "resource": {"kind": "controlnet", "sha256": "2" * 64},
        }]
    elif operation == "detailer":
        payload["resources"].append({"kind": "detailer", "name": "face.onnx", "sha256": "2" * 64})
        payload["detailers"] = [{
            "kind": "detailer", "model": "face.onnx",
            "resource": {"kind": "detailer", "sha256": "2" * 64},
        }]
    elif operation == "postprocess":
        payload["postprocess"] = [{
            "kind": "upscale", "model": "4x.pth", "scale": 2,
            "resource": {"kind": "upscaler", "sha256": "1" * 64},
        }]
    else:
        payload["passes"][1]["upscale_model"] = "4x.pth"
    recipe = GenerationRecipe.model_validate(payload)

    with pytest.raises(RecipeCompileError) as raised:
        compile_generation_recipe_workflow(recipe, _report(recipe), model_family="sdxl", input_bindings={"pose.png": {"filename": "pose.png", "sha256": "3" * 64}})

    assert raised.value.diagnostic["code"] == "unsupported_operation"
    assert raised.value.diagnostic["canonical_field"] == canonical_field
    assert raised.value.workflow is None
