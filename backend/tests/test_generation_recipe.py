"""CIV-A generation recipe schema and offline normalization tests."""
from pydantic import ValidationError
import hashlib
import json
import pytest

from app.schemas.generation_recipe import (
    EvidenceRecord,
    EvidenceSource,
    GenerationRecipe,
    MissingCriticality,
    RecipeSource,
    ReproductionLevel,
    _build_recipe_from_trusted_evidence,
    _issue_trusted_provenance_capability,
    assess_reproduction,
    canonical_runtime_lock_document,
    normalize_recipe_payload,
)

SHA = "a" * 64


def _trusted_recipe(payload: dict) -> GenerationRecipe:
    capability = _issue_trusted_provenance_capability(
        EvidenceRecord.model_validate(item) for item in payload.get("confirmed", [])
    )
    return _build_recipe_from_trusted_evidence(payload, capability=capability)


def _complete_payload() -> dict:
    return {
        "source": {
            "provider": "civitai",
            "image_id": " 123 ",
            "url": " https://civitai.com/images/123 ",
        },
        "base_prompt": "1girl, studio light",
        "negative_prompt": "lowres",
        "resources": [
            {"kind": "checkpoint", "name": "base.safetensors", "sha256": SHA},
            {
                "kind": "lora",
                "name": "style.safetensors",
                "sha256": "b" * 64,
                "strength_model": 0.8,
                "strength_clip": 0.6,
            },
            {
                "kind": "lora",
                "name": "detail.safetensors",
                "sha256": "c" * 64,
                "strength_model": 0.5,
            },
            {"kind": "controlnet", "name": "openpose.safetensors", "sha256": "d" * 64},
            {"kind": "detailer", "name": "face-yolo.pt", "sha256": "e" * 64},
            {"kind": "upscaler", "name": "4x-anime.pth", "sha256": "f" * 64},
        ],
        "sampling": {
            "seed": 9223372036854775807,
            "steps": 30,
            "cfg": 6.5,
            "sampler": "dpmpp_2m",
            "scheduler": "karras",
            "denoise": 1.0,
            "width": 1024,
            "height": 1536,
        },
        "passes": [
            {"name": "base", "inherits_from": "recipe.sampling", "sampling": {"steps": 30, "cfg": 6.5}},
            {
                "name": "hires",
                "inherits_from": "base",
                "sampling": {"steps": 12, "denoise": 0.35, "width": 1536, "height": 2304},
                "scale": 1.5,
                "upscale_model": "4x-anime.pth",
            },
        ],
        "inputs": [{"reference": "pose.png", "sha256": "1" * 64, "kind": "image"}],
        "controls": [
            {
                "kind": "pose",
                "input_ref": "pose.png",
                "model": "openpose.safetensors",
                "weight": 0.8,
            }
        ],
        "detailers": [{"kind": "face", "model": "face-yolo.pt", "denoise": 0.25}],
        "postprocess": [{"kind": "upscale", "model": "4x-anime.pth", "scale": 2}],
        "workflow": {
            "reference": "civitai:image:123:workflow",
            "snapshot": {"1": {"class_type": "KSampler", "inputs": {"steps": 30}}},
        },
        "runtime": {
            "engine": "ComfyUI",
            "engine_version": "0.3.0",
            "reference": "civitai:image:123:runtime",
        },
        "raw": {"meta": {"unknown_vendor_field": "preserved"}},
        "confirmed": [
            {
                "canonical_field": "workflow",
                "source": "embedded_metadata",
                "reference": "png:parameters",
            }
        ],
        "inferred": [
            {
                "canonical_field": "model_family",
                "source": "importer",
                "reference": "family-detector:v1",
            }
        ],
        "missing": [],
    }


def test_normalization_canonicalizes_known_values_and_losslessly_preserves_unknown_metadata() -> None:
    payload = _complete_payload()
    payload["unmapped_top_level"] = {"vendor": True}
    payload["source"]["vendor_source_key"] = "source-value"
    payload["controls"][0]["vendor_control_key"] = ["kept"]

    normalized = normalize_recipe_payload(payload)

    assert normalized["schema_version"] == "1.0"
    assert normalized["source"]["provider"] == "civitai"
    assert normalized["source"]["image_id"] == 123
    assert normalized["source"]["url"] == "https://civitai.com/images/123"
    assert normalized["resources"][0]["sha256"] == SHA
    assert "unmapped_top_level" not in normalized
    assert "vendor_source_key" not in normalized["source"]
    assert "vendor_control_key" not in normalized["controls"][0]
    assert normalized["raw"]["importer_payload"]["unmapped_top_level"] == {"vendor": True}
    assert normalized["raw"]["importer_payload"]["controls"][0]["vendor_control_key"] == ["kept"]
    assert normalized["raw"]["normalization"]["unknown_fields"]


def test_normalization_is_idempotent_without_recursive_importer_payload_growth() -> None:
    payload = _complete_payload()
    payload["vendor_extension"] = {"opaque": True}

    once = normalize_recipe_payload(payload)
    twice = normalize_recipe_payload(once)

    assert twice == once
    assert twice["raw"]["importer_payload"] == payload
    assert "importer_payload" not in twice["raw"]["importer_payload"].get("raw", {})


def test_recipe_preserves_ordered_multi_loras_and_all_recipe_sections() -> None:
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(_complete_payload()))

    assert recipe.schema_version == "1.0"
    assert [resource.name for resource in recipe.loras] == ["style.safetensors", "detail.safetensors"]
    assert recipe.loras[0].strength_model == 0.8
    assert recipe.loras[0].strength_clip == 0.6
    assert recipe.loras[1].strength_clip is None
    assert recipe.sampling is not None
    assert recipe.sampling.seed == 9223372036854775807
    assert len(recipe.passes) == 2
    assert recipe.controls[0].input_ref == "pose.png"
    assert len(recipe.detailers) == 1
    assert len(recipe.postprocess) == 1
    assert recipe.base_prompt == "1girl, studio light"
    assert recipe.negative_prompt == "lowres"
    assert recipe.confirmed == []
    assert any(item.source is EvidenceSource.EMBEDDED_METADATA for item in recipe.inferred)


