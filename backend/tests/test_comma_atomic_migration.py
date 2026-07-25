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


def test_dry_run_is_locked_complete_and_byte_stable(legacy_library: Path) -> None:
    migration = CommaAtomicPromptLibraryMigration(legacy_library)
    privilege = migration.issue_privilege()
    before = document_hashes(legacy_library)

    report = migration.audit(privilege, mode="dry-run")

    assert report.eligible is True
    assert report.inventory.model_dump() == {
        "source_entries": 297,
        "comma_entries": 146,
        "retained_entries": 151,
        "derived_atoms": 532,
        "final_entries": 683,
        "blank_atoms": 0,
        "combination_ids": [
            "character",
            "niji基礎瑟瑟",
            "portrait",
            "portrait-detail",
        ],
        "combination_atoms": {
            "character": 2,
            "niji基礎瑟瑟": 25,
            "portrait-detail": 5,
            "portrait": 4,
        },
    }
    assert len(report.details["atom_projections"]) == 532
    assert len(report.legacy_ref_expansions) == 146
    assert len(report.planned_mutations) == 17
    assert document_hashes(legacy_library) == before


def test_apply_keeps_marker_and_second_dry_run_is_zero_change(
    legacy_library: Path,
) -> None:
    migration = CommaAtomicPromptLibraryMigration(legacy_library)
    privilege = migration.issue_privilege()
    pre_manifest = (legacy_library / "manifest.json").read_bytes()
    report = migration.audit(privilege, mode="dry-run")

    result = migration.apply(
        privilege,
        plan_hash=report.plan_hash,
        run_id="test-run",
    )

    assert result.state == "validating"
    status = migration.control.status()
    assert status.marker_present is True
    assert status.comma_atomic_ready is False
    assert status.data_validated is True
    assert status.atomic_enforcement_active is False
    second = migration.audit(privilege, mode="dry-run")
    assert second.eligible is True
    assert second.planned_mutations == []
    assert second.inventory.source_entries == 683
    assert second.inventory.comma_entries == 0
    assert second.inventory.retained_entries == 151
    assert second.inventory.derived_atoms == 532
    assert (
        legacy_library / ".comma-atomic-rollbacks/test-run/rollback.json"
    ).exists()
    assert (legacy_library / "manifest.json").read_bytes() != pre_manifest

    for path in sorted(
        [
            *(legacy_library / "positive").glob("*.json"),
            *(legacy_library / "negative").glob("*.json"),
        ]
    ):
        category = json.loads(path.read_text(encoding="utf-8"))
        assert all(
            entry["prompt"].strip() and "," not in entry["prompt"]
            for entry in category["entries"]
        )


def test_finalize_refuses_until_atomic_enforcement_is_active(
    legacy_library: Path,
) -> None:
    migration = CommaAtomicPromptLibraryMigration(legacy_library)
    privilege = migration.issue_privilege()
    report = migration.audit(privilege)
    migration.apply(privilege, plan_hash=report.plan_hash, run_id="finalize-run")

    with pytest.raises(PromptLibraryError) as captured:
        migration.finalize(privilege, plan_hash=report.plan_hash)

    assert captured.value.code == "migration_finalize_blocked"
    assert migration.control.status().marker_present is True


def test_activate_finalize_and_rollback_guards(legacy_library: Path) -> None:
    migration = CommaAtomicPromptLibraryMigration(legacy_library)
    privilege = migration.issue_privilege()
    report = migration.audit(privilege)
    migration.apply(privilege, plan_hash=report.plan_hash, run_id="complete-run")
    migration.activate_atomic_enforcement(
        privilege,
        plan_hash=report.plan_hash,
    )
    assert migration.control.status().atomic_enforcement_active is True

    finalized = migration.finalize(privilege, plan_hash=report.plan_hash)

    assert finalized.state == "finalized"
    assert migration.control.status().comma_atomic_ready is True
    assert not migration.control.marker_path.exists()

    rolled_back = migration.rollback(privilege, run_id="complete-run")

    assert rolled_back.state == "rolled_back_required"
    assert migration.control.status().state == "rolled_back_required"
    assert migration.control.status().comma_atomic_ready is False


