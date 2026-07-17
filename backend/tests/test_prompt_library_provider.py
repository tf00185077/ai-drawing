from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.core.prompt_library import FilePromptLibraryProvider
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_models import PromptCategory
from app.core.prompt_library_store import PromptLibraryStore


@pytest.fixture
def library_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True)
    (root / "negative").mkdir()
    (root / "combinations").mkdir()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "library_id": "default",
                "name": "Test Prompt Library",
                "description_zh": "測試用提示詞資料庫",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def entry_dict(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "id": "dress",
        "name_zh": "洋裝",
        "description_zh": "測試洋裝條目",
        "prompt": "dress",
        "aliases": ["連身裙"],
        "keywords": ["wardrobe"],
        "order": 10,
        "revision": 1,
        "archived": False,
    }
    return values | overrides


def category_dict(
    category_id: str, polarity: str, *, entries: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": category_id,
        "polarity": polarity,
        "name_zh": "服裝",
        "description_zh": "測試服裝分類",
        "aliases": ["outfit"],
        "keywords": ["clothing"],
        "order": 10,
        "revision": 1,
        "archived": False,
        "entries": entries,
    }


def write_category(
    root: Path,
    polarity: str,
    category_id: str,
    *,
    entries: list[dict[str, object]],
    document_id: str | None = None,
    document_polarity: str | None = None,
) -> Path:
    path = root / polarity / f"{category_id}.json"
    path.write_text(
        json.dumps(
            category_dict(
                document_id or category_id,
                document_polarity or polarity,
                entries=entries,
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_catalog_loads_valid_category_from_temporary_library(library_root: Path) -> None:
    write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    provider = FilePromptLibraryProvider(library_root)

    catalog = provider.catalog()

    assert catalog.manifest.library_id == "default"
    assert [(item.polarity, item.id, item.entry_count) for item in catalog.categories] == [
        ("positive", "clothing", 1)
    ]
    assert catalog.diagnostics == []


def test_catalog_keeps_valid_files_and_reports_bad_neighbor(library_root: Path) -> None:
    write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    (library_root / "positive" / "broken.json").write_text("{not-json", encoding="utf-8")
    provider = FilePromptLibraryProvider(library_root)

    catalog = provider.catalog()

    assert [item.id for item in catalog.categories] == ["clothing"]
    assert catalog.diagnostics[0].code == "invalid_json"
    assert catalog.diagnostics[0].path == "positive/broken.json"


def test_catalog_reports_id_filename_mismatch_without_hiding_neighbors(library_root: Path) -> None:
    write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    write_category(
        library_root,
        "positive",
        "mismatched",
        document_id="other-category",
        entries=[entry_dict()],
    )

    catalog = FilePromptLibraryProvider(library_root).catalog()

    assert [item.id for item in catalog.categories] == ["clothing"]
    assert catalog.diagnostics[0].code == "id_filename_mismatch"
    assert catalog.diagnostics[0].path == "positive/mismatched.json"


def test_catalog_reports_polarity_mismatch_without_hiding_neighbors(library_root: Path) -> None:
    write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    write_category(
        library_root,
        "positive",
        "wrong-polarity",
        document_polarity="negative",
        entries=[entry_dict()],
    )

    catalog = FilePromptLibraryProvider(library_root).catalog()

    assert [item.id for item in catalog.categories] == ["clothing"]
    assert catalog.diagnostics[0].code == "polarity_mismatch"
    assert catalog.diagnostics[0].path == "positive/wrong-polarity.json"


def test_store_does_not_leak_internal_location_mismatch(library_root: Path) -> None:
    write_category(
        library_root,
        "positive",
        "clothing",
        document_id="other-category",
        entries=[entry_dict()],
    )

    with pytest.raises(PromptLibraryError) as caught:
        PromptLibraryStore(library_root).read_category("positive", "clothing")

    assert caught.value.code == "invalid_document"


def test_external_byte_change_updates_etag_without_trusting_mtime(library_root: Path) -> None:
    path = write_category(library_root, "positive", "clothing", entries=[entry_dict()])
    provider = FilePromptLibraryProvider(library_root)
    first = provider.get_category("positive", "clothing")
    stat = path.stat()
    path.write_text(
        path.read_text(encoding="utf-8").replace("dress", "gown"), encoding="utf-8"
    )
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    second = provider.get_category("positive", "clothing")

    assert second.etag != first.etag
    assert second.category.entries[0].prompt == "gown"


@pytest.mark.parametrize("category_id", ["../secret", "a/b", "A"])
def test_get_category_rejects_unsafe_locator(
    library_root: Path, category_id: str
) -> None:
    provider = FilePromptLibraryProvider(library_root)

    with pytest.raises(PromptLibraryError) as caught:
        provider.get_category("positive", category_id)  # type: ignore[arg-type]

    assert caught.value.code == "invalid_locator"


def test_replace_json_is_validated_and_writes_stable_utf8_document(library_root: Path) -> None:
    store = PromptLibraryStore(library_root)
    path = store.category_path("positive", "clothing")
    category = PromptCategory.model_validate(
        category_dict("clothing", "positive", entries=[entry_dict()])
    )

    etag = store.replace_json(path, category)

    raw = path.read_bytes()
    assert etag
    assert raw.endswith(b"\n")
    assert b"\\u670d" not in raw
    assert json.loads(raw) == category.model_dump(mode="json")
    assert list(path.parent.glob("*.tmp")) == []
