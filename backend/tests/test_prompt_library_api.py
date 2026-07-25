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
            "schema_version": 2,
            "library_id": "default",
            "name": "Test Prompt Library",
            "description_zh": "測試提示詞庫",
            "comma_atomic_version": 1,
            "comma_atomic_migration_required": False,
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


@pytest.mark.parametrize(
    ("prompt", "error_code"),
    [
        ("masterpiece, best quality", "comma_not_atomic"),
        ("   ", "blank_prompt_fragment"),
    ],
)
def test_entry_write_rejects_non_atomic_or_blank_without_token_change(
    client_with_prompt_library: TestClient,
    prompt: str,
    error_code: str,
) -> None:
    before = client_with_prompt_library.get(
        "/api/prompt-library/categories/positive/clothing"
    ).json()
    response = client_with_prompt_library.put(
        "/api/prompt-library/categories/positive/clothing/entries/dress",
        json={
            "name_zh": "洋裝",
            "description_zh": "一件式裙裝",
            "prompt": prompt,
            "expected_revision": before["category"]["revision"],
            "expected_etag": before["etag"],
        },
    )
    after = client_with_prompt_library.get(
        "/api/prompt-library/categories/positive/clothing"
    ).json()

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == error_code
    assert after["category"]["revision"] == before["category"]["revision"]
    assert after["etag"] == before["etag"]


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


def test_compose_can_save_and_read_back_safe_unicode_combination_id(
    client_with_prompt_library: TestClient,
) -> None:
    response = client_with_prompt_library.post(
        "/api/prompt-library/compose",
        json={
            "positive": [{"kind": "literal", "snapshot": "masterpiece"}],
            "negative": [{"kind": "literal", "snapshot": "worst quality"}],
            "save_as": {
                "id": "niji基礎瑟瑟",
                "name_zh": "niji基礎瑟瑟",
                "description_zh": "niji基礎瑟瑟",
                "expected_revision": 0,
            },
        },
    )

    assert response.status_code == 200
    saved = response.json()["saved_combination"]["combination"]
    assert saved["id"] == "niji基礎瑟瑟"
    detail = client_with_prompt_library.get(
        "/api/prompt-library/combinations/niji%E5%9F%BA%E7%A4%8E%E7%91%9F%E7%91%9F"
    )
    assert detail.status_code == 200
    assert detail.json()["combination"]["id"] == "niji基礎瑟瑟"


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
        "/api/prompt-library/migration-status",
        "/api/prompt-library/catalog",
        "/api/prompt-library/categories/{polarity}/{category_id}",
        "/api/prompt-library/search",
        "/api/prompt-library/categories/{polarity}/{category_id}/entries/{entry_id}",
        "/api/prompt-library/archive",
        "/api/prompt-library/restore",
        "/api/prompt-library/compose",
        "/api/prompt-library/combinations",
        "/api/prompt-library/combinations/{combination_id}",
        "/api/prompt-library/combinations/{combination_id}/acknowledge-literal-conversion",
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
    assert "post" in paths["/api/prompt-library/restore"]


def _archive_via_api(client: TestClient, resource_type: str) -> dict[str, object]:
    current = client.get("/api/prompt-library/categories/positive/clothing").json()
    payload: dict[str, object] = {
        "resource_type": resource_type,
        "resource_id": "clothing" if resource_type == "category" else "dress",
        "polarity": "positive",
        "expected_revision": current["category"]["revision"],
        "expected_etag": current["etag"],
    }
    if resource_type == "entry":
        payload["category_id"] = "clothing"
    response = client.post("/api/prompt-library/archive", json=payload)
    assert response.status_code == 200
    return response.json()


def test_category_restore_route_returns_new_versioned_category(
    client_with_prompt_library: TestClient,
) -> None:
    archived = _archive_via_api(client_with_prompt_library, "category")["category"]
    response = client_with_prompt_library.post(
        "/api/prompt-library/restore",
        json={
            "resource_type": "category",
            "resource_id": "clothing",
            "polarity": "positive",
            "expected_revision": archived["category"]["revision"],
            "expected_etag": archived["etag"],
        },
    )

    assert response.status_code == 200
    versioned = response.json()["category"]
    assert versioned["category"]["archived"] is False
    assert versioned["category"]["revision"] == archived["category"]["revision"] + 1
    assert versioned["etag"] != archived["etag"]


def test_entry_restore_route_returns_entry_and_parent_version(
    client_with_prompt_library: TestClient,
) -> None:
    archived = _archive_via_api(client_with_prompt_library, "entry")
    response = client_with_prompt_library.post(
        "/api/prompt-library/restore",
        json={
            "resource_type": "entry",
            "resource_id": "dress",
            "polarity": "positive",
            "category_id": "clothing",
            "expected_revision": archived["category"]["category"]["revision"],
            "expected_etag": archived["category"]["etag"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entry"]["archived"] is False
    assert body["entry_revision"] == body["entry"]["revision"]
    assert body["category"]["category"]["revision"] == (
        archived["category"]["category"]["revision"] + 1
    )


def test_restore_conflict_is_actionable(client_with_prompt_library: TestClient) -> None:
    response = client_with_prompt_library.post(
        "/api/prompt-library/restore",
        json={
            "resource_type": "category",
            "resource_id": "clothing",
            "polarity": "positive",
            "expected_revision": 999,
            "expected_etag": "stale",
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "revision_conflict"
    assert detail["message"]
    assert detail["hint"]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "resource_type": "combination",
            "resource_id": "portrait-dress",
            "polarity": "positive",
            "expected_revision": 1,
        },
        {
            "resource_type": "entry",
            "resource_id": "dress",
            "polarity": "positive",
            "expected_revision": 1,
        },
        {
            "resource_type": "category",
            "resource_id": "clothing",
            "polarity": "positive",
            "category_id": "clothing",
            "expected_revision": 1,
        },
    ],
)
def test_restore_rejects_unsupported_or_invalid_locator_shapes(
    client_with_prompt_library: TestClient, payload: dict[str, object]
) -> None:
    response = client_with_prompt_library.post(
        "/api/prompt-library/restore", json=payload
    )

    assert response.status_code == 422
