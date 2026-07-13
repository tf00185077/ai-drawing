"""CIV-SA-R explicit immutable source-alias version resolve API acceptance matrix."""
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
from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
from app.services.civitai_source_alias_registry import remember_source_alias

_ROUTE = "/api/civitai-recipes/source-aliases/resolve-explicit-version"
_MESSAGE = "source alias explicit-version resolution failed"


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _remember_payload(image_id: int = 123) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 42}}, "provider": "civitai"}
    return {
        "primary_alias": "Sunset Hero", "alternate_aliases": ["Apple Alternate"],
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence, "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "a" * 64, "thumbnail_url": "https://image.civitai.com/original.jpg",
        "thumbnail_path": "thumbs/original.png", "user_note": "original target", "approved_tags": ["original"],
        "prompt_summary": "original summary",
    }


def _replacement(image_id: int = 456) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 99}}, "provider": "civitai"}
    return {
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence, "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "b" * 64, "thumbnail_url": "https://image.civitai.com/replacement.jpg",
        "thumbnail_path": "thumbs/replacement.png", "user_note": "replacement target", "approved_tags": ["replacement"],
        "prompt_summary": "replacement summary",
    }


@contextmanager
def _client(tmp_path: Path, name: str):
    from app.db import models  # noqa: F401

    engine = create_engine(f"sqlite:///{tmp_path / (name + '.db')}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    injected = []

    def override_db():
        db = Session()
        injected.append(db)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), Session, injected
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _remember(Session):
    with Session() as db:
        result = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_remember_payload()), db=db)
    assert result.status == "success"
    return result


def _repoint(Session):
    from app.services.civitai_source_alias_registry import repoint_source_alias

    with Session() as db:
        result = repoint_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 1, "replacement": _replacement()}, db=db)
    assert result.status == "success"
    return result


def _snapshot(Session):
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord, CivitaiSourceAliasRepointTransition

    with Session() as db:
        return {
            "records": [(r.registry_version, r.source_identity_json, r.acquisition_evidence_json, r.acquisition_evidence_sha256, r.parent_recipe_sha256, r.thumbnail_url, r.thumbnail_path, r.user_note, r.approved_tags_json, r.prompt_summary, r.created_at, r.archived_at) for r in db.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)],
            "aliases": [(a.id, a.registry_version, a.original_alias, a.normalized_key, a.alias_kind) for a in db.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)],
            "history": [(h.id, h.registry_version, h.operation, h.before_aliases_json, h.after_aliases_json, h.previous_event_sha256, h.event_sha256, h.created_at) for h in db.query(CivitaiSourceAliasHistory).order_by(CivitaiSourceAliasHistory.id)],
            "transitions": [(t.id, t.from_registry_version, t.to_registry_version, t.aliases_json, t.from_record_sha256, t.to_record_sha256, t.source_history_tail_sha256, t.previous_repoint_event_sha256, t.event_sha256, t.created_at) for t in db.query(CivitaiSourceAliasRepointTransition).order_by(CivitaiSourceAliasRepointTransition.id)],
        }


def _expected(Session, alias: str, registry_version: int):
    from app.services.civitai_source_alias_registry import resolve_source_alias_exact_version

    with Session() as db:
        result = resolve_source_alias_exact_version({"alias": alias, "registry_version": registry_version}, db=db)
    assert result.status == "success" and result.record is not None and result.alias is not None
    return {"matched_alias": result.alias.model_dump(mode="json"), **result.record.model_dump(mode="json")}


def test_explicit_version_resolve_api_returns_current_and_historical_audited_bindings(tmp_path: Path) -> None:
    """CIV-SA-R-AC1: current and outgoing-snapshot aliases retain exact requested bindings."""
    with _client(tmp_path, "success") as (client, Session, _):
        _remember(Session)
        _repoint(Session)
        for alias, version in (("Sunset Hero", 2), ("Apple Alternate", 2), ("Sunset Hero", 1), ("Apple Alternate", 1)):
            expected = _expected(Session, alias, version)
            response = client.post(_ROUTE, json={"alias": alias, "registry_version": version})
            assert response.status_code == 200
            assert response.json() == expected
            assert response.json()["created_at"].endswith("Z")
            assert response.json()["registry_version"] == version


