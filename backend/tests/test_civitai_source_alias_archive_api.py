"""CIV-SA-L typed source-alias archive HTTP facade acceptance matrix (offline)."""
from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app
from app.schemas.civitai_source_aliases import (
    CivitaiSourceAliasArchiveResult,
    CivitaiSourceAliasHistoryEventView,
    CivitaiSourceAliasRememberRequest,
)
from app.services.civitai_source_alias_registry import remember_source_alias

_ROUTE = "/api/civitai-recipes/source-aliases/archive"
_SECRETS = (
    "Authorization: SECRET-AUTH", "Bearer SECRET-BEARER", "token=SECRET-TOKEN",
    "cookie=SECRET-COOKIE", "password=SECRET-PASSWORD", "signed-query=SECRET-SIGNED-QUERY",
)


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _payload(*, primary: str = "Sunset Hero", image_id: int = 123) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 42}}, "provider": "civitai"}
    return {
        "primary_alias": primary, "alternate_aliases": ["zebra alternate", "Apple Alternate"],
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence, "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "a" * 64, "thumbnail_url": "https://image.civitai.com/x.jpg",
        "thumbnail_path": "2026-07/hero-thumb.png", "user_note": "approved source",
        "approved_tags": ["hero", "sunset"], "prompt_summary": "hero at sunset",
    }


@contextmanager
def _client(tmp_path: Path, name: str):
    from app.db import models  # noqa: F401 - registers source-alias tables

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


def _remember(Session):
    with Session() as db:
        result = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_payload()), db=db)
    assert result.status == "success"
    return result


def _request(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {"current_primary_alias": "Sunset Hero", "expected_registry_version": 1}
    value.update(overrides)
    return value


def _snapshot(Session):
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord

    with Session() as db:
        return {
            "registry": [(r.registry_version, r.source_identity_json, r.acquisition_evidence_json,
                          r.acquisition_evidence_sha256, r.parent_recipe_sha256, r.thumbnail_url,
                          r.thumbnail_path, r.user_note, r.approved_tags_json, r.prompt_summary,
                          r.created_at, r.archived_at)
                         for r in db.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)],
            "aliases": [(a.id, a.registry_version, a.original_alias, a.normalized_key, a.alias_kind)
                        for a in db.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)],
            "history": [(h.id, h.registry_version, h.operation, h.before_aliases_json, h.after_aliases_json,
                         h.previous_event_sha256, h.event_sha256, h.created_at)
                        for h in db.query(CivitaiSourceAliasHistory).order_by(CivitaiSourceAliasHistory.id)],
        }


def _assert_redacted(response) -> None:
    detail = response.json()["detail"]
    assert isinstance(detail, dict)
    assert all(secret.lower() not in response.text.lower() for secret in _SECRETS)

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return {str(key) for key in value} | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert not ({"record", "alias", "history", "event", "exception"} & keys(detail))


def test_source_alias_archive_api_success_returns_terminal_audit_evidence(tmp_path: Path) -> None:
    """CIV-SA-L-AC1: archive success preserves core audit evidence and terminal read-back."""
    from app.services.civitai_source_alias_registry import exact_resolve

    with _client(tmp_path, "success") as (client, Session, _):
        remembered = _remember(Session)
        before = _snapshot(Session)
        response = client.post(_ROUTE, json=_request())
        after = _snapshot(Session)

        assert response.status_code == 200
        body = response.json()
        assert (body["status"], body["code"], body["record"]) == ("success", "archived", remembered.record.model_dump(mode="json"))
        assert set(body["event"]) == {"id", "registry_version", "operation", "before_aliases", "after_aliases", "previous_event_sha256", "event_sha256", "created_at"}
        assert body["archived_at"].endswith("Z") and body["event"]["created_at"] == body["archived_at"]
        assert body["event"]["operation"] == "archive"
        assert body["event"]["before_aliases"] == body["event"]["after_aliases"]
        assert after["registry"][0][:-1] == before["registry"][0][:-1]
        assert after["aliases"] == before["aliases"] and len(after["history"]) == len(before["history"]) + 1
        with Session() as db:
            results = [exact_resolve(alias, db=db) for alias in ("Sunset Hero", "Apple Alternate", "zebra alternate")]
        assert all((result.status, result.code) == ("archived", "target_archived") for result in results)


