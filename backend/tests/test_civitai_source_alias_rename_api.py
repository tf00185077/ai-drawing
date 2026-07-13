"""CIV-SA-J typed source-alias rename HTTP facade acceptance matrix (offline)."""
from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app
from app.schemas.civitai_source_aliases import (
    CivitaiSourceAliasHistoryEventView,
    CivitaiSourceAliasRememberRequest,
    CivitaiSourceAliasRenameResult,
)
from app.services.civitai_source_alias_registry import remember_source_alias

_ROUTE = "/api/civitai-recipes/source-aliases/rename"
_SECRET_SENTINELS = (
    "Authorization: SECRET-AUTH",
    "Bearer SECRET-BEARER",
    "token=SECRET-TOKEN",
    "cookie=SECRET-COOKIE",
    "password=SECRET-PASSWORD",
    "signed-query=SECRET-SIGNED-QUERY",
)


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _remember_payload(*, primary: str = "Sunset Hero", alternates: list[str] | None = None, image_id: int = 123) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 42}}, "provider": "civitai"}
    return {
        "primary_alias": primary,
        "alternate_aliases": ["zebra alternate", "Apple Alternate"] if alternates is None else alternates,
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence,
        "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "a" * 64,
        "thumbnail_url": "https://image.civitai.com/x.jpg",
        "thumbnail_path": "2026-07/hero-thumb.png",
        "user_note": "approved source",
        "approved_tags": ["hero", "sunset"],
        "prompt_summary": "hero at sunset",
    }


@pytest.fixture
def alias_client(tmp_path: Path):
    from app.db import models  # noqa: F401 - register source alias tables

    engine = create_engine(f"sqlite:///{tmp_path / 'source-alias-rename-api.db'}")
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


def _remember(Session, **overrides: object):
    with Session() as db:
        result = remember_source_alias(
            CivitaiSourceAliasRememberRequest.model_validate(_remember_payload(**overrides)), db=db,
        )
        assert result.status == "success"
        return result


@contextmanager
def _isolated_alias_client(tmp_path: Path, case_name: str):
    """One case, one physically distinct clean SQLite database and dependency Session."""
    from app.db import models  # noqa: F401 - register source alias tables

    engine = create_engine(f"sqlite:///{tmp_path / f'{case_name}.db'}")
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


def _snapshot(Session):
    """Full persisted registry/alias/history values, including every audit hash/timestamp."""
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord

    with Session() as db:
        return {
            "registry": [
                (row.registry_version, row.source_identity_json, row.acquisition_evidence_json,
                 row.acquisition_evidence_sha256, row.parent_recipe_sha256, row.thumbnail_url,
                 row.thumbnail_path, row.user_note, row.approved_tags_json, row.prompt_summary,
                 row.created_at, row.archived_at)
                for row in db.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)
            ],
            "aliases": [
                (row.id, row.registry_version, row.original_alias, row.normalized_key, row.alias_kind)
                for row in db.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)
            ],
            "history": [
                (row.id, row.registry_version, row.operation, row.before_aliases_json, row.after_aliases_json,
                 row.previous_event_sha256, row.event_sha256, row.created_at)
                for row in db.query(CivitaiSourceAliasHistory).order_by(CivitaiSourceAliasHistory.id)
            ],
        }


def _assert_secret_free_failure(response) -> None:
    detail = response.json()["detail"]
    assert isinstance(detail, dict)
    text = response.text.lower()
    for sentinel in _SECRET_SENTINELS:
        assert sentinel.lower() not in text

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return {str(key) for key in value} | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert not ({"record", "alias", "history", "event", "exception"} & keys(detail))


def _base_request(**overrides: object) -> dict[str, object]:
    request: dict[str, object] = {
        "current_primary_alias": "Sunset Hero",
        "new_primary_alias": "Aurora Hero",
        "expected_registry_version": 1,
    }
    request.update(overrides)
    return request


