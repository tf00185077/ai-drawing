"""Offline CIV-G regression for the audited public Civitai Images API fixture."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.schemas.generation_recipe import MAX_SIGNED_64_BIT_SEED, ResourceKind, assess_reproduction
from app.services.civitai_acquisition import CivitaiTransportResponse, acquire_civitai_recipe


FIXTURE = Path(__file__).parent / "fixtures" / "civitai" / "live_public_image.json"


@dataclass
class FixtureTransport:
    payloads: list[dict]

    def get_json(self, url: str, *, params: dict | None = None, headers: dict | None = None) -> CivitaiTransportResponse:
        assert url.startswith("https://civitai.com/api/v1/")
        assert headers == {}
        return CivitaiTransportResponse(200, self.payloads.pop(0), {})


def test_live_public_image_fixture_preserves_auditable_recipe_fields() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = acquire_civitai_recipe(
        fixture["source"]["image_id"],
        transport=FixtureTransport([fixture["images_api_with_meta"], fixture["model_version"]]),
    )

    recipe = result.recipe
    assert recipe is not None
    assert recipe.schema_version == "1.0"
    assert recipe.source.image_id == fixture["source"]["image_id"]
    assert recipe.source.url == fixture["source"]["url"]
    assert result.raw_api_payload is not None
    assert result.raw_api_payload["unknown_top_level"] == {"preserve": ["live", 1]}
    assert result.raw_api_payload["meta"]["outerVendorField"] == {"preserve": True}
    assert result.raw_api_payload["meta"]["meta"]["unknown_metadata"] == {"must": "survive"}
    assert result.raw_api_payload["meta"]["meta"]["resources"][0]["unmatched"] is True
    assert recipe.sampling is not None
    assert recipe.sampling.seed is not None
    assert recipe.sampling.seed == fixture["expected"]["seed"]
    assert 0 <= recipe.sampling.seed <= MAX_SIGNED_64_BIT_SEED
    assert [(item.kind, item.name) for item in recipe.resources] == [
        (ResourceKind.CHECKPOINT, fixture["expected"]["checkpoint_name"]),
    ]
    assert recipe.resources[0].sha256 == fixture["expected"]["checkpoint_sha256"]
    assert recipe.resources[0].civitai_model_version_id == fixture["expected"]["model_version_id"]
    assert recipe.resources[0].civitai_file_id == fixture["expected"]["file_id"]
    report = assess_reproduction(recipe)
    assert report.level == fixture["expected"]["reproduction_level"]
    assert report.requirements["confirmed_source_identity"] is True
    assert report.caveats
    assert "workflow" in report.caveats
