from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from app.core.prompt_library import FilePromptLibraryProvider


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_POSITIVE = {
    "quality-ratings": 33,
    "body-appearance": 54,
    "clothing": 63,
    "underwear": 53,
    "accessories": 8,
    "environment": 26,
    "camera-composition": 46,
    "poses": 72,
    "actions-interactions": 170,
    "expressions": 43,
    "physical-effects": 11,
}
EXPECTED_NEGATIVE = {
    "base-negative": 104,
}


@pytest.fixture
def finalized_seed_provider(tmp_path: Path) -> FilePromptLibraryProvider:
    root = tmp_path / "prompt_library"
    shutil.copytree(
        PROJECT_ROOT / "prompt_library",
        root,
        ignore=shutil.ignore_patterns(
            ".comma-atomic-migration.json",
            ".comma-atomic-rollbacks",
            ".comma-atomic-stage",
            ".prompt-library.lock",
        ),
    )
    return FilePromptLibraryProvider(root)


def test_seed_has_only_three_exact_atomized_legacy_combinations(
    finalized_seed_provider: FilePromptLibraryProvider,
) -> None:
    provider = finalized_seed_provider
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
    assert {key: len(value.positive) for key, value in legacy.items()} == {
        "character": 2,
        "portrait": 4,
        "portrait-detail": 5,
    }
    assert all(item.negative == [] for item in legacy.values())
