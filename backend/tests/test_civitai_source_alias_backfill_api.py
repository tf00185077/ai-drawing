"""CIV-SA-Z typed Gallery source-alias backfill HTTP facade acceptance matrix (offline)."""
from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app
from app.schemas.civitai_source_aliases import canonical_sha256
from app.services.civitai_recipe_gallery import build_recipe_provenance_bundle, persistable_bundle

_ROUTE = "/api/civitai-recipes/source-aliases/backfill-gallery"
_SECRETS = (
    "Authorization: SECRET-AUTH", "Bearer SECRET-BEARER", "token=SECRET-TOKEN",
    "cookie=SECRET-COOKIE", "password=SECRET-PASSWORD", "signed-query=SECRET-SIGNED-QUERY",
)


def _sha_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle(tmp_path: Path, image_id: int) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    model = tmp_path / "base.safetensors"
    model.write_bytes(b"model")
    model_sha = _sha_bytes(model)
    workflow = {"1": {"class_type": "KSampler", "inputs": {"seed": 42}}}
    recipe = {
        "schema_version": "1.0",
        "source": {"provider": "civitai", "image_id": image_id},
        "base_prompt": "gallery backfill",
        "resources": [{"kind": "checkpoint", "name": "base.safetensors", "sha256": model_sha}],
        "sampling": {"seed": 42, "steps": 20, "cfg": 7.0, "sampler": "euler", "scheduler": "normal", "denoise": 1.0, "width": 512, "height": 512},
        "passes": [{"name": "base", "inherits_from": "recipe.sampling"}],
        "runtime": {"engine": "ComfyUI", "engine_version": "1", "reference": "runtime:1"},
        "workflow": {"reference": "gallery", "snapshot": workflow, "snapshot_sha256": canonical_sha256(workflow)},
    }
    return build_recipe_provenance_bundle(
        recipe=recipe, workflow=workflow, input_hashes=[],
        resource_locks=[{"index": 0, "kind": "checkpoint", "sha256": model_sha, "local_path": str(model), "local_sha256": model_sha}],
        runtime_provenance=recipe["runtime"], reproduction_level="workflow_ready_but_runtime_may_differ",
    )


@contextmanager
def _client(tmp_path: Path, name: str):
    from app.db import models  # noqa: F401 - register all audited tables

    engine = create_engine(f"sqlite:///{tmp_path / (name + '.db')}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    injected_sessions = []

    def override_db():
        db = Session()
        injected_sessions.append(db)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), Session, injected_sessions
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _gallery(Session, bundle: dict, image_path: str):
    from app.db.models import GeneratedImage

    with Session() as db:
        row = GeneratedImage(image_path=image_path, **persistable_bundle(bundle))
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def _snapshot(Session):
    from app.db.models import (
        CivitaiSourceAlias, CivitaiSourceAliasBackfillCandidate,
        CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord,
        CivitaiSourceAliasRepointTransition, GeneratedImage,
    )

    models = (GeneratedImage, CivitaiSourceAliasBackfillCandidate, CivitaiSourceAliasRegistryRecord,
              CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRepointTransition)
    with Session() as db:
        return tuple(
            (model.__tablename__, tuple(tuple(getattr(row, col.name) for col in model.__table__.columns)
             for row in db.query(model).order_by(*model.__mapper__.primary_key).all()))
            for model in models
        )


def _assert_redacted(response) -> None:
    detail = response.json()["detail"]
    assert set(detail) == {"code", "message"}
    assert all(secret.lower() not in response.text.lower() for secret in _SECRETS)
    assert not ({"record", "candidate", "source_identity", "exception", "gallery"} & set(detail))


