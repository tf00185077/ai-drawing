from __future__ import annotations

import re
from pathlib import Path

from app.core.prompt_library import FilePromptLibraryProvider


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_POSITIVE = {
    "quality-ratings": 20,
    "body-appearance": 36,
    "clothing": 25,
    "underwear": 39,
    "accessories": 7,
    "environment": 23,
    "camera-composition": 34,
    "poses": 27,
    "actions-interactions": 60,
    "expressions": 16,
    "physical-effects": 5,
}
EXPECTED_NEGATIVE = {
    "base-negative": 5,
}


def test_seed_catalog_is_complete_bilingual_and_clean() -> None:
    provider = FilePromptLibraryProvider(PROJECT_ROOT / "prompt_library")
    catalog = provider.catalog()
    assert catalog.diagnostics == []
    counts = {(item.polarity, item.id): item.entry_count for item in catalog.categories}
    assert {key: counts[("positive", key)] for key in EXPECTED_POSITIVE} == EXPECTED_POSITIVE
    assert {key: counts[("negative", key)] for key in EXPECTED_NEGATIVE} == EXPECTED_NEGATIVE
    assert sum(counts.values()) == 297

    ids: set[tuple[str, str, str]] = set()
    for summary in catalog.categories:
        loaded = provider.get_category(summary.polarity, summary.id).category
        assert loaded.revision >= 1
        assert loaded.name_zh.strip() and loaded.description_zh.strip()
        for item in loaded.entries:
            key = (loaded.polarity, loaded.id, item.id)
            assert key not in ids
            ids.add(key)
            assert item.name_zh.strip() and item.description_zh.strip()
            assert item.prompt.strip()
            assert re.search(r"[\u3400-\u9fff]", item.prompt) is None
            assert item.aliases and item.keywords
            assert item.revision == 1 and item.archived is False


def test_seed_has_only_three_exact_legacy_combinations() -> None:
    provider = FilePromptLibraryProvider(PROJECT_ROOT / "prompt_library")
    legacy = {
        item.id: provider.get_combination(item.id).combination
        for item in provider.catalog().combinations
        if item.legacy_template
    }
    assert {key: value.positive_prompt_snapshot for key, value in legacy.items()} == {
        "portrait": "1girl, {人物}, {風格}, solo",
        "portrait-detail": "1girl, {人物}, {風格}, solo, {細節}",
        "character": "{trigger} {人物}, {風格}",
    }
    assert all(len(item.positive) == 1 and item.negative == [] for item in legacy.values())
