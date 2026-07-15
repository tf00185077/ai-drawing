"""Offline CIV-B acquisition contract tests."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path

import pytest

from app.schemas.generation_recipe import GenerationRecipe, ResourceKind, assess_reproduction
from app.services.civitai_acquisition import (
    AcquisitionError,
    AcquisitionResult,
    CivitaiTransportResponse,
    acquire_civitai_recipe,
    parse_civitai_locator,
)
from app.services.civitai_embedded_metadata import extract_embedded_metadata


FIXTURES = Path(__file__).parent / "fixtures" / "civitai"


def _json_fixture(name: str) -> dict:
    return json.loads((FIXTURES / "api" / name).read_text(encoding="utf-8"))


@dataclass
class FakeTransport:
    responses: list[CivitaiTransportResponse]

    def __post_init__(self) -> None:
        self.calls: list[dict] = []

    def get_json(self, url: str, *, params: dict | None = None, headers: dict | None = None) -> CivitaiTransportResponse:
        self.calls.append({"url": url, "params": dict(params or {}), "headers": dict(headers or {})})
        if not self.responses:
            raise AssertionError("unexpected transport call")
        return self.responses.pop(0)


def test_supported_locators_are_canonicalized_and_unsafe_or_conflicting_locators_are_rejected() -> None:
    image = parse_civitai_locator("123")
    assert image.kind == "image"
    assert image.image_id == 123
    assert image.canonical_url == "https://civitai.com/images/123"

    post = parse_civitai_locator("https://www.civitai.com/posts/777")
    assert post.kind == "post"
    assert post.post_id == 777
    assert post.canonical_url == "https://civitai.com/posts/777"

    model = parse_civitai_locator("https://civitai.com/models/999/a-model?modelVersionId=456")
    assert model.kind == "model"
    assert model.model_id == 999
    assert model.model_version_id == 456
    assert model.canonical_url == "https://civitai.com/models/999/a-model?modelVersionId=456"

    cdn = parse_civitai_locator("https://images.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example/width=832/example.webp")
    assert cdn.kind == "cdn"
    assert cdn.media_url == "https://images.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example/width=832/example.webp"

    for unsafe in (
        "http://civitai.com/images/123",
        "https://user:secret@civitai.com/images/123",
        "https://evil.example/images/123",
        "0",
        "https://civitai.com/images/123?imageId=999",
    ):
        with pytest.raises(AcquisitionError) as exc_info:
            parse_civitai_locator(unsafe)
        assert exc_info.value.code == "unsupported_locator"


@pytest.mark.parametrize(
    "locator",
    [
        "0",
        "-1",
        "12.3",
        "http://civitai.com/images/123",
        "https://user:secret@civitai.com/images/123",
        "https://civitai.com:443/images/123",
        "https://evil.example/images/123",
        "https://civitai.com.evil/images/123",
        "https://civitai.com/images/not-an-id",
        "https://civitai.com/images/123?imageId=999",
        "https://civitai.com/images/123?postId=777",
        "https://civitai.com/posts/777?imageId=123",
        "https://civitai.com/models/999/a-model?imageId=123",
        "https://civitai.com/models/999/a-model?modelId=123",
        "https://civitai.com/models/999/a-model?modelVersionId=0",
        "https://civitai.com/models/999/a-model?modelVersionId=456&modelVersionId=789",
        "https://images.civitai.com/",
    ],
)
def test_strict_locator_parser_rejects_unsafe_or_conflicting_identity(locator: str) -> None:
    with pytest.raises(AcquisitionError) as exc_info:
        parse_civitai_locator(locator)
    assert exc_info.value.code == "unsupported_locator"


def test_image_locator_uses_public_images_query_endpoint_with_image_id() -> None:
    transport = FakeTransport(
        [CivitaiTransportResponse(200, {"items": [_json_fixture("image_123.json")]}, {})]
    )

    result = acquire_civitai_recipe("123", transport=transport)

    assert result.image_id == 123
    assert transport.calls == [
        {
            "url": "https://civitai.com/api/v1/images",
            "params": {"withMeta": "true", "imageId": 123},
            "headers": {},
        }
    ]


def test_exact_image_locator_retries_soft_rating_when_default_filter_hides_candidate() -> None:
    image = _json_fixture("image_123.json")
    transport = FakeTransport([
        CivitaiTransportResponse(200, {"items": []}, {}),
        CivitaiTransportResponse(200, {"items": [image]}, {}),
    ])

    result = acquire_civitai_recipe("123", transport=transport)

    assert result.image_id == 123
    assert [call["params"] for call in transport.calls] == [
        {"withMeta": "true", "imageId": 123},
        {"withMeta": "true", "imageId": 123, "nsfw": "Soft"},
    ]
    assert [entry["params"] for entry in result.provenance["requests"]] == [
        {"withMeta": "true", "imageId": 123},
        {"withMeta": "true", "imageId": 123, "nsfw": "Soft"},
    ]


def test_images_requests_force_with_meta_and_ambiguous_post_or_model_fails_closed() -> None:
    transport = FakeTransport(
        [CivitaiTransportResponse(200, _json_fixture("post_777_images.json"), {})]
    )
    assert acquire_civitai_recipe("https://civitai.com/posts/777", transport=transport).image_id == 123
    assert [call["params"]["withMeta"] for call in transport.calls] == ["true"]

    model_transport = FakeTransport(
        [CivitaiTransportResponse(200, _json_fixture("model_999_images_unique.json"), {})]
    )
    assert acquire_civitai_recipe("https://civitai.com/models/999/a-model", transport=model_transport).image_id == 124
    assert [call["params"]["withMeta"] for call in model_transport.calls] == ["true"]

    for locator, fixture, code in (
        ("https://civitai.com/posts/888", "empty_images.json", "not_found"),
        ("https://civitai.com/models/999/a-model", "model_999_images_ambiguous.json", "ambiguous_locator"),
    ):
        with pytest.raises(AcquisitionError) as exc_info:
            acquire_civitai_recipe(locator, transport=FakeTransport([CivitaiTransportResponse(200, _json_fixture(fixture), {})]))
        assert exc_info.value.code == code


def test_retry_policy_is_bounded_and_authorization_is_redacted(caplog: pytest.LogCaptureFixture) -> None:
    secret = "TEST_AUTHORIZATION_SECRET"
    for status in (429, 500, 503):
        sleeps: list[float] = []
        transport = FakeTransport([
            CivitaiTransportResponse(status, {"error": secret}, {"Retry-After": "2"}),
            CivitaiTransportResponse(status, {"error": secret}, {}),
            CivitaiTransportResponse(200, _json_fixture("image_123.json"), {}),
        ])
        result = acquire_civitai_recipe(
            "123", transport=transport, authorization=f"Bearer {secret}",
            backoff=lambda attempt, response: attempt / 2, sleep=sleeps.append,
        )
        assert result.status == "ok"
        assert len(transport.calls) == 3
        assert sleeps == [2.0, 1.0]
        assert secret not in json.dumps(result.to_dict(), sort_keys=True)

    exhausted = FakeTransport([CivitaiTransportResponse(503, {"error": secret}, {})] * 3)
    with pytest.raises(AcquisitionError) as exc_info:
        acquire_civitai_recipe("123", transport=exhausted, authorization=f"Bearer {secret}", sleep=lambda _: None)
    assert exc_info.value.code == "retry_exhausted"
    assert len(exhausted.calls) == 3
    assert [entry["attempt"] for entry in exc_info.value.provenance["requests"]] == [1, 2, 3]

    for status in (400, 401, 403, 404):
        transport = FakeTransport([CivitaiTransportResponse(status, {"error": secret}, {})])
        with pytest.raises(AcquisitionError) as non_retry:
            acquire_civitai_recipe("123", transport=transport, authorization=f"Bearer {secret}", sleep=lambda _: None)
        assert len(transport.calls) == 1
        assert secret not in str(non_retry.value)
        assert secret not in json.dumps(non_retry.value.provenance, sort_keys=True)
    assert secret not in caplog.text


def test_post_and_model_resolution_fail_closed_without_unique_candidate() -> None:
    post_result = acquire_civitai_recipe(
        "https://civitai.com/posts/777",
        transport=FakeTransport([CivitaiTransportResponse(200, _json_fixture("post_777_images.json"), {})]),
    )
    assert post_result.image_id == 123

    with pytest.raises(AcquisitionError) as not_found:
        acquire_civitai_recipe(
            "https://civitai.com/posts/888",
            transport=FakeTransport([CivitaiTransportResponse(200, _json_fixture("empty_images.json"), {})]),
        )
    assert not_found.value.code == "not_found"

    with pytest.raises(AcquisitionError) as ambiguous:
        acquire_civitai_recipe(
            "https://civitai.com/models/999/a-model",
            transport=FakeTransport([CivitaiTransportResponse(200, _json_fixture("model_999_images_ambiguous.json"), {})]),
        )
    assert ambiguous.value.code == "ambiguous_locator"


def test_nested_live_api_meta_is_normalized_without_losing_raw_payload() -> None:
    image = _json_fixture("image_123.json")
    generation_meta = image["meta"]
    image["meta"] = {"id": image["id"], "meta": generation_meta, "outerVendorField": "preserved"}

    result = acquire_civitai_recipe(
        "123",
        transport=FakeTransport([CivitaiTransportResponse(200, {"items": [image]}, {})]),
    )

    recipe = result.recipe
    assert recipe is not None
    assert recipe.base_prompt == generation_meta["prompt"]
    assert recipe.sampling is not None
    assert recipe.sampling.seed == 9223372036854775807
    assert len(recipe.resources) == 3
    assert recipe.passes
    assert result.raw_api_payload is not None
    assert result.raw_api_payload == image
    assert result.raw_api_payload["meta"]["outerVendorField"] == "preserved"


def test_base_txt2img_sampling_uses_auditable_execution_semantics_when_metadata_omits_them() -> None:
    image = _json_fixture("image_123.json")
    image["meta"].pop("scheduler", None)
    image["meta"].pop("Schedule type", None)
    image["meta"]["sampler"] = "Euler a"
    image["meta"]["Denoising strength"] = "0.4"

    result = acquire_civitai_recipe(
        "123",
        transport=FakeTransport([CivitaiTransportResponse(200, image, {})]),
    )

    assert result.recipe is not None
    assert result.recipe.sampling is not None
    assert result.recipe.sampling.scheduler == "normal"
    assert result.recipe.sampling.denoise == 1.0
    assert result.recipe.passes[0].sampling.denoise is None
    assert result.raw_api_payload is not None
    assert result.raw_api_payload["meta"]["Denoising strength"] == "0.4"


def test_single_image_model_version_identity_is_bound_to_sole_checkpoint() -> None:
    image = _json_fixture("image_123.json")
    image["modelVersionIds"] = [2940478]
    image["meta"]["resources"] = [
        {"name": "illustriousXL_v10.safetensors", "type": "model", "hash": "fa486caafc"}
    ]

    result = acquire_civitai_recipe(
        "123",
        transport=FakeTransport([
            CivitaiTransportResponse(200, {"items": [image]}, {}),
            CivitaiTransportResponse(200, {
                "id": 2940478,
                "files": [{
                    "id": 7654321,
                    "hashes": {"SHA256": "fa486caafc330f133605d3c18b418d183812f14946631c6544bfb28730db6d6f"},
                }],
            }, {}),
        ]),
    )

    assert result.recipe is not None
    assert len(result.recipe.resources) == 1
    assert result.recipe.resources[0].kind == ResourceKind.CHECKPOINT
    assert result.recipe.resources[0].civitai_model_version_id == 2940478
    assert result.recipe.resources[0].civitai_file_id == 7654321
    assert result.recipe.resources[0].sha256 == "fa486caafc330f133605d3c18b418d183812f14946631c6544bfb28730db6d6f"


def test_identity_only_civitai_resources_resolve_names_and_hashes_via_model_versions() -> None:
    image = _json_fixture("image_123.json")
    image["modelVersionIds"] = [2883731, 1835318]
    image["meta"]["resources"] = []
    image["meta"]["civitaiResources"] = [
        {"type": "checkpoint", "weight": 1, "modelVersionId": 2883731},
        {"type": "lora", "weight": 0.8, "modelVersionId": 1835318},
    ]

    transport = FakeTransport([
        CivitaiTransportResponse(200, {"items": [image]}, {}),
        CivitaiTransportResponse(200, {
            "id": 2883731,
            "modelId": 827184,
            "model": {"name": "WAI-illustrious-SDXL", "type": "Checkpoint"},
            "files": [{
                "id": 111222,
                "name": "waiIllustriousSDXL_v170.safetensors",
                "primary": True,
                "hashes": {"SHA256": "F116B0C78FF44146AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
            }],
        }, {}),
        CivitaiTransportResponse(200, {
            "id": 1835318,
            "modelId": 555555,
            "model": {"name": "Size Slider", "type": "LORA"},
            "files": [{
                "id": 333444,
                "name": "size-slider-illustrious.safetensors",
                "hashes": {"SHA256": "F780407226B00477BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"},
            }],
        }, {}),
    ])
    result = acquire_civitai_recipe("123", transport=transport)

    assert result.recipe is not None
    assert [(resource.kind, resource.name) for resource in result.recipe.resources] == [
        (ResourceKind.CHECKPOINT, "waiIllustriousSDXL_v170.safetensors"),
        (ResourceKind.LORA, "size-slider-illustrious.safetensors"),
    ]
    checkpoint, lora = result.recipe.resources
    assert checkpoint.civitai_model_version_id == 2883731
    assert checkpoint.civitai_model_id == 827184
    assert checkpoint.civitai_file_id == 111222
    assert checkpoint.sha256 == "f116b0c78ff44146aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert lora.civitai_model_version_id == 1835318
    assert lora.strength_model == 0.8
    assert [call["url"] for call in transport.calls[1:]] == [
        "https://civitai.com/api/v1/model-versions/2883731",
        "https://civitai.com/api/v1/model-versions/1835318",
    ]


def test_deleted_model_version_keeps_identity_only_civitai_resource() -> None:
    image = _json_fixture("image_123.json")
    image["modelVersionIds"] = [1088507]
    image["meta"]["resources"] = []
    image["meta"]["civitaiResources"] = [{"type": "checkpoint", "modelVersionId": 1088507}]

    result = acquire_civitai_recipe(
        "123",
        transport=FakeTransport([
            CivitaiTransportResponse(200, {"items": [image]}, {}),
            CivitaiTransportResponse(404, {"error": "Model not found"}, {}),
        ]),
    )

    assert result.recipe is not None
    assert len(result.recipe.resources) == 1
    resource = result.recipe.resources[0]
    assert resource.kind == ResourceKind.CHECKPOINT
    assert resource.name == "civitai-version-1088507"
    assert resource.civitai_model_version_id == 1088507


def test_civitai_resources_deduplicate_against_named_meta_resources_by_version_id() -> None:
    image = _json_fixture("image_123.json")
    image["meta"]["resources"] = [image["meta"]["resources"][1]]  # blue-style lora, version 2002
    image["meta"]["civitaiResources"] = [
        {"type": "lora", "weight": 0.75, "modelVersionId": 2002},
        {"type": "checkpoint", "weight": 1, "modelVersionId": 2883731},
    ]

    result = acquire_civitai_recipe(
        "123",
        transport=FakeTransport([
            CivitaiTransportResponse(200, {"items": [image]}, {}),
            CivitaiTransportResponse(404, {"error": "Model not found"}, {}),
        ]),
    )

    assert result.recipe is not None
    assert [(resource.kind, resource.name) for resource in result.recipe.resources] == [
        (ResourceKind.LORA, "blue-style.safetensors"),
        (ResourceKind.CHECKPOINT, "civitai-version-2883731"),
    ]


def test_out_of_range_civitai_resource_weight_is_omitted_not_fatal() -> None:
    image = _json_fixture("image_123.json")
    image["meta"]["resources"] = []
    image["meta"]["civitaiResources"] = [{"type": "lora", "weight": 5.9, "modelVersionId": 1835318}]

    result = acquire_civitai_recipe(
        "123",
        transport=FakeTransport([
            CivitaiTransportResponse(200, {"items": [image]}, {}),
            CivitaiTransportResponse(404, {"error": "Model not found"}, {}),
        ]),
    )

    assert result.recipe is not None
    assert len(result.recipe.resources) == 1
    assert result.recipe.resources[0].kind == ResourceKind.LORA
    assert result.recipe.resources[0].strength_model is None


def test_api_meta_maps_to_ordered_recipe_fields_without_losing_raw_payload() -> None:
    result = acquire_civitai_recipe(
        "123",
        transport=FakeTransport([CivitaiTransportResponse(200, _json_fixture("image_123.json"), {})]),
    )

    recipe = result.recipe
    assert recipe is not None
    assert recipe.source.image_id == 123
    assert recipe.base_prompt == "masterpiece, 1girl, blue dress, <lora:blue-style:0.75>"
    assert recipe.negative_prompt == "lowres, bad anatomy"
    assert recipe.sampling is not None
    assert recipe.sampling.seed == 9223372036854775807
    assert recipe.sampling.width == 832
    assert recipe.sampling.height == 1216
    assert [(resource.kind, resource.name) for resource in recipe.resources] == [
        (ResourceKind.CHECKPOINT, "illustriousXL_v10.safetensors"),
        (ResourceKind.LORA, "blue-style.safetensors"),
        (ResourceKind.LORA, "detail-line.safetensors"),
    ]
    assert [resource.strength_model for resource in recipe.resources[1:]] == [0.75, 0.4]
    assert recipe.raw["civitai_api"]["payload"]["unknown_vendor_field"] == {
        "nested": ["preserve", 2],
    }
    assert recipe.raw["civitai_api"]["payload"]["extraTopLevel"] == "preserved raw"
    assert recipe.confirmed
    assert assess_reproduction(recipe).requirements["confirmed_source_identity"] is True

    public_roundtrip = GenerationRecipe.model_validate(recipe.model_dump())
    assert public_roundtrip.confirmed == []
    assert public_roundtrip.inferred


def test_api_and_embedded_conflicts_record_both_values_without_overwrite() -> None:
    embedded = extract_embedded_metadata(FIXTURES / "images" / "a1111_parameters.png")
    result = acquire_civitai_recipe(
        "123",
        transport=FakeTransport([CivitaiTransportResponse(200, _json_fixture("image_123.json"), {})]),
        embedded_metadata=embedded,
    )

    assert result.recipe is not None
    assert result.recipe.base_prompt == "masterpiece, 1girl, blue dress, <lora:blue-style:0.75>"
    conflict = result.conflicts[0]
    assert conflict["field"] == "base_prompt"
    assert conflict["kept"]["reference"] == "civitai_api:images:123:/meta/prompt"
    assert conflict["incoming"]["reference"] == "embedded_metadata:png_text:parameters:/a1111/prompt"
    assert "red dress" in conflict["incoming"]["value"]
    assert result.recipe.raw["normalization"]["conflicts"] == result.conflicts
    assert any(item.canonical_field == "base_prompt" for item in result.recipe.missing)


@dataclass
class FakeMediaTransport(FakeTransport):
    media: bytes = b""

    def get_bytes(self, url: str) -> CivitaiTransportResponse:
        self.calls.append({"url": url, "params": {}, "headers": {}})
        return CivitaiTransportResponse(200, self.media, {})


def test_only_digest_bound_boundary_evidence_can_be_confirmed() -> None:
    embedded = extract_embedded_metadata(FIXTURES / "images" / "comfyui_workflow.png")
    api_payload = _json_fixture("image_123.json")

    unbound = acquire_civitai_recipe(
        "123",
        transport=FakeTransport([CivitaiTransportResponse(200, deepcopy(api_payload), {})]),
        embedded_metadata=embedded,
    )
    assert unbound.recipe is not None
    assert not any(item.canonical_field == "workflow" for item in unbound.recipe.confirmed)

    acquired = acquire_civitai_recipe(
        "123",
        transport=FakeMediaTransport(
            [CivitaiTransportResponse(200, deepcopy(api_payload), {})],
            (FIXTURES / "images" / "comfyui_workflow.png").read_bytes(),
        ),
        embedded_metadata=embedded,
    )
    assert acquired.recipe is not None
    assert acquired.media_sha256 == embedded.image_sha256
    assert any(item.canonical_field == "workflow" for item in acquired.recipe.confirmed)
    assert acquired.recipe.evidence_manifest
    acquired.recipe.evidence_manifest[0].payload["response"]["id"] = 999
    assert assess_reproduction(acquired.recipe).requirements["confirmed_source_identity"] is False


def test_conflicting_api_and_embedded_values_are_audited_and_not_exact_ready() -> None:
    api_payload = _json_fixture("image_123.json")
    api_payload["meta"].update({
        "workflow": {"1": {"class_type": "KSampler", "inputs": {"seed": 7}}},
    })
    media = (FIXTURES / "images" / "conflicting_a1111_comfyui.png").read_bytes()
    result = acquire_civitai_recipe(
        "123",
        transport=FakeMediaTransport([CivitaiTransportResponse(200, api_payload, {})], media),
    )
    assert result.recipe is not None
    fields = {item["field"] for item in result.conflicts}
    assert "base_prompt" in fields
    assert "sampling.seed" in fields
    assert "workflow" in fields
    assert any(item.canonical_field == "workflow" for item in result.recipe.missing)
    assert assess_reproduction(result.recipe).level != "exact_ready"


def test_jpeg_conflict_references_name_the_actual_embedded_container_and_key() -> None:
    result = acquire_civitai_recipe(
        "123",
        transport=FakeMediaTransport(
            [CivitaiTransportResponse(200, _json_fixture("image_123.json"), {})],
            (FIXTURES / "images" / "jpeg_metadata.jpg").read_bytes(),
        ),
    )

    assert result.recipe is not None
    by_field = {item["field"]: item for item in result.conflicts}
    prompt_conflict = by_field["base_prompt"]
    assert prompt_conflict["kept"] == {
        "value": "masterpiece, 1girl, blue dress, <lora:blue-style:0.75>",
        "reference": "civitai_api:images:123:/meta/prompt",
    }
    assert prompt_conflict["incoming"] == {
        "value": "masterpiece, 1girl, red dress, <lora:red-style:0.65>",
        "reference": "embedded_metadata:jpeg_exif:ImageDescription:/a1111/prompt",
    }