def test_validation_rejects_invalid_hash_and_non_positive_dimensions() -> None:
    payload = _complete_payload()
    payload["resources"][0]["sha256"] = "not-a-sha256"
    with pytest.raises(ValidationError, match="sha256"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    payload = _complete_payload()
    payload["sampling"]["width"] = 0
    with pytest.raises(ValidationError):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


def test_validation_rejects_conflicting_confirmed_and_inferred_evidence() -> None:
    payload = _complete_payload()
    payload["inferred"].append(
        {"canonical_field": "workflow", "source": "importer", "reference": "guess"}
    )

    with pytest.raises(ValidationError, match="confirmed and inferred"):
        _trusted_recipe(payload)


def test_reproduction_assessment_derives_exact_from_actual_evidence_not_magic_claims() -> None:
    exact = _trusted_recipe(_auditable_exact_payload())
    report = assess_reproduction(exact)

    assert report.level is ReproductionLevel.EXACT_READY
    assert all(report.requirements.values())


def test_exact_ready_fails_closed_when_checkpoint_digest_changes_without_a_loader_resource_lock() -> None:
    """A loader filename is not a hash binding: same label may select another file."""
    payload = _auditable_exact_payload()
    payload["resources"][0]["sha256"] = "0" * 64

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow_resources"] is False


def test_exact_ready_rejects_confirmed_text_labels_without_a_snapshot_or_lock_identity() -> None:
    """Evidence labels alone are assertions, not auditable evidence bindings."""
    payload = _auditable_exact_payload()
    for evidence in payload["confirmed"]:
        evidence.pop("snapshot_sha256")
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY


def test_exact_ready_fails_closed_for_same_filename_when_lock_identity_differs() -> None:
    payload = _auditable_exact_payload()
    payload["runtime"]["resource_locks"][0]["resource"]["civitai_file_id"] = 999

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow_resources"] is False


def test_empty_shell_confirmed_claims_never_become_exact_ready() -> None:
    payload = _complete_payload()
    payload["resources"] = [{"kind": "checkpoint", "name": "base.safetensors", "sha256": SHA}]
    payload["workflow"] = None
    payload["runtime"] = None
    payload["inputs"] = []
    payload["confirmed"] = [
        {"canonical_field": field, "source": "importer", "reference": "caller-claim"}
        for field in ("workflow", "resources", "inputs", "runtime")
    ]
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)
    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow"] is False
    assert report.requirements["runtime"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["inputs"].clear(),
        lambda payload: payload["controls"][0].update({"input_ref": "missing.png"}),
        lambda payload: payload["controls"][0]["resource"].update({"sha256": "0" * 64}),
        lambda payload: payload["detailers"][0]["resource"].update({"sha256": "0" * 64}),
        lambda payload: payload["postprocess"][0]["resource"].update({"sha256": "0" * 64}),
        lambda payload: payload["passes"][1]["upscale_resource"].update({"sha256": "0" * 64}),
    ],
)
def test_required_input_and_dependency_gaps_fail_closed(mutate) -> None:
    payload = _auditable_exact_payload()
    mutate(payload)
    try:
        recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    except ValidationError:
        return

    report = assess_reproduction(recipe)
    assert report.level is ReproductionLevel.NOT_REPRODUCIBLE
    assert report.critical_missing


def test_declared_critical_missing_item_fails_closed() -> None:
    payload = _complete_payload()
    payload["missing"] = [
        {
            "canonical_field": "controls[0].input_ref",
            "criticality": "critical",
            "reason": "source image unavailable",
        }
    ]
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)
    assert recipe.missing[0].criticality is MissingCriticality.CRITICAL
    assert report.level is ReproductionLevel.NOT_REPRODUCIBLE


def test_workflow_runtime_and_conditioning_evidence_are_required_for_exact() -> None:
    for field in ("workflow", "runtime", "base_prompt", "negative_prompt"):
        payload = _complete_payload()
        payload[field] = None
        recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
        assert assess_reproduction(recipe).level is not ReproductionLevel.EXACT_READY


def test_same_filename_with_different_sha_is_not_the_same_resource_identity() -> None:
    payload = _complete_payload()
    payload["resources"].append(
        {"kind": "lora", "name": "style.safetensors", "sha256": "9" * 64}
    )

    with pytest.raises(ValidationError, match="different sha256"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


def test_recipe_source_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError):
        RecipeSource(provider="unknown", image_id=1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", " "),
        ("url", "https://example.invalid/images/123"),
        ("media_url", "https://evil.example/civitai.com/images/123"),
        ("media_url", "javascript:alert(1)"),
    ],
)
def test_source_urls_fail_closed_unless_they_are_supported_civitai_identities(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        RecipeSource(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", "https://civitai.com/images/123"),
        ("url", "https://www.civitai.com/posts/123"),
        ("url", "https://civitai.com/models/123"),
        ("media_url", "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example/width=768/example.webp"),
    ],
)
def test_source_urls_accept_supported_civitai_image_post_model_and_cdn_identities(field: str, value: str) -> None:
    source = RecipeSource(**{field: value})
    assert getattr(source, field) == value


def _complete_workflow() -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "positive"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "negative"}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1536, "batch_size": 1}},
        "5": {
            "class_type": "KSampler",
            "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": 9223372036854775807, "steps": 30, "cfg": 6.5, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0},
        },
        "6": {"class_type": "LatentUpscale", "inputs": {"samples": ["5", 0], "width": 1536, "height": 2304}},
        "7": {
            "class_type": "KSampler",
            "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["6", 0], "seed": 9223372036854775807, "steps": 12, "cfg": 6.5, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 0.35},
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "recipe"}},
    }


