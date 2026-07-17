"""Concurrency-safe writes and snapshot repair for the Prompt Library."""

from __future__ import annotations

from app.core.prompt_composer import PromptComposer
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_models import (
    Polarity,
    PromptCategory,
    PromptCombination,
    PromptEntry,
)
from app.core.prompt_library_store import PromptLibraryStore
from app.schemas.prompt_library import (
    ArchiveRequest,
    CategoryWriteRequest,
    CombinationWriteRequest,
    ComposeRequest,
    EntryWriteRequest,
    VersionedCategory,
    VersionedCombination,
    WriteResponse,
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
    def __init__(self, store: PromptLibraryStore) -> None:
        self.store = store
        self.composer = PromptComposer(store)

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

    def repair_combination(self, combination_id: str) -> VersionedCombination:
        with self.store.locked():
            current = self.store.read_combination(combination_id)
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