def test_immediate_rollback_restores_preimages_and_stays_closed(
    legacy_library: Path,
) -> None:
    migration = CommaAtomicPromptLibraryMigration(legacy_library)
    privilege = migration.issue_privilege()
    before = document_hashes(legacy_library)
    report = migration.audit(privilege)
    migration.apply(privilege, plan_hash=report.plan_hash, run_id="rollback-run")

    result = migration.rollback(privilege, run_id="rollback-run")

    assert result.state == "rolled_back_required"
    after = document_hashes(legacy_library)
    for relative, digest in before.items():
        if relative == ".comma-atomic-migration.json":
            continue
        assert after[relative] == digest
    status = migration.control.status()
    assert status.state == "rolled_back_required"
    assert status.comma_atomic_ready is False


def test_rollback_refuses_diverged_post_image(legacy_library: Path) -> None:
    migration = CommaAtomicPromptLibraryMigration(legacy_library)
    privilege = migration.issue_privilege()
    report = migration.audit(privilege)
    migration.apply(privilege, plan_hash=report.plan_hash, run_id="diverged-run")
    category_path = legacy_library / "positive" / "clothing.json"
    category_path.write_bytes(category_path.read_bytes() + b" ")

    with pytest.raises(PromptLibraryError) as captured:
        migration.rollback(privilege, run_id="diverged-run")

    assert captured.value.code == "migration_rollback_diverged"
    assert migration.control.status().marker_present is True


def test_post_finalize_divergence_refuses_rollback_and_restores_ready_state(
    legacy_library: Path,
) -> None:
    migration = CommaAtomicPromptLibraryMigration(legacy_library)
    privilege = migration.issue_privilege()
    report = migration.audit(privilege)
    migration.apply(privilege, plan_hash=report.plan_hash, run_id="final-diverged")
    migration.activate_atomic_enforcement(privilege, plan_hash=report.plan_hash)
    migration.finalize(privilege, plan_hash=report.plan_hash)
    category_path = legacy_library / "positive" / "clothing.json"
    category_path.write_bytes(category_path.read_bytes() + b" ")

    with pytest.raises(PromptLibraryError) as captured:
        migration.rollback(privilege, run_id="final-diverged")

    assert captured.value.code == "migration_rollback_diverged"
    status = migration.control.status()
    assert status.marker_present is False
    assert status.comma_atomic_ready is True


def test_apply_refuses_reviewed_plan_after_source_hash_drift(
    legacy_library: Path,
) -> None:
    migration = CommaAtomicPromptLibraryMigration(legacy_library)
    privilege = migration.issue_privilege()
    report = migration.audit(privilege)
    source = legacy_library / "positive" / "clothing.json"
    source.write_bytes(source.read_bytes() + b" ")

    with pytest.raises(PromptLibraryError) as captured:
        migration.apply(
            privilege,
            plan_hash=report.plan_hash,
            run_id="stale-plan",
        )

    assert captured.value.code == "migration_plan_hash_mismatch"
    assert not (legacy_library / ".comma-atomic-rollbacks/stale-plan").exists()
    assert migration.control.status().state == "required"


def test_interrupted_apply_resumes_same_locked_plan(
    legacy_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = CommaAtomicPromptLibraryMigration(legacy_library)
    privilege = migration.issue_privilege()
    report = migration.audit(privilege)
    original_replace = migration_module.os.replace
    interrupted = False
    staged_replacements = 0

    def fail_once(source, destination):
        nonlocal interrupted, staged_replacements
        if ".comma-atomic-stage/resume-run" in str(source):
            staged_replacements += 1
            if staged_replacements == 2 and not interrupted:
                interrupted = True
                raise OSError("simulated interrupted atomic replacement")
        return original_replace(source, destination)

    monkeypatch.setattr(
        "app.core.comma_atomic_migration.os.replace",
        fail_once,
    )
    with pytest.raises(OSError, match="simulated interrupted"):
        migration.apply(
            privilege,
            plan_hash=report.plan_hash,
            run_id="resume-run",
        )

    assert migration.control.status().state == "incomplete"
    result = migration.resume(
        privilege,
        run_id="resume-run",
        plan_hash=report.plan_hash,
    )

    assert result.state == "validating"
    assert migration.control.status().data_validated is True
    assert migration.audit(privilege).planned_mutations == []


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