def _sha_json(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _runtime_lock_for_payload(runtime: dict) -> str:
    return _sha_json({
        "engine": runtime["engine"],
        "engine_version": runtime["engine_version"],
        "node_versions": runtime["node_versions"],
        "package_versions": runtime["package_versions"],
        "runtime_settings": runtime["runtime_settings"],
        "resource_locks": runtime["resource_locks"],
    })


def _auditable_exact_payload() -> dict:
    payload = _complete_payload()
    snapshot = _complete_workflow()
    payload["workflow"] = {
        "reference": "civitai:image:123:workflow",
        "snapshot": snapshot,
        "snapshot_sha256": _sha_json(snapshot),
    }
    payload["passes"][0]["ksampler_node_id"] = "5"
    payload["passes"][1]["ksampler_node_id"] = "7"
    payload["resources"][0]["civitai_model_id"] = 101
    payload["resources"][0]["civitai_model_version_id"] = 201
    payload["resources"][0]["civitai_file_id"] = 301
    payload["runtime"] = {
        "engine": "ComfyUI",
        "engine_version": "0.3.0",
        "reference": "civitai:image:123:runtime",
        "runtime_lock_sha256": "7" * 64,
        "node_versions": {
            "KSampler": "8" * 64,
            "CheckpointLoaderSimple": "9" * 64,
            "CLIPTextEncode": "a" * 64,
            "EmptyLatentImage": "b" * 64,
            "LatentUpscale": "c" * 64,
            "VAEDecode": "d" * 64,
            "SaveImage": "e" * 64,
        },
        "package_versions": {"comfyui": "1.0.0"},
        "runtime_settings": {"cuda": "12.0"},
        "inspection_snapshot": {},
        "resource_locks": [
            {
                "node_id": "1",
                "input_name": "ckpt_name",
                "resource": {
                    "kind": "checkpoint",
                    "sha256": SHA,
                    "civitai_model_id": 101,
                    "civitai_model_version_id": 201,
                    "civitai_file_id": 301,
                },
            }
        ],
    }
    payload["controls"][0]["resource"] = {"kind": "controlnet", "sha256": "d" * 64}
    payload["detailers"][0]["resource"] = {"kind": "detailer", "sha256": "e" * 64}
    payload["postprocess"][0]["resource"] = {"kind": "upscaler", "sha256": "f" * 64}
    payload["passes"][1]["upscale_resource"] = {"kind": "upscaler", "sha256": "f" * 64}
    confirmed = [
        "source.identity", "workflow", "sampling", "conditioning", "runtime", "inputs[0].sha256",
        "controls[0].resource", "detailers[0].resource", "postprocess[0].resource", "passes[1].upscale_resource",
    ]
    confirmed.extend(f"resources[{index}].identity" for index in range(len(payload["resources"])))
    workflow_fields = {"workflow", "sampling", "conditioning"}
    source_reference = "civitai:image:123:source"
    payload["raw"]["evidence_snapshots"] = {source_reference: "6" * 64}
    payload["confirmed"] = [
        {
            "canonical_field": field,
            "source": "embedded_metadata",
            "reference": (
                source_reference if field == "source.identity"
                else payload["workflow"]["reference"] if field in workflow_fields
                else payload["runtime"]["reference"]
            ),
            "snapshot_sha256": (
                "6" * 64 if field == "source.identity"
                else payload["workflow"]["snapshot_sha256"] if field in workflow_fields
                else payload["runtime"]["runtime_lock_sha256"]
            ),
        }
        for field in confirmed
    ]
    payload["inferred"] = []
    # Exact fixtures explicitly represent every declared operation in the snapshot and
    # bind that exact node/input to a runtime resource lock.
    snapshot["control"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": "openpose.safetensors"}}
    snapshot["detail"] = {"class_type": "UltralyticsDetectorProvider", "inputs": {"model_name": "face-yolo.pt"}}
    snapshot["upscale"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": "4x-anime.pth"}}
    payload["workflow"]["operation_bindings"] = [
        {"canonical_field": "passes[0]", "node_id": "1", "input_name": "ckpt_name", "resource": {"kind": "checkpoint", "sha256": SHA}},
        {"canonical_field": "passes[1]", "node_id": "upscale", "input_name": "model_name", "resource": {"kind": "upscaler", "sha256": "f" * 64}},
        {"canonical_field": "controls[0]", "node_id": "control", "input_name": "control_net_name", "resource": {"kind": "controlnet", "sha256": "d" * 64}},
        {"canonical_field": "detailers[0]", "node_id": "detail", "input_name": "model_name", "resource": {"kind": "detailer", "sha256": "e" * 64}},
        {"canonical_field": "postprocess[0]", "node_id": "upscale", "input_name": "model_name", "resource": {"kind": "upscaler", "sha256": "f" * 64}},
    ]
    payload["runtime"]["node_versions"].update({"ControlNetLoader": "c" * 64, "UltralyticsDetectorProvider": "d" * 64, "UpscaleModelLoader": "e" * 64})
    payload["runtime"]["resource_locks"].extend([
        {"node_id": "control", "input_name": "control_net_name", "resource": {"kind": "controlnet", "sha256": "d" * 64}},
        {"node_id": "detail", "input_name": "model_name", "resource": {"kind": "detailer", "sha256": "e" * 64}},
        {"node_id": "upscale", "input_name": "model_name", "resource": {"kind": "upscaler", "sha256": "f" * 64}},
    ])
    payload["workflow"]["snapshot_sha256"] = _sha_json(snapshot)
    payload["runtime"]["runtime_lock_sha256"] = _runtime_lock_for_payload(payload["runtime"])
    payload["runtime"]["inspection_snapshot"] = {
        "runtime_lock": {
            "engine": payload["runtime"]["engine"],
            "engine_version": payload["runtime"]["engine_version"],
            "node_versions": payload["runtime"]["node_versions"],
            "package_versions": payload["runtime"]["package_versions"],
            "runtime_settings": payload["runtime"]["runtime_settings"],
            "resource_locks": payload["runtime"]["resource_locks"],
        }
    }
    for evidence in payload["confirmed"]:
        if evidence["reference"] == payload["workflow"]["reference"]:
            evidence["snapshot_sha256"] = payload["workflow"]["snapshot_sha256"]
    payload["evidence_manifest"] = _evidence_manifest_for(payload)
    return payload


def test_exact_ready_requires_confirmed_provenance_for_every_required_field() -> None:
    payload = _auditable_exact_payload()
    payload["confirmed"] = [
        item for item in payload["confirmed"] if item["canonical_field"] != "runtime"
    ]
    payload["inferred"].append(
        {"canonical_field": "runtime", "source": "importer", "reference": "guess"}
    )
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["confirmed_runtime"] is False


def test_all_inferred_evidence_never_becomes_exact_ready() -> None:
    payload = _auditable_exact_payload()
    payload["inferred"] = [
        {**item, "source": "importer", "reference": f"inferred:{item['canonical_field']}"}
        for item in payload["confirmed"]
    ]
    payload["confirmed"] = []
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert not any(value for name, value in report.requirements.items() if name.startswith("confirmed_"))


def test_importer_labeled_confirmed_evidence_never_becomes_exact_ready() -> None:
    payload = _auditable_exact_payload()
    for item in payload["confirmed"]:
        item["source"] = "importer"
        item["reference"] = f"importer:{item['canonical_field']}"
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert not any(value for name, value in report.requirements.items() if name.startswith("confirmed_"))


def test_source_provider_without_auditable_civitai_identity_never_becomes_exact_ready() -> None:
    payload = _auditable_exact_payload()
    payload["source"] = {"provider": "civitai"}
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["source_identity"] is False


@pytest.mark.parametrize(
    "source",
    [
        {"provider": "civitai", "url": "https://civitai.com/models/123/a-model"},
        {"provider": "civitai", "url": "https://civitai.com/api/download/models/456"},
        {"provider": "civitai", "url": "https://civitai.com/posts/789"},
    ],
)
def test_model_download_or_post_page_url_alone_never_establishes_exact_source_identity(source: dict) -> None:
    payload = _auditable_exact_payload()
    payload["source"] = source
    payload["evidence_manifest"] = _evidence_manifest_for(payload)
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["source_identity"] is False


@pytest.mark.parametrize(
    "source",
    [
        {"provider": "civitai", "image_id": 123},
        {"provider": "civitai", "url": "https://civitai.com/images/123"},
        {
            "provider": "civitai",
            "url": "https://civitai.com/posts/789",
            "media_url": "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example/width=768/example.webp",
        },
    ],
)
def test_image_or_auditable_media_identity_can_establish_exact_source_identity(source: dict) -> None:
    payload = _auditable_exact_payload()
    payload["source"] = source
    payload["evidence_manifest"] = _evidence_manifest_for(payload)
    recipe = _trusted_recipe(payload)

    report = assess_reproduction(recipe)

    assert report.level is ReproductionLevel.EXACT_READY
    assert report.requirements["source_identity"] is True


def test_inferred_source_identity_never_becomes_exact_ready() -> None:
    payload = _auditable_exact_payload()
    payload["confirmed"] = [
        item for item in payload["confirmed"] if item["canonical_field"] != "source.identity"
    ]
    payload["inferred"].append(
        {"canonical_field": "source.identity", "source": "importer", "reference": "guess:source"}
    )
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["confirmed_source_identity"] is False


def test_nonempty_arbitrary_workflow_snapshot_and_runtime_strings_are_not_exact_ready() -> None:
    payload = _auditable_exact_payload()
    payload["workflow"] = {"reference": "somewhere", "snapshot": {"x": 1}, "snapshot_sha256": _sha_json({"x": 1})}
    payload["runtime"] = {"engine": "x", "engine_version": "y", "reference": "z"}
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow"] is False
    assert report.requirements["runtime"] is False


def test_dependency_reference_fails_closed_for_same_filename_across_kinds() -> None:
    payload = _auditable_exact_payload()
    payload["resources"].append({"kind": "lora", "name": "openpose.safetensors", "sha256": "0" * 64})
    payload["controls"][0]["resource"] = {"kind": "lora", "sha256": "0" * 64}
    with pytest.raises(ValidationError, match="controls\\[0\\]\\.resource"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


def test_dependency_reference_fails_closed_when_same_hash_has_conflicting_identity() -> None:
    payload = _auditable_exact_payload()
    payload["resources"].append(
        {"kind": "controlnet", "name": "other-openpose.safetensors", "sha256": "d" * 64, "civitai_file_id": 99}
    )
    payload["resources"][3]["civitai_file_id"] = 98

    with pytest.raises(ValidationError, match="ambiguous|ledger"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


def test_dependency_reference_must_match_expected_kind_even_when_hash_exists() -> None:
    payload = _auditable_exact_payload()
    payload["controls"][0]["resource"] = {"kind": "upscaler", "sha256": "f" * 64}
    with pytest.raises(ValidationError, match="controls\\[0\\]\\.resource"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["postprocess"][0].update({"kind": "face_restore", "resource": {"kind": "upscaler", "sha256": "f" * 64}}),
        lambda payload: payload["postprocess"][0].update({"kind": "face_restore", "resource": {"kind": "detailer", "sha256": "0" * 64}}),
        lambda payload: payload["resources"].append({"kind": "detailer", "name": "second-face-yolo.pt", "sha256": "e" * 64}),
    ],
)
def test_non_upscale_postprocess_references_must_have_unique_compatible_resources(mutate) -> None:
    payload = _auditable_exact_payload()
    payload["postprocess"][0].update({"kind": "face_restore", "resource": {"kind": "detailer", "sha256": "e" * 64}})
    payload["detailers"][0]["resource"] = None
    mutate(payload)

    with pytest.raises(ValidationError, match="postprocess\\[0\\]\\.resource"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


def test_modelled_face_restore_without_auditable_resource_fails_closed() -> None:
    payload = _auditable_exact_payload()
    payload["postprocess"][0] = {"kind": "face_restore", "model": "face-yolo.pt"}
    payload["confirmed"] = [
        item
        for item in payload["confirmed"]
        if item["canonical_field"] != "postprocess[0].resource"
    ]
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is ReproductionLevel.NOT_REPRODUCIBLE
    assert "postprocess[0].resource" in report.critical_missing
    assert report.requirements["dependencies"] is False


def test_unknown_modelled_postprocess_without_auditable_resource_fails_closed() -> None:
    payload = _auditable_exact_payload()
    payload["postprocess"][0] = {"kind": "mystery_vendor_filter", "model": "some-model.bin"}
    payload["confirmed"] = [
        item
        for item in payload["confirmed"]
        if item["canonical_field"] != "postprocess[0].resource"
    ]
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is ReproductionLevel.NOT_REPRODUCIBLE
    assert "postprocess[0].resource" in report.critical_missing
    assert report.requirements["dependencies"] is False


def test_unknown_postprocess_external_model_param_without_auditable_resource_fails_closed() -> None:
    payload = _auditable_exact_payload()
    payload["postprocess"][0] = {
        "kind": "mystery_vendor_filter",
        "params": {"model_name": "some-model.bin"},
    }
    payload["confirmed"] = [
        item
        for item in payload["confirmed"]
        if item["canonical_field"] != "postprocess[0].resource"
    ]
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is ReproductionLevel.NOT_REPRODUCIBLE
    assert "postprocess[0].resource" in report.critical_missing
    assert report.requirements["dependencies"] is False


@pytest.mark.parametrize(
    "seed",
    [
        9223372036854775807,
        9223372036854775808,
    ],
)
def test_sampling_seed_uses_signed_64_bit_persistence_range(seed: int) -> None:
    payload = _complete_payload()
    payload["sampling"]["seed"] = seed

    if seed == 9223372036854775807:
        recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
        assert recipe.sampling is not None
        assert recipe.sampling.seed == seed
    else:
        with pytest.raises(ValidationError, match="less than or equal to 9223372036854775807"):
            GenerationRecipe.model_validate(normalize_recipe_payload(payload))


@pytest.mark.parametrize(
    "reference",
    [
        {"kind": "detailer", "civitai_model_version_id": 200},
        {"kind": "detailer", "civitai_model_id": 100, "civitai_model_version_id": 200},
    ],
)
def test_resource_reference_accepts_stable_civitai_model_and_version_identities(reference: dict) -> None:
    payload = _auditable_exact_payload()
    payload["resources"][4].update({"civitai_model_id": 100, "civitai_model_version_id": 200})
    payload["detailers"][0]["resource"] = reference

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    assert recipe.detailers[0].resource is not None
    assert recipe.detailers[0].resource.civitai_model_version_id == 200


def test_resource_reference_conflicting_civitai_identity_fails_closed() -> None:
    payload = _auditable_exact_payload()
    payload["resources"][3].update({"civitai_model_id": 100, "civitai_model_version_id": 200})
    payload["controls"][0]["resource"] = {
        "kind": "controlnet",
        "civitai_model_id": 100,
        "civitai_model_version_id": 999,
    }

    with pytest.raises(ValidationError, match="controls\\[0\\]\\.resource"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


def test_model_page_url_with_slug_and_version_query_is_accepted_and_preserved() -> None:
    url = "https://civitai.com/models/123/a-model-slug?modelVersionId=456"
    source = RecipeSource(url=url)
    assert source.url == url


@pytest.mark.parametrize(
    "url",
    [
        "http://civitai.com/models/123/a-model-slug",
        "https://user@civitai.com/models/123/a-model-slug",
        "https://civitai.com:443/models/123/a-model-slug",
        "https://civitai.com/models/not-an-id/a-model-slug",
        "https://civitai.com/models/123/",
    ],
)
def test_model_page_url_with_invalid_transport_or_structure_fails_closed(url: str) -> None:
    with pytest.raises(ValidationError):
        RecipeSource(url=url)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["passes"][1].update({"upscale_model": None, "upscale_resource": {"kind": "upscaler", "sha256": "0" * 64}}),
        lambda payload: payload["passes"][1].update({"upscale_resource": {"kind": "lora", "sha256": "b" * 64}}),
        lambda payload: payload["passes"][1].update({"upscale_model": "different.pth"}),
        lambda payload: payload["resources"].append({"kind": "upscaler", "name": "second-4x-anime.pth", "sha256": "f" * 64}),
    ],
)
def test_pass_upscale_resource_is_always_unique_and_consistent_with_upscale_model(mutate) -> None:
    payload = _auditable_exact_payload()
    mutate(payload)
    payload["postprocess"][0]["resource"] = None

    with pytest.raises(ValidationError, match="passes\\[1\\]\\.upscale_resource|passes\\[1\\]\\.upscale_model"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


def test_exact_ready_fails_closed_when_checkpoint_loader_name_is_not_the_recipe_resource() -> None:
    payload = _auditable_exact_payload()
    payload["workflow"]["snapshot"]["1"]["inputs"]["ckpt_name"] = "totally-different.safetensors"
    payload["workflow"]["snapshot_sha256"] = _sha_json(payload["workflow"]["snapshot"])
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow_resources"] is False


def test_recipe_source_rejects_conflicting_image_id_and_image_url_identity() -> None:
    with pytest.raises(ValidationError, match="image_id"):
        RecipeSource(image_id=123, url="https://civitai.com/images/999")


@pytest.mark.parametrize(
    ("field", "value", "url"),
    [
        ("post_id", 123, "https://civitai.com/posts/999"),
        ("model_id", 123, "https://civitai.com/models/999/a-model"),
        ("model_version_id", 123, "https://civitai.com/models/999/a-model?modelVersionId=456"),
    ],
)
def test_recipe_source_rejects_conflicting_post_model_and_model_version_url_identities(
    field: str, value: int, url: str
) -> None:
    with pytest.raises(ValidationError, match=field):
        RecipeSource(**{field: value, "url": url})


@pytest.mark.parametrize(
    "query_name,query_values",
    [
        ("modelVersionId", ("456", "789")),
        ("modelId", ("456", "789")),
    ],
)
def test_recipe_source_rejects_ambiguous_repeated_model_identity_query_values(
    query_name: str, query_values: tuple[str, str]
) -> None:
    url = f"https://civitai.com/models/999/a-model?{query_name}={query_values[0]}&{query_name}={query_values[1]}"

    with pytest.raises(ValidationError, match=query_name):
        RecipeSource(url=url)


@pytest.mark.parametrize(
    "query_name,invalid_value",
    [
        ("modelVersionId", "0"),
        ("modelVersionId", "-1"),
        ("modelVersionId", "not-an-id"),
        ("modelId", "0"),
        ("modelId", "-1"),
        ("modelId", "not-an-id"),
    ],
)
def test_recipe_source_rejects_non_positive_or_non_integer_model_identity_query_values(
    query_name: str, invalid_value: str
) -> None:
    url = f"https://civitai.com/models/999/a-model?{query_name}={invalid_value}"

    with pytest.raises(ValidationError, match=query_name):
        RecipeSource(url=url)


@pytest.mark.parametrize(
    "field,query_name,supplied_value,query_value",
    [
        ("model_version_id", "modelVersionId", 123, 456),
        ("model_id", "modelId", 123, 456),
    ],
)
def test_recipe_source_rejects_supplied_model_identity_that_conflicts_with_unique_query_value(
    field: str, query_name: str, supplied_value: int, query_value: int
) -> None:
    url = f"https://civitai.com/models/999/a-model?{query_name}={query_value}"

    with pytest.raises(ValidationError, match=field):
        RecipeSource(**{field: supplied_value, "url": url})


@pytest.mark.parametrize(
    ("class_type", "input_name", "resource_kind", "resource_name", "resource_sha"),
    [
        ("UNETLoader", "unet_name", "diffusion_model", "unet.safetensors", "2" * 64),
        ("CLIPLoader", "clip_name", "text_encoder", "text_encoder.safetensors", "3" * 64),
        ("VAELoader", "vae_name", "vae", "vae.safetensors", "4" * 64),
        ("LoraLoader", "lora_name", "lora", "style.safetensors", "b" * 64),
        ("ControlNetLoader", "control_net_name", "controlnet", "openpose.safetensors", "d" * 64),
        ("UpscaleModelLoader", "model_name", "upscaler", "4x-anime.pth", "f" * 64),
        ("UltralyticsDetectorProvider", "model_name", "detailer", "face-yolo.pt", "e" * 64),
    ],
)
def test_exact_ready_binds_each_recognized_workflow_loader_to_a_matching_resource(
    class_type: str,
    input_name: str,
    resource_kind: str,
    resource_name: str,
    resource_sha: str,
) -> None:
    payload = _auditable_exact_payload()
    payload["workflow"]["snapshot"]["loader"] = {
        "class_type": class_type,
        "inputs": {input_name: resource_name},
    }
    payload["workflow"]["snapshot_sha256"] = _sha_json(payload["workflow"]["snapshot"])
    for evidence in payload["confirmed"]:
        if evidence["reference"] == payload["workflow"]["reference"]:
            evidence["snapshot_sha256"] = payload["workflow"]["snapshot_sha256"]
    payload["runtime"]["node_versions"][class_type] = "c" * 64
    if resource_kind in {"diffusion_model", "text_encoder", "vae"}:
        payload["resources"].append({"kind": resource_kind, "name": resource_name, "sha256": resource_sha})
        index = len(payload["resources"]) - 1
        payload["confirmed"].append(
            {
                "canonical_field": f"resources[{index}].identity",
                "source": "embedded_metadata",
                "reference": payload["runtime"]["reference"],
                "snapshot_sha256": payload["runtime"]["runtime_lock_sha256"],
            }
        )
    payload["runtime"]["resource_locks"].append(
        {
            "node_id": "loader",
            "input_name": input_name,
            "resource": {"kind": resource_kind, "sha256": resource_sha},
        }
    )
    payload["evidence_manifest"] = _evidence_manifest_for(payload)
    matching_recipe = _trusted_recipe(payload)
    assert assess_reproduction(matching_recipe).level is ReproductionLevel.EXACT_READY

    payload["workflow"]["snapshot"]["loader"]["inputs"][input_name] = "totally-different.safetensors"
    payload["workflow"]["snapshot_sha256"] = _sha_json(payload["workflow"]["snapshot"])
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow_resources"] is False


def test_exact_ready_rejects_declared_operations_without_workflow_edges() -> None:
    """A base KSampler alone cannot attest to declared out-of-graph pipeline stages."""
    payload = _auditable_exact_payload()
    payload["workflow"]["snapshot"] = _complete_workflow()
    payload["workflow"]["operation_bindings"] = []
    payload["workflow"]["snapshot_sha256"] = _sha_json(payload["workflow"]["snapshot"])
    payload["runtime"]["node_versions"] = {
        key: value for key, value in payload["runtime"]["node_versions"].items()
        if key in {"CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler"}
    }
    payload["evidence_manifest"] = _evidence_manifest_for(payload)

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow_declared_operations"] is False


@pytest.mark.parametrize("section,index", [("controls", 0), ("detailers", 0), ("postprocess", 0)])
def test_model_filename_must_match_resolved_resource_name_for_all_modelled_dependencies(
    section: str, index: int
) -> None:
    payload = _auditable_exact_payload()
    payload[section][index]["model"] = "different-model.bin"

    with pytest.raises(ValidationError, match=rf"{section}\[{index}\]\.model"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


def test_raw_evidence_snapshot_labels_cannot_confirm_source_identity_without_typed_manifest() -> None:
    payload = _auditable_exact_payload()
    payload["raw"]["evidence_snapshots"] = {"civitai:image:123:source": "6" * 64}
    payload["evidence_manifest"] = []

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["confirmed_source_identity"] is False


def test_typed_manifest_recomputes_digest_and_rejects_payload_mutation() -> None:
    payload = _auditable_exact_payload()
    payload["evidence_manifest"] = _evidence_manifest_for(payload)
    payload["evidence_manifest"][0]["payload"]["image_id"] = 999

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["confirmed_source_identity"] is False


def test_evidence_manifest_ignores_caller_assertion_value_when_pointer_still_derives_recipe_value() -> None:
    payload = _auditable_exact_payload()
    payload["evidence_manifest"] = _evidence_manifest_for(payload)
    for entry in payload["evidence_manifest"]:
        for assertion in entry["assertions"]:
            if assertion["canonical_field"] == "sampling":
                assertion["value"] = {"seed": 0}

    recipe = _trusted_recipe(payload)
    report = assess_reproduction(recipe)

    assert report.level is ReproductionLevel.EXACT_READY
    assert report.requirements["confirmed_sampling"] is True


def _evidence_manifest_for(payload: dict) -> list[dict]:
    """Build one digest-bound pointer assertion per canonical confirmation."""
    payload["runtime"]["runtime_lock_sha256"] = _runtime_lock_for_payload(payload["runtime"])
    payload["runtime"]["inspection_snapshot"] = {"runtime_lock": {
        "engine": payload["runtime"]["engine"], "engine_version": payload["runtime"]["engine_version"],
        "node_versions": payload["runtime"]["node_versions"], "package_versions": payload["runtime"]["package_versions"],
        "runtime_settings": payload["runtime"]["runtime_settings"], "resource_locks": payload["runtime"]["resource_locks"],
    }}
    recipe = GenerationRecipe.model_validate(normalize_recipe_payload({**payload, "evidence_manifest": []}))
    manifests: list[dict] = []
    for index, evidence in enumerate(payload["confirmed"]):
        field = evidence["canonical_field"]
        if field == "runtime":
            evidence["source"] = "runtime_inspection"
            evidence["reference"] = payload["runtime"]["reference"]
            evidence_payload = payload["runtime"]["inspection_snapshot"]
            path = "/runtime_lock"
        else:
            evidence["reference"] = f"evidence:{index}:{field}"
            evidence_payload = {"value": _canonical_value_for_fixture(recipe, field)}
            path = "/value"
        manifest = {
            "identity": f"evidence:{index}",
            "reference": evidence["reference"],
            "payload": evidence_payload,
            "assertions": [{"canonical_field": field, "path": path, "extractor": "json_pointer"}],
        }
        manifest["sha256"] = _sha_json({
            "identity": manifest["identity"], "reference": manifest["reference"],
            "payload": manifest["payload"], "assertions": manifest["assertions"],
        })
        evidence["snapshot_sha256"] = manifest["sha256"]
        manifests.append(manifest)
    return manifests


def _canonical_value_for_fixture(recipe: GenerationRecipe, field: str):
    if field == "source.identity":
        if recipe.source.image_id is not None:
            return {"image_id": recipe.source.image_id}
        return {key: value for key, value in recipe.source.model_dump(exclude_none=True).items() if key in {"url", "media_url"}}
    if field == "workflow":
        return recipe.workflow.snapshot
    if field == "sampling":
        return recipe.sampling.model_dump(exclude_none=True)
    if field == "conditioning":
        return {"base_prompt": recipe.base_prompt, "negative_prompt": recipe.negative_prompt}
    if field == "runtime":
        return canonical_runtime_lock_document(recipe.runtime)
    match = __import__("re").fullmatch(r"resources\[([0-9]+)\]\.identity", field)
    if match:
        return recipe.resources[int(match.group(1))].model_dump(exclude_none=True)
    match = __import__("re").fullmatch(r"inputs\[([0-9]+)\]\.sha256", field)
    if match:
        return recipe.inputs[int(match.group(1))].sha256
    match = __import__("re").fullmatch(r"(controls|detailers|postprocess)\[([0-9]+)\]\.resource", field)
    if match:
        return getattr(recipe, match.group(1))[int(match.group(2))].resource.model_dump(exclude_none=True)
    match = __import__("re").fullmatch(r"passes\[([0-9]+)\]\.upscale_resource", field)
    if match:
        return recipe.passes[int(match.group(1))].upscale_resource.model_dump(exclude_none=True)
    raise AssertionError(field)


def test_confirmed_assertion_value_cannot_attest_to_an_unrelated_digest_bound_payload() -> None:
    """The payload, not a caller-controlled assertion.value, must derive confirmation."""
    payload = _auditable_exact_payload()
    manifests = _evidence_manifest_for(payload)
    for manifest in manifests:
        manifest["payload"] = {"unrelated": True}
        manifest["sha256"] = _sha_json(manifest["payload"])
    payload["evidence_manifest"] = manifests

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    assert assess_reproduction(recipe).level is not ReproductionLevel.EXACT_READY


def test_runtime_lock_sha256_is_recomputed_from_the_canonical_runtime_document() -> None:
    payload = _auditable_exact_payload()
    payload["evidence_manifest"] = _evidence_manifest_for(payload)
    payload["runtime"]["runtime_lock_sha256"] = "0" * 64

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    assert assess_reproduction(recipe).level is not ReproductionLevel.EXACT_READY
    assert assess_reproduction(recipe).requirements["runtime"] is False


def test_pass_without_declared_upscale_dependency_needs_sampler_binding_but_no_upscaler_resource() -> None:
    payload = _auditable_exact_payload()
    payload["passes"] = [{"name": "base", "sampling": dict(payload["sampling"])}]
    payload["workflow"]["operation_bindings"] = [
        binding for binding in payload["workflow"]["operation_bindings"]
        if binding["canonical_field"] != "passes[1]"
    ]
    payload["confirmed"] = [
        item for item in payload["confirmed"]
        if item["canonical_field"] != "passes[1].upscale_resource"
    ]
    payload["evidence_manifest"] = _evidence_manifest_for(payload)

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    assert assess_reproduction(recipe).level is not ReproductionLevel.EXACT_READY
    assert assess_reproduction(recipe).requirements["pass_sampling"] is False


def test_runtime_lock_with_an_extra_conflicting_civitai_file_id_fails_closed() -> None:
    payload = _auditable_exact_payload()
    payload["runtime"]["resource_locks"][0]["resource"]["civitai_file_id"] = 999
    payload["evidence_manifest"] = _evidence_manifest_for(payload)

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    assert assess_reproduction(recipe).level is not ReproductionLevel.EXACT_READY


def test_control_percentages_must_be_ordered_and_resource_identities_cannot_be_blank() -> None:
    payload = _complete_payload()
    payload["controls"][0].update({"start_percent": 0.8, "end_percent": 0.2})
    with pytest.raises(ValidationError, match="start_percent"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))

    payload = _complete_payload()
    payload["resources"][0]["air"] = "   "
    with pytest.raises(ValidationError, match="air"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


def _refresh_exact_evidence(payload: dict) -> None:
    """Re-hash intentionally mutated fixtures; the gate must inspect content, not stale digests."""
    payload["workflow"]["snapshot_sha256"] = _sha_json(payload["workflow"]["snapshot"])
    payload["evidence_manifest"] = _evidence_manifest_for(payload)


def test_exact_ready_requires_explicit_pass_to_ksampler_binding_not_workflow_order() -> None:
    payload = _auditable_exact_payload()
    payload["passes"] = [{"name": "base", "sampling": dict(payload["sampling"])}]
    payload["workflow"]["operation_bindings"] = [
        binding for binding in payload["workflow"]["operation_bindings"]
        if binding["canonical_field"] != "passes[1]"
    ]
    payload["confirmed"] = [item for item in payload["confirmed"] if item["canonical_field"] != "passes[1].upscale_resource"]
    _refresh_exact_evidence(payload)

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["pass_sampling"] is False


def test_exact_ready_rejects_ksampler_sampling_mutation_after_rehashing_evidence() -> None:
    payload = _auditable_exact_payload()
    for generation_pass, node_id in zip(payload["passes"], ("5", "7")):
        generation_pass["ksampler_node_id"] = node_id
    payload["workflow"]["snapshot"]["5"]["inputs"].update({
        "seed": 0, "steps": 1, "cfg": 1.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 0.1,
    })
    _refresh_exact_evidence(payload)

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["pass_sampling"] is False


@pytest.mark.parametrize("class_type,input_name", [
    ("VendorCheckpointLoader", "checkpoint_file"),
    ("VendorLoRAStack", "weights"),
    ("VendorControlLoader", "control_model"),
    ("VendorIPAdapterLoader", "model_file"),
])
def test_exact_ready_fails_closed_for_unclassified_custom_resource_loader(class_type: str, input_name: str) -> None:
    payload = _auditable_exact_payload()
    payload["workflow"]["snapshot"]["custom"] = {"class_type": class_type, "inputs": {input_name: "unlocked.bin"}}
    payload["runtime"]["node_versions"][class_type] = "0" * 64
    _refresh_exact_evidence(payload)

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow_resources"] is False


def test_global_resource_ledger_rejects_same_civitai_file_id_with_different_sha() -> None:
    payload = _auditable_exact_payload()
    payload["resources"].append({
        "kind": "lora", "name": "conflict.safetensors", "sha256": "9" * 64, "civitai_file_id": 301,
    })

    with pytest.raises(ValidationError, match="ledger|identity"):
        GenerationRecipe.model_validate(normalize_recipe_payload(payload))


def test_user_supplied_or_forged_source_labels_cannot_establish_exact_confirmation() -> None:
    payload = _auditable_exact_payload()
    for item in payload["confirmed"]:
        item["source"] = "user_supplied"
    _refresh_exact_evidence(payload)

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["confirmed_source_identity"] is False


@pytest.mark.parametrize(
    "source",
    ["civitai_api", "embedded_metadata", "workflow_snapshot", "runtime_inspection"],
)
def test_normal_importer_payload_cannot_forge_authoritative_confirmation_with_valid_manifest(
    source: str,
) -> None:
    """Caller-selected labels and self-hashed payloads are not a trust boundary."""
    payload = _auditable_exact_payload()
    for evidence in payload["confirmed"]:
        evidence["source"] = source
    _refresh_exact_evidence(payload)

    direct_recipe = GenerationRecipe.model_validate(payload)
    normalized = normalize_recipe_payload(payload)
    recipe = GenerationRecipe.model_validate(normalized)
    direct_report = assess_reproduction(direct_recipe)
    report = assess_reproduction(recipe)

    assert direct_report.level is not ReproductionLevel.EXACT_READY
    assert normalized["confirmed"] == []
    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["confirmed_source_identity"] is False


def test_internal_acquisition_or_inspection_constructor_can_grant_confirmed_evidence() -> None:
    recipe = _trusted_recipe(_auditable_exact_payload())
    report = assess_reproduction(recipe)

    assert report.level is ReproductionLevel.EXACT_READY
    assert report.requirements["confirmed_source_identity"] is True


def test_exact_ready_rejects_disconnected_or_wrong_typed_ksampler_links_after_rehashing() -> None:
    payload = _auditable_exact_payload()
    for generation_pass, node_id in zip(payload["passes"], ("5", "7")):
        generation_pass["ksampler_node_id"] = node_id
    sampler = payload["workflow"]["snapshot"]["5"]["inputs"]
    sampler.update({"model": ["4", 0], "positive": ["1", 0], "negative": ["4", 0], "latent_image": ["1", 0]})
    _refresh_exact_evidence(payload)

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow"] is False


def test_declared_operation_resource_lock_requires_full_bidirectional_identity_tuple() -> None:
    payload = _auditable_exact_payload()
    resource = payload["resources"][3]
    resource.update({"civitai_model_id": 401, "civitai_model_version_id": 402, "civitai_file_id": 403, "air": "urn:air:control:403"})
    identity = {key: resource[key] for key in ("kind", "sha256", "civitai_model_id", "civitai_model_version_id", "civitai_file_id", "air")}
    payload["controls"][0]["resource"] = dict(identity)
    for binding in payload["workflow"]["operation_bindings"]:
        if binding["canonical_field"] == "controls[0]":
            binding["resource"] = dict(identity)
    for lock in payload["runtime"]["resource_locks"]:
        if lock["node_id"] == "control":
            lock["resource"] = dict(identity)
    # An otherwise matching SHA cannot omit a Civitai/AIR component on an exact edge.
    for binding in payload["workflow"]["operation_bindings"]:
        if binding["canonical_field"] == "controls[0]":
            binding["resource"].pop("civitai_file_id")
    _refresh_exact_evidence(payload)

    recipe = GenerationRecipe.model_validate(normalize_recipe_payload(payload))
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow_resources"] is True
    assert report.requirements["workflow_declared_operations"] is False


def test_public_model_validate_demotes_caller_confirmed_records_before_model_dump() -> None:
    """A future API/DB/gallery caller must not need to remember normalization first."""
    recipe = GenerationRecipe.model_validate(_auditable_exact_payload())

    assert recipe.confirmed == []
    assert recipe.model_dump()["confirmed"] == []
    assert recipe.inferred


def test_trusted_recipe_builder_requires_an_explicit_nonserializable_capability() -> None:
    with pytest.raises((PermissionError, TypeError)):
        _build_recipe_from_trusted_evidence(_auditable_exact_payload())


def test_exact_ready_rejects_a_workflow_without_terminal_decode_and_save_path() -> None:
    payload = _auditable_exact_payload()
    payload["workflow"]["snapshot"].pop("8")
    payload["workflow"]["snapshot"].pop("9")
    _refresh_exact_evidence(payload)

    recipe = _trusted_recipe(payload)
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow"] is False


def test_exact_ready_rejects_hires_pass_that_reuses_base_empty_latent_after_rehashing() -> None:
    payload = _auditable_exact_payload()
    for generation_pass, node_id in zip(payload["passes"], ("5", "7")):
        generation_pass["ksampler_node_id"] = node_id
    payload["workflow"]["snapshot"]["7"]["inputs"]["latent_image"] = ["4", 0]
    _refresh_exact_evidence(payload)

    recipe = _trusted_recipe(payload)
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["pass_sampling"] is False


def test_exact_ready_rejects_unknown_custom_node_even_when_input_name_avoids_substring_heuristics() -> None:
    payload = _auditable_exact_payload()
    payload["workflow"]["snapshot"]["custom"] = {
        "class_type": "VendorArtifactFetch",
        "inputs": {"artifact": "remote-model.bin"},
    }
    payload["runtime"]["node_versions"]["VendorArtifactFetch"] = "0" * 64
    _refresh_exact_evidence(payload)

    recipe = _trusted_recipe(payload)
    report = assess_reproduction(recipe)

    assert report.level is not ReproductionLevel.EXACT_READY
    assert report.requirements["workflow_resources"] is False
