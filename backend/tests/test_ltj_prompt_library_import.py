from pathlib import Path

import pytest

from scripts.import_ltj_prompt_library import (
    build_categories,
    clear_existing_categories,
    require_healthy_backend,
    validate_categories,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LTJ_SOURCE = PROJECT_ROOT.parent / "LTJ" / "scenario_gui.py"


def test_build_categories_extracts_bilingual_static_ltj_entries() -> None:
    categories = build_categories(LTJ_SOURCE)

    validate_categories(categories)

    assert {item["id"] for item in categories} >= {
        "body-appearance",
        "clothing",
        "environment",
        "camera-composition",
        "expressions",
    }
    assert all(
        entry["name_zh"]
        and entry["description_zh"]
        and entry["prompt"]
        for item in categories
        for entry in item["entries"]
    )


def test_build_categories_keeps_each_ltj_prompt_fragment_exact() -> None:
    categories = build_categories(LTJ_SOURCE)
    body = next(item for item in categories if item["id"] == "body-appearance")

    assert any(entry["prompt"] == "gigantic breasts" for entry in body["entries"])


def test_clear_existing_categories_leaves_manifest_and_other_files(tmp_path: Path) -> None:
    root = tmp_path / "prompt_library"
    (root / "positive").mkdir(parents=True)
    (root / "negative").mkdir()
    (root / "manifest.json").write_text("{}", encoding="utf-8")
    (root / "positive" / "test.json").write_text("{}", encoding="utf-8")
    (root / "negative" / "test.json").write_text("{}", encoding="utf-8")

    removed = clear_existing_categories(root)

    assert sorted(path.name for path in removed) == ["test.json", "test.json"]
    assert (root / "manifest.json").exists()
    assert not list((root / "positive").glob("*.json"))
    assert not list((root / "negative").glob("*.json"))


def test_require_healthy_backend_rejects_unreachable_backend() -> None:
    with pytest.raises(RuntimeError, match="backend"):
        require_healthy_backend("http://127.0.0.1:1")
