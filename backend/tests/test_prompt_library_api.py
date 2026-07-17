from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.prompt_library import FilePromptLibraryProvider
from app.main import app


@pytest.fixture
def client_with_prompt_library(tmp_path: Path):
    from app.api import prompt_library as prompt_library_api

    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True)
    (root / "negative").mkdir()
    (root / "combinations").mkdir()
    documents = {
        root / "manifest.json": {
            "schema_version": 1,
            "library_id": "default",
            "name": "Test Prompt Library",
            "description_zh": "測試提示詞庫",
        },
        root / "positive" / "clothing.json": {
            "schema_version": 1,
            "id": "clothing",
            "polarity": "positive",
            "name_zh": "服裝",
            "description_zh": "服裝提示詞",
            "aliases": ["outfit"],
            "keywords": ["clothing"],
            "order": 10,
            "revision": 1,
            "archived": False,
            "entries": [
                {
                    "id": "dress",
                    "name_zh": "洋裝",
                    "description_zh": "一件式裙裝",
                    "prompt": "dress",
                    "aliases": ["裙裝"],
                    "keywords": ["wardrobe"],
                    "order": 10,
                    "revision": 1,
                    "archived": False,
                }
            ],
        },
    }
    for path, value in documents.items():
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    provider = FilePromptLibraryProvider(root)
    app.dependency_overrides[prompt_library_api._provider] = lambda: provider
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(prompt_library_api._provider, None)


def test_catalog_search_and_detail(client_with_prompt_library: TestClient) -> None:
    catalog = client_with_prompt_library.get("/api/prompt-library/catalog")
    search = client_with_prompt_library.get(
        "/api/prompt-library/search", params={"q": "裙裝", "polarity": "positive"}
    )
    detail = client_with_prompt_library.get(
        "/api/prompt-library/categories/positive/clothing"
    )
    assert catalog.status_code == search.status_code == detail.status_code == 200
    assert catalog.json()["categories"][0]["etag"]
    assert search.json()["results"][0]["matched_fields"]
    assert detail.json()["category"]["entries"][0]["prompt"] == "dress"


def test_entry_write_conflict_is_actionable(
    client_with_prompt_library: TestClient,
) -> None:
    response = client_with_prompt_library.put(
        "/api/prompt-library/categories/positive/clothing/entries/dress",
        json={
            "name_zh": "洋裝",
            "description_zh": "一件式裙裝",
            "prompt": "dress",
            "expected_revision": 999,
            "expected_etag": "stale",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "revision_conflict"
    assert response.json()["detail"]["message"]
    assert response.json()["detail"]["hint"]


def test_compose_can_optionally_save_combination(
    client_with_prompt_library: TestClient,
) -> None:
    response = client_with_prompt_library.post(
        "/api/prompt-library/compose",
        json={
            "positive": [
                {
                    "kind": "entry",
                    "ref": {
                        "polarity": "positive",
                        "category_id": "clothing",
                        "entry_id": "dress",
                    },
                    "snapshot": "dress",
                    "source_revision": 1,
                }
            ],
            "negative": [],
            "save_as": {
                "id": "my-dress",
                "name_zh": "我的洋裝",
                "description_zh": "常用洋裝提示詞",
                "aliases": [],
                "keywords": [],
                "expected_revision": 0,
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["positive_prompt"] == "dress"
    assert response.json()["saved_combination"]["combination"]["id"] == "my-dress"


def test_write_list_detail_and_archive_routes(
    client_with_prompt_library: TestClient,
) -> None:
    category = client_with_prompt_library.put(
        "/api/prompt-library/categories/positive/poses",
        json={
            "name_zh": "姿勢",
            "description_zh": "姿勢提示詞",
            "expected_revision": 0,
        },
    )
    assert category.status_code == 200
    assert category.json()["category"]["category"]["id"] == "poses"

    created = client_with_prompt_library.put(
        "/api/prompt-library/combinations/simple",
        json={
            "name_zh": "簡單組合",
            "description_zh": "測試組合",
            "positive": [{"kind": "literal", "snapshot": "masterpiece"}],
            "expected_revision": 0,
        },
    )
    assert created.status_code == 200
    versioned = created.json()["combination"]

    listing = client_with_prompt_library.get("/api/prompt-library/combinations")
    detail = client_with_prompt_library.get(
        "/api/prompt-library/combinations/simple"
    )
    assert listing.status_code == detail.status_code == 200
    assert [item["id"] for item in listing.json()] == ["simple"]

    archived = client_with_prompt_library.post(
        "/api/prompt-library/archive",
        json={
            "resource_type": "combination",
            "resource_id": "simple",
            "expected_revision": versioned["combination"]["revision"],
            "expected_etag": versioned["etag"],
        },
    )
    assert archived.status_code == 200
    assert archived.json()["combination"]["combination"]["archived"] is True


def test_openapi_contains_prompt_library_route_table() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/prompt-library/catalog",
        "/api/prompt-library/categories/{polarity}/{category_id}",
        "/api/prompt-library/search",
        "/api/prompt-library/categories/{polarity}/{category_id}/entries/{entry_id}",
        "/api/prompt-library/archive",
        "/api/prompt-library/compose",
        "/api/prompt-library/combinations",
        "/api/prompt-library/combinations/{combination_id}",
    }
    assert expected <= set(paths)
    assert set(paths["/api/prompt-library/categories/{polarity}/{category_id}"]) >= {
        "get",
        "put",
    }
    assert set(paths["/api/prompt-library/combinations/{combination_id}"]) >= {
        "get",
        "put",
    }