def test_gallery_backfill_api_returns_typed_named_pending_and_idempotent_success(tmp_path: Path) -> None:
    """CIV-SA-Z-AC1: API serialization is parity with the frozen core for all successes."""
    from app.schemas.civitai_source_alias_backfill import CivitaiSourceAliasGalleryBackfillRequest
    from app.services.civitai_source_alias_backfill import backfill_gallery_source_alias

    with _client(tmp_path, "success") as (client, Session, _):
        named_id = _gallery(Session, _bundle(tmp_path / "named", 101), "gallery/named.png")
        with Session() as db:
            direct_named = backfill_gallery_source_alias(CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=named_id, primary_alias="Named Parent"), db=db)
        assert direct_named.status == "named"
        # A distinct row proves the HTTP facade without reusing the direct core write.
        api_named_id = _gallery(Session, _bundle(tmp_path / "api-named", 102), "gallery/api-named.png")
        response = client.post(_ROUTE, json={"gallery_image_id": api_named_id, "primary_alias": "API Named Parent"})
        assert response.status_code == 200
        body = response.json()
        with Session() as db:
            expected = backfill_gallery_source_alias(CivitaiSourceAliasGalleryBackfillRequest(gallery_image_id=api_named_id, primary_alias="API Named Parent"), db=db)
        assert expected.status == "named"
        assert body["status"] == expected.status
        assert {key: body[key] for key in body if key != "code"} == {
            key: value for key, value in expected.model_dump(mode="json").items() if key != "code"
        }
        assert set(body) == {"status", "code", "record", "candidate", "source_identity", "acquisition_evidence_snapshot", "acquisition_evidence_sha256", "parent_recipe_sha256"}
        assert not ({"selected", "resolved", "build", "job", "lineage"} & set(body))

        pending_id = _gallery(Session, _bundle(tmp_path / "pending", 103), "gallery/pending.png")
        pending = client.post(_ROUTE, json={"gallery_image_id": pending_id})
        retry = client.post(_ROUTE, json={"gallery_image_id": pending_id})
        assert pending.status_code == retry.status_code == 200
        pending_body, retry_body = pending.json(), retry.json()
        assert pending_body["status"] == "pending_name" and retry_body["status"] == "already_backfilled"
        assert pending_body["candidate"]["id"] == retry_body["candidate"]["id"]
        from app.services.civitai_source_alias_registry import exact_resolve
        with Session() as db:
            assert exact_resolve(pending_body["candidate"]["suggested_alias"], db=db).status == "missing"
        assert pending_body["record"] is None and retry_body["record"] is None


def test_gallery_backfill_api_maps_validation_ineligible_conflict_and_corrupt_to_redacted_fail_closed_http(tmp_path: Path) -> None:
    """CIV-SA-Z-AC2: all invalid/domain outcomes are stable, redacted, and write-free."""
    from app.db.models import GeneratedImage

    with _client(tmp_path, "failures") as (client, Session, _):
        for payload in ({}, {"gallery_image_id": "1"}, {"gallery_image_id": True}, {"gallery_image_id": 1.0}, {"gallery_image_id": 0}, {"gallery_image_id": -1}, {"gallery_image_id": 1, "primary_alias": " \t"}, {"gallery_image_id": 1, "primary_alias": "x" * 513}, {"gallery_image_id": 1, "extra": _SECRETS}):
            before = _snapshot(Session)
            response = client.post(_ROUTE, json=payload)
            assert response.status_code == 422
            assert response.json()["detail"] == {"code": "source_alias_gallery_backfill_invalid", "message": "source alias Gallery backfill request invalid"}
            _assert_redacted(response)
            assert _snapshot(Session) == before

        missing = client.post(_ROUTE, json={"gallery_image_id": 999})
        assert missing.status_code == 404 and missing.json()["detail"] == {"code": "gallery_not_found", "message": "source alias Gallery backfill failed"}
        _assert_redacted(missing)

        ineligible_id = _gallery(Session, _bundle(tmp_path / "ineligible", 201), "gallery/ineligible.png")
        with Session() as db:
            row = db.get(GeneratedImage, ineligible_id)
            recipe = json.loads(row.recipe_json)
            recipe["source"] = {"provider": "civitai"}
            row.recipe_json = json.dumps(recipe, separators=(",", ":"), sort_keys=True)
            row.recipe_sha256 = canonical_sha256(recipe)
            db.commit()
        before = _snapshot(Session)
        ineligible = client.post(_ROUTE, json={"gallery_image_id": ineligible_id})
        assert ineligible.status_code == 422 and ineligible.json()["detail"]["code"] == "gallery_parent_ineligible"
        _assert_redacted(ineligible)
        assert _snapshot(Session) == before

        first_id = _gallery(Session, _bundle(tmp_path / "first", 202), "gallery/first.png")
        assert client.post(_ROUTE, json={"gallery_image_id": first_id, "primary_alias": "occupied"}).status_code == 200
        conflict_id = _gallery(Session, _bundle(tmp_path / "conflict", 203), "gallery/conflict.png")
        before = _snapshot(Session)
        conflict = client.post(_ROUTE, json={"gallery_image_id": conflict_id, "primary_alias": "occupied"})
        assert conflict.status_code == 409 and conflict.json()["detail"]["code"]
        _assert_redacted(conflict)
        assert _snapshot(Session) == before

        corrupt_id = _gallery(Session, _bundle(tmp_path / "corrupt", 204), "gallery/corrupt.png")
        with Session() as db:
            row = db.get(GeneratedImage, corrupt_id)
            row.recipe_sha256 = "0" * 64
            db.commit()
        before = _snapshot(Session)
        corrupt = client.post(_ROUTE, json={"gallery_image_id": corrupt_id})
        assert corrupt.status_code == 409 and corrupt.json()["detail"] == {"code": "source_alias_gallery_backfill_corrupt", "message": "source alias Gallery backfill corrupt"}
        _assert_redacted(corrupt)
        assert _snapshot(Session) == before


