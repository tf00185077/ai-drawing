from __future__ import annotations

import json
import base64
import shutil
from pathlib import Path

import pytest

import app.core.comma_atomic_migration as migration_module
from app.core.comma_atomic_migration import (
    CURATION_RELATIVE,
    REGISTRY_RELATIVE,
    CommaAtomicPromptLibraryMigration,
    curation_key,
    sha256_bytes,
    sha256_text,
)
from app.core.prompt_library_errors import PromptLibraryError


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def legacy_library(tmp_path: Path) -> Path:
    destination = tmp_path / "prompt_library"
    shutil.copytree(
        PROJECT_ROOT / "prompt_library",
        destination,
        ignore=shutil.ignore_patterns(
            ".comma-atomic-rollbacks",
            ".comma-atomic-stage",
            ".prompt-library.lock",
        ),
    )
    rollback = json.loads(
        (
            PROJECT_ROOT
            / "prompt_library"
            / ".comma-atomic-rollbacks"
            / "comma-atomic-v1"
            / "rollback.json"
        ).read_text(encoding="utf-8")
    )
    for relative, record in rollback["preimages"].items():
        path = destination / relative
        raw = base64.b64decode(record["base64"])
        assert sha256_bytes(raw) == record["sha256"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (destination / ".comma-atomic-migration.json").unlink(missing_ok=True)
    control = CommaAtomicPromptLibraryMigration(destination).control
    status = control.bootstrap()
    assert status.state == "required"
    assert status.comma_atomic_ready is False
    return destination


def document_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_checked_rollback_manifest_uses_exact_predecessor_manifest_bytes() -> None:
    rollback = json.loads(
        (
            PROJECT_ROOT
            / "prompt_library"
            / ".comma-atomic-rollbacks"
            / "comma-atomic-v1"
            / "rollback.json"
        ).read_text(encoding="utf-8")
    )
    predecessor = (
        base64.b64decode(
            (
                PROJECT_ROOT
                / "backend/tests/fixtures/comma_atomic_predecessor_manifest.base64"
            ).read_text(encoding="ascii")
        )
    )
    record = rollback["preimages"]["manifest.json"]

    assert base64.b64decode(record["base64"]) == predecessor
    assert record["sha256"] == sha256_bytes(predecessor)


def test_reviewed_curation_has_exact_new_atom_scope_and_registry() -> None:
    root = PROJECT_ROOT / "prompt_library"
    curation = json.loads((root / CURATION_RELATIVE).read_text(encoding="utf-8"))
    registry = json.loads((root / REGISTRY_RELATIVE).read_text(encoding="utf-8"))
    records = curation["records"]

    assert curation["review_status"] == "reviewed"
    assert curation["record_count"] == len(records) == 532
    assert registry["review_status"] == "reviewed"
    assert registry["expansion_count"] == len(registry["expansions"]) == 146
    assert len(
        {
            curation_key(
                record["polarity"],
                record["category_id"],
                record["source_entry_id"],
                record["source_prompt_sha256"],
                record["segment_index"],
            )
            for record in records
        }
    ) == 532
    assert all(record["reviewed"] is True for record in records)
    assert all(record["raw_segment"].strip() for record in records)

    retained = {
        (category["polarity"], category["id"], entry["id"])
        for polarity in ("positive", "negative")
        for path in sorted((root / polarity).glob("*.json"))
        for category in [json.loads(path.read_text(encoding="utf-8"))]
        for entry in category["entries"]
        if "," not in entry["prompt"]
    }
    curated_sources = {
        (
            record["polarity"],
            record["category_id"],
            record["source_entry_id"],
        )
        for record in records
    }
    assert retained.isdisjoint(curated_sources)


def test_clothing_and_quality_tokens_have_distinct_curated_names() -> None:
    records = json.loads(
        (
            PROJECT_ROOT / "prompt_library" / CURATION_RELATIVE
        ).read_text(encoding="utf-8")
    )["records"]
    by_token = {
        record["raw_segment"].strip(): record["name_zh"]
        for record in records
    }

    assert by_token["shirt"] == "襯衫"
    assert by_token["white shirt"] == "白襯衫"
    assert by_token["white buttoned shirt"] == "白色鈕扣襯衫"
    assert by_token["collared shirt"] == "有領襯衫"
    assert len(
        {
            by_token["shirt"],
            by_token["white shirt"],
            by_token["white buttoned shirt"],
            by_token["collared shirt"],
        }
    ) == 4
    assert by_token["masterpiece"] == "傑作"
    assert by_token["best quality"] == "最佳品質"
    assert by_token["amazing quality"] == "驚艷品質"


def test_id_derivation_is_stable_for_known_quality_atom() -> None:
    records = json.loads(
        (
            PROJECT_ROOT / "prompt_library" / CURATION_RELATIVE
        ).read_text(encoding="utf-8")
    )["records"]
    record = next(
        item
        for item in records
        if item["source_entry_id"] == "illustrious-quality"
        and item["raw_segment"] == "masterpiece"
    )

    assert record["source_prompt_sha256"] == sha256_text(
        "masterpiece, best quality, amazing quality, absurdres"
    )
    assert record["derived_entry_id"].startswith(
        "illustrious-quality-masterpiece-"
    )
