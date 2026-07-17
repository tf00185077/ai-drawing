"""Long-lived, cache-aware read facade for Prompt Library JSON documents."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_models import Polarity, PromptCategory, PromptCombination
from app.core.prompt_library_store import PromptLibraryStore, StoredDocument, sha256_bytes
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


@dataclass(frozen=True)
class _CacheEntry:
    mtime_ns: int
    size: int
    etag: str
    document: StoredDocument[BaseModel]


class FilePromptLibraryProvider:
    def __init__(self, root: Path, lock_timeout: float = 5.0) -> None:
        self.root = root.resolve()
        self.store = PromptLibraryStore(self.root, lock_timeout=lock_timeout)
        self._cache: dict[Path, _CacheEntry] = {}
        self._cache_lock = threading.RLock()

    def catalog(self) -> CatalogResponse:
        manifest = self.store.read_manifest()
        categories, category_diagnostics = self._scan_categories()
        combinations, combination_diagnostics = self._scan_combinations()
        category_summaries = sorted(
            (self._category_summary(document) for document in categories),
            key=lambda item: (item.order, item.id),
        )
        combination_summaries = sorted(
            (self._combination_summary(document) for document in combinations),
            key=lambda item: (item.order, item.id),
        )
        return CatalogResponse(
            manifest=manifest,
            categories=category_summaries,
            combinations=combination_summaries,
            diagnostics=category_diagnostics + combination_diagnostics,
        )

    def get_category(self, polarity: Polarity, category_id: str) -> VersionedCategory:
        path = self.store.category_path(polarity, category_id)
        document = self._cached_read(path, PromptCategory)
        self._validate_category_location(document.model, path, polarity)
        return VersionedCategory(category=document.model, etag=document.etag)

    def get_combination(self, combination_id: str) -> VersionedCombination:
        path = self.store.combination_path(combination_id)
        document = self._cached_read(path, PromptCombination)
        if document.model.id != path.stem:
            raise PromptLibraryError.invalid_document(
                path.relative_to(self.root).as_posix(),
                "document id does not match its filename",
            )
        return VersionedCombination(combination=document.model, etag=document.etag)

    def _scan_categories(self) -> tuple[list[StoredDocument[PromptCategory]], list]:
        documents: list[StoredDocument[PromptCategory]] = []
        diagnostics = []
        for polarity in ("positive", "negative"):
            parent = self.root / polarity
            if not parent.is_dir():
                continue
            for path in sorted(parent.glob("*.json"), key=lambda item: item.name):
                try:
                    document = self._cached_read(path, PromptCategory)
                    self._validate_category_location(document.model, path, polarity)
                except PromptLibraryError as exc:
                    diagnostics.append(self._diagnostic(path, exc))
                else:
                    documents.append(document)
        return documents, diagnostics

    def _scan_combinations(self) -> tuple[list[StoredDocument[PromptCombination]], list]:
        documents: list[StoredDocument[PromptCombination]] = []
        diagnostics = []
        parent = self.root / "combinations"
        if not parent.is_dir():
            return documents, diagnostics
        for path in sorted(parent.glob("*.json"), key=lambda item: item.name):
            try:
                document = self._cached_read(path, PromptCombination)
                if document.model.id != path.stem:
                    raise PromptLibraryError.invalid_document(
                        path.relative_to(self.root).as_posix(),
                        "document id does not match its filename",
                    )
            except PromptLibraryError as exc:
                diagnostics.append(self._diagnostic(path, exc))
            else:
                documents.append(document)
        return documents, diagnostics

    def _cached_read(
        self, path: Path, model_type: type[BaseModel]
    ) -> StoredDocument:
        path = path.resolve()
        if not path.is_file():
            raise PromptLibraryError.not_found("document", path.relative_to(self.root).as_posix())
        raw = path.read_bytes()
        stat = path.stat()
        etag = sha256_bytes(raw)
        with self._cache_lock:
            cached = self._cache.get(path)
            if (
                cached is not None
                and (cached.mtime_ns, cached.size, cached.etag)
                == (stat.st_mtime_ns, stat.st_size, etag)
            ):
                return cached.document
            try:
                model = model_type.model_validate_json(raw)
            except UnicodeDecodeError as exc:
                raise PromptLibraryError.invalid_document(
                    path.relative_to(self.root).as_posix(), "invalid UTF-8"
                ) from exc
            except json.JSONDecodeError as exc:
                raise PromptLibraryError.invalid_document(
                    path.relative_to(self.root).as_posix(), "invalid JSON"
                ) from exc
            except ValidationError as exc:
                reason = (
                    "invalid JSON"
                    if any(error["type"] == "json_invalid" for error in exc.errors())
                    else str(exc)
                )
                raise PromptLibraryError.invalid_document(
                    path.relative_to(self.root).as_posix(), reason
                ) from exc
            document = StoredDocument(model=model, etag=etag, path=path)
            self._cache[path] = _CacheEntry(
                mtime_ns=stat.st_mtime_ns, size=stat.st_size, etag=etag, document=document
            )
            return document

    def _validate_category_location(
        self, category: PromptCategory, path: Path, polarity: Polarity
    ) -> None:
        if category.id != path.stem:
            raise PromptLibraryError.invalid_document(
                path.relative_to(self.root).as_posix(),
                "id_filename_mismatch: document id does not match its filename",
            )
        if category.polarity != polarity:
            raise PromptLibraryError.invalid_document(
                path.relative_to(self.root).as_posix(),
                "polarity_mismatch: document polarity does not match its directory",
            )

    def _diagnostic(self, path: Path, error: PromptLibraryError):
        message = error.message
        if "invalid JSON" in message:
            code = "invalid_json"
        elif "id_filename_mismatch" in message:
            code = "id_filename_mismatch"
        elif "polarity_mismatch" in message:
            code = "polarity_mismatch"
        else:
            code = "invalid_document"
        from app.schemas.prompt_library import PromptLibraryDiagnostic

        return PromptLibraryDiagnostic(
            code=code,
            message=message,
            hint="Correct this file without changing unrelated Prompt Library documents.",
            path=path.relative_to(self.root).as_posix(),
            details=error.details,
        )

    @staticmethod
    def _category_summary(document: StoredDocument[PromptCategory]) -> CategorySummary:
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
    def _combination_summary(document: StoredDocument[PromptCombination]) -> CombinationSummary:
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
