"""Long-lived facade for the safe file-backed Prompt Library store."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import get_settings
from app.core.prompt_library_models import Polarity
from app.core.prompt_library_store import PromptLibraryStore, StoredDocument
from app.schemas.prompt_library import (
    CatalogResponse,
    CategorySummary,
    CombinationSummary,
    VersionedCategory,
    VersionedCombination,
)


class PromptLibraryProvider(Protocol):
    def catalog(self) -> CatalogResponse: ...

    def get_category(self, polarity: Polarity, category_id: str) -> VersionedCategory: ...

    def get_combination(self, combination_id: str) -> VersionedCombination: ...


class FilePromptLibraryProvider:
    def __init__(self, root: Path, lock_timeout: float = 5.0) -> None:
        self.store = PromptLibraryStore(root, lock_timeout=lock_timeout)
        self.root = self.store.root
        # Kept as an observable provider attribute while the store owns the
        # single RLock-protected snapshot/cache transaction.
        self._cache = self.store._cache

    def catalog(self) -> CatalogResponse:
        manifest = self.store.read_manifest()
        categories, category_diagnostics = self.store.scan_categories()
        combinations, combination_diagnostics = self.store.scan_combinations()
        return CatalogResponse(
            manifest=manifest,
            categories=sorted(
                (self._category_summary(document) for document in categories),
                key=lambda item: (item.order, item.id),
            ),
            combinations=sorted(
                (self._combination_summary(document) for document in combinations),
                key=lambda item: (item.order, item.id),
            ),
            diagnostics=category_diagnostics + combination_diagnostics,
        )

    def get_category(self, polarity: Polarity, category_id: str) -> VersionedCategory:
        document = self.store.read_category(polarity, category_id)
        return VersionedCategory(category=document.model, etag=document.etag)

    def get_combination(self, combination_id: str) -> VersionedCombination:
        document = self.store.read_combination(combination_id)
        return VersionedCombination(combination=document.model, etag=document.etag)

    @staticmethod
    def _category_summary(document: StoredDocument) -> CategorySummary:
        category = document.model
        return CategorySummary(
            id=category.id,
            polarity=category.polarity,
            name_zh=category.name_zh,
            description_zh=category.description_zh,
            aliases=category.aliases,
            keywords=category.keywords,
            order=category.order,
            revision=category.revision,
            archived=category.archived,
            entry_count=len(category.entries),
            etag=document.etag,
        )

    @staticmethod
    def _combination_summary(document: StoredDocument) -> CombinationSummary:
        combination = document.model
        return CombinationSummary(
            id=combination.id,
            name_zh=combination.name_zh,
            description_zh=combination.description_zh,
            aliases=combination.aliases,
            keywords=combination.keywords,
            order=combination.order,
            revision=combination.revision,
            archived=combination.archived,
            legacy_template=combination.legacy_template,
            positive_prompt_snapshot=combination.positive_prompt_snapshot,
            negative_prompt_snapshot=combination.negative_prompt_snapshot,
            etag=document.etag,
        )


@lru_cache(maxsize=8)
def _provider_for(root: str, lock_timeout: float) -> FilePromptLibraryProvider:
    return FilePromptLibraryProvider(Path(root), lock_timeout=lock_timeout)


def get_default_prompt_library_provider() -> FilePromptLibraryProvider:
    settings = get_settings()
    return _provider_for(settings.prompt_library_dir, settings.prompt_library_lock_timeout)
