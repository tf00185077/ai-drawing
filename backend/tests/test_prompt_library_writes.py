from __future__ import annotations

import json
from pathlib import Path

import pytest
from filelock import FileLock

from app.core.prompt_library import FilePromptLibraryProvider
from app.core.prompt_library_errors import PromptLibraryError
from app.schemas.prompt_library import (
    ArchiveRequest,
    CategoryWriteRequest,
    CombinationWriteRequest,
    EntryWriteRequest,
)


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def provider(tmp_path: Path) -> FilePromptLibraryProvider:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True)
    (root / "negative").mkdir()
    (root / "combinations").mkdir()
    _write_json(
        root / "manifest.json",
        {
            "schema_version": 1,
            "library_id": "default",
            "name": "Test Prompt Library",
            "description_zh": "測試提示詞庫",
        },
    )
    _write_json(
        root / "positive" / "clothing.json",
        {
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
                    "aliases": ["連身裙"],
                    "keywords": ["wardrobe"],
                    "order": 10,
                    "revision": 1,
                    "archived": False,
                }
            ],
        },
    )
    _write_json(
        root / "combinations" / "portrait-dress.json",
        {
            "schema_version": 1,
            "id": "portrait-dress",
            "name_zh": "洋裝肖像",
            "description_zh": "測試組合",
            "aliases": [],
            "keywords": [],
            "order": 10,
            "revision": 1,
            "archived": False,
            "legacy_template": False,
            "positive": [
                {
                    "kind": "literal",
                    "snapshot": "1girl",
                    "weight": 1.0,
                    "order": 10,
                },
                {
                    "kind": "entry",
                    "ref": {
                        "polarity": "positive",
                        "category_id": "clothing",
                        "entry_id": "dress",
                    },
                    "snapshot": "dress",
                    "source_revision": 1,
                    "weight": 1.0,
                    "order": 20,
                },
            ],
            "negative": [],
            "positive_prompt_snapshot": "1girl, dress",
            "negative_prompt_snapshot": "",
        },
    )
    return FilePromptLibraryProvider(root)


def entry_write(**overrides: object) -> EntryWriteRequest:
    values: dict[str, object] = {
        "name_zh": "洋裝",
        "description_zh": "一件式裙裝",
        "prompt": "dress",
        "aliases": ["連身裙"],
        "keywords": ["wardrobe"],
        "order": 10,
        "expected_revision": 1,
        "expected_etag": None,
    }
    return EntryWriteRequest.model_validate(values | overrides)


def test_existing_write_requires_matching_revision_and_etag(provider) -> None:
    current = provider.get_category("positive", "clothing")
    with pytest.raises(PromptLibraryError) as revision:
        provider.save_entry(
            "positive",
            "clothing",
            "dress",
            entry_write(expected_revision=999, expected_etag=current.etag),
        )
    assert revision.value.code == "revision_conflict"

    path = provider.root / "positive" / "clothing.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(PromptLibraryError) as external:
        provider.save_entry(
            "positive",
            "clothing",
            "dress",
            entry_write(
                expected_revision=current.category.revision,
                expected_etag=current.etag,
            ),
        )
    assert external.value.code == "external_change"


def test_create_requires_revision_zero_and_no_etag(provider) -> None:
    request = CategoryWriteRequest(
        name_zh="姿勢",
        description_zh="姿勢提示詞",
        expected_revision=1,
    )
    with pytest.raises(PromptLibraryError) as caught:
        provider.save_category("positive", "poses", request)
    assert caught.value.code == "revision_conflict"


def test_metadata_only_category_update_preserves_entries(provider) -> None:
    current = provider.get_category("positive", "clothing")
    saved = provider.save_category(
        "positive",
        "clothing",
        CategoryWriteRequest(
            name_zh="衣著",
            description_zh="更新後描述",
            aliases=["outfit"],
            keywords=["clothing"],
            order=20,
            expected_revision=current.category.revision,
            expected_etag=current.etag,
        ),
    )
    assert saved.category is not None
    assert saved.category.category.revision == 2
    assert [entry.id for entry in saved.category.category.entries] == ["dress"]