def test_source_alias_archive_api_fail_closed_status_mapping_and_redaction(tmp_path: Path) -> None:
    """CIV-SA-L-AC2: strict input and core outcomes map deterministically with zero writes."""
    from app.db.models import CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import archive_source_alias

    def exercise(name, payload, expected_status, expected_code, setup=None):
        with _client(tmp_path, name) as (client, Session, _):
            _remember(Session)
            if setup == "archived":
                with Session() as db:
                    assert archive_source_alias(_request(), db=db).status == "success"
            elif setup == "registry-corrupt":
                with Session() as db:
                    db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "b" * 64})
                    db.commit()
            elif setup == "history-corrupt":
                with Session() as db:
                    assert archive_source_alias(_request(), db=db).status == "success"
                    db.query(CivitaiSourceAliasHistory).update({"event_sha256": "c" * 64})
                    db.commit()
            before = _snapshot(Session)
            response = client.post(_ROUTE, json=payload)
            assert response.status_code == expected_status
            assert response.json()["detail"]["code"] == expected_code
            _assert_redacted(response)
            assert _snapshot(Session) == before

    for name, payload, expected_code in (
        ("missing", {}, "source_alias_archive_invalid"),
        ("blank", _request(current_primary_alias=" \t"), "invalid_request"),
        ("long", _request(current_primary_alias="x" * 513), "source_alias_archive_invalid"),
        ("wrong-alias", _request(current_primary_alias=1), "source_alias_archive_invalid"),
        ("wrong-version", _request(expected_registry_version="1"), "source_alias_archive_invalid"),
        ("bool-version", _request(expected_registry_version=True), "source_alias_archive_invalid"),
        ("zero-version", _request(expected_registry_version=0), "source_alias_archive_invalid"),
        ("extra", _request(extra={"Authorization": _SECRETS[0], "nested": list(_SECRETS)}), "source_alias_archive_invalid"),
    ):
        exercise(name, payload, 422, expected_code)
    for name, payload, expected_status, expected_code, setup in (
        ("missing-primary", _request(current_primary_alias="Missing"), 404, "current_alias_not_found", None),
        ("not-primary", _request(current_primary_alias="Apple Alternate"), 404, "current_alias_not_primary", None),
        ("stale", _request(expected_registry_version=2), 409, "stale_registry_version", None),
        ("archived", _request(), 409, "already_archived", "archived"),
        ("registry-corrupt", _request(), 409, "source_alias_registry_corrupt", "registry-corrupt"),
        ("history-corrupt", _request(), 409, "source_alias_registry_corrupt", "history-corrupt"),
    ):
        exercise(name, payload, expected_status, expected_code, setup)


@contextmanager
def _forbidden_boundary_bombs():
    def bomb(*_args, **_kwargs):
        raise AssertionError("archive facade invoked a forbidden fallback")

    targets = (
        "app.api.civitai_recipes.resolve_source_alias_exact", "app.api.civitai_recipes.search_registry_sources",
        "app.api.civitai_recipes.list_registry_sources", "app.api.civitai_recipes.rename_primary_source_alias",
        "app.api.civitai_recipes.httpx.get", "app.api.civitai_recipes.httpx.post", "pathlib.Path.mkdir",
        "app.api.civitai_recipes.import_recipe", "app.api.civitai_recipes.inspect_recipe",
        "app.api.civitai_recipes.resolve_recipe", "app.api.civitai_recipes.build_recipe",
        "app.api.civitai_recipes.submit_custom", "app.api.civitai_recipes.build_recipe_provenance_bundle",
        "app.api.civitai_recipes.generate_one_variant", "app.api.civitai_recipes.create_variation_set",
        "app.api.civitai_recipes.get_variation_set", "app.api.civitai_recipes.export_variation_set",
        "app.api.civitai_recipes.cancel_variation_set",
    )
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, side_effect=bomb))
        yield


