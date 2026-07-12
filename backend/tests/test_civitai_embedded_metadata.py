"""Offline CIV-B embedded metadata extraction tests."""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.schemas.generation_recipe import GenerationRecipe
from app.services.civitai_embedded_metadata import (
    embedded_metadata_to_recipe_payload,
    extract_embedded_metadata,
)


FIXTURES = Path(__file__).parent / "fixtures" / "civitai" / "images"

EXPECTED_SHA256 = {
    "a1111_parameters.png": "42028519633e269426effb66041a5767292588982f84f24eb64df88f59b7a875",
    "comfyui_workflow.png": "8fc856bf0b923eb1159fc5ce65dba3b98a91228d5e883945ccd416a98a35d4da",
    "jpeg_metadata.jpg": "0d50725748032056d6fc9dd9c1283c66637e972b6daeadc47d31335ae0931a01",
    "webp_metadata.webp": "b6591f8009f5444bfbaaa52388a200fb9171758abecc691bad1e071956e08161",
}


def test_png_jpeg_webp_metadata_and_unknown_fields_are_preserved() -> None:
    for filename, expected in EXPECTED_SHA256.items():
        assert hashlib.sha256((FIXTURES / filename).read_bytes()).hexdigest() == expected
    png = extract_embedded_metadata(FIXTURES / "a1111_parameters.png")
    jpeg = extract_embedded_metadata(FIXTURES / "jpeg_metadata.jpg")
    webp = extract_embedded_metadata(FIXTURES / "webp_metadata.webp")
    assert any(item["key"] == "vendor:opaque" and item["value"] == "keep me" for item in png.raw["containers"])
    assert any(item["container"] == "jpeg_comment" and item["value"] == "jpeg comment value" for item in jpeg.raw["containers"])
    assert any(item["container"] == "webp_xmp" and "civitaiWorkflow" in item["value"] for item in webp.raw["containers"])
    assert webp.a1111 is not None
    assert webp.a1111["prompt"] == "webp masterpiece, 1girl, green dress"
    assert webp.a1111["parameters"]["seed"] == 3141592653589793238
    assert any(
        item["container"] == "webp_xmp" and 'vendor:opaque="webp unknown value"' in item["value"]
        for item in webp.raw["containers"]
    )


def test_png_a1111_parameters_are_extracted_and_mapped_without_losing_unknown_chunks() -> None:
    result = extract_embedded_metadata(FIXTURES / "a1111_parameters.png")

    assert result.image_sha256 == EXPECTED_SHA256["a1111_parameters.png"]
    assert result.format == "PNG"
    assert result.a1111 is not None
    assert result.a1111["prompt"] == "masterpiece, 1girl, red dress, <lora:red-style:0.65>"
    assert result.a1111["negative_prompt"] == "lowres, blurry"
    assert result.a1111["parameters"]["steps"] == 30
    assert result.a1111["parameters"]["sampler"] == "Euler a"
    assert result.a1111["parameters"]["scheduler"] == "Karras"
    assert result.a1111["parameters"]["seed"] == 9223372036854775807
    assert result.a1111["parameters"]["width"] == 640
    assert result.a1111["parameters"]["height"] == 960
    assert result.a1111["loras"] == [{"name": "red-style", "strength_model": 0.65}]
    assert any(container["key"] == "vendor:opaque" and container["value"] == "keep me" for container in result.raw["containers"])

    payload = embedded_metadata_to_recipe_payload(result, source={"provider": "civitai", "image_id": 123})
    recipe = GenerationRecipe.model_validate(payload)
    assert recipe.base_prompt == result.a1111["prompt"]
    assert recipe.sampling is not None
    assert recipe.sampling.seed == 9223372036854775807
    assert recipe.resources[0].kind == "lora"
    assert recipe.raw["embedded_metadata"]["containers"][1]["key"] == "vendor:opaque"


def test_png_comfyui_prompt_and_workflow_json_are_extracted_as_snapshots() -> None:
    result = extract_embedded_metadata(FIXTURES / "comfyui_workflow.png")

    assert result.comfyui_workflow is not None
    assert result.comfyui_workflow["1"]["class_type"] == "CheckpointLoaderSimple"
    assert result.comfyui_prompt is not None
    assert result.comfyui_prompt["3"]["inputs"]["seed"] == 42
    assert any(container["key"] == "mystery" for container in result.raw["containers"])

    payload = embedded_metadata_to_recipe_payload(result, source={"provider": "civitai", "image_id": 123})
    assert payload["workflow"]["snapshot"] == result.comfyui_workflow
    assert len(payload["workflow"]["snapshot_sha256"]) == 64
    assert payload["raw"]["embedded_metadata"]["comfyui_prompt"]["3"]["class_type"] == "KSampler"


def test_jpeg_exif_comment_and_xmp_are_retained_as_raw_metadata() -> None:
    result = extract_embedded_metadata(FIXTURES / "jpeg_metadata.jpg")

    containers = result.raw["containers"]
    assert result.format == "JPEG"
    assert any(container["container"] == "jpeg_exif" and container["key"] == "ImageDescription" for container in containers)
    assert any(container["container"] == "jpeg_comment" and container["value"] == "jpeg comment value" for container in containers)
    assert any(container["container"] == "jpeg_xmp" and "jpeg xmp prompt" in container["value"] for container in containers)
    assert result.a1111 is not None
    assert result.a1111["parameters"]["steps"] == 30


def test_webp_exif_and_xmp_are_retained_as_raw_metadata() -> None:
    result = extract_embedded_metadata(FIXTURES / "webp_metadata.webp")

    containers = result.raw["containers"]
    assert result.format == "WEBP"
    assert any(container["container"] == "webp_exif" and container["key"] == "ImageDescription" for container in containers)
    assert any(container["container"] == "webp_xmp" and "civitaiWorkflow" in container["value"] for container in containers)
