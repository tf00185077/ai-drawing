"""Deterministic, privileged migration of the repository Prompt Library."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.prompt_atomic import atomize_nonblank, render_prompt_lane
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_migration_control import (
    CommaAtomicMigrationControl,
    MigrationPrivilege,
)
from app.core.prompt_library_models import (
    PromptCategory,
    PromptCombination,
    PromptLibraryManifest,
)
from app.schemas.prompt_library_migration import (
    CommaAtomicMarker,
    CuratedAtomRecord,
    LegacyRefExpansion,
    LegacyRefLocator,
    MigrationDiagnostic,
    MigrationInventory,
    MigrationMutationResult,
    MigrationReport,
)


EXPECTED_SOURCE_ENTRIES = 297
EXPECTED_COMMA_ENTRIES = 146
EXPECTED_RETAINED_ENTRIES = 151
EXPECTED_DERIVED_ATOMS = 532
EXPECTED_FINAL_ENTRIES = 683
EXPECTED_COMBINATIONS = {
    "character": 2,
    "niji基礎瑟瑟": 25,
    "portrait-detail": 5,
    "portrait": 4,
}
CURATION_RELATIVE = Path("migrations/comma-atomic-v1/curation.json")
REGISTRY_RELATIVE = Path("migrations/comma-atomic-v1/legacy-ref-registry.json")
REPORT_RELATIVE = Path("migrations/comma-atomic-v1/final-dry-run.json")
ROLLBACK_DIR = ".comma-atomic-rollbacks"
STAGE_DIR = ".comma-atomic-stage"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def normalized_metadata_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def stable_deduplicate(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = normalized_metadata_key(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def token_slug(raw_segment: str) -> str:
    normalized = unicodedata.normalize("NFKD", raw_segment.strip()).encode(
        "ascii", "ignore"
    ).decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
    return (slug or "atom")[:32].strip("-") or "atom"


def source_slug(source_entry_id: str) -> str:
    return source_entry_id[:48].rstrip("-")


def provenance_identity(
    *,
    polarity: str,
    category_id: str,
    source_entry_id: str,
    source_prompt_sha256: str,
    segment_index: int,
    raw_segment: str,
) -> str:
    material = "\n".join(
        (
            polarity,
            category_id,
            source_entry_id,
            source_prompt_sha256,
            str(segment_index),
            raw_segment,
        )
    )
    return sha256_text(material)


def allocate_derived_id(
    *,
    source_entry_id: str,
    raw_segment: str,
    identity_sha256: str,
    occupied: dict[str, str | None],
) -> str:
    base = f"{source_slug(source_entry_id)}-{token_slug(raw_segment)}"
    for length in (8, 12, 16, 64):
        candidate = f"{base}-{identity_sha256[:length]}"
        existing = occupied.get(candidate)
        if existing is None and candidate not in occupied:
            occupied[candidate] = identity_sha256
            return candidate
        if existing == identity_sha256:
            return candidate
    raise ValueError(
        f"unresolvable derived id collision for {source_entry_id!r} "
        f"identity={identity_sha256}"
    )


def curation_key(
    polarity: str,
    category_id: str,
    source_entry_id: str,
    source_prompt_hash: str,
    segment_index: int,
) -> str:
    return "/".join(
        (
            polarity,
            category_id,
            source_entry_id,
            source_prompt_hash,
            str(segment_index),
        )
    )


@dataclass
class MigrationPlan:
    report: MigrationReport
    targets: dict[str, bytes]
    registry: list[LegacyRefExpansion]


class CommaAtomicPromptLibraryMigration:
    def __init__(self, root: Path, *, lock_timeout: float = 5.0) -> None:
        self.root = root.resolve()
        self.control = CommaAtomicMigrationControl(
            self.root, lock_timeout=lock_timeout
        )

    def issue_privilege(self) -> MigrationPrivilege:
        return self.control.issue_privilege()

    def audit(
        self, privilege: MigrationPrivilege, *, mode: str = "dry-run"
    ) -> MigrationReport:
        if mode not in {"audit", "dry-run", "validate"}:
            raise ValueError(f"unsupported migration report mode: {mode}")
        with self.control.locked(privilege):
            return self._build_plan(mode=mode).report

    def build_plan(self, privilege: MigrationPrivilege) -> MigrationPlan:
        with self.control.locked(privilege):
            return self._build_plan(mode="dry-run")

    def apply(
        self,
        privilege: MigrationPrivilege,
        *,
        plan_hash: str,
        run_id: str | None = None,
    ) -> MigrationMutationResult:
        with self.control.locked(privilege) as marker:
            if marker is None:
                raise self._migration_error(
                    "migration_marker_required",
                    "The migration marker is required before apply.",
                )
            plan = self._build_plan(mode="dry-run")
            if not plan.report.eligible:
                raise self._migration_error(
                    "migration_plan_ineligible",
                    "Dry-run contains blocking diagnostics.",
                    diagnostics=[
                        diagnostic.model_dump(mode="json")
                        for diagnostic in plan.report.diagnostics
                    ],
                )
            if plan.report.plan_hash != plan_hash:
                raise self._migration_error(
                    "migration_plan_hash_mismatch",
                    "The reviewed dry-run plan hash no longer matches.",
                    expected=plan_hash,
                    actual=plan.report.plan_hash,
                )
            if not plan.targets:
                return MigrationMutationResult(
                    action="apply",
                    run_id=run_id or marker.run_id or "no-op",
                    state=marker.state,
                )

            selected_run_id = run_id or uuid.uuid4().hex
            backup_root = self.root / ROLLBACK_DIR / selected_run_id
            stage_root = self.root / STAGE_DIR / selected_run_id
            if backup_root.exists() or stage_root.exists():
                raise self._migration_error(
                    "migration_run_exists",
                    "The migration run id already has staged or rollback data.",
                    run_id=selected_run_id,
                )
            preimages = self._capture_preimages(plan.targets)
            backup_root.mkdir(parents=True)
            stage_root.mkdir(parents=True)
            rollback_manifest = {
                "schema_version": 1,
                "run_id": selected_run_id,
                "plan_hash": plan_hash,
                "preimages": {
                    path: {
                        "sha256": sha256_bytes(raw),
                        "base64": base64.b64encode(raw).decode("ascii"),
                    }
                    for path, raw in preimages.items()
                },
                "post_hashes": {
                    path: sha256_bytes(raw) for path, raw in plan.targets.items()
                },
            }
            self._write_new(
                backup_root / "rollback.json",
                canonical_json_bytes(rollback_manifest),
            )
            for relative, raw in plan.targets.items():
                target = stage_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                self._write_new(target, raw)
                self._validate_target(relative, raw)

            applying = marker.model_copy(
                update={
                    "state": "applying",
                    "run_id": selected_run_id,
                    "plan_hash": plan_hash,
                    "data_validated": False,
                    "atomic_enforcement_active": False,
                }
            )
            self.control.write_marker(applying, privilege=privilege)
            changed: list[str] = []
            try:
                for relative in sorted(plan.targets):
                    source = stage_root / relative
                    destination = self.root / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, destination)
                    changed.append(relative)
                shutil.rmtree(stage_root)
                validating = applying.model_copy(
                    update={"state": "validating", "data_validated": True}
                )
                self.control.write_marker(validating, privilege=privilege)
                validation = self._build_plan(mode="validate")
                if validation.report.diagnostics or validation.report.planned_mutations:
                    raise self._migration_error(
                        "migration_post_write_validation_failed",
                        "Post-write validation did not produce a zero-mutation plan.",
                        diagnostics=[
                            item.model_dump(mode="json")
                            for item in validation.report.diagnostics
                        ],
                        planned_mutations=validation.report.planned_mutations,
                    )
            except Exception:
                incomplete = applying.model_copy(update={"state": "incomplete"})
                self.control.write_marker(incomplete, privilege=privilege)
                raise
            post_hashes = {
                path: sha256_bytes((self.root / path).read_bytes())
                for path in sorted(plan.targets)
            }
            return MigrationMutationResult(
                action="apply",
                run_id=selected_run_id,
                state="validating",
                changed_paths=changed,
                pre_hashes={path: sha256_bytes(raw) for path, raw in preimages.items()},
                post_hashes=post_hashes,
            )

    def resume(
        self, privilege: MigrationPrivilege, *, run_id: str, plan_hash: str
    ) -> MigrationMutationResult:
        with self.control.locked(privilege) as marker:
            if (
                marker is None
                or marker.state not in {"applying", "incomplete"}
                or marker.run_id != run_id
                or marker.plan_hash != plan_hash
            ):
                raise self._migration_error(
                    "migration_resume_context_mismatch",
                    "Resume requires the same interrupted run and reviewed plan hash.",
                )
            stage_root = self.root / STAGE_DIR / run_id
            rollback = self._read_rollback(run_id)
            changed: list[str] = []
            for relative, expected in sorted(rollback["post_hashes"].items()):
                destination = self.root / relative
                if destination.exists() and sha256_bytes(destination.read_bytes()) == expected:
                    continue
                source = stage_root / relative
                if not source.exists() or sha256_bytes(source.read_bytes()) != expected:
                    raise self._migration_error(
                        "migration_stage_diverged",
                        "Staged bytes required for resume are missing or changed.",
                        path=relative,
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, destination)
                changed.append(relative)
            shutil.rmtree(stage_root, ignore_errors=True)
            validating = marker.model_copy(
                update={"state": "validating", "data_validated": True}
            )
            self.control.write_marker(validating, privilege=privilege)
            validation = self._build_plan(mode="validate")
            if validation.report.diagnostics or validation.report.planned_mutations:
                self.control.write_marker(
                    validating.model_copy(update={"state": "incomplete"}),
                    privilege=privilege,
                )
                raise self._migration_error(
                    "migration_post_write_validation_failed",
                    "Resumed migration did not reach a valid zero-mutation state.",
                )
            return MigrationMutationResult(
                action="resume",
                run_id=run_id,
                state="validating",
                changed_paths=changed,
            )

    def rollback(
        self, privilege: MigrationPrivilege, *, run_id: str
    ) -> MigrationMutationResult:
        with self.control.locked(privilege) as marker:
            rollback = self._read_rollback(run_id)
            reopened_finalized = False
            if marker is None:
                if not self.control.status().comma_atomic_ready:
                    raise self._migration_error(
                        "migration_marker_required",
                        "Rollback requires a migration marker or finalized atomic data.",
                    )
                marker = CommaAtomicMarker(
                    state="applying",
                    run_id=run_id,
                    plan_hash=rollback["plan_hash"],
                    data_validated=True,
                    atomic_enforcement_active=True,
                )
                self.control.write_marker(marker, privilege=privilege)
                reopened_finalized = True
            restore_root = self.root / STAGE_DIR / f"rollback-{run_id}"
            changed: list[str] = []
            try:
                for relative, expected_hash in rollback["post_hashes"].items():
                    path = self.root / relative
                    actual_hash = (
                        sha256_bytes(path.read_bytes()) if path.exists() else None
                    )
                    if actual_hash != expected_hash:
                        raise self._migration_error(
                            "migration_rollback_diverged",
                            "Rollback refuses to overwrite a changed post-image.",
                            path=relative,
                            expected=expected_hash,
                            actual=actual_hash,
                        )
                restore_root.mkdir(parents=True, exist_ok=False)
                for relative, record in rollback["preimages"].items():
                    raw = base64.b64decode(record["base64"])
                    if sha256_bytes(raw) != record["sha256"]:
                        raise self._migration_error(
                            "migration_rollback_backup_invalid",
                            "Rollback pre-image checksum is invalid.",
                            path=relative,
                        )
                    staged = restore_root / relative
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    self._write_new(staged, raw)
                    self._validate_target(relative, raw, allow_legacy=True)
                for relative in sorted(rollback["preimages"]):
                    destination = self.root / relative
                    os.replace(restore_root / relative, destination)
                    changed.append(relative)
            except Exception:
                shutil.rmtree(restore_root, ignore_errors=True)
                if reopened_finalized and not changed:
                    self.control.marker_path.unlink(missing_ok=True)
                elif changed:
                    self.control.write_marker(
                        marker.model_copy(
                            update={
                                "state": "incomplete",
                                "data_validated": False,
                            }
                        ),
                        privilege=privilege,
                    )
                raise
            shutil.rmtree(restore_root, ignore_errors=True)
            rolled_back = CommaAtomicMarker(
                state="rolled_back_required",
                run_id=run_id,
                plan_hash=rollback["plan_hash"],
                data_validated=False,
                atomic_enforcement_active=False,
            )
            self.control.write_marker(rolled_back, privilege=privilege)
            return MigrationMutationResult(
                action="rollback",
                run_id=run_id,
                state="rolled_back_required",
                changed_paths=changed,
            )

    def activate_atomic_enforcement(
        self, privilege: MigrationPrivilege, *, plan_hash: str
    ) -> None:
        with self.control.locked(privilege) as marker:
            if (
                marker is None
                or marker.state != "validating"
                or not marker.data_validated
                or marker.plan_hash != plan_hash
            ):
                raise self._migration_error(
                    "atomic_enforcement_activation_blocked",
                    "Atomic enforcement requires the validated reviewed migration plan.",
                )
            validation = self._build_plan(mode="validate")
            if validation.report.diagnostics or validation.report.planned_mutations:
                raise self._migration_error(
                    "atomic_enforcement_activation_blocked",
                    "Atomic enforcement requires clean post-write validation.",
                )
            self.control.write_marker(
                marker.model_copy(update={"atomic_enforcement_active": True}),
                privilege=privilege,
            )

    def finalize(
        self, privilege: MigrationPrivilege, *, plan_hash: str
    ) -> MigrationMutationResult:
        with self.control.locked(privilege) as marker:
            if (
                marker is None
                or marker.state != "validating"
                or not marker.data_validated
                or not marker.atomic_enforcement_active
                or marker.plan_hash != plan_hash
            ):
                raise self._migration_error(
                    "migration_finalize_blocked",
                    "Finalize requires validated data and active atomic Backend enforcement.",
                )
            validation = self._build_plan(mode="validate")
            if validation.report.diagnostics or validation.report.planned_mutations:
                raise self._migration_error(
                    "migration_finalize_blocked",
                    "Finalize revalidation found migration drift.",
                )
            self.control.marker_path.unlink()
            return MigrationMutationResult(
                action="finalize",
                run_id=marker.run_id or "unknown",
                state="finalized",
            )

    def _build_plan(self, *, mode: str) -> MigrationPlan:
        source_hashes: dict[str, str] = {}
        categories = self._read_documents(
            ("positive", "negative"), source_hashes=source_hashes
        )
        combinations = self._read_documents(
            ("combinations",), source_hashes=source_hashes
        )
        manifest_path = self.root / "manifest.json"
        manifest_raw = manifest_path.read_bytes()
        source_hashes["manifest.json"] = sha256_bytes(manifest_raw)
        manifest = json.loads(manifest_raw)
        curation, curation_diagnostics = self._load_curation()

        source_entries = sum(len(document["entries"]) for _, document in categories)
        comma_entries = sum(
            1
            for _, document in categories
            for entry in document["entries"]
            if "," in entry["prompt"]
        )
        retained_entries = source_entries - comma_entries
        migrated = comma_entries == 0 and manifest.get("comma_atomic_version") == 1
        diagnostics = list(curation_diagnostics)
        targets: dict[str, bytes] = {}
        registry: list[LegacyRefExpansion] = []
        atom_details: list[dict[str, object]] = []
        retained_locators: list[str] = []
        derived_count = 0
        blank_count = 0

        if migrated:
            derived_count = sum(
                1
                for _, document in categories
                for entry in document["entries"]
                if entry.get("comma_atomic_provenance") is not None
            )
            retained_entries = source_entries - derived_count
            for relative, document in categories:
                for entry in document["entries"]:
                    prompt = entry["prompt"]
                    if not str(prompt).strip() or "," in prompt:
                        diagnostics.append(
                            MigrationDiagnostic(
                                code="post_migration_entry_not_atomic",
                                message="Migrated entry is blank or comma-bearing.",
                                locator=f"{document['polarity']}/{document['id']}/{entry['id']}",
                            )
                        )
            registry, registry_diagnostics = self._load_registry()
            diagnostics.extend(registry_diagnostics)
            combination_atoms = {
                document["id"]: len(document["positive"]) + len(document["negative"])
                for _, document in combinations
            }
            final_entries = source_entries
        else:
            occupied_by_category: dict[str, dict[str, str | None]] = {}
            expanded_by_source: dict[str, list[LegacyRefLocator]] = {}
            for relative, document in categories:
                category_key = f"{document['polarity']}/{document['id']}"
                occupied = occupied_by_category.setdefault(
                    category_key,
                    {
                        entry["id"]: (
                            entry.get("comma_atomic_provenance") or {}
                        ).get("identity_sha256")
                        for entry in document["entries"]
                        if "," not in entry["prompt"]
                    },
                )
                new_entries: list[dict[str, object]] = []
                category_changed = False
                for entry in document["entries"]:
                    prompt = entry["prompt"]
                    locator = f"{category_key}/{entry['id']}"
                    if "," not in prompt:
                        if not prompt.strip():
                            diagnostics.append(
                                MigrationDiagnostic(
                                    code="retained_entry_blank",
                                    message="Retained atomic entry is blank.",
                                    locator=locator,
                                )
                            )
                        retained_locators.append(locator)
                        new_entries.append(entry)
                        continue
                    category_changed = True
                    source_prompt_hash = sha256_text(prompt)
                    atoms = prompt.split(",")
                    blank_count += sum(not atom.strip() for atom in atoms)
                    derived_locators: list[LegacyRefLocator] = []
                    for segment_index, raw_segment in enumerate(atoms):
                        key = curation_key(
                            document["polarity"],
                            document["id"],
                            entry["id"],
                            source_prompt_hash,
                            segment_index,
                        )
                        record = curation.get(key)
                        if record is None:
                            diagnostics.append(
                                MigrationDiagnostic(
                                    code="curation_missing",
                                    message="Derived atom is missing reviewed curation.",
                                    locator=key,
                                    details={"raw_segment": raw_segment},
                                )
                            )
                            continue
                        if record.raw_segment != raw_segment:
                            diagnostics.append(
                                MigrationDiagnostic(
                                    code="curation_raw_mismatch",
                                    message="Curated raw segment does not match source bytes.",
                                    locator=key,
                                )
                            )
                            continue
                        identity = provenance_identity(
                            polarity=document["polarity"],
                            category_id=document["id"],
                            source_entry_id=entry["id"],
                            source_prompt_sha256=source_prompt_hash,
                            segment_index=segment_index,
                            raw_segment=raw_segment,
                        )
                        try:
                            derived_id = allocate_derived_id(
                                source_entry_id=entry["id"],
                                raw_segment=raw_segment,
                                identity_sha256=identity,
                                occupied=occupied,
                            )
                        except ValueError as exc:
                            diagnostics.append(
                                MigrationDiagnostic(
                                    code="derived_id_collision",
                                    message=str(exc),
                                    locator=key,
                                )
                            )
                            continue
                        if record.derived_entry_id != derived_id:
                            diagnostics.append(
                                MigrationDiagnostic(
                                    code="curation_id_mismatch",
                                    message="Curated derived ID is stale.",
                                    locator=key,
                                    details={
                                        "expected": derived_id,
                                        "actual": record.derived_entry_id,
                                    },
                                )
                            )
                            continue
                        derived = {
                            "id": derived_id,
                            "name_zh": record.name_zh,
                            "description_zh": record.description_zh,
                            "prompt": raw_segment,
                            "aliases": stable_deduplicate(
                                [*entry.get("aliases", []), *record.aliases]
                            ),
                            "keywords": stable_deduplicate(
                                [*entry.get("keywords", []), *record.keywords]
                            ),
                            "order": entry.get("order", 10),
                            "revision": 1,
                            "archived": entry.get("archived", False),
                            "comma_atomic_provenance": {
                                "source_polarity": document["polarity"],
                                "source_category_id": document["id"],
                                "source_entry_id": entry["id"],
                                "source_prompt_sha256": source_prompt_hash,
                                "segment_index": segment_index,
                                "raw_segment_sha256": sha256_text(raw_segment),
                                "identity_sha256": identity,
                            },
                        }
                        PromptCategory.model_validate(
                            {
                                **document,
                                "entries": [derived],
                            }
                        )
                        new_entries.append(derived)
                        derived_count += 1
                        locator_model = LegacyRefLocator(
                            polarity=document["polarity"],
                            category_id=document["id"],
                            entry_id=derived_id,
                        )
                        derived_locators.append(locator_model)
                        atom_details.append(
                            {
                                "source_locator": locator,
                                "source_revision": entry["revision"],
                                "source_etag": source_hashes[relative],
                                "segment_index": segment_index,
                                "raw_segment": raw_segment,
                                "derived_entry_id": derived_id,
                                "identity_sha256": identity,
                            }
                        )
                    source_locator = LegacyRefLocator(
                        polarity=document["polarity"],
                        category_id=document["id"],
                        entry_id=entry["id"],
                    )
                    registry.append(
                        LegacyRefExpansion(
                            source=source_locator,
                            derived=derived_locators,
                        )
                    )
                    expanded_by_source[
                        f"{document['polarity']}/{document['id']}/{entry['id']}"
                    ] = derived_locators
                if category_changed and not diagnostics:
                    migrated_category = {
                        **document,
                        "revision": document["revision"] + 1,
                        "entries": new_entries,
                    }
                    model = PromptCategory.model_validate(migrated_category)
                    targets[relative] = canonical_json_bytes(
                        model.model_dump(mode="json", exclude_none=True)
                    )

            combination_atoms, combination_targets, combination_diagnostics = (
                self._migrate_combinations(combinations, expanded_by_source)
            )
            diagnostics.extend(combination_diagnostics)
            if not diagnostics:
                targets.update(combination_targets)
                next_manifest = {
                    **manifest,
                    "schema_version": 2,
                    "comma_atomic_version": 1,
                    "comma_atomic_migration_required": False,
                }
                targets["manifest.json"] = canonical_json_bytes(
                    PromptLibraryManifest.model_validate(next_manifest).model_dump(
                        mode="json"
                    )
                )
            final_entries = retained_entries + derived_count

        inventory = MigrationInventory(
            source_entries=source_entries,
            comma_entries=comma_entries,
            retained_entries=retained_entries,
            derived_atoms=derived_count,
            final_entries=final_entries,
            blank_atoms=blank_count,
            combination_ids=sorted(combination_atoms),
            combination_atoms=combination_atoms,
        )
        diagnostics.extend(self._inventory_diagnostics(inventory, migrated=migrated))
        target_hashes = {
            relative: sha256_bytes(raw) for relative, raw in sorted(targets.items())
        }
        plan_material = {
            "source_hashes": source_hashes,
            "target_hashes": target_hashes,
            "registry": [
                item.model_dump(mode="json") for item in sorted(
                    registry,
                    key=lambda item: (
                        item.source.polarity,
                        item.source.category_id,
                        item.source.entry_id,
                    ),
                )
            ],
        }
        plan_hash = sha256_bytes(
            json.dumps(
                plan_material,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        report = MigrationReport(
            mode=mode,
            inventory=inventory,
            curation_records=len(curation),
            source_hashes=dict(sorted(source_hashes.items())),
            target_hashes=target_hashes,
            legacy_ref_expansions=sorted(
                registry,
                key=lambda item: (
                    item.source.polarity,
                    item.source.category_id,
                    item.source.entry_id,
                ),
            ),
            planned_mutations=sorted(targets),
            diagnostics=diagnostics,
            details={
                "atom_projections": atom_details,
                "retained_locators": retained_locators,
                "collision_policy": [8, 12, 16, 64],
            },
            plan_hash=plan_hash,
            eligible=not diagnostics,
        )
        return MigrationPlan(report=report, targets=targets, registry=registry)

    def _migrate_combinations(
        self,
        combinations: list[tuple[str, dict[str, object]]],
        expanded_by_source: dict[str, list[LegacyRefLocator]],
    ) -> tuple[
        dict[str, int],
        dict[str, bytes],
        list[MigrationDiagnostic],
    ]:
        counts: dict[str, int] = {}
        targets: dict[str, bytes] = {}
        diagnostics: list[MigrationDiagnostic] = []
        for relative, document in combinations:
            changed = False
            migrated_lanes: dict[str, list[dict[str, object]]] = {}
            for polarity in ("positive", "negative"):
                result: list[dict[str, object]] = []
                for fragment in document[polarity]:
                    ref = fragment.get("ref")
                    if fragment["kind"] == "entry" and ref:
                        ref_key = (
                            f"{ref['polarity']}/{ref['category_id']}/{ref['entry_id']}"
                        )
                        expansion = expanded_by_source.get(ref_key)
                        if expansion:
                            changed = True
                            for locator in expansion:
                                result.append(
                                    {
                                        **fragment,
                                        "ref": locator.model_dump(mode="json"),
                                        "snapshot": self._curated_snapshot(locator),
                                        "source_revision": 1,
                                    }
                                )
                            continue
                        if "," in fragment["snapshot"]:
                            diagnostics.append(
                                MigrationDiagnostic(
                                    code="legacy_reference_unresolved",
                                    message="Legacy source ref has no reviewed expansion.",
                                    locator=f"{document['id']}/{polarity}/{len(result) + 1}",
                                    details={"ref": ref},
                                )
                            )
                            continue
                    if "," in fragment["snapshot"]:
                        changed = True
                        try:
                            atoms = atomize_nonblank(fragment["snapshot"])
                        except ValueError as exc:
                            diagnostics.append(
                                MigrationDiagnostic(
                                    code="combination_blank_atom",
                                    message=str(exc),
                                    locator=f"{document['id']}/{polarity}/{len(result) + 1}",
                                )
                            )
                            continue
                        result.extend(
                            {
                                **fragment,
                                "snapshot": atom,
                            }
                            for atom in atoms
                        )
                    else:
                        result.append(fragment)
                for index, fragment in enumerate(result):
                    fragment["order"] = (index + 1) * 10
                migrated_lanes[polarity] = result
            counts[document["id"]] = len(migrated_lanes["positive"]) + len(
                migrated_lanes["negative"]
            )
            if changed and not diagnostics:
                migrated_document = {
                    **document,
                    "revision": document["revision"] + 1,
                    "positive": migrated_lanes["positive"],
                    "negative": migrated_lanes["negative"],
                    "positive_prompt_snapshot": render_prompt_lane(
                        [
                            (fragment["snapshot"], fragment.get("weight", 1.0))
                            for fragment in migrated_lanes["positive"]
                        ]
                    )
                    if migrated_lanes["positive"]
                    else "",
                    "negative_prompt_snapshot": render_prompt_lane(
                        [
                            (fragment["snapshot"], fragment.get("weight", 1.0))
                            for fragment in migrated_lanes["negative"]
                        ]
                    )
                    if migrated_lanes["negative"]
                    else "",
                }
                model = PromptCombination.model_validate(migrated_document)
                targets[relative] = canonical_json_bytes(
                    model.model_dump(mode="json", exclude_none=False)
                )
        return counts, targets, diagnostics

    def _curated_snapshot(self, locator: LegacyRefLocator) -> str:
        curation, _ = self._load_curation()
        for record in curation.values():
            if record.derived_entry_id == locator.entry_id:
                return record.raw_segment
        raise ValueError(f"derived ref missing curation: {locator.entry_id}")

    def _load_curation(
        self,
    ) -> tuple[dict[str, CuratedAtomRecord], list[MigrationDiagnostic]]:
        path = self.root / CURATION_RELATIVE
        diagnostics: list[MigrationDiagnostic] = []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = [
                CuratedAtomRecord.model_validate(record)
                for record in payload.get("records", [])
            ]
        except (OSError, ValueError, TypeError) as exc:
            return {}, [
                MigrationDiagnostic(
                    code="curation_unavailable",
                    message=f"Reviewed curation data is unavailable: {exc}",
                    locator=str(CURATION_RELATIVE),
                )
            ]
        result: dict[str, CuratedAtomRecord] = {}
        for record in records:
            key = curation_key(
                record.polarity,
                record.category_id,
                record.source_entry_id,
                record.source_prompt_sha256,
                record.segment_index,
            )
            if key in result:
                diagnostics.append(
                    MigrationDiagnostic(
                        code="curation_duplicate",
                        message="Curation key is duplicated.",
                        locator=key,
                    )
                )
            result[key] = record
        if len(records) != EXPECTED_DERIVED_ATOMS:
            diagnostics.append(
                MigrationDiagnostic(
                    code="curation_cardinality",
                    message="Curation must contain exactly 532 reviewed derived atoms.",
                    locator=str(CURATION_RELATIVE),
                    details={
                        "expected": EXPECTED_DERIVED_ATOMS,
                        "actual": len(records),
                    },
                )
            )
        return result, diagnostics

    def _load_registry(
        self,
    ) -> tuple[list[LegacyRefExpansion], list[MigrationDiagnostic]]:
        path = self.root / REGISTRY_RELATIVE
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            registry = [
                LegacyRefExpansion.model_validate(item)
                for item in payload.get("expansions", [])
            ]
        except (OSError, ValueError, TypeError) as exc:
            return [], [
                MigrationDiagnostic(
                    code="legacy_registry_unavailable",
                    message=f"Reviewed legacy ref registry is unavailable: {exc}",
                    locator=str(REGISTRY_RELATIVE),
                )
            ]
        if len(registry) != EXPECTED_COMMA_ENTRIES:
            return registry, [
                MigrationDiagnostic(
                    code="legacy_registry_cardinality",
                    message="Legacy ref registry must cover all 146 removed entries.",
                    locator=str(REGISTRY_RELATIVE),
                    details={
                        "expected": EXPECTED_COMMA_ENTRIES,
                        "actual": len(registry),
                    },
                )
            ]
        return registry, []

    def _inventory_diagnostics(
        self, inventory: MigrationInventory, *, migrated: bool
    ) -> list[MigrationDiagnostic]:
        expected = (
            {
                "source_entries": EXPECTED_FINAL_ENTRIES,
                "comma_entries": 0,
                "retained_entries": EXPECTED_RETAINED_ENTRIES,
                "derived_atoms": EXPECTED_DERIVED_ATOMS,
                "final_entries": EXPECTED_FINAL_ENTRIES,
                "blank_atoms": 0,
            }
            if migrated
            else {
                "source_entries": EXPECTED_SOURCE_ENTRIES,
                "comma_entries": EXPECTED_COMMA_ENTRIES,
                "retained_entries": EXPECTED_RETAINED_ENTRIES,
                "derived_atoms": EXPECTED_DERIVED_ATOMS,
                "final_entries": EXPECTED_FINAL_ENTRIES,
                "blank_atoms": 0,
            }
        )
        actual = inventory.model_dump()
        diagnostics: list[MigrationDiagnostic] = []
        for field, expected_value in expected.items():
            if actual[field] != expected_value:
                diagnostics.append(
                    MigrationDiagnostic(
                        code="inventory_mismatch",
                        message=f"Reviewed inventory field {field} drifted.",
                        details={
                            "field": field,
                            "expected": expected_value,
                            "actual": actual[field],
                        },
                    )
                )
        if inventory.combination_atoms != EXPECTED_COMBINATIONS:
            diagnostics.append(
                MigrationDiagnostic(
                    code="combination_inventory_mismatch",
                    message="Reviewed combination projection drifted.",
                    details={
                        "expected": EXPECTED_COMBINATIONS,
                        "actual": inventory.combination_atoms,
                    },
                )
            )
        return diagnostics

    def _read_documents(
        self,
        directories: tuple[str, ...],
        *,
        source_hashes: dict[str, str],
    ) -> list[tuple[str, dict[str, object]]]:
        result: list[tuple[str, dict[str, object]]] = []
        for directory in directories:
            for path in sorted((self.root / directory).glob("*.json")):
                relative = path.relative_to(self.root).as_posix()
                raw = path.read_bytes()
                source_hashes[relative] = sha256_bytes(raw)
                result.append((relative, json.loads(raw)))
        return result

    def _capture_preimages(self, targets: dict[str, bytes]) -> dict[str, bytes]:
        return {relative: (self.root / relative).read_bytes() for relative in targets}

    def _read_rollback(self, run_id: str) -> dict[str, object]:
        path = self.root / ROLLBACK_DIR / run_id / "rollback.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise self._migration_error(
                "migration_rollback_manifest_unavailable",
                "Rollback manifest is unavailable or invalid.",
                run_id=run_id,
            ) from exc

    @staticmethod
    def _write_new(path: Path, raw: bytes) -> None:
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _validate_target(
        relative: str,
        raw: bytes,
        *,
        allow_legacy: bool = False,
    ) -> None:
        payload = json.loads(raw)
        if relative == "manifest.json":
            PromptLibraryManifest.model_validate(payload)
        elif relative.startswith(("positive/", "negative/")):
            if allow_legacy:
                compatibility_payload = {
                    **payload,
                    "entries": [
                        {
                            **entry,
                            "prompt": atomize_nonblank(entry["prompt"])[0],
                        }
                        for entry in payload["entries"]
                    ],
                }
                PromptCategory.model_validate(compatibility_payload)
            else:
                PromptCategory.model_validate(payload)
        elif relative.startswith("combinations/"):
            PromptCombination.model_validate(payload)

    @staticmethod
    def _migration_error(
        code: str, message: str, **details: object
    ) -> PromptLibraryError:
        return PromptLibraryError(
            code=code,
            message=message,
            hint="Review the privileged dry-run report and retry with unchanged inputs.",
            status_code=409,
            details=details,
        )
