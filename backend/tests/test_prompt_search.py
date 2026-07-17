from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.prompt_library import FilePromptLibraryProvider


@pytest.fixture
def library_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompt_library"
    for directory in ("positive", "negative", "combinations"):
        (root / directory).mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "library_id": "default",
                "name": "Test Prompt Library",
                "description_zh": "測試提示詞資料庫",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def entry(
    entry_id: str,
    *,
    name_zh: str,
    description_zh: str,
    prompt: str,
    aliases: list[str] | None = None,
    keywords: list[str] | None = None,
    order: int = 10,
    archived: bool = False,
) -> dict[str, object]:
    return {
        "id": entry_id,
        "name_zh": name_zh,
        "description_zh": description_zh,
        "prompt": prompt,
        "aliases": aliases or [],
        "keywords": keywords or [],
        "order": order,
        "revision": 1,
        "archived": archived,
    }


def write_category(
    root: Path,
    polarity: str,
    category_id: str,
    *,
    name_zh: str,
    description_zh: str,
    entries: list[dict[str, object]],
    aliases: list[str] | None = None,
    order: int = 10,
    archived: bool = False,
) -> None:
    document = {
        "schema_version": 1,
        "id": category_id,
        "polarity": polarity,
        "name_zh": name_zh,
        "description_zh": description_zh,
        "aliases": aliases or [],
        "keywords": [],
        "order": order,
        "revision": 1,
        "archived": archived,
        "entries": entries,
    }
    (root / polarity / f"{category_id}.json").write_text(
        json.dumps(document, ensure_ascii=False), encoding="utf-8"
    )


def write_combination(root: Path, *, archived: bool = False) -> None:
    document = {
        "schema_version": 1,
        "id": "portrait-dress",
        "name_zh": "洋裝人像",
        "description_zh": "連身裙角色構圖",
        "aliases": ["portrait outfit"],
        "keywords": ["fashion"],
        "order": 15,
        "revision": 1,
        "archived": archived,
        "legacy_template": False,
        "positive": [],
        "negative": [],
        "positive_prompt_snapshot": "1girl, dress",
        "negative_prompt_snapshot": "low quality",
    }
    (root / "combinations" / "portrait-dress.json").write_text(
        json.dumps(document, ensure_ascii=False), encoding="utf-8"
    )


@pytest.fixture
def provider(library_root: Path) -> FilePromptLibraryProvider:
    write_category(
        library_root,
        "positive",
        "clothing",
        name_zh="服裝",
        description_zh="角色穿著與服裝細節",
        aliases=["dress category"],
        order=20,
        entries=[
            entry(
                "dress",
                name_zh="連身裙",
                description_zh="一件式裙裝",
                prompt="dress",
                aliases=["洋裝", "one-piece dress"],
                keywords=["wardrobe"],
                order=10,
            ),
            entry(
                "wardrobe-guide",
                name_zh="衣櫃指南",
                description_zh="dres",
                prompt="layered outfit",
                order=20,
            ),
            entry(
                "archived-dress",
                name_zh="舊洋裝",
                description_zh="archived dress",
                prompt="dress archive",
                archived=True,
            ),
        ],
    )
    write_category(
        library_root,
        "negative",
        "quality",
        name_zh="品質",
        description_zh="避免低品質成像",
        order=10,
        entries=[
            entry(
                "low-quality",
                name_zh="低品質",
                description_zh="避免模糊與瑕疵",
                prompt="low quality",
                aliases=["bad quality"],
            )
        ],
    )
    write_category(
        library_root,
        "positive",
        "archived-category",
        name_zh="舊分類",
        description_zh="archive dress category",
        archived=True,
        entries=[
            entry(
                "hidden-dress",
                name_zh="隱藏洋裝",
                description_zh="dress",
                prompt="hidden dress",
            )
        ],
    )
    write_combination(library_root)
    return FilePromptLibraryProvider(library_root)