def test_source_alias_rename_api_success_returns_audited_lifecycle_result(alias_client) -> None:
    """CIV-SA-J-AC1: HTTP success preserves every audited core-result field verbatim."""
    from app.services.civitai_source_alias_registry import exact_resolve

    client, Session, _ = alias_client
    remembered = _remember(Session)
    before = _snapshot(Session)
    response = client.post(_ROUTE, json=_base_request())
    after = _snapshot(Session)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["code"] == "renamed"
    assert body["record"] == remembered.record.model_dump(mode="json")
    assert body["new_primary"] == {"original_alias": "Aurora Hero", "normalized_key": "aurora hero", "kind": "primary"}
    assert body["preserved_old_alternate"] == {"original_alias": "Sunset Hero", "normalized_key": "sunset hero", "kind": "alternate"}
    assert body["alternate_aliases"] == [
        {"original_alias": "Apple Alternate", "normalized_key": "apple alternate", "kind": "alternate"},
        {"original_alias": "Sunset Hero", "normalized_key": "sunset hero", "kind": "alternate"},
        {"original_alias": "zebra alternate", "normalized_key": "zebra alternate", "kind": "alternate"},
    ]
    assert set(body["event"]) == {
        "id", "registry_version", "operation", "before_aliases", "after_aliases",
        "previous_event_sha256", "event_sha256", "created_at",
    }
    assert body["event"]["operation"] == "rename"
    assert body["event"]["created_at"].endswith("Z")
    assert after["registry"] == before["registry"]
    assert after["aliases"] != before["aliases"]
    assert len(after["history"]) == len(before["history"]) + 1
    with Session() as db:
        new, old = exact_resolve("Aurora Hero", db=db), exact_resolve("Sunset Hero", db=db)
    assert new.record.model_dump(mode="json") == old.record.model_dump(mode="json") == body["record"]


def test_source_alias_rename_api_fail_closed_status_mapping_and_redaction(tmp_path: Path) -> None:
    """CIV-SA-J-AC2: each isolated rejected case is snapshot-stable and redacted."""
    from app.db.models import CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import archive_source_alias, rename_primary_source_alias

    def exercise(name: str, payload: dict[str, object], expected_status: int, expected_code: str, **setup: bool) -> None:
        with _isolated_alias_client(tmp_path, name) as (client, Session):
            _remember(Session)
            if setup.get("collision"):
                _remember(Session, primary="Taken", alternates=[], image_id=456)
            if setup.get("archived"):
                with Session() as db:
                    assert archive_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 1}, db=db).status == "success"
            if setup.get("registry_corrupt"):
                with Session() as db:
                    db.query(CivitaiSourceAliasRegistryRecord).filter_by(registry_version=1).update(
                        {"acquisition_evidence_sha256": "b" * 64}
                    )
                    db.commit()
            if setup.get("history_corrupt"):
                with Session() as db:
                    seeded = rename_primary_source_alias(
                        _base_request(new_primary_alias="History Seed"), db=db,
                    )
                    assert seeded.status == "success"
                    db.query(CivitaiSourceAliasHistory).update({"event_sha256": "c" * 64})
                    db.commit()
            before = _snapshot(Session)
            response = client.post(_ROUTE, json=payload)
            assert response.status_code == expected_status
            assert response.json()["detail"]["code"] == expected_code
            _assert_secret_free_failure(response)
            assert _snapshot(Session) == before

    malformed_cases = (
        ("missing-body-fields", {}, "source_alias_rename_invalid"),
        ("blank-current", _base_request(current_primary_alias=" "), "invalid_request"),
        ("blank-new", _base_request(new_primary_alias=" \t\n"), "invalid_request"),
        ("overlong-new", _base_request(new_primary_alias="x" * 513), "source_alias_rename_invalid"),
        ("wrong-current-type", _base_request(current_primary_alias=1), "source_alias_rename_invalid"),
        ("wrong-new-type", _base_request(new_primary_alias=1), "source_alias_rename_invalid"),
        ("wrong-version-type", _base_request(expected_registry_version="1"), "source_alias_rename_invalid"),
        ("bool-version", _base_request(expected_registry_version=True), "source_alias_rename_invalid"),
        ("zero-version", _base_request(expected_registry_version=0), "source_alias_rename_invalid"),
        ("extra-secret-field", _base_request(extra={"Authorization": _SECRET_SENTINELS[0], "nested": list(_SECRET_SENTINELS)}), "source_alias_rename_invalid"),
    )
    for name, payload, expected_code in malformed_cases:
        exercise(name, payload, 422, expected_code)

    domain_cases = (
        ("unchanged", {}, _base_request(new_primary_alias=" sunset\u2003hero "), 422, "alias_unchanged"),
        ("missing", {}, _base_request(current_primary_alias="Missing"), 404, "current_alias_not_found"),
        ("not-primary", {}, _base_request(current_primary_alias="Apple Alternate"), 404, "current_alias_not_primary"),
        ("collision", {"collision": True}, _base_request(new_primary_alias="Taken"), 409, "alias_already_bound"),
        ("stale", {}, _base_request(expected_registry_version=2), 409, "stale_registry_version"),
        ("archived", {"archived": True}, _base_request(), 409, "target_archived"),
        ("registry-corrupt", {"registry_corrupt": True}, _base_request(), 409, "source_alias_registry_corrupt"),
        ("history-corrupt", {"history_corrupt": True}, _base_request(current_primary_alias="History Seed"), 409, "source_alias_registry_corrupt"),
    )
    for name, setup, payload, expected_status, expected_code in domain_cases:
        exercise(name, payload, expected_status, expected_code, **setup)


