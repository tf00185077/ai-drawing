"""CIV-SA-C exact source-alias resolution facade acceptance matrix (offline)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app
from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
from app.services.civitai_source_alias_registry import remember_source_alias


_ROUTE = "/api/civitai-recipes/source-aliases/resolve"


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _remember_payload(**overrides: object) -> dict[str, object]:
    evidence = {"image": {"id": 123, "meta": {"seed": 42}}, "provider": "civitai"}
    payload: dict[str, object] = {
        "primary_alias": "Sunset Hero",
        "alternate_aliases": ["Sunset Protagonist"],
        "source_identity": {"provider": "civitai", "image_id": 123, "url": "https://civitai.com/images/123"},
        "acquisition_evidence_snapshot": evidence,
        "acquisition_evidence_sha256": _canonical_sha256(evidence),
        "parent_recipe_sha256": "a" * 64,
        "thumbnail_url": "https://image.civitai.com/x.jpg",
        "thumbnail_path": "2026-07/hero-thumb.png",
        "user_note": "approved source",
        "approved_tags": ["hero", "sunset"],
        "prompt_summary": "hero at sunset",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def alias_client(tmp_path: Path):
    from app.db import models  # noqa: F401 - register source alias tables

    engine = create_engine(f"sqlite:///{tmp_path / 'source-aliases.db'}")
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
        yield TestClient(app), Session, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _remember(Session, **overrides: object):
    with Session() as db:
        result = remember_source_alias(CivitaiSourceAliasRememberRequest.model_validate(_remember_payload(**overrides)), db=db)
        assert result.status == "success"
        return result


def _resolved(Session, alias: str):
    from app.services.civitai_source_alias_registry import resolve_source_alias_exact

    with Session() as db:
        result = resolve_source_alias_exact(alias, db=db)
        assert result.status == "success" and result.record is not None and result.alias is not None
        return result


def _snapshot(Session) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasRegistryRecord

    with Session() as db:
        records = [
            (
                row.registry_version, row.source_identity_json, row.acquisition_evidence_json,
                row.acquisition_evidence_sha256, row.parent_recipe_sha256, row.thumbnail_url,
                row.thumbnail_path, row.user_note, row.approved_tags_json, row.prompt_summary,
                row.created_at.isoformat(),
            )
            for row in db.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)
        ]
        aliases = [
            (row.id, row.registry_version, row.original_alias, row.normalized_key, row.alias_kind)
            for row in db.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)
        ]
    return records, aliases


def test_exact_resolve_api_returns_full_audited_binding(alias_client) -> None:
    """CIV-SA-C-AC1: success is a strict field-for-field resolver binding."""
    client, Session, _ = alias_client
    _remember(Session)
    expected = _resolved(Session, "Sunset Hero")

    response = client.post(_ROUTE, json={"alias": "Sunset Hero"})

    assert response.status_code == 200
    assert response.json() == {
        "matched_alias": expected.alias.model_dump(mode="json"),
        **expected.record.model_dump(mode="json"),
    }
    assert response.json()["created_at"].endswith("Z")
    assert set(response.json()) == {
        "matched_alias", "registry_version", "source_identity", "acquisition_evidence_snapshot",
        "acquisition_evidence_sha256", "parent_recipe_sha256", "thumbnail_url", "thumbnail_path",
        "user_note", "approved_tags", "prompt_summary", "created_at",
    }


def test_exact_resolve_api_normalizes_unicode_case_whitespace_and_resolves_alternate_alias(alias_client) -> None:
    """CIV-SA-C-AC2: the committed resolver owns exact-key normalization and match kind."""
    client, Session, _ = alias_client
    expected = _remember(Session)

    response = client.post(_ROUTE, json={"alias": "  ＳＵＮＳＥＴ\u2003\tprotagonist  "})

    assert response.status_code == 200
    body = response.json()
    assert body["matched_alias"] == {
        "original_alias": "Sunset Protagonist",
        "normalized_key": "sunset protagonist",
        "kind": "alternate",
    }
    assert {key: value for key, value in body.items() if key != "matched_alias"} == expected.record.model_dump(mode="json")


@pytest.mark.parametrize(
    "payload, mutation, expected_status, expected_code",
    [
        ({}, None, 404, "invalid_alias"),
        ({"alias": "Sunset Hero", "unexpected": True}, None, 404, "invalid_alias"),
        ({"alias": " \t\n "}, None, 404, "invalid_alias"),
        ({"alias": "not remembered"}, None, 404, "not_found"),
        ({"alias": "Sunset Hero"}, "evidence_hash", 409, "corrupt_registry"),
        ({"alias": "Sunset Hero"}, "malformed_evidence", 409, "corrupt_registry"),
        ({"alias": "Sunset Hero"}, "missing_record", 409, "corrupt_registry"),
        ({"alias": "duplicate"}, "non_unique_alias", 409, "corrupt_registry"),
    ],
)
def test_exact_resolve_api_missing_invalid_and_corrupt_fail_closed_without_side_effects(
    alias_client, payload: dict[str, object], mutation: str | None, expected_status: int, expected_code: str,
) -> None:
    """CIV-SA-C-AC3: all rejected outcomes are redacted and make no registry/generation side effects."""
    client, Session, engine = alias_client
    _remember(Session)
    if mutation == "evidence_hash":
        with Session() as db:
            from app.db.models import CivitaiSourceAliasRegistryRecord
            db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "b" * 64})
            db.commit()
    elif mutation == "malformed_evidence":
        with Session() as db:
            from app.db.models import CivitaiSourceAliasRegistryRecord
            db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_json": "{malformed"})
            db.commit()
    elif mutation == "missing_record":
        with Session() as db:
            from app.db.models import CivitaiSourceAliasRegistryRecord
            db.query(CivitaiSourceAliasRegistryRecord).delete()
            db.commit()
    elif mutation == "non_unique_alias":
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE civitai_source_aliases"))
            connection.execute(text("CREATE TABLE civitai_source_aliases (id INTEGER PRIMARY KEY, registry_version INTEGER NOT NULL, original_alias VARCHAR(512) NOT NULL, normalized_key VARCHAR(512) NOT NULL, alias_kind VARCHAR(16) NOT NULL)"))
            connection.execute(text("INSERT INTO civitai_source_aliases (registry_version, original_alias, normalized_key, alias_kind) VALUES (1, 'first', 'duplicate', 'primary'), (1, 'second', 'duplicate', 'alternate')"))

    before = _snapshot(Session)
    def bomb(*_args, **_kwargs):
        raise AssertionError("read-only alias resolution invoked a forbidden side-effect path")

    with (
        # These are the imported call sites for the compiler/build, queue,
        # gallery provenance, and network paths on the recipe facade.
        patch("app.api.civitai_recipes.build_recipe", side_effect=bomb),
        patch("app.api.civitai_recipes.submit_custom", side_effect=bomb),
        patch("app.api.civitai_recipes.build_recipe_provenance_bundle", side_effect=bomb),
        patch("app.api.civitai_recipes.import_recipe", side_effect=bomb),
        patch("app.api.civitai_recipes.inspect_recipe", side_effect=bomb),
        patch("app.api.civitai_recipes.resolve_recipe", side_effect=bomb),
        patch("app.api.civitai_recipes.httpx.get", side_effect=bomb),
        # The queue is the actual ComfyUI call path; filesystem and network
        # imports are separately bombed at their facade call sites above.
        patch("app.core.queue.get_comfy_client", side_effect=bomb),
        patch("pathlib.Path.mkdir", side_effect=bomb),
    ):
        response = client.post(_ROUTE, json=payload)

    assert response.status_code == expected_status
    assert response.json() == {"detail": {"code": expected_code, "message": "source alias resolution failed"}}
    assert _snapshot(Session) == before


def test_exact_resolve_route_is_registered_and_existing_recipe_routes_remain_registered() -> None:
    """CIV-SA-C-AC4: one POST facade and the frozen existing recipe route surface remain intact."""
    registered = {(route.path, method) for route in app.routes if isinstance(route, APIRoute) for method in route.methods}
    expected = {
        (_ROUTE, "POST"),
        ("/api/civitai-recipes/import", "POST"),
        ("/api/civitai-recipes/inspect", "POST"),
        ("/api/civitai-recipes/resolve", "POST"),
        ("/api/civitai-recipes/build", "POST"),
        ("/api/civitai-recipes/run", "POST"),
        ("/api/civitai-recipes/compatibility", "POST"),
        ("/api/civitai-recipes/variants/generate-one", "POST"),
        ("/api/civitai-recipes/variation-sets", "POST"),
        ("/api/civitai-recipes/variation-sets/{variation_set_id}", "GET"),
        ("/api/civitai-recipes/variation-sets/{variation_set_id}/cancel", "POST"),
        ("/api/civitai-recipes/variation-sets/{variation_set_id}/export", "GET"),
    }
    assert expected <= registered
    assert sum(path == _ROUTE and method == "POST" for path, method in registered) == 1