def test_explicit_version_resolve_api_strict_schema_and_fail_closed_status_matrix(tmp_path: Path) -> None:
    """CIV-SA-R-AC2: strict OpenAPI and contract-only statuses expose no rejected inputs."""
    from app.db.models import CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import archive_source_alias

    with _client(tmp_path, "matrix") as (client, Session, _):
        _remember(Session)
        for payload in ({}, {"alias": "Sunset Hero"}, {"registry_version": 1}, {"alias": "Sunset Hero", "registry_version": 1, "extra": "SECRET"}, {"alias": " \t", "registry_version": 1}, {"alias": "x" * 513, "registry_version": 1}, {"alias": "Sunset Hero", "registry_version": True}, {"alias": "Sunset Hero", "registry_version": "1"}, {"alias": "Sunset Hero", "registry_version": 1.0}, {"alias": "Sunset Hero", "registry_version": 0}, {"alias": "Sunset Hero", "registry_version": -1}):
            response = client.post(_ROUTE, json=payload)
            assert response.status_code == 422
            assert response.json() == {"detail": {"code": "source_alias_explicit_version_resolve_invalid", "message": _MESSAGE}}
            assert "SECRET" not in response.text
        for payload, code in (({"alias": "Sunset Hero", "registry_version": 9}, "registry_version_not_found"), ({"alias": "missing", "registry_version": 1}, "alias_not_bound_to_registry_version")):
            response = client.post(_ROUTE, json=payload)
            assert response.status_code == 404
            assert response.json() == {"detail": {"code": code, "message": _MESSAGE}}
        assert archive_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 1}, db=Session()).status == "success"
        response = client.post(_ROUTE, json={"alias": "Sunset Hero", "registry_version": 1})
        assert response.status_code == 409 and response.json() == {"detail": {"code": "target_archived", "message": _MESSAGE}}
    with _client(tmp_path, "corrupt-record") as (client, Session, _):
        _remember(Session)
        with Session() as db:
            db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "c" * 64})
            db.commit()
        response = client.post(_ROUTE, json={"alias": "Sunset Hero", "registry_version": 1})
        assert response.status_code == 409 and response.json() == {"detail": {"code": "source_alias_registry_corrupt", "message": _MESSAGE}}

    # Separate CIV-SA-Q verifier failures must be collapsed into the one audited
    # facade error, without returning either raw verifier details or input values.
    from app.db.models import CivitaiSourceAliasHistory, CivitaiSourceAliasRepointTransition
    from app.services.civitai_source_alias_registry import rename_primary_source_alias

    with _client(tmp_path, "corrupt-history") as (client, Session, _):
        _remember(Session)
        _repoint(Session)
        with Session() as db:
            assert rename_primary_source_alias({"current_primary_alias": "Sunset Hero", "new_primary_alias": "Aurora Hero", "expected_registry_version": 2}, db=db).status == "success"
            db.query(CivitaiSourceAliasHistory).filter_by(registry_version=2).one().event_sha256 = "0" * 64
            db.commit()
        response = client.post(_ROUTE, json={"alias": "Aurora Hero", "registry_version": 2})
        assert response.status_code == 409
        assert response.json() == {"detail": {"code": "source_alias_registry_corrupt", "message": _MESSAGE}}
        assert not ({"record", "matched_alias", "candidate", "input", "errors"} & set(response.json()["detail"]))
        assert "Aurora Hero" not in response.text and "history_invalid" not in response.text

    with _client(tmp_path, "corrupt-repoint") as (client, Session, _):
        _remember(Session)
        _repoint(Session)
        with Session() as db:
            db.query(CivitaiSourceAliasRepointTransition).one().event_sha256 = "0" * 64
            db.commit()
        response = client.post(_ROUTE, json={"alias": "Sunset Hero", "registry_version": 2})
        assert response.status_code == 409
        assert response.json() == {"detail": {"code": "source_alias_registry_corrupt", "message": _MESSAGE}}
        assert not ({"record", "matched_alias", "candidate", "input", "errors"} & set(response.json()["detail"]))
        assert "Sunset Hero" not in response.text and "repoint_invalid" not in response.text

    openapi = app.openapi()["components"]["schemas"]["CivitaiSourceAliasExplicitVersionResolveRequest"]
    assert openapi["additionalProperties"] is False and openapi["required"] == ["alias", "registry_version"]
    assert openapi["properties"]["alias"] == {"type": "string", "maxLength": 512, "minLength": 1, "title": "Alias"}
    assert openapi["properties"]["registry_version"] == {"type": "integer", "minimum": 1.0, "title": "Registry Version"}


@contextmanager
def _forbidden_bombs():
    def bomb(*_args, **_kwargs):
        raise AssertionError("explicit-version facade invoked a forbidden path")

    targets = (
        "app.api.civitai_recipes.resolve_source_alias_exact", "app.api.civitai_recipes.search_registry_sources", "app.api.civitai_recipes.list_registry_sources", "app.api.civitai_recipes.import_recipe", "app.api.civitai_recipes.rename_primary_source_alias", "app.api.civitai_recipes.archive_source_alias", "app.api.civitai_recipes.repoint_source_alias", "app.api.civitai_recipes.httpx.get", "app.api.civitai_recipes.httpx.post", "pathlib.Path.mkdir", "app.api.civitai_recipes.build_recipe", "app.api.civitai_recipes.resolve_recipe", "app.api.civitai_recipes.submit_custom", "app.api.civitai_recipes.generate_one_variant", "app.api.civitai_recipes.create_variation_set", "app.api.civitai_recipes.get_variation_set", "app.api.civitai_recipes.export_variation_set", "app.api.civitai_recipes.cancel_variation_set",
    )
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, side_effect=bomb))
        yield