def _success_result() -> CivitaiSourceAliasRenameResult:
    event = CivitaiSourceAliasHistoryEventView(
        id=1, registry_version=1, operation="rename", before_aliases={"primary": "Sunset Hero"},
        after_aliases={"primary": "Aurora Hero"}, previous_event_sha256=None, event_sha256="d" * 64,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return CivitaiSourceAliasRenameResult.model_validate({
        "status": "success", "code": "renamed", "record": {
            "registry_version": 1, "source_identity": {"provider": "civitai", "image_id": 123},
            "acquisition_evidence_snapshot": {"image": {"id": 123}}, "acquisition_evidence_sha256": "a" * 64,
            "parent_recipe_sha256": "b" * 64, "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        },
        "new_primary": {"original_alias": "Aurora Hero", "normalized_key": "aurora hero", "kind": "primary"},
        "preserved_old_alternate": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero", "kind": "alternate"},
        "alternate_aliases": [{"original_alias": "Sunset Hero", "normalized_key": "sunset hero", "kind": "alternate"}],
        "event": event,
    })


@contextmanager
def _forbidden_boundary_bombs():
    """The route must be a one-call facade, never a fallback orchestration point."""
    def bomb(*_args, **_kwargs):
        raise AssertionError("rename facade invoked a forbidden fallback")

    targets = (
        "app.api.civitai_recipes.resolve_source_alias_exact",
        "app.api.civitai_recipes.search_registry_sources",
        "app.api.civitai_recipes.list_registry_sources",
        "app.api.civitai_recipes.httpx.get",
        "app.api.civitai_recipes.import_recipe",
        "app.api.civitai_recipes.inspect_recipe",
        "app.api.civitai_recipes.resolve_recipe",
        "app.api.civitai_recipes.build_recipe",
        "app.api.civitai_recipes.submit_custom",
        "app.api.civitai_recipes.build_recipe_provenance_bundle",
        "app.api.civitai_recipes.generate_one_variant",
        "app.api.civitai_recipes.create_variation_set",
        "app.api.civitai_recipes.get_variation_set",
        "app.api.civitai_recipes.export_variation_set",
        "app.api.civitai_recipes.cancel_variation_set",
        "pathlib.Path.mkdir",
    )
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, side_effect=bomb))
        yield


