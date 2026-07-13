"""CIV-SA-B import-boundary source-alias acceptance contracts; entirely offline."""
from __future__ import annotations

import base64
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasRegistryRecord
from app.main import app
from app.schemas.civitai_source_aliases import CivitaiSourceAliasDomainResult
from app.schemas.generation_recipe import GenerationRecipe
from app.services.civitai_acquisition import AcquisitionError, AcquisitionResult, CivitaiLocator, redact_secrets
from app.services.civitai_source_alias_registry import exact_resolve


def _recipe(*, image_id: int | None = 123, media_url: str | None = None) -> GenerationRecipe:
    source = {"provider": "civitai"}
    if image_id is not None:
        source["image_id"] = image_id
    if media_url is not None:
        source["media_url"] = media_url
    return GenerationRecipe.model_validate({
        "schema_version": "1.0",
        "source": source,
        "base_prompt": "positive",
        "resources": [{"kind": "checkpoint", "name": "base.safetensors", "sha256": "a" * 64}],
        "sampling": {"seed": 42, "steps": 20, "cfg": 7.0, "sampler": "euler", "scheduler": "normal", "denoise": 1.0, "width": 512, "height": 512},
        "passes": [{"name": "base", "inherits_from": "recipe.sampling"}],
    })


def _acquisition(*, image_id: int | None = 123, media_url: str | None = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/fixture.jpg") -> AcquisitionResult:
    recipe = _recipe(image_id=image_id, media_url=media_url if image_id is None else None)
    return AcquisitionResult(
        status="completed",
        locator=CivitaiLocator(kind="image" if image_id is not None else "media", canonical_url=media_url or "https://civitai.com/images/123", image_id=image_id, media_url=media_url),
        image_id=image_id,
        recipe=recipe,
        raw_api_payload={"id": image_id, "url": media_url, "meta": {"seed": 42}},
        media_url=media_url,
        media_sha256=None,
        provenance={"requests": [{"params": {"withMeta": "true"}}]},
        conflicts=[],
        errors=[],
    )


@contextmanager
def _client(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'aliases.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), Session
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _snapshot(session) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    records = [
        (
            row.registry_version, row.source_identity_json, row.acquisition_evidence_json,
            row.acquisition_evidence_sha256, row.parent_recipe_sha256, row.thumbnail_url,
            row.thumbnail_path, row.user_note, row.approved_tags_json, row.prompt_summary,
            row.created_at.isoformat() if row.created_at is not None else None,
        )
        for row in session.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)
    ]
    aliases = [
        (row.id, row.registry_version, row.original_alias, row.normalized_key, row.alias_kind)
        for row in session.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)
    ]
    return records, aliases


def _counts(session) -> tuple[int, int, list[tuple[int, str]], list[tuple[int, str, str]]]:
    return (
        session.query(CivitaiSourceAliasRegistryRecord).count(),
        session.query(CivitaiSourceAlias).count(),
        [(row.registry_version, row.source_identity_json) for row in session.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)],
        [(row.registry_version, row.original_alias, row.normalized_key) for row in session.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)],
    )