def test_explicit_version_resolve_api_is_read_only_and_never_falls_back_or_generates(tmp_path: Path) -> None:
    """CIV-SA-R-AC3: every matrix path is a snapshot-preserving one-call facade."""
    from app.db.models import CivitaiSourceAliasRepointTransition
    from app.services.civitai_source_alias_registry import archive_source_alias
    import app.api.civitai_recipes as recipe_api

    def run_case(name: str, payload: dict[str, object], expected_status: int, setup=None, *, validated: bool = True) -> None:
        with _client(tmp_path, name) as (client, Session, injected):
            _remember(Session)
            _repoint(Session)
            if setup is not None:
                setup(Session)
            before = _snapshot(Session)
            with patch("app.api.civitai_recipes.resolve_source_alias_exact_version", wraps=recipe_api.resolve_source_alias_exact_version) as delegated:
                with _forbidden_bombs():
                    response = client.post(_ROUTE, json=payload)
            assert response.status_code == expected_status
            if validated:
                assert delegated.call_count == 1
                assert delegated.call_args.kwargs == {"db": injected[-1]}
                assert delegated.call_args.args[0].model_dump(mode="json") == payload
            else:
                delegated.assert_not_called()
            assert _snapshot(Session) == before

    def archive_current(Session) -> None:
        with Session() as db:
            assert archive_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 2}, db=db).status == "success"

    def corrupt_repoint(Session) -> None:
        with Session() as db:
            db.query(CivitaiSourceAliasRepointTransition).one().event_sha256 = "0" * 64
            db.commit()

    # Both audited successes and every contract failure run under the same forbidden
    # boundary bombs and full four-table snapshot comparison.
    run_case("current-success", {"alias": "Sunset Hero", "registry_version": 2}, 200)
    run_case("historical-success", {"alias": "Apple Alternate", "registry_version": 1}, 200)
    run_case("validation-invalid", {"alias": "Sunset Hero", "registry_version": True}, 422, validated=False)
    run_case("missing-version", {"alias": "Sunset Hero", "registry_version": 9}, 404)
    run_case("alias-mismatch", {"alias": "missing", "registry_version": 2}, 404)
    run_case("archived", {"alias": "Sunset Hero", "registry_version": 2}, 409, archive_current)
    run_case("corrupt", {"alias": "Sunset Hero", "registry_version": 2}, 409, corrupt_repoint)


def test_explicit_version_resolve_api_openapi_and_route_non_regression(tmp_path: Path) -> None:
    """CIV-SA-R-AC4: exactly one typed route preserves adjacent aliases and recipe routes."""
    from app.services.civitai_source_alias_registry import resolve_source_alias_exact

    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    registered = {(route.path, method) for route in routes for method in route.methods}
    expected = {
        (_ROUTE, "POST"), ("/api/civitai-recipes/source-aliases/resolve", "POST"),
        ("/api/civitai-recipes/source-aliases/search", "POST"), ("/api/civitai-recipes/source-aliases/rename", "POST"),
        ("/api/civitai-recipes/source-aliases/archive", "POST"), ("/api/civitai-recipes/source-aliases/repoint", "POST"),
        ("/api/civitai-recipes/import", "POST"), ("/api/civitai-recipes/build", "POST"),
        ("/api/civitai-recipes/run", "POST"), ("/api/civitai-recipes/variants/generate-one", "POST"),
        ("/api/civitai-recipes/variation-sets", "POST"),
        ("/api/civitai-recipes/variation-sets/{variation_set_id}", "GET"),
        ("/api/civitai-recipes/variation-sets/{variation_set_id}/cancel", "POST"),
        ("/api/civitai-recipes/variation-sets/{variation_set_id}/export", "GET"),
    }
    assert expected <= registered
    assert sum(route.path == _ROUTE and "POST" in route.methods for route in routes) == 1
    route = next(route for route in routes if route.path == _ROUTE and "POST" in route.methods)
    assert type(route).__name__ == "_SourceAliasExplicitVersionResolveValidationRoute"
    operation = app.openapi()["paths"][_ROUTE]["post"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/CivitaiSourceAliasResolveResponse"}

    # The new endpoint must not soften the established bare-resolve repoint rule.
    with _client(tmp_path, "bare-remains-closed") as (client, Session, _):
        _remember(Session)
        _repoint(Session)
        for alias in ("Sunset Hero", "Apple Alternate"):
            with Session() as db:
                domain = resolve_source_alias_exact(alias, db=db)
            assert (domain.status, domain.code, domain.record, domain.alias) == ("repointed", "explicit_registry_version_required", None, None)
            response = client.post("/api/civitai-recipes/source-aliases/resolve", json={"alias": alias})
            assert response.status_code == 409
            assert response.json() == {"detail": {"code": "corrupt_registry", "message": "source alias resolution failed"}}