def test_entry_correction_repairs_referencing_combinations(provider) -> None:
    category = provider.get_category("positive", "clothing")
    saved = provider.save_entry(
        "positive",
        "clothing",
        "dress",
        entry_write(
            prompt="evening dress",
            expected_revision=category.category.revision,
            expected_etag=category.etag,
        ),
    )
    combination = provider.get_combination("portrait-dress")
    referenced = next(item for item in combination.combination.positive if item.ref)
    assert referenced.snapshot == "evening dress"
    assert referenced.source_revision == saved.entry_revision
    assert combination.combination.positive_prompt_snapshot == "1girl, evening dress"
    assert saved.affected_combinations == ["portrait-dress"]


def test_lazy_read_repairs_partial_eager_update(provider) -> None:
    category_path = provider.root / "positive" / "clothing.json"
    category = json.loads(category_path.read_text(encoding="utf-8"))
    category["revision"] = 2
    category["entries"][0]["revision"] = 2
    category["entries"][0]["prompt"] = "corrected dress"
    _write_json(category_path, category)

    combination_path = provider.root / "combinations" / "portrait-dress.json"
    before = json.loads(combination_path.read_text(encoding="utf-8"))["revision"]
    loaded = provider.get_combination("portrait-dress")
    assert loaded.repaired is True
    assert loaded.combination.revision == before + 1
    assert loaded.combination.positive_prompt_snapshot == "1girl, corrected dress"


def test_archive_entry_uses_parent_token_and_marks_entry_archived(provider) -> None:
    current = provider.get_category("positive", "clothing")
    saved = provider.archive(
        ArchiveRequest(
            resource_type="entry",
            resource_id="dress",
            polarity="positive",
            category_id="clothing",
            expected_revision=current.category.revision,
            expected_etag=current.etag,
        )
    )
    assert saved.entry is not None and saved.entry.archived is True
    assert saved.category is not None and saved.category.category.revision == 2


@pytest.mark.parametrize("resource_type", ["category", "combination"])
def test_archive_marks_top_level_resource_archived(provider, resource_type: str) -> None:
    if resource_type == "category":
        current = provider.get_category("positive", "clothing")
        request = ArchiveRequest(
            resource_type="category",
            resource_id="clothing",
            polarity="positive",
            expected_revision=current.category.revision,
            expected_etag=current.etag,
        )
    else:
        current = provider.get_combination("portrait-dress")
        request = ArchiveRequest(
            resource_type="combination",
            resource_id="portrait-dress",
            expected_revision=current.combination.revision,
            expected_etag=current.etag,
        )

    saved = provider.archive(request)

    if resource_type == "category":
        assert saved.category is not None and saved.category.category.archived is True
    else:
        assert saved.combination is not None
        assert saved.combination.combination.archived is True


def test_combination_create_composes_snapshots(provider) -> None:
    saved = provider.save_combination(
        "new-combination",
        CombinationWriteRequest(
            name_zh="新組合",
            description_zh="新提示詞組合",
            positive=[
                {
                    "kind": "literal",
                    "snapshot": "masterpiece",
                    "order": 10,
                }
            ],
            expected_revision=0,
        ),
    )
    assert saved.combination is not None
    assert saved.combination.combination.revision == 1
    assert saved.combination.combination.positive_prompt_snapshot == "masterpiece"


def test_stale_lock_timeout_maps_to_domain_error(provider) -> None:
    held_lock = FileLock(provider.root / ".lock")
    held_lock.acquire()
    provider.store.lock_timeout = 0
    try:
        with pytest.raises(PromptLibraryError) as caught:
            provider.save_category(
                "positive",
                "poses",
                CategoryWriteRequest(
                    name_zh="姿勢",
                    description_zh="姿勢提示詞",
                    expected_revision=0,
                ),
            )
    finally:
        held_lock.release()
    assert caught.value.code == "lock_timeout"