def test_source_alias_rename_api_delegates_once_without_target_or_generation_fallback(alias_client) -> None:
    """CIV-SA-J-AC3: every typed core outcome is delegated once with the injected Session."""
    from app.services.civitai_source_alias_registry import rename_primary_source_alias

    client, _Session, injected_sessions = alias_client
    outcomes = (
        ("success", _success_result(), 200),
        ("domain-422", CivitaiSourceAliasRenameResult(status="rejected", code="alias_unchanged"), 422),
        ("missing", CivitaiSourceAliasRenameResult(status="missing", code="alias_not_found"), 404),
        ("not-primary", CivitaiSourceAliasRenameResult(status="missing", code="current_alias_not_primary"), 404),
        ("collision", CivitaiSourceAliasRenameResult(status="conflict", code="alias_already_bound"), 409),
        ("stale", CivitaiSourceAliasRenameResult(status="rejected", code="stale_registry_version"), 409),
        ("archived", CivitaiSourceAliasRenameResult(status="rejected", code="target_archived"), 409),
        ("corrupt", CivitaiSourceAliasRenameResult(status="corrupt", code="history_invalid"), 409),
    )
    payload = _base_request()
    for _name, result, expected_status in outcomes:
        with patch("app.api.civitai_recipes.rename_primary_source_alias", return_value=result) as delegated:
            with _forbidden_boundary_bombs():
                response = client.post(_ROUTE, json=payload)
        assert response.status_code == expected_status
        assert delegated.call_count == 1
        assert len(delegated.call_args.args) == 1
        assert delegated.call_args.kwargs == {"db": injected_sessions[-1]}
        typed_request = delegated.call_args.args[0]
        assert type(typed_request).__name__ == "CivitaiSourceAliasRenameRequest"
        assert typed_request.model_dump() == payload

    with patch("app.api.civitai_recipes.rename_primary_source_alias", wraps=rename_primary_source_alias) as delegated:
        for malformed in ({}, _base_request(expected_registry_version="1"), _base_request(extra=True)):
            response = client.post(_ROUTE, json=malformed)
            assert response.status_code == 422
        delegated.assert_not_called()


def test_source_alias_rename_route_registration_preserves_existing_routes() -> None:
    """CIV-SA-J-AC4: one local POST; adjacent routes retain their method/path contracts."""
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    registered = {(route.path, method) for route in routes for method in route.methods}
    expected = {
        (_ROUTE, "POST"),
        ("/api/civitai-recipes/source-aliases/resolve", "POST"),
        ("/api/civitai-recipes/source-aliases", "GET"),
        ("/api/civitai-recipes/source-aliases/search", "POST"),
        ("/api/civitai-recipes/import", "POST"), ("/api/civitai-recipes/inspect", "POST"),
        ("/api/civitai-recipes/resolve", "POST"), ("/api/civitai-recipes/build", "POST"),
        ("/api/civitai-recipes/run", "POST"), ("/api/civitai-recipes/compatibility", "POST"),
        ("/api/civitai-recipes/variants/generate-one", "POST"), ("/api/civitai-recipes/variation-sets", "POST"),
    }
    assert expected <= registered
    assert sum(route.path == _ROUTE and "POST" in route.methods for route in routes) == 1
    rename_route = next(route for route in routes if route.path == _ROUTE and "POST" in route.methods)
    assert type(rename_route).__name__ == "_SourceAliasRenameValidationRoute"
    neighbors = {route.path: type(route).__name__ for route in routes if route.path in {
        "/api/civitai-recipes/source-aliases/resolve", "/api/civitai-recipes/source-aliases", "/api/civitai-recipes/source-aliases/search",
    }}
    assert neighbors == {
        "/api/civitai-recipes/source-aliases/resolve": "_SourceAliasResolveValidationRoute",
        "/api/civitai-recipes/source-aliases": "_SourceAliasDiscoveryValidationRoute",
        "/api/civitai-recipes/source-aliases/search": "_SourceAliasDiscoveryValidationRoute",
    }
