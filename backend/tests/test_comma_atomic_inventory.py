from __future__ import annotations

import base64
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIBRARY_ROOT = PROJECT_ROOT / "prompt_library"


def _categories() -> list[dict[str, object]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for polarity in ("positive", "negative")
        for path in sorted((LIBRARY_ROOT / polarity).glob("*.json"))
    ]


def _legacy_preimages() -> dict[str, dict[str, object]]:
    rollback = json.loads(
        (
            LIBRARY_ROOT
            / ".comma-atomic-rollbacks"
            / "comma-atomic-v1"
            / "rollback.json"
        ).read_text(encoding="utf-8")
    )
    return {
        relative: json.loads(base64.b64decode(record["base64"]))
        for relative, record in rollback["preimages"].items()
    }


def test_legacy_fixture_covers_reviewed_compatibility_cases() -> None:
    fixture = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "comma_atomic_legacy_cases.json"
        ).read_text(encoding="utf-8")
    )

    assert fixture["comma_reference"]["weight"] == 1.2
    assert fixture["parenthesized"] == "(a,b:1.2)"
    assert fixture["quoted"] == '"a,b"'
    assert fixture["blank_subsegments"] == ["a,,b", ",a", "a,"]
    assert fixture["resolution_paths"] == [
        "ordinary_edit",
        "replacement_refs",
        "acknowledge_convert_to_literals",
    ]