@contextmanager
def _forbidden_boundary_bombs():
    def bomb(*_args, **_kwargs):
        raise AssertionError("Gallery backfill facade invoked a forbidden fallback")

    targets = (
        "app.api.civitai_recipes.resolve_source_alias_exact",
        "app.api.civitai_recipes.resolve_source_alias_exact_version", "app.api.civitai_recipes.list_registry_sources",
        "app.api.civitai_recipes.search_registry_sources", "app.api.civitai_recipes.rename_primary_source_alias",
        "app.api.civitai_recipes.archive_source_alias", "app.api.civitai_recipes.repoint_source_alias",
        "app.api.civitai_recipes.import_recipe", "app.api.civitai_recipes.build_recipe_provenance_bundle",
        "app.api.civitai_recipes.resolve_recipe", "app.api.civitai_recipes.build_recipe",
        "app.api.civitai_recipes.submit_custom", "app.api.civitai_recipes.generate_one_variant",
        "app.api.civitai_recipes.create_variation_set", "app.api.civitai_recipes.httpx.get",
        "app.api.civitai_recipes.httpx.post", "pathlib.Path.mkdir",
    )
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, side_effect=bomb))
        yield


def test_gallery_backfill_api_delegates_once_with_injected_session_without_fallback(tmp_path: Path) -> None:
    """CIV-SA-Z-AC3: valid requests make one typed core call with precisely the injected Session."""
    from app.schemas.civitai_source_alias_backfill import CivitaiSourceAliasGalleryBackfillResult

    with _client(tmp_path, "delegation") as (client, _Session, injected):
        for status, code, expected_http in (("ineligible", "gallery_not_found", 404), ("ineligible", "gallery_parent_ineligible", 422), ("conflict", "pending_name_exists", 409), ("corrupt", "sentinel Authorization: SECRET-AUTH", 409)):
            result = CivitaiSourceAliasGalleryBackfillResult(status=status, code=code)
            with patch("app.api.civitai_recipes.backfill_gallery_source_alias", return_value=result) as delegated:
                with _forbidden_boundary_bombs():
                    response = client.post(_ROUTE, json={"gallery_image_id": 1})
            assert response.status_code == expected_http
            assert delegated.call_count == 1
            assert delegated.call_args.kwargs == {"db": injected[-1]}
            request = delegated.call_args.args[0]
            assert type(request).__name__ == "CivitaiSourceAliasGalleryBackfillRequest"
            assert request.model_dump() == {"gallery_image_id": 1, "primary_alias": None}
        with patch("app.api.civitai_recipes.backfill_gallery_source_alias") as delegated:
            assert client.post(_ROUTE, json={"gallery_image_id": "1"}).status_code == 422
            delegated.assert_not_called()


def test_gallery_backfill_api_openapi_and_route_registration_preserve_existing_contracts() -> None:
    """CIV-SA-Z-AC4: one locally isolated typed route preserves neighboring contracts."""
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert sum(route.path == _ROUTE and "POST" in route.methods for route in routes) == 1
    route = next(route for route in routes if route.path == _ROUTE and "POST" in route.methods)
    assert type(route).__name__ == "_SourceAliasGalleryBackfillValidationRoute"
    expected_paths = {
        ("/api/civitai-recipes/import", "POST"), ("/api/civitai-recipes/source-aliases/resolve", "POST"),
        ("/api/civitai-recipes/source-aliases/resolve-explicit-version", "POST"), ("/api/civitai-recipes/source-aliases", "GET"),
        ("/api/civitai-recipes/source-aliases/search", "POST"), ("/api/civitai-recipes/source-aliases/rename", "POST"),
        ("/api/civitai-recipes/source-aliases/archive", "POST"), ("/api/civitai-recipes/source-aliases/repoint", "POST"),
        ("/api/civitai-recipes/variants/generate-one", "POST"), ("/api/civitai-recipes/variation-sets", "POST"),
    }
    assert expected_paths <= {(route.path, method) for route in routes for method in route.methods}
    schema = app.openapi()
    operation = schema["paths"][_ROUTE]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/CivitaiSourceAliasGalleryBackfillRequest"}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/CivitaiSourceAliasGalleryBackfillResult"}
    request = schema["components"]["schemas"]["CivitaiSourceAliasGalleryBackfillRequest"]
    assert request["additionalProperties"] is False
    assert request["properties"]["gallery_image_id"]["minimum"] == 1.0
    alias = request["properties"]["primary_alias"]
    assert alias["anyOf"] == [{"type": "string", "maxLength": 512, "minLength": 1}, {"type": "null"}]
    for name in ("CivitaiSourceAliasGalleryBackfillResult", "CivitaiSourceAliasRegistryView", "CivitaiSourceAliasBackfillCandidateView"):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False