def test_search_matches_chinese_description_and_english_alias(
    provider: FilePromptLibraryProvider,
) -> None:
    zh = provider.search("裙裝", polarity="positive")
    en = provider.search("ＯＮＥ—ＰＩＥＣＥ!!!", polarity="positive")

    assert zh.results[0].id == "dress"
    assert "description_zh" in zh.results[0].matched_fields
    assert en.results[0].id == "dress"
    assert "aliases" in en.results[0].matched_fields


def test_search_preserves_cjk_and_normalizes_case_punctuation_and_whitespace(
    provider: FilePromptLibraryProvider,
) -> None:
    assert provider.search("  連身裙  ").results[0].id == "dress"
    assert provider.search("ONE_piece---DRESS").results[0].id == "dress"


def test_search_is_deterministic_and_excludes_archived_by_default(
    provider: FilePromptLibraryProvider,
) -> None:
    first = provider.search("dress", limit=50)
    second = provider.search("dress", limit=50)

    assert [(hit.resource_type, hit.id, hit.score) for hit in first.results] == [
        (hit.resource_type, hit.id, hit.score) for hit in second.results
    ]
    assert all(not hit.archived for hit in first.results)
    assert "archived-dress" not in {hit.id for hit in first.results}
    assert "hidden-dress" not in {hit.id for hit in first.results}


def test_search_can_explicitly_include_archived_resources(
    provider: FilePromptLibraryProvider,
) -> None:
    result = provider.search("dress", include_archived=True)

    ids = {hit.id for hit in result.results}
    assert {"archived-dress", "archived-category", "hidden-dress"} <= ids
    assert next(hit for hit in result.results if hit.id == "hidden-dress").archived is True


def test_description_fuzzy_match_scores_below_exact_prompt(
    provider: FilePromptLibraryProvider,
) -> None:
    result = provider.search("dress")

    exact = next(hit for hit in result.results if hit.id == "dress")
    description_only = next(hit for hit in result.results if hit.id == "wardrobe-guide")
    assert exact.score > description_only.score >= 45


def test_search_includes_categories_entries_and_combinations(
    provider: FilePromptLibraryProvider,
) -> None:
    result = provider.search("dress")

    resource_types = {hit.resource_type for hit in result.results}
    assert {"category", "entry", "combination"} <= resource_types
    combination = next(hit for hit in result.results if hit.resource_type == "combination")
    assert "positive_prompt_snapshot" in combination.matched_fields


def test_entry_search_uses_category_context_at_lower_weight(
    provider: FilePromptLibraryProvider,
) -> None:
    result = provider.search("角色穿著", threshold=45)

    dress = next(hit for hit in result.results if hit.id == "dress")
    assert dress.score == 54
    assert dress.matched_fields == ["category_context"]


def test_polarity_filter_applies_to_polarized_resources(
    provider: FilePromptLibraryProvider,
) -> None:
    result = provider.search("quality", polarity="negative")

    assert result.results
    assert all(hit.polarity == "negative" for hit in result.results)


def test_ties_use_polarity_category_order_resource_order_name_and_id(
    library_root: Path,
) -> None:
    for polarity in ("positive", "negative"):
        write_category(
            library_root,
            polarity,
            f"{polarity}-category",
            name_zh="分類",
            description_zh="tie",
            order=10 if polarity == "negative" else 20,
            entries=[
                entry(
                    f"{polarity}-two",
                    name_zh="乙",
                    description_zh="tie",
                    prompt="same",
                    order=20,
                ),
                entry(
                    f"{polarity}-one",
                    name_zh="甲",
                    description_zh="tie",
                    prompt="same",
                    order=10,
                ),
            ],
        )
    provider = FilePromptLibraryProvider(library_root)

    result = provider.search("same")

    assert [hit.id for hit in result.results] == [
        "negative-one",
        "negative-two",
        "positive-one",
        "positive-two",
    ]


def test_threshold_and_limit_are_bounded_and_applied(
    provider: FilePromptLibraryProvider,
) -> None:
    assert len(provider.search("dress", threshold=80, limit=1).results) == 1
    assert all(hit.score >= 80 for hit in provider.search("dress", threshold=80).results)

    with pytest.raises((ValueError, ValidationError)):
        provider.search("dress", limit=0)
    with pytest.raises((ValueError, ValidationError)):
        provider.search("dress", limit=201)