def _result(status: str, code: str) -> CivitaiSourceAliasArchiveResult:
    if status != "success":
        return CivitaiSourceAliasArchiveResult(status=status, code=code)
    event = CivitaiSourceAliasHistoryEventView(id=1, registry_version=1, operation="archive", before_aliases={"primary": "Sunset Hero"}, after_aliases={"primary": "Sunset Hero"}, previous_event_sha256=None, event_sha256="d" * 64, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    return CivitaiSourceAliasArchiveResult.model_validate({"status": "success", "code": "archived", "record": {"registry_version": 1, "source_identity": {"provider": "civitai", "image_id": 123}, "acquisition_evidence_snapshot": {"image": {"id": 123}}, "acquisition_evidence_sha256": "a" * 64, "parent_recipe_sha256": "b" * 64, "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}, "archived_at": event.created_at, "event": event})


def test_source_alias_archive_api_delegates_once_without_lifecycle_or_generation_fallback(tmp_path: Path) -> None:
    """CIV-SA-L-AC3: every valid core outcome is one typed call with the injected Session."""
    with _client(tmp_path, "delegation") as (client, _Session, injected):
        for result, expected_status in ((_result("success", "archived"), 200), (_result("rejected", "invalid_request"), 422), (_result("missing", "current_alias_not_found"), 404), (_result("conflict", "already_archived"), 409), (_result("corrupt", "history_invalid"), 409)):
            with patch("app.api.civitai_recipes.archive_source_alias", return_value=result) as delegated:
                with _forbidden_boundary_bombs():
                    response = client.post(_ROUTE, json=_request())
            assert response.status_code == expected_status
            assert delegated.call_count == 1 and delegated.call_args.kwargs == {"db": injected[-1]}
            assert type(delegated.call_args.args[0]).__name__ == "CivitaiSourceAliasArchiveRequest"
            assert delegated.call_args.args[0].model_dump() == _request()
        with patch("app.api.civitai_recipes.archive_source_alias") as delegated:
            assert client.post(_ROUTE, json=_request(extra=True)).status_code == 422
            delegated.assert_not_called()


def test_source_alias_archive_route_registration_preserves_existing_routes() -> None:
    """CIV-SA-L-AC4: archive has one local route and adjacent route classes/paths are unchanged."""
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    registered = {(route.path, method) for route in routes for method in route.methods}
    expected = {(_ROUTE, "POST"), ("/api/civitai-recipes/source-aliases/resolve", "POST"), ("/api/civitai-recipes/source-aliases", "GET"), ("/api/civitai-recipes/source-aliases/search", "POST"), ("/api/civitai-recipes/source-aliases/rename", "POST"), ("/api/civitai-recipes/import", "POST"), ("/api/civitai-recipes/inspect", "POST"), ("/api/civitai-recipes/resolve", "POST"), ("/api/civitai-recipes/build", "POST"), ("/api/civitai-recipes/run", "POST"), ("/api/civitai-recipes/compatibility", "POST"), ("/api/civitai-recipes/variants/generate-one", "POST"), ("/api/civitai-recipes/variation-sets", "POST")}
    assert expected <= registered
    assert sum(route.path == _ROUTE and "POST" in route.methods for route in routes) == 1
    archive = next(route for route in routes if route.path == _ROUTE and "POST" in route.methods)
    assert type(archive).__name__ == "_SourceAliasArchiveValidationRoute"
    neighbors = {route.path: type(route).__name__ for route in routes if route.path in {"/api/civitai-recipes/source-aliases/resolve", "/api/civitai-recipes/source-aliases", "/api/civitai-recipes/source-aliases/search", "/api/civitai-recipes/source-aliases/rename"}}
    assert neighbors == {"/api/civitai-recipes/source-aliases/resolve": "_SourceAliasResolveValidationRoute", "/api/civitai-recipes/source-aliases": "_SourceAliasDiscoveryValidationRoute", "/api/civitai-recipes/source-aliases/search": "_SourceAliasDiscoveryValidationRoute", "/api/civitai-recipes/source-aliases/rename": "_SourceAliasRenameValidationRoute"}
