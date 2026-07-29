"""Concurrency-safe writes and snapshot repair for the Prompt Library."""

from __future__ import annotations

from collections import Counter
import hashlib
import json

from app.core.prompt_atomic import atomize_nonblank, render_prompt_lane
from app.core.prompt_composer import PromptComposer
from app.core.prompt_document_context import PromptDocumentContextCodec
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_models import (
    Polarity,
    PromptCategory,
    PromptCombination,
    PromptEntry,
    PromptEntryRef,
    PromptFragment,
)
from app.core.prompt_library_store import PromptLibraryStore
from app.schemas.prompt_library import (
    ArchiveRequest,
    CategoryWriteRequest,
    CombinationWriteRequest,
    ComposeRequest,
    EntryWriteRequest,
    LiteralConversionAcknowledgeRequest,
    LiteralConversionAcknowledgeResponse,
    MoveEntryRequest,
    PromptWarning,
    RestoreRequest,
    VersionedCategory,
    VersionedCombination,
    WriteResponse,
)
from app.schemas.prompt_library_migration import (
    BlockingDocumentDiagnostic,
    LegacyRefLocator,
)


def assert_precondition(
    *,
    exists: bool,
    actual_revision: int | None,
    actual_etag: str | None,
    expected_revision: int,
    expected_etag: str | None,
) -> None:
    if not exists:
        if expected_revision != 0 or expected_etag is not None:
            raise PromptLibraryError.revision_conflict(expected_revision, None)
        return
    if expected_revision != actual_revision:
        raise PromptLibraryError.revision_conflict(expected_revision, actual_revision)
    if expected_etag is None or expected_etag != actual_etag:
        raise PromptLibraryError.external_change(expected_etag, actual_etag)


