from __future__ import annotations

import re
from pathlib import Path

from app.core.prompt_library import FilePromptLibraryProvider


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_POSITIVE = {
    "subjects": 15,
    "appearance": 18,
    "expressions": 15,
    "clothing": 22,
    "accessories": 34,
    "actions": 18,
    "poses": 32,
    "camera-angles": 32,
    "composition": 15,
    "lighting": 18,
    "styles": 18,
    "environment": 24,
    "quality-details": 16,
    "colors-textures": 18,
}
EXPECTED_NEGATIVE = {
    "quality": 14,
    "anatomy": 14,
    "face-hands": 16,
    "composition": 14,
    "clothing-colors": 10,
    "artifacts": 10,
    "text-watermark": 10,
    "duplicates": 10,
}


def test_seed_catalog_is_complete_bilingual_and_clean() -> None:
    provider = FilePromptLibraryProvider(PROJECT_ROOT / "prompt_library")
    catalog = provider.catalog()
    assert catalog.diagnostics == []
    counts = {(item.polarity, item.id): item.entry_count for item in catalog.categories}
    assert {key: counts[("positive", key)] for key in EXPECTED_POSITIVE} == EXPECTED_POSITIVE
    assert {key: counts[("negative", key)] for key in EXPECTED_NEGATIVE} == EXPECTED_NEGATIVE
    assert sum(counts.values()) == 393

    ids: set[tuple[str, str, str]] = set()
    prompts: set[tuple[str, str]] = set()
    for summary in catalog.categories:
        loaded = provider.get_category(summary.polarity, summary.id).category
        assert loaded.revision == 1
        assert loaded.name_zh.strip() and loaded.description_zh.strip()
        for item in loaded.entries:
            key = (loaded.polarity, loaded.id, item.id)
            assert key not in ids
            ids.add(key)
            prompt_key = (loaded.polarity, item.prompt.casefold().strip())
            assert prompt_key not in prompts
            prompts.add(prompt_key)
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