def test_import_with_remember_alias_persists_exact_audited_binding(tmp_path: Path) -> None:
    acquisition = _acquisition()
    assert acquisition.raw_api_payload is not None
    acquisition.raw_api_payload["token"] = "AC1-EVIDENCE-SENTINEL"
    with _client(tmp_path) as (client, Session), patch("app.services.civitai_recipe_pipeline.acquire_civitai_recipe", return_value=acquisition):
        response = client.post("/api/civitai-recipes/import", json={"locator": 123, "remember_alias": "  Sunset Hero  "})

        assert response.status_code == 200
        result = response.json()["source_alias_result"]
        assert result["persisted"] is True
        with Session() as db:
            resolved = exact_resolve("sunset hero", db=db)
            assert resolved.status == "success"
            record = resolved.record.model_dump(mode="json")
        for field in ("registry_version", "source_identity", "acquisition_evidence_sha256", "parent_recipe_sha256", "thumbnail_url", "thumbnail_path", "created_at"):
            assert result[field] == record[field]
        assert result["normalized_alias"] == "sunset hero"
        assert result["source_identity"] == {"provider": "civitai", "image_id": 123}
        assert record["acquisition_evidence_snapshot"]["raw_api_payload"]["token"] == "[REDACTED]"
        assert result["acquisition_evidence_sha256"] == hashlib.sha256(json.dumps(redact_secrets(acquisition.to_dict()), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert result["parent_recipe_sha256"] == hashlib.sha256(json.dumps(acquisition.recipe.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_import_remember_is_idempotent_and_conflict_is_409_without_mutation(tmp_path: Path) -> None:
    same = _acquisition(image_id=123)
    other = _acquisition(image_id=456)
    with _client(tmp_path) as (client, Session), patch("app.services.civitai_recipe_pipeline.acquire_civitai_recipe", return_value=same):
        first = client.post("/api/civitai-recipes/import", json={"locator": 123, "remember_alias": "Hero"})
        second = client.post("/api/civitai-recipes/import", json={"locator": 123, "remember_alias": "  hero  "})
        assert first.status_code == second.status_code == 200
        assert first.json()["source_alias_result"]["registry_version"] == second.json()["source_alias_result"]["registry_version"]
        with Session() as db:
            before = _counts(db)
        with patch("app.services.civitai_recipe_pipeline.acquire_civitai_recipe", return_value=other):
            conflict = client.post("/api/civitai-recipes/import", json={"locator": 456, "remember_alias": "HERO"})
        with Session() as db:
            after = _counts(db)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "alias_conflict"
    assert before == after


def test_import_without_alias_returns_deterministic_image_and_media_suggestions_without_writes(tmp_path: Path) -> None:
    image = _acquisition(image_id=123)
    media_url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/media-only.jpg"
    media = _acquisition(image_id=None, media_url=media_url)
    expected_media = "civitai-media-" + hashlib.sha256(media_url.encode()).hexdigest()[:12]
    with _client(tmp_path) as (client, Session), patch("app.services.civitai_recipe_pipeline.acquire_civitai_recipe", return_value=image):
        occupied = client.post("/api/civitai-recipes/import", json={"locator": 123, "remember_alias": "civitai-image-123"})
        assert occupied.status_code == 200
        with Session() as db:
            before_image_suggestions = _snapshot(db)
        first = client.post("/api/civitai-recipes/import", json={"locator": 123})
        second = client.post("/api/civitai-recipes/import", json={"locator": 123})
        assert first.status_code == second.status_code == 200
        assert first.json()["source_alias_result"] == {"persisted": False, "suggested_alias": "civitai-image-123"}
        with Session() as db:
            assert _snapshot(db) == before_image_suggestions
        with patch("app.services.civitai_recipe_pipeline.acquire_civitai_recipe", return_value=media):
            media_response = client.post("/api/civitai-recipes/import", json={"locator": media_url})
        assert media_response.status_code == 200
        assert media_response.json()["source_alias_result"] == {"persisted": False, "suggested_alias": expected_media}
        with Session() as db:
            assert _snapshot(db) == before_image_suggestions


def test_import_alias_failures_are_redacted_and_have_zero_registry_build_queue_side_effects(tmp_path: Path) -> None:
    sentinel = "SECRET-ALIAS-SENTINEL"
    invalid_identity = _acquisition()
    invalid_identity.recipe = _recipe(image_id=None, media_url=None)
    cases: list[tuple[str, dict[str, object], Any]] = [
        (
            "acquisition",
            {"locator": 123, "remember_alias": "hero"},
            patch(
                "app.services.civitai_recipe_pipeline.acquire_civitai_recipe",
                side_effect=AcquisitionError("not_found", f"Bearer {sentinel}"),
            ),
        ),
        (
            "embedded_metadata",
            {"locator": 123, "remember_alias": "hero", "embedded_image_base64": base64.b64encode(b"fixture").decode()},
            patch(
                "app.services.civitai_recipe_pipeline.extract_embedded_metadata",
                side_effect=ValueError(sentinel),
            ),
        ),
        (
            "canonical_recipe_absent",
            {"locator": 123, "remember_alias": "hero"},
            patch("app.services.civitai_recipe_pipeline.acquire_civitai_recipe", return_value=type("AbsentRecipe", (), {"recipe": None})()),
        ),
        (
            "immutable_identity",
            {"locator": 123, "remember_alias": "hero"},
            patch("app.services.civitai_recipe_pipeline.acquire_civitai_recipe", return_value=invalid_identity),
        ),
        (
            "registry_integrity",
            {"locator": 123, "remember_alias": "hero"},
            patch("app.services.civitai_recipe_pipeline.remember_source_alias", return_value=CivitaiSourceAliasDomainResult(status="corrupt", code="record_invalid")),
        ),
    ]
    with _client(tmp_path) as (client, Session), \
        patch("app.services.civitai_recipe_pipeline.compile_generation_recipe_workflow") as compile_workflow, \
        patch("app.services.civitai_recipe_pipeline.build_recipe") as build_recipe, \
        patch("app.api.civitai_recipes.submit_custom") as submit:
        for _name, payload, failure in cases:
            with Session() as db:
                before = _snapshot(db)
            with failure:
                response = client.post("/api/civitai-recipes/import", json=payload)
            with Session() as db:
                after = _snapshot(db)
            assert response.status_code == 422
            assert before == after
            detail = response.json()["detail"]
            assert isinstance(detail, dict)
            assert detail["code"] in {"not_found", "embedded_metadata_invalid", "alias_identity_invalid", "alias_registry_corrupt"}
            assert sentinel not in json.dumps(response.json())

    compile_workflow.assert_not_called()
    build_recipe.assert_not_called()
    submit.assert_not_called()