class PromptLibraryWriter:
    def __init__(
        self,
        store: PromptLibraryStore,
        *,
        document_context: PromptDocumentContextCodec | None = None,
    ) -> None:
        self.store = store
        self.composer = PromptComposer(store)
        self.document_context = document_context or PromptDocumentContextCodec()

    def _validate_parent(self, polarity: Polarity, category_id: str, parent_id: str) -> None:
        if parent_id == category_id:
            raise PromptLibraryError(
                code="invalid_parent_self",
                message="A category cannot be its own parent.",
                hint="Choose a different parent category or leave it empty for a root.",
                status_code=422,
                details={"category_id": category_id},
            )
        categories, _ = self.store.scan_categories()
        by_id = {
            doc.model.id: doc.model
            for doc in categories
            if doc.model.polarity == polarity
        }
        if parent_id not in by_id:
            raise PromptLibraryError(
                code="parent_not_found",
                message="The parent category does not exist in this polarity.",
                hint="Create the parent first, or pick an existing same-polarity category.",
                status_code=422,
                details={"category_id": category_id, "parent_id": parent_id},
            )
        # walk up from parent; reaching category_id means a cycle
        seen: set[str] = set()
        cursor: str | None = parent_id
        while cursor is not None:
            if cursor == category_id:
                raise PromptLibraryError(
                    code="parent_cycle",
                    message="Setting this parent would create a category cycle.",
                    hint="Pick a parent that is not a descendant of this category.",
                    status_code=422,
                    details={"category_id": category_id, "parent_id": parent_id},
                )
            if cursor in seen:
                break
            seen.add(cursor)
            cursor = by_id[cursor].parent_id if cursor in by_id else None

    def save_category(
        self, polarity: Polarity, category_id: str, request: CategoryWriteRequest
    ) -> WriteResponse:
        path = self.store.category_path(polarity, category_id)
        with self.store.locked():
            current = self.store.read_category(polarity, category_id) if path.exists() else None
            assert_precondition(
                exists=current is not None,
                actual_revision=current.model.revision if current else None,
                actual_etag=current.etag if current else None,
                expected_revision=request.expected_revision,
                expected_etag=request.expected_etag,
            )
            if request.parent_id is not None:
                self._validate_parent(polarity, category_id, request.parent_id)
            category = PromptCategory(
                id=category_id,
                polarity=polarity,
                name_zh=request.name_zh,
                description_zh=request.description_zh,
                aliases=request.aliases,
                keywords=request.keywords,
                order=request.order,
                revision=1 if current is None else current.model.revision + 1,
                archived=False if current is None else current.model.archived,
                entries=[] if current is None else current.model.entries,
                parent_id=request.parent_id,
            )
            etag = self.store.replace_json(path, category)
        return WriteResponse(category=VersionedCategory(category=category, etag=etag))

    def save_entry(
        self,
        polarity: Polarity,
        category_id: str,
        entry_id: str,
        request: EntryWriteRequest,
    ) -> WriteResponse:
        if not request.prompt.strip():
            raise PromptLibraryError.blank_fragment(
                polarity=polarity, positions=[1]
            )
        if "," in request.prompt:
            raise PromptLibraryError.comma_not_atomic(field="prompt")
        with self.store.locked():
            current = self.store.read_category(polarity, category_id)
            assert_precondition(
                exists=True,
                actual_revision=current.model.revision,
                actual_etag=current.etag,
                expected_revision=request.expected_revision,
                expected_etag=request.expected_etag,
            )
            previous = next(
                (item for item in current.model.entries if item.id == entry_id), None
            )
            entry = PromptEntry(
                id=entry_id,
                name_zh=request.name_zh,
                description_zh=request.description_zh,
                prompt=request.prompt,
                aliases=request.aliases,
                keywords=request.keywords,
                order=request.order,
                revision=1 if previous is None else previous.revision + 1,
                archived=False if previous is None else previous.archived,
            )
            entries = [item for item in current.model.entries if item.id != entry_id]
            entries.append(entry)
            entries.sort(key=lambda item: (item.order, item.id))
            category = current.model.model_copy(
                deep=True,
                update={"entries": entries, "revision": current.model.revision + 1},
            )
            etag = self.store.replace_json(current.path, category)
            affected = self._propagate_entry(polarity, category_id, entry)
        return WriteResponse(
            category=VersionedCategory(category=category, etag=etag),
            entry=entry,
            entry_revision=entry.revision,
            affected_combinations=affected,
        )

    def move_entry(
        self,
        polarity: Polarity,
        from_category_id: str,
        entry_id: str,
        request: MoveEntryRequest,
    ) -> WriteResponse:
        if request.to_category_id == from_category_id:
            return self.save_entry(polarity, from_category_id, entry_id, request)
        if not request.prompt.strip():
            raise PromptLibraryError.blank_fragment(polarity=polarity, positions=[1])
        if "," in request.prompt:
            raise PromptLibraryError.comma_not_atomic(field="prompt")
        with self.store.locked():
            source = self.store.read_category(polarity, from_category_id)
            assert_precondition(
                exists=True,
                actual_revision=source.model.revision,
                actual_etag=source.etag,
                expected_revision=request.expected_revision,
                expected_etag=request.expected_etag,
            )
            if not any(item.id == entry_id for item in source.model.entries):
                raise PromptLibraryError(
                    code="entry_not_found",
                    message="The entry to move does not exist in the source category.",
                    hint="Reload the category and try again.",
                    status_code=404,
                    details={"category_id": from_category_id, "entry_id": entry_id},
                )
            dest_path = self.store.category_path(polarity, request.to_category_id)
            if not dest_path.exists():
                raise PromptLibraryError(
                    code="target_category_not_found",
                    message="The target category does not exist.",
                    hint="Pick an existing same-polarity category.",
                    status_code=404,
                    details={"to_category_id": request.to_category_id},
                )
            dest = self.store.read_category(polarity, request.to_category_id)
            if any(item.id == entry_id for item in dest.model.entries):
                raise PromptLibraryError(
                    code="entry_id_conflict",
                    message="The target category already has an entry with this id.",
                    hint="Rename the entry id or pick another category.",
                    status_code=422,
                    details={"entry_id": entry_id, "to_category_id": request.to_category_id},
                )
            moved = PromptEntry(
                id=entry_id,
                name_zh=request.name_zh,
                description_zh=request.description_zh,
                prompt=request.prompt,
                aliases=request.aliases,
                keywords=request.keywords,
                order=request.order,
                revision=1,
                archived=False,
            )
            source_entries = [item for item in source.model.entries if item.id != entry_id]
            source_category = source.model.model_copy(
                deep=True,
                update={"entries": source_entries, "revision": source.model.revision + 1},
            )
            self.store.replace_json(source.path, source_category)
            dest_entries = [*dest.model.entries, moved]
            dest_entries.sort(key=lambda item: (item.order, item.id))
            dest_category = dest.model.model_copy(
                deep=True,
                update={"entries": dest_entries, "revision": dest.model.revision + 1},
            )
            dest_etag = self.store.replace_json(dest.path, dest_category)
            affected = self._propagate_entry(polarity, request.to_category_id, moved)
        return WriteResponse(
            category=VersionedCategory(category=dest_category, etag=dest_etag),
            entry=moved,
            entry_revision=moved.revision,
            affected_combinations=affected,
        )

    def save_combination(
        self, combination_id: str, request: CombinationWriteRequest
    ) -> WriteResponse:
        path = self.store.combination_path(combination_id)
        with self.store.locked():
            current = self.store.read_combination(combination_id) if path.exists() else None
            assert_precondition(
                exists=current is not None,
                actual_revision=current.model.revision if current else None,
                actual_etag=current.etag if current else None,
                expected_revision=request.expected_revision,
                expected_etag=request.expected_etag,
            )
            blocked_source = None
            if current is not None:
                blocked_source = self._blocked_version(current)
            if request.source_combination_id is not None:
                source = self.store.read_combination(request.source_combination_id)
                source_blocked = self._blocked_version(source)
                if source_blocked is not None:
                    blocked_source = source_blocked
            if blocked_source is not None:
                self._assert_explicit_resolution(request, blocked_source)
            composed = self.composer.compose(
                ComposeRequest(positive=request.positive, negative=request.negative)
            )
            combination = PromptCombination(
                id=combination_id,
                name_zh=request.name_zh,
                description_zh=request.description_zh,
                aliases=request.aliases,
                keywords=request.keywords,
                order=request.order,
                revision=1 if current is None else current.model.revision + 1,
                archived=False if current is None else current.model.archived,
                legacy_template=request.legacy_template,
                positive=composed.positive,
                negative=composed.negative,
                positive_prompt_snapshot=composed.positive_prompt,
                negative_prompt_snapshot=composed.negative_prompt,
            )
            etag = self.store.replace_json(path, combination)
        return WriteResponse(
            combination=VersionedCombination(
                combination=combination,
                etag=etag,
                repaired=composed.snapshot_repaired,
                warnings=composed.warnings,
            )
        )

    def archive(self, request: ArchiveRequest) -> WriteResponse:
        if request.resource_type == "entry":
            if request.polarity is None or request.category_id is None:
                raise PromptLibraryError.invalid_locator(request.resource_id)
            return self._archive_entry(request)
        if request.resource_type == "category":
            if request.polarity is None:
                raise PromptLibraryError.invalid_locator(request.resource_id)
            return self._archive_category(request)
        return self._archive_combination(request)

    def restore(self, request: RestoreRequest) -> WriteResponse:
        if request.resource_type == "entry":
            return self._restore_entry(request)
        return self._restore_category(request)

    def repair_combination(self, combination_id: str) -> VersionedCombination:
        with self.store.locked():
            current = self.store.read_combination(combination_id)
            blocked = self._blocked_version(current)
            if blocked is not None:
                return blocked
            composed = self.composer.compose(
                ComposeRequest(
                    positive=current.model.positive,
                    negative=current.model.negative,
                )
            )
            if not composed.snapshot_repaired:
                return VersionedCombination(
                    combination=current.model,
                    etag=current.etag,
                    warnings=composed.warnings,
                )
            repaired = current.model.model_copy(
                deep=True,
                update={
                    "positive": composed.positive,
                    "negative": composed.negative,
                    "positive_prompt_snapshot": composed.positive_prompt,
                    "negative_prompt_snapshot": composed.negative_prompt,
                    "revision": current.model.revision + 1,
                },
            )
            etag = self.store.replace_json(current.path, repaired)
            return VersionedCombination(
                combination=repaired,
                etag=etag,
                repaired=True,
                warnings=composed.warnings,
            )

    def acknowledge_literal_conversion(
        self,
        combination_id: str,
        request: LiteralConversionAcknowledgeRequest,
    ) -> LiteralConversionAcknowledgeResponse:
        with self.store.locked():
            current = self.store.read_combination(combination_id)
            blocked = self._blocked_version(current)
            if blocked is None:
                raise PromptLibraryError(
                    code="document_not_blocked",
                    message="The combination has no unresolved legacy provenance.",
                    hint="Reload the combination; no literal-conversion acknowledgment is needed.",
                    status_code=409,
                )
            self.document_context.validate_document_context(
                request.document_context_token,
                blocked.blocking_diagnostics,
            )
            token = self.document_context.issue_literal_conversion(
                request.document_context_token,
                blocked.blocking_diagnostics,
            )
            return LiteralConversionAcknowledgeResponse(
                literal_conversion_token=token,
                diagnostic_ids=[
                    diagnostic.id for diagnostic in blocked.blocking_diagnostics
                ],
            )

    def _blocked_version(
        self, current
    ) -> VersionedCombination | None:
        categories, _ = self.store.scan_categories()
        entries = {
            (category.model.polarity, category.model.id, entry.id): entry
            for category in categories
            for entry in category.model.entries
        }
        registry = self.composer._legacy_registry()
        diagnostics: list[BlockingDocumentDiagnostic] = []
        warnings: list[PromptWarning] = []
        lanes: dict[Polarity, list[PromptFragment]] = {
            "positive": [],
            "negative": [],
        }
        for polarity in ("positive", "negative"):
            for fragment in sorted(
                getattr(current.model, polarity),
                key=lambda item: item.order,
            ):
                ref = fragment.ref
                if (
                    fragment.kind != "entry"
                    or ref is None
                    or (
                        ref.polarity,
                        ref.category_id,
                        ref.entry_id,
                    )
                    in entries
                    or (
                        ref.polarity,
                        ref.category_id,
                        ref.entry_id,
                    )
                    in registry
                ):
                    lanes[polarity].append(fragment.model_copy(deep=True))
                    continue
                try:
                    atoms = (
                        atomize_nonblank(fragment.snapshot)
                        if "," in fragment.snapshot
                        else [fragment.snapshot]
                    )
                except ValueError:
                    raise PromptLibraryError.blank_fragment(
                        polarity=polarity,
                        positions=[
                            index + 1
                            for index, atom in enumerate(
                                fragment.snapshot.split(",")
                            )
                            if not atom.strip()
                        ],
                    )
                atom_hashes = [
                    hashlib.sha256(atom.encode("utf-8")).hexdigest()
                    for atom in atoms
                ]
                diagnostic_material = json.dumps(
                    {
                        "combination_id": current.model.id,
                        "revision": current.model.revision,
                        "etag": current.etag,
                        "ref": ref.model_dump(mode="json"),
                        "polarity": polarity,
                        "fallback_start_position": len(lanes[polarity]) + 1,
                        "fallback_count": len(atoms),
                        "atom_hashes": atom_hashes,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                diagnostic_id = hashlib.sha256(diagnostic_material).hexdigest()
                diagnostic = BlockingDocumentDiagnostic(
                    id=diagnostic_id,
                    original_ref=LegacyRefLocator.model_validate(
                        ref.model_dump(mode="json")
                    ),
                    combination_id=current.model.id,
                    revision=current.model.revision,
                    etag=current.etag,
                    polarity=polarity,
                    fallback_start_position=len(lanes[polarity]) + 1,
                    fallback_count=len(atoms),
                    fallback_atom_hashes=atom_hashes,
                )
                diagnostics.append(diagnostic)
                warnings.append(
                    PromptWarning(
                        code="legacy_reference_unresolved",
                        message=(
                            "A legacy source ref could not be transferred; "
                            "literal fallback atoms are blocked from persistence."
                        ),
                        hint=(
                            "Choose replacement entries or explicitly acknowledge "
                            "conversion to literals."
                        ),
                        ref=ref,
                        details={
                            "diagnostic_id": diagnostic_id,
                            "polarity": polarity,
                            "fallback_atom_hashes": atom_hashes,
                            "resolution": "explicit_action_required",
                        },
                    )
                )
                lanes[polarity].extend(
                    PromptFragment(
                        kind="literal",
                        snapshot=atom,
                        weight=fragment.weight,
                        order=10,
                    )
                    for atom in atoms
                )
        if not diagnostics:
            return None
        for polarity in ("positive", "negative"):
            lanes[polarity] = [
                fragment.model_copy(update={"order": (index + 1) * 10})
                for index, fragment in enumerate(lanes[polarity])
            ]
        fallback = current.model.model_copy(
            deep=True,
            update={
                "positive": lanes["positive"],
                "negative": lanes["negative"],
                "positive_prompt_snapshot": (
                    render_prompt_lane(
                        [
                            (fragment.snapshot, fragment.weight)
                            for fragment in lanes["positive"]
                        ]
                    )
                    if lanes["positive"]
                    else ""
                ),
                "negative_prompt_snapshot": (
                    render_prompt_lane(
                        [
                            (fragment.snapshot, fragment.weight)
                            for fragment in lanes["negative"]
                        ]
                    )
                    if lanes["negative"]
                    else ""
                ),
            },
        )
        context_token = self.document_context.issue_document_context(diagnostics)
        return VersionedCombination(
            combination=fallback,
            etag=current.etag,
            repaired=False,
            warnings=warnings,
            blocking_diagnostics=diagnostics,
            document_context_token=context_token,
        )

    def _assert_explicit_resolution(
        self,
        request: CombinationWriteRequest,
        blocked: VersionedCombination,
    ) -> None:
        diagnostics = blocked.blocking_diagnostics
        if request.document_context_token is None:
            raise self._provenance_blocked(diagnostics)
        self.document_context.validate_document_context(
            request.document_context_token, diagnostics
        )
        if request.literal_conversion_token is not None:
            self.document_context.validate_literal_conversion(
                request.literal_conversion_token,
                request.document_context_token,
                diagnostics,
            )
            return
        resolutions = {
            resolution.diagnostic_id: resolution
            for resolution in request.provenance_resolutions
        }
        if set(resolutions) != {item.id for item in diagnostics}:
            raise self._provenance_blocked(diagnostics)
        requested_refs = {
            (
                fragment.ref.polarity,
                fragment.ref.category_id,
                fragment.ref.entry_id,
            )
            for fragment in [*request.positive, *request.negative]
            if fragment.ref is not None
        }
        categories, _ = self.store.scan_categories()
        valid_refs = {
            (category.model.polarity, category.model.id, entry.id)
            for category in categories
            for entry in category.model.entries
        }
        diagnostic_by_id = {item.id: item for item in diagnostics}
        ordered_diagnostics = sorted(
            diagnostics,
            key=lambda item: (
                item.polarity,
                item.fallback_start_position,
                item.id,
            ),
        )
        replacement_sizes = {
            diagnostic.id: len(resolutions[diagnostic.id].replacement_refs)
            for diagnostic in ordered_diagnostics
        }
        for resolution in resolutions.values():
            if resolution.action not in {
                "reviewed_mapping",
                "replacement_entries",
            }:
                raise self._provenance_blocked(diagnostics)
            ordered_replacement_refs = [
                (item.polarity, item.category_id, item.entry_id)
                for item in resolution.replacement_refs
            ]
            replacement_refs = set(ordered_replacement_refs)
            if (
                not replacement_refs
                or not replacement_refs <= valid_refs
                or not replacement_refs <= requested_refs
            ):
                raise self._provenance_blocked(diagnostics)
            diagnostic = diagnostic_by_id[resolution.diagnostic_id]
            shift = sum(
                replacement_sizes[item.id] - item.fallback_count
                for item in ordered_diagnostics
                if item.polarity == diagnostic.polarity
                and item.fallback_start_position
                < diagnostic.fallback_start_position
            )
            start = diagnostic.fallback_start_position - 1 + shift
            lane = (
                request.positive
                if diagnostic.polarity == "positive"
                else request.negative
            )
            installed_refs = [
                (
                    fragment.ref.polarity,
                    fragment.ref.category_id,
                    fragment.ref.entry_id,
                )
                if fragment.kind == "entry" and fragment.ref is not None
                else None
                for fragment in lane[
                    start : start + len(ordered_replacement_refs)
                ]
            ]
            if installed_refs != ordered_replacement_refs:
                raise self._provenance_blocked(diagnostics)
        for polarity in ("positive", "negative"):
            lane_diagnostics = [
                item for item in diagnostics if item.polarity == polarity
            ]
            if not lane_diagnostics:
                continue
            baseline_lane = getattr(blocked.combination, polarity)
            request_lane = getattr(request, polarity)
            baseline_literal_hashes = Counter(
                hashlib.sha256(fragment.snapshot.encode("utf-8")).hexdigest()
                for fragment in baseline_lane
                if fragment.kind == "literal"
            )
            diagnostic_hashes = Counter(
                atom_hash
                for diagnostic in lane_diagnostics
                for atom_hash in diagnostic.fallback_atom_hashes
            )
            submitted_literal_hashes = Counter(
                hashlib.sha256(fragment.snapshot.encode("utf-8")).hexdigest()
                for fragment in request_lane
                if fragment.kind == "literal"
            )
            if any(
                submitted_literal_hashes[atom_hash]
                > baseline_literal_hashes[atom_hash] - fallback_count
                for atom_hash, fallback_count in diagnostic_hashes.items()
            ):
                raise self._provenance_blocked(diagnostics)

    @staticmethod
    def _provenance_blocked(
        diagnostics: list[BlockingDocumentDiagnostic],
    ) -> PromptLibraryError:
        return PromptLibraryError(
            code="unresolved_legacy_provenance",
            message="This document still has unresolved legacy source provenance.",
            hint=(
                "Resolve every diagnostic with reviewed mapping or replacement "
                "entries, or explicitly acknowledge conversion to literals."
            ),
            status_code=409,
            details={
                "diagnostic_ids": [item.id for item in diagnostics],
                "blocking": True,
            },
        )

    def _propagate_entry(
        self, polarity: Polarity, category_id: str, entry: PromptEntry
    ) -> list[str]:
        affected: list[str] = []
        combinations, _ = self.store.scan_combinations()
        for document in combinations:
            combination = document.model
            if combination.archived:
                continue
            matched = False
            for lane in (combination.positive, combination.negative):
                for index, fragment in enumerate(lane):
                    ref = fragment.ref
                    if (
                        fragment.kind == "entry"
                        and ref is not None
                        and ref.polarity == polarity
                        and ref.category_id == category_id
                        and ref.entry_id == entry.id
                    ):
                        lane[index] = fragment.model_copy(
                            deep=True,
                            update={
                                "snapshot": entry.prompt,
                                "source_revision": entry.revision,
                            },
                        )
                        matched = True
            if not matched:
                continue
            composed = self.composer.compose(
                ComposeRequest(
                    positive=combination.positive,
                    negative=combination.negative,
                )
            )
            updated = combination.model_copy(
                deep=True,
                update={
                    "positive": composed.positive,
                    "negative": composed.negative,
                    "positive_prompt_snapshot": composed.positive_prompt,
                    "negative_prompt_snapshot": composed.negative_prompt,
                    "revision": combination.revision + 1,
                },
            )
            self.store.replace_json(document.path, updated)
            affected.append(combination.id)
        return sorted(affected)

    def _archive_entry(self, request: ArchiveRequest) -> WriteResponse:
        assert request.polarity is not None and request.category_id is not None
        with self.store.locked():
            current = self.store.read_category(request.polarity, request.category_id)
            assert_precondition(
                exists=True,
                actual_revision=current.model.revision,
                actual_etag=current.etag,
                expected_revision=request.expected_revision,
                expected_etag=request.expected_etag,
            )
            entry = next(
                (item for item in current.model.entries if item.id == request.resource_id),
                None,
            )
            if entry is None:
                raise PromptLibraryError.not_found("entry", request.resource_id)
            archived = entry.model_copy(
                deep=True,
                update={"archived": True, "revision": entry.revision + 1},
            )
            entries = [archived if item.id == archived.id else item for item in current.model.entries]
            category = current.model.model_copy(
                deep=True,
                update={"entries": entries, "revision": current.model.revision + 1},
            )
            etag = self.store.replace_json(current.path, category)
        return WriteResponse(
            category=VersionedCategory(category=category, etag=etag),
            entry=archived,
            entry_revision=archived.revision,
        )

    def _archive_category(self, request: ArchiveRequest) -> WriteResponse:
        assert request.polarity is not None
        with self.store.locked():
            current = self.store.read_category(request.polarity, request.resource_id)
            assert_precondition(
                exists=True,
                actual_revision=current.model.revision,
                actual_etag=current.etag,
                expected_revision=request.expected_revision,
                expected_etag=request.expected_etag,
            )
            category = current.model.model_copy(
                deep=True,
                update={"archived": True, "revision": current.model.revision + 1},
            )
            etag = self.store.replace_json(current.path, category)
        return WriteResponse(category=VersionedCategory(category=category, etag=etag))

    def _archive_combination(self, request: ArchiveRequest) -> WriteResponse:
        with self.store.locked():
            current = self.store.read_combination(request.resource_id)
            assert_precondition(
                exists=True,
                actual_revision=current.model.revision,
                actual_etag=current.etag,
                expected_revision=request.expected_revision,
                expected_etag=request.expected_etag,
            )
            combination = current.model.model_copy(
                deep=True,
                update={"archived": True, "revision": current.model.revision + 1},
            )
            etag = self.store.replace_json(current.path, combination)
        return WriteResponse(
            combination=VersionedCombination(combination=combination, etag=etag)
        )

    def _restore_entry(self, request: RestoreRequest) -> WriteResponse:
        assert request.category_id is not None
        with self.store.locked():
            current = self.store.read_category(request.polarity, request.category_id)
            assert_precondition(
                exists=True,
                actual_revision=current.model.revision,
                actual_etag=current.etag,
                expected_revision=request.expected_revision,
                expected_etag=request.expected_etag,
            )
            entry = next(
                (item for item in current.model.entries if item.id == request.resource_id),
                None,
            )
            if entry is None:
                raise PromptLibraryError.not_found("entry", request.resource_id)
            if current.model.archived:
                raise PromptLibraryError.archived_parent(
                    request.polarity, request.category_id, request.resource_id
                )
            if not entry.archived:
                raise PromptLibraryError.already_active("entry", request.resource_id)
            restored = entry.model_copy(
                deep=True,
                update={"archived": False, "revision": entry.revision + 1},
            )
            entries = [
                restored if item.id == restored.id else item
                for item in current.model.entries
            ]
            category = current.model.model_copy(
                deep=True,
                update={"entries": entries, "revision": current.model.revision + 1},
            )
            etag = self.store.replace_json(current.path, category)
        return WriteResponse(
            category=VersionedCategory(category=category, etag=etag),
            entry=restored,
            entry_revision=restored.revision,
        )

    def _restore_category(self, request: RestoreRequest) -> WriteResponse:
        with self.store.locked():
            current = self.store.read_category(request.polarity, request.resource_id)
            assert_precondition(
                exists=True,
                actual_revision=current.model.revision,
                actual_etag=current.etag,
                expected_revision=request.expected_revision,
                expected_etag=request.expected_etag,
            )
            if not current.model.archived:
                raise PromptLibraryError.already_active("category", request.resource_id)
            category = current.model.model_copy(
                deep=True,
                update={"archived": False, "revision": current.model.revision + 1},
            )
            etag = self.store.replace_json(current.path, category)
        return WriteResponse(category=VersionedCategory(category=category, etag=etag))
