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


def test_reviewed_repository_inventory_is_exact() -> None:
    entries = [
        entry
        for category in _categories()
        for entry in category["entries"]  # type: ignore[index]
    ]
    derived = [
        entry
        for entry in entries
        if entry.get("comma_atomic_provenance") is not None
    ]
    retained = [
        entry
        for entry in entries
        if entry.get("comma_atomic_provenance") is None
    ]
    reviewed = json.loads(
        (
            LIBRARY_ROOT
            / "migrations"
            / "comma-atomic-v1"
            / "reviewed-pre-apply-dry-run.json"
        ).read_text(encoding="utf-8")
    )

    assert reviewed["inventory"]["source_entries"] == 297
    assert reviewed["inventory"]["comma_entries"] == 146
    assert reviewed["inventory"]["retained_entries"] == 151
    assert reviewed["inventory"]["derived_atoms"] == 532
    assert len(entries) == 683
    assert len(retained) == 151
    assert len(derived) == 532
    assert all(entry["prompt"].strip() and "," not in entry["prompt"] for entry in entries)


def test_reviewed_combination_projection_is_exact() -> None:
    expected = {
        "character": 2,
        "niji基礎瑟瑟": 25,
        "portrait-detail": 5,
        "portrait": 4,
    }
    actual: dict[str, int] = {}
    for path in sorted((LIBRARY_ROOT / "combinations").glob("*.json")):
        combination = json.loads(path.read_text(encoding="utf-8"))
        fragments = [*combination["positive"], *combination["negative"]]
        atoms = [
            atom
            for fragment in fragments
            for atom in fragment["snapshot"].split(",")
        ]
        assert all(atom.strip() for atom in atoms)
        actual[combination["id"]] = len(atoms)

    assert actual == expected
    assert sum(actual.values()) == 36


def test_retained_entries_are_byte_equivalent_metadata_records() -> None:
    legacy = _legacy_preimages()
    legacy_retained = {
        (category["polarity"], category["id"], entry["id"]): entry
        for relative, category in legacy.items()
        if relative.startswith(("positive/", "negative/"))
        for entry in category["entries"]
        if "," not in entry["prompt"]
    }
    migrated_retained = {
        (category["polarity"], category["id"], entry["id"]): entry
        for category in _categories()
        for entry in category["entries"]  # type: ignore[index]
        if entry.get("comma_atomic_provenance") is None
    }

    assert len(legacy_retained) == len(migrated_retained) == 151
    assert migrated_retained == legacy_retained


def test_derived_entries_match_reviewed_curation_and_source_invariants() -> None:
    legacy = _legacy_preimages()
    sources = {
        (category["polarity"], category["id"], entry["id"]): entry
        for relative, category in legacy.items()
        if relative.startswith(("positive/", "negative/"))
        for entry in category["entries"]
        if "," in entry["prompt"]
    }
    current = {
        (category["polarity"], category["id"], entry["id"]): entry
        for category in _categories()
        for entry in category["entries"]  # type: ignore[index]
        if entry.get("comma_atomic_provenance") is not None
    }
    records = json.loads(
        (
            LIBRARY_ROOT
            / "migrations"
            / "comma-atomic-v1"
            / "curation.json"
        ).read_text(encoding="utf-8")
    )["records"]

    assert len(records) == len(current) == 532
    for record in records:
        key = (
            record["polarity"],
            record["category_id"],
            record["derived_entry_id"],
        )
        entry = current[key]
        source = sources[
            (
                record["polarity"],
                record["category_id"],
                record["source_entry_id"],
            )
        ]
        assert entry["prompt"] == record["raw_segment"]
        assert entry["name_zh"] == record["name_zh"]
        assert entry["description_zh"] == record["description_zh"]
        assert entry["order"] == source["order"]
        assert entry["revision"] == 1
        assert entry["archived"] == source["archived"]
        assert set(record["aliases"]) <= set(entry["aliases"])
        assert set(source["aliases"]) <= set(entry["aliases"])
        assert set(record["keywords"]) <= set(entry["keywords"])
        assert set(source["keywords"]) <= set(entry["keywords"])
        provenance = entry["comma_atomic_provenance"]
        assert provenance["source_entry_id"] == record["source_entry_id"]
        assert provenance["source_prompt_sha256"] == record["source_prompt_sha256"]
        assert provenance["segment_index"] == record["segment_index"]


def test_migrated_combinations_preserve_metadata_and_exact_rendered_text() -> None:
    legacy = _legacy_preimages()
    expected_counts = {
        "character": 2,
        "niji基礎瑟瑟": 25,
        "portrait-detail": 5,
        "portrait": 4,
    }
    for relative, before in legacy.items():
        if not relative.startswith("combinations/"):
            continue
        after = json.loads(
            (LIBRARY_ROOT / relative).read_text(encoding="utf-8")
        )
        for field in (
            "id",
            "name_zh",
            "description_zh",
            "aliases",
            "keywords",
            "order",
            "archived",
            "legacy_template",
            "positive_prompt_snapshot",
            "negative_prompt_snapshot",
        ):
            assert after[field] == before[field]
        assert after["revision"] == before["revision"] + 1
        assert len(after["positive"]) + len(after["negative"]) == expected_counts[
            after["id"]
        ]
        for polarity in ("positive", "negative"):
            rendered = ",".join(
                fragment["snapshot"]
                if fragment["weight"] == 1
                else f"({fragment['snapshot']}:{fragment['weight']})"
                for fragment in after[polarity]
            )
            assert rendered == after[f"{polarity}_prompt_snapshot"]


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
