"""Safe, typed access to the folder-backed Prompt Library documents."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from filelock import FileLock, Timeout
from pydantic import BaseModel, ValidationError

from app.core.prompt_library_errors import PromptLibraryError
from app.core.prompt_library_models import (
    SLUG_PATTERN,
    Polarity,
    PromptCategory,
    PromptCombination,
    PromptLibraryManifest,
)
from app.schemas.prompt_library import PromptLibraryDiagnostic


DocumentModel = TypeVar("DocumentModel", bound=BaseModel)


@dataclass(frozen=True)
class StoredDocument(Generic[DocumentModel]):
    """A parsed JSON document together with the raw-byte concurrency token."""

    model: DocumentModel
    etag: str
    path: Path


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class PromptLibraryStore:
    def __init__(self, root: Path, lock_timeout: float = 5.0) -> None:
        self.root = root.resolve()
        self.lock_timeout = lock_timeout

    def category_path(self, polarity: Polarity, category_id: str) -> Path:
        return self._confined(self.root / polarity, category_id)

    def combination_path(self, combination_id: str) -> Path:
        return self._confined(self.root / "combinations", combination_id)

    def read_manifest(self) -> PromptLibraryManifest:
        return self._read_model(self.root / "manifest.json", PromptLibraryManifest).model

    def read_category(
        self, polarity: Polarity, category_id: str
    ) -> StoredDocument[PromptCategory]:
        path = self.category_path(polarity, category_id)
        document = self._read_model(path, PromptCategory)
        try:
            self._validate_category_location(document.model, path, polarity)
        except _LocationMismatch as exc:
            raise PromptLibraryError.invalid_document(self._relative(path), exc.reason) from exc
        return document

    def read_combination(self, combination_id: str) -> StoredDocument[PromptCombination]:
        path = self.combination_path(combination_id)
        document = self._read_model(path, PromptCombination)
        if document.model.id != path.stem:
            raise PromptLibraryError.invalid_document(
                self._relative(path), "document id does not match its filename"
            )
        return document

    def scan_categories(
        self,
    ) -> tuple[list[StoredDocument[PromptCategory]], list[PromptLibraryDiagnostic]]:
        documents: list[StoredDocument[PromptCategory]] = []
        diagnostics: list[PromptLibraryDiagnostic] = []
        for polarity in ("positive", "negative"):
            parent = self.root / polarity
            for path in self._json_files(parent):
                try:
                    document = self._read_model(path, PromptCategory)
                    self._validate_category_location(document.model, path, polarity)
                except _LocationMismatch as exc:
                    diagnostics.append(self._diagnostic(exc.code, path, exc.reason))
                except PromptLibraryError as exc:
                    diagnostics.append(self._diagnostic_for_error(path, exc))
                else:
                    documents.append(document)
        return documents, diagnostics

    def scan_combinations(
        self,
    ) -> tuple[list[StoredDocument[PromptCombination]], list[PromptLibraryDiagnostic]]:
        documents: list[StoredDocument[PromptCombination]] = []
        diagnostics: list[PromptLibraryDiagnostic] = []
        for path in self._json_files(self.root / "combinations"):
            try:
                document = self._read_model(path, PromptCombination)
                if document.model.id != path.stem:
                    raise _LocationMismatch(
                        "id_filename_mismatch", "document id does not match its filename"
                    )
            except _LocationMismatch as exc:
                diagnostics.append(self._diagnostic(exc.code, path, exc.reason))
            except PromptLibraryError as exc:
                diagnostics.append(self._diagnostic_for_error(path, exc))
            else:
                documents.append(document)
        return documents, diagnostics

    @contextmanager
    def locked(self) -> Generator[None, None, None]:
        lock = FileLock(self.root / ".lock", timeout=self.lock_timeout)
        try:
            with lock:
                yield
        except Timeout as exc:
            raise PromptLibraryError.lock_timeout(self.lock_timeout) from exc

    def replace_json(self, path: Path, model: BaseModel) -> str:
        path = path.resolve()
        self._ensure_within_root(path)
        if path.suffix != ".json":
            raise PromptLibraryError.invalid_locator(path.name)

        raw = (
            json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n"
        ).encode("utf-8")
        try:
            type(model).model_validate_json(raw)
        except ValidationError as exc:
            raise PromptLibraryError.invalid_document(self._relative(path), str(exc)) from exc

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(raw)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return sha256_bytes(raw)

    def _confined(self, parent: Path, resource_id: str) -> Path:
        if re.fullmatch(SLUG_PATTERN, resource_id) is None:
            raise PromptLibraryError.invalid_locator(resource_id)
        candidate = (parent / f"{resource_id}.json").resolve()
        try:
            candidate.relative_to(parent.resolve())
        except ValueError as exc:
            raise PromptLibraryError.invalid_locator(resource_id) from exc
        self._ensure_within_root(candidate)
        return candidate

    def _read_model(
        self, path: Path, model_type: type[DocumentModel]
    ) -> StoredDocument[DocumentModel]:
        self._ensure_within_root(path)
        if not path.is_file():
            raise PromptLibraryError.not_found("document", self._relative(path))
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise PromptLibraryError.invalid_document(self._relative(path), str(exc)) from exc
        try:
            model = model_type.model_validate_json(raw)
        except UnicodeDecodeError as exc:
            raise PromptLibraryError.invalid_document(self._relative(path), "invalid UTF-8") from exc
        except json.JSONDecodeError as exc:
            raise PromptLibraryError.invalid_document(self._relative(path), "invalid JSON") from exc
        except ValidationError as exc:
            if any(error["type"] == "json_invalid" for error in exc.errors()):
                raise PromptLibraryError.invalid_document(
                    self._relative(path), "invalid JSON"
                ) from exc
            raise PromptLibraryError.invalid_document(self._relative(path), str(exc)) from exc
        return StoredDocument(model=model, etag=sha256_bytes(raw), path=path)

    def _validate_category_location(
        self, category: PromptCategory, path: Path, polarity: Polarity
    ) -> None:
        if category.id != path.stem:
            raise _LocationMismatch(
                "id_filename_mismatch", "document id does not match its filename"
            )
        if category.polarity != polarity:
            raise _LocationMismatch(
                "polarity_mismatch", "document polarity does not match its directory"
            )

    def _json_files(self, parent: Path) -> list[Path]:
        if not parent.is_dir():
            return []
        return sorted((path for path in parent.glob("*.json") if path.is_file()), key=lambda p: p.name)

    def _ensure_within_root(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self.root)
        except ValueError as exc:
            raise PromptLibraryError.invalid_locator(str(path)) from exc

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def _diagnostic_for_error(
        self, path: Path, error: PromptLibraryError
    ) -> PromptLibraryDiagnostic:
        code = "invalid_json" if "invalid JSON" in error.message else "invalid_document"
        return self._diagnostic(code, path, error.message, error.details)

    def _diagnostic(
        self,
        code: str,
        path: Path,
        message: str,
        details: dict[str, object] | None = None,
    ) -> PromptLibraryDiagnostic:
        return PromptLibraryDiagnostic(
            code=code,
            message=message,
            hint="Correct this file without changing unrelated Prompt Library documents.",
            path=self._relative(path),
            details=details or {},
        )


class _LocationMismatch(Exception):
    def __init__(self, code: str, reason: str) -> None:
        self.code = code
        self.reason = reason
