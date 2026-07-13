"""CIV-SA-F typed, fail-closed HTTP facade acceptance matrix (offline)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import ANY, patch

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app
from app.schemas.civitai_source_aliases import CivitaiSourceAliasRememberRequest
from app.services.civitai_source_alias_registry import remember_source_alias

_LIST_ROUTE = "/api/civitai-recipes/source-aliases"
_SEARCH_ROUTE = "/api/civitai-recipes/source-aliases/search"
_INVALID_DETAIL = {
    "detail": {
        "code": "source_alias_discovery_invalid",
        "message": "source alias discovery request invalid",
    }
}
_CORRUPT_DETAIL = {
    "detail": {
        "code": "source_alias_registry_corrupt",
        "message": "source alias discovery unavailable",
    }
}


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _remember_payload(*, ordinal: int, primary: str, alternates: list[str] | None = None) -> dict[str, object]:
    evidence = {
        "safe": {"label": f"evidence-{ordinal}"},
        "token": {"sentinel": f"SECRET-EVIDENCE-{ordinal}"},
    }
    return {
        "primary_alias": primary,
        "alternate_aliases": alternates or [],
        "source_identity": {
            "provider": "civitai",
            "image_id": 1000 + ordinal,
            "url": f"https://civitai.com/images/{1000 + ordinal}",
        },
        "acquisition_evidence_snapshot": evidence,
        "acquisition_evidence_sha256": _canonical_sha256(evidence),
        "parent_recipe_sha256": (format(ordinal % 16, "x") * 64),
        "thumbnail_url": f"https://image.civitai.com/thumbnail-{ordinal}.png",
        "thumbnail_path": f"hidden/{ordinal}.png",
        "user_note": f"note-{ordinal}",
        "approved_tags": [f"tag-{ordinal}"],
        "prompt_summary": f"prompt-{ordinal}",
    }


@pytest.fixture
def alias_client(tmp_path: Path):
    from app.db import models  # noqa: F401 - register source alias tables

    engine = create_engine(f"sqlite:///{tmp_path / 'source-alias-discovery-api.db'}")
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


def _remember(Session, *, ordinal: int, primary: str, alternates: list[str] | None = None) -> None:
    with Session() as db:
        result = remember_source_alias(
            CivitaiSourceAliasRememberRequest.model_validate(
                _remember_payload(ordinal=ordinal, primary=primary, alternates=alternates)
            ),
            db=db,
        )
        assert result.status == "success"


def _snapshot(Session) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasRegistryRecord

    with Session() as db:
        return (
            [
                (
                    row.registry_version, row.source_identity_json, row.acquisition_evidence_json,
                    row.acquisition_evidence_sha256, row.parent_recipe_sha256, row.thumbnail_url,
                    row.thumbnail_path, row.user_note, row.approved_tags_json, row.prompt_summary,
                )
                for row in db.query(CivitaiSourceAliasRegistryRecord).order_by(CivitaiSourceAliasRegistryRecord.registry_version)
            ],
            [
                (row.registry_version, row.original_alias, row.normalized_key, row.alias_kind)
                for row in db.query(CivitaiSourceAlias).order_by(CivitaiSourceAlias.id)
            ],
        )


def test_source_alias_list_api_forwards_paging_and_returns_audited_entries(alias_client) -> None:
    """CIV-SA-F-AC1: list delegates once and returns the complete CIV-SA-E audited page unchanged."""
    from app.services.civitai_source_alias_registry import list_registry_sources

    client, Session = alias_client
    _remember(Session, ordinal=1, primary="First", alternates=["First Alt"])
    _remember(Session, ordinal=2, primary="Second")
    with Session() as db:
        expected = list_registry_sources(db=db, limit=1, offset=1).model_dump(mode="json")

    with patch("app.api.civitai_recipes.list_registry_sources", wraps=list_registry_sources) as delegated:
        response = client.get(_LIST_ROUTE, params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert response.json() == expected
    delegated.assert_called_once_with(db=ANY, limit=1, offset=1)
    entry = response.json()["entries"][0]
    assert set(entry) == {"primary_alias", "alternate_aliases", "record"}
    assert entry["record"]["acquisition_evidence_snapshot"] == expected["entries"][0]["record"]["acquisition_evidence_snapshot"]


def test_source_alias_search_api_returns_ranked_candidates_without_resolution(alias_client) -> None:
    """CIV-SA-F-AC2: search delegates once, preserves ranked evidence, and never resolves a candidate."""
    from app.services.civitai_source_alias_registry import search_registry_sources

    client, Session = alias_client
    _remember(Session, ordinal=1, primary="Solar Hero", alternates=["Day Champion"])
    _remember(Session, ordinal=2, primary="Solar Other")
    with Session() as db:
        expected = search_registry_sources("solar", db=db, limit=1, offset=0).model_dump(mode="json")

    def bomb(*_args, **_kwargs):
        raise AssertionError("candidate discovery must not invoke exact resolution")

    with (
        patch("app.api.civitai_recipes.search_registry_sources", wraps=search_registry_sources) as delegated,
        patch("app.api.civitai_recipes.resolve_source_alias_exact", side_effect=bomb),
    ):
        response = client.post(_SEARCH_ROUTE, json={"query": "solar", "limit": 1, "offset": 0})

    assert response.status_code == 200
    assert response.json() == expected
    delegated.assert_called_once_with("solar", db=ANY, limit=1, offset=0)
    body = response.json()
    assert "selected" not in body and "resolved_target" not in body
    assert body["candidates"][0]["score"] == expected["candidates"][0]["score"]
    assert body["candidates"][0]["matched_fields"] == expected["candidates"][0]["matched_fields"]


def test_source_alias_discovery_api_maps_invalid_and_corrupt_fail_closed_without_side_effects(alias_client) -> None:
    """CIV-SA-F-AC3: malformed/rejected map to redacted 422; corrupt maps to redacted 409 without side effects."""
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasRegistryListResult

    client, Session = alias_client
    _remember(Session, ordinal=1, primary="Valid Primary")
    before = _snapshot(Session)
    sentinel = "SECRET-EVIDENCE-1"

    def bomb(*_args, **_kwargs):
        raise AssertionError("discovery facade invoked a forbidden side-effect path")

    rejected = CivitaiSourceAliasRegistryListResult(status="rejected", code="internal-rejected")
    with (
        patch("app.api.civitai_recipes.list_registry_sources", return_value=rejected),
        patch("app.api.civitai_recipes.resolve_source_alias_exact", side_effect=bomb),
        patch("app.api.civitai_recipes.httpx.get", side_effect=bomb),
        patch("app.api.civitai_recipes.build_recipe", side_effect=bomb),
        patch("app.api.civitai_recipes.submit_custom", side_effect=bomb),
        patch("app.core.queue.get_comfy_client", side_effect=bomb),
        patch("pathlib.Path.mkdir", side_effect=bomb),
    ):
        responses = [
            client.get(_LIST_ROUTE, params={"limit": 0}),
            client.get(_LIST_ROUTE, params={"offset": -1}),
            client.post(_SEARCH_ROUTE, json={"query": " \t\n "}),
            client.post(_SEARCH_ROUTE, json={"query": "x" * 513}),
            client.post(_SEARCH_ROUTE, json={"query": "valid", "extra": sentinel}),
            client.get(_LIST_ROUTE),
        ]
    assert all(response.status_code == 422 and response.json() == _INVALID_DETAIL for response in responses)
    assert all(sentinel not in response.text for response in responses)
    assert _snapshot(Session) == before

    with Session() as db:
        from app.db.models import CivitaiSourceAliasRegistryRecord
        db.query(CivitaiSourceAliasRegistryRecord).update({"acquisition_evidence_sha256": "f" * 64})
        db.commit()
    corrupt_before = _snapshot(Session)
    with (
        patch("app.api.civitai_recipes.resolve_source_alias_exact", side_effect=bomb),
        patch("app.api.civitai_recipes.httpx.get", side_effect=bomb),
        patch("app.api.civitai_recipes.build_recipe", side_effect=bomb),
        patch("app.api.civitai_recipes.submit_custom", side_effect=bomb),
        patch("app.core.queue.get_comfy_client", side_effect=bomb),
        patch("pathlib.Path.mkdir", side_effect=bomb),
    ):
        corrupt_list = client.get(_LIST_ROUTE)
        corrupt_search = client.post(_SEARCH_ROUTE, json={"query": "valid"})
    assert corrupt_list.status_code == corrupt_search.status_code == 409
    assert corrupt_list.json() == corrupt_search.json() == _CORRUPT_DETAIL
    assert sentinel not in corrupt_list.text + corrupt_search.text
    assert _snapshot(Session) == corrupt_before


def test_source_alias_discovery_openapi_contract_and_existing_routes_remain_registered() -> None:
    """CIV-SA-F-AC4: list/search OpenAPI is typed and import/exact-resolve registrations remain intact."""
    registered = {(route.path, method) for route in app.routes if isinstance(route, APIRoute) for method in route.methods}
    assert {
        (_LIST_ROUTE, "GET"),
        (_SEARCH_ROUTE, "POST"),
        ("/api/civitai-recipes/import", "POST"),
        ("/api/civitai-recipes/source-aliases/resolve", "POST"),
    } <= registered

    schema = app.openapi()
    list_operation = schema["paths"][_LIST_ROUTE]["get"]
    search_operation = schema["paths"][_SEARCH_ROUTE]["post"]
    assert list_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("SourceAliasRegistryListResponse")
    assert search_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("SourceAliasRegistrySearchRequest")
    assert search_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("SourceAliasRegistrySearchResponse")
    components = schema["components"]["schemas"]
    for name in ("SourceAliasRegistryListResponse", "SourceAliasRegistrySearchRequest", "SourceAliasRegistrySearchResponse"):
        assert name in components
    assert "entries" in components["SourceAliasRegistryListResponse"]["properties"]
    assert "candidates" in components["SourceAliasRegistrySearchResponse"]["properties"]
    assert "record" in components["CivitaiSourceAliasRegistryEntry"]["properties"]
    assert "score" in components["CivitaiSourceAliasSearchCandidate"]["properties"]
    assert "matched_fields" in components["CivitaiSourceAliasSearchCandidate"]["properties"]
