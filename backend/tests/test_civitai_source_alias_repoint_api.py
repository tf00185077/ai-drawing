"""CIV-SA-O typed source-alias repoint HTTP facade acceptance matrix (offline)."""
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
    CivitaiSourceAliasRememberRequest,
    CivitaiSourceAliasRepointResult,
    CivitaiSourceAliasRepointTransitionEventView,
)
from app.services.civitai_source_alias_registry import remember_source_alias

_ROUTE = "/api/civitai-recipes/source-aliases/repoint"
_SECRETS = (
    "Authorization: SECRET-AUTH", "Bearer SECRET-BEARER", "token=SECRET-TOKEN",
    "cookie=SECRET-COOKIE", "password=SECRET-PASSWORD", "signed-query=SECRET-SIGNED-QUERY",
)


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _remember_payload(image_id: int = 123) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 42}}, "provider": "civitai"}
    return {
        "primary_alias": "Sunset Hero", "alternate_aliases": ["Apple Alternate", "zebra alternate"],
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence, "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "a" * 64, "thumbnail_url": "https://image.civitai.com/original.jpg",
        "thumbnail_path": "thumbs/original.png", "user_note": "original target", "approved_tags": ["original"],
        "prompt_summary": "original summary",
    }


def _replacement(image_id: int = 456, **overrides: object) -> dict[str, object]:
    evidence = {"image": {"id": image_id, "meta": {"seed": 99}}, "provider": "civitai"}
    value: dict[str, object] = {
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": evidence, "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "b" * 64, "thumbnail_url": "https://image.civitai.com/replacement.jpg",
        "thumbnail_path": "thumbs/replacement.png", "user_note": "replacement target",
        "approved_tags": ["replacement", "verified"], "prompt_summary": "replacement summary",
    }
    value.update(overrides)
    return value


def _request(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {"current_primary_alias": "Sunset Hero", "expected_registry_version": 1, "replacement": _replacement()}
    value.update(overrides)
    return value


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
        result = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_remember_payload()), db=db)
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

    assert not ({"record", "alias", "history", "event", "exception", "transition"} & keys(detail))


def test_source_alias_repoint_api_success_returns_audited_transition_and_requires_explicit_version(tmp_path: Path) -> None:
    """CIV-SA-O-AC1: HTTP success is field-parity over one audited core transition."""
    from app.services.civitai_source_alias_registry import exact_resolve

    with _client(tmp_path, "success") as (client, Session, _):
        remembered = _remember(Session)
        before = _snapshot(Session)
        response = client.post(_ROUTE, json=_request())
        after = _snapshot(Session)
        with Session() as db:
            bare = [exact_resolve(alias, db=db) for alias in ("Sunset Hero", "Apple Alternate", "zebra alternate")]

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["code"], body["from_record"]) == ("success", "repointed", remembered.record.model_dump(mode="json"))
    assert body["to_record"]["registry_version"] == 2
    assert body["to_record"]["source_identity"] == _replacement()["source_identity"]
    assert set(body["event"]) == {"id", "from_registry_version", "to_registry_version", "aliases", "from_record_sha256", "to_record_sha256", "source_history_tail_sha256", "previous_repoint_event_sha256", "event_sha256", "created_at"}
    assert body["event"]["created_at"].endswith("Z")
    assert len(after["records"]) == len(before["records"]) + 1
    assert len(after["transitions"]) == len(before["transitions"]) + 1
    assert [(row[0], *row[2:]) for row in after["aliases"]] == [(row[0], *row[2:]) for row in before["aliases"]]
    assert {row[1] for row in after["aliases"]} == {2}
    assert all((result.status, result.code, result.record, result.alias) == ("repointed", "explicit_registry_version_required", None, None) for result in bare)


def test_source_alias_repoint_api_fail_closed_status_mapping_and_redaction(tmp_path: Path) -> None:
    """CIV-SA-O-AC2: malformed/domain/corrupt outcomes are stable, redacted, and write-free."""
    from app.db.models import CivitaiSourceAliasRegistryRecord
    from app.services.civitai_source_alias_registry import archive_source_alias

    def exercise(name, payload, expected_status, expected_code, setup=None):
        with _client(tmp_path, name) as (client, Session, _):
            _remember(Session)
            if setup == "archived":
                with Session() as db:
                    assert archive_source_alias({"current_primary_alias": "Sunset Hero", "expected_registry_version": 1}, db=db).status == "success"
            elif setup == "corrupt":
                with Session() as db:
                    db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "c" * 64})
                    db.commit()
            before = _snapshot(Session)
            response = client.post(_ROUTE, json=payload)
            assert response.status_code == expected_status
            assert response.json()["detail"]["code"] == expected_code
            _assert_redacted(response)
            assert _snapshot(Session) == before

    for name, payload in (
        ("missing", {}), ("blank", _request(current_primary_alias=" \t")),
        ("overlong", _request(current_primary_alias="x" * 513)), ("wrong-current", _request(current_primary_alias=1)),
        ("wrong-version", _request(expected_registry_version="1")), ("bool-version", _request(expected_registry_version=True)),
        ("extra-secret", _request(extra={"Authorization": _SECRETS[0], "nested": list(_SECRETS)})),
        ("bad-evidence", _request(replacement=_replacement(acquisition_evidence_sha256="0" * 64))),
        ("replacement-extra", _request(replacement=_replacement(extra={"token": _SECRETS[2]}))),
    ):
        exercise(name, payload, 422, "source_alias_repoint_invalid")
    for name, payload, expected_status, expected_code, setup in (
        ("same-target", _request(replacement=_replacement(123)), 422, "same_immutable_target", None),
        ("missing-primary", _request(current_primary_alias="Missing"), 404, "current_alias_not_found", None),
        ("alternate-only", _request(current_primary_alias="Apple Alternate"), 404, "current_alias_not_primary", None),
        ("stale", _request(expected_registry_version=2), 409, "stale_registry_version", None),
        ("archived", _request(), 409, "target_archived", "archived"),
        ("corrupt", _request(), 409, "source_alias_registry_corrupt", "corrupt"),
    ):
        exercise(name, payload, expected_status, expected_code, setup)


def _result(status: str, code: str) -> CivitaiSourceAliasRepointResult:
    if status != "success":
        return CivitaiSourceAliasRepointResult(status=status, code=code)
    event = CivitaiSourceAliasRepointTransitionEventView(id=1, from_registry_version=1, to_registry_version=2, aliases={"primary": {"original_alias": "Sunset Hero"}}, from_record_sha256="c" * 64, to_record_sha256="d" * 64, source_history_tail_sha256=None, previous_repoint_event_sha256=None, event_sha256="e" * 64, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    return CivitaiSourceAliasRepointResult.model_validate({"status": "success", "code": "repointed", "from_record": {"registry_version": 1, "source_identity": {"provider": "civitai", "image_id": 123}, "acquisition_evidence_snapshot": {"image": {"id": 123}}, "acquisition_evidence_sha256": "a" * 64, "parent_recipe_sha256": "b" * 64, "created_at": event.created_at}, "to_record": {"registry_version": 2, "source_identity": {"provider": "civitai", "image_id": 456}, "acquisition_evidence_snapshot": {"image": {"id": 456}}, "acquisition_evidence_sha256": "f" * 64, "parent_recipe_sha256": "0" * 64, "created_at": event.created_at}, "event": event})


@contextmanager
def _forbidden_boundary_bombs():
    def bomb(*_args, **_kwargs):
        raise AssertionError("repoint facade invoked a forbidden fallback")

    targets = (
        "app.api.civitai_recipes.resolve_source_alias_exact", "app.api.civitai_recipes.search_registry_sources", "app.api.civitai_recipes.list_registry_sources", "app.api.civitai_recipes.rename_primary_source_alias", "app.api.civitai_recipes.archive_source_alias", "app.api.civitai_recipes.httpx.get", "app.api.civitai_recipes.httpx.post", "pathlib.Path.mkdir", "app.api.civitai_recipes.import_recipe", "app.api.civitai_recipes.inspect_recipe", "app.api.civitai_recipes.resolve_recipe", "app.api.civitai_recipes.build_recipe", "app.api.civitai_recipes.submit_custom", "app.api.civitai_recipes.build_recipe_provenance_bundle", "app.api.civitai_recipes.generate_one_variant", "app.api.civitai_recipes.create_variation_set", "app.api.civitai_recipes.get_variation_set", "app.api.civitai_recipes.export_variation_set", "app.api.civitai_recipes.cancel_variation_set",
    )
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, side_effect=bomb))
        yield


def test_source_alias_repoint_api_delegates_once_without_resolution_or_generation_fallback(tmp_path: Path) -> None:
    """CIV-SA-O-AC3: valid typed requests make exactly one core call with the injected Session."""
    with _client(tmp_path, "delegation") as (client, _Session, injected):
        for result, expected_status in ((_result("success", "repointed"), 200), (_result("rejected", "same_immutable_target"), 422), (_result("missing", "current_alias_not_found"), 404), (_result("rejected", "stale_registry_version"), 409), (_result("conflict", "repoint_conflict"), 409), (_result("corrupt", "history_invalid"), 409)):
            with patch("app.api.civitai_recipes.repoint_source_alias", return_value=result) as delegated:
                with _forbidden_boundary_bombs():
                    response = client.post(_ROUTE, json=_request())
            assert response.status_code == expected_status
            assert delegated.call_count == 1 and delegated.call_args.kwargs == {"db": injected[-1]}
            assert type(delegated.call_args.args[0]).__name__ == "CivitaiSourceAliasRepointRequest"
            assert delegated.call_args.args[0].model_dump(mode="json") == delegated.call_args.args[0].__class__.model_validate(_request()).model_dump(mode="json")
        with patch("app.api.civitai_recipes.repoint_source_alias") as delegated:
            assert client.post(_ROUTE, json=_request(extra=True)).status_code == 422
            delegated.assert_not_called()


def test_source_alias_repoint_route_registration_preserves_existing_routes() -> None:
    """CIV-SA-O-AC4: exactly one local route without changing adjacent route classes."""
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    registered = {(route.path, method) for route in routes for method in route.methods}
    expected = {(_ROUTE, "POST"), ("/api/civitai-recipes/source-aliases/resolve", "POST"), ("/api/civitai-recipes/source-aliases", "GET"), ("/api/civitai-recipes/source-aliases/search", "POST"), ("/api/civitai-recipes/source-aliases/rename", "POST"), ("/api/civitai-recipes/source-aliases/archive", "POST"), ("/api/civitai-recipes/import", "POST"), ("/api/civitai-recipes/inspect", "POST"), ("/api/civitai-recipes/resolve", "POST"), ("/api/civitai-recipes/build", "POST"), ("/api/civitai-recipes/run", "POST"), ("/api/civitai-recipes/compatibility", "POST"), ("/api/civitai-recipes/variants/generate-one", "POST"), ("/api/civitai-recipes/variation-sets", "POST")}
    assert expected <= registered
    assert sum(route.path == _ROUTE and "POST" in route.methods for route in routes) == 1
    repoint = next(route for route in routes if route.path == _ROUTE and "POST" in route.methods)
    assert type(repoint).__name__ == "_SourceAliasRepointValidationRoute"
    neighbors = {route.path: type(route).__name__ for route in routes if route.path in {"/api/civitai-recipes/source-aliases/resolve", "/api/civitai-recipes/source-aliases", "/api/civitai-recipes/source-aliases/search", "/api/civitai-recipes/source-aliases/rename", "/api/civitai-recipes/source-aliases/archive"}}
    assert neighbors == {"/api/civitai-recipes/source-aliases/resolve": "_SourceAliasResolveValidationRoute", "/api/civitai-recipes/source-aliases": "_SourceAliasDiscoveryValidationRoute", "/api/civitai-recipes/source-aliases/search": "_SourceAliasDiscoveryValidationRoute", "/api/civitai-recipes/source-aliases/rename": "_SourceAliasRenameValidationRoute", "/api/civitai-recipes/source-aliases/archive": "_SourceAliasArchiveValidationRoute"}
