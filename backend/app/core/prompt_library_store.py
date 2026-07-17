"""Safe, cache-aware access to folder-backed Prompt Library JSON documents."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
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
_REPARSE_POINT = 0x400
_SNAPSHOT_ATTEMPTS = 3


@dataclass(frozen=True)
class StoredDocument(Generic[DocumentModel]):
    """A validated document and the stable raw-byte snapshot that produced it."""

    model: DocumentModel
    etag: str
    path: Path
    mtime_ns: int
    size: int


@dataclass(frozen=True)
class _DocumentIssue(Exception):
    code: str
    path: str
    message: str
    details: dict[str, object]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class PromptLibraryStore:
    """The one safe enumeration, reading, validation, and diagnostic primitive."""

    def __init__(self, root: Path, lock_timeout: float = 5.0) -> None:
        self.root = Path(root).expanduser().absolute()
        self._resolved_root = self.root.resolve(strict=False)
        self.lock_timeout = lock_timeout
        self._cache: dict[Path, StoredDocument[BaseModel]] = {}
        self._cache_lock = threading.RLock()

    def category_path(self, polarity: Polarity, category_id: str) -> Path:
        if polarity not in ("positive", "negative"):
            raise PromptLibraryError.invalid_locator(str(polarity))
        return self._confined(self.root / polarity, category_id)

    def combination_path(self, combination_id: str) -> Path:
        return self._confined(self.root / "combinations", combination_id)

    def read_manifest(self) -> PromptLibraryManifest:
        return self._domain_read(self.root / "manifest.json", PromptLibraryManifest).model

    def read_category(
        self, polarity: Polarity, category_id: str
    ) -> StoredDocument[PromptCategory]:
        path = self.category_path(polarity, category_id)
        try:
            document = self._read_document(path, PromptCategory)
            self._validate_category_location(document.model, path, polarity)
            return document
        except _DocumentIssue as issue:
            raise self._as_domain_error(issue) from issue

    def read_combination(self, combination_id: str) -> StoredDocument[PromptCombination]:
        path = self.combination_path(combination_id)
        try:
            document = self._read_document(path, PromptCombination)
            self._validate_combination_location(document.model, path)
            return document
        except _DocumentIssue as issue:
            raise self._as_domain_error(issue) from issue

    def scan_categories(
        self,
    ) -> tuple[list[StoredDocument[PromptCategory]], list[PromptLibraryDiagnostic]]:
        documents: list[StoredDocument[PromptCategory]] = []
        diagnostics: list[PromptLibraryDiagnostic] = []
        for polarity in ("positive", "negative"):
            for path, issue in self._enumerate_json(self.root / polarity):
                if issue is not None:
                    diagnostics.append(self._diagnostic(issue))
                    continue
                assert path is not None
                try:
                    document = self._read_document(path, PromptCategory)
                    self._validate_category_location(document.model, path, polarity)
                except _DocumentIssue as problem:
                    diagnostics.append(self._diagnostic(problem))
                else:
                    documents.append(document)
        return documents, diagnostics

    def scan_combinations(
        self,
    ) -> tuple[list[StoredDocument[PromptCombination]], list[PromptLibraryDiagnostic]]:
        documents: list[StoredDocument[PromptCombination]] = []
        diagnostics: list[PromptLibraryDiagnostic] = []
        for path, issue in self._enumerate_json(self.root / "combinations"):
            if issue is not None:
                diagnostics.append(self._diagnostic(issue))
                continue
            assert path is not None
            try:
                document = self._read_document(path, PromptCombination)
                self._validate_combination_location(document.model, path)
            except _DocumentIssue as problem:
                diagnostics.append(self._diagnostic(problem))
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
        path = Path(path).absolute()
        try:
            self._assert_safe_write_path(path)
        except _DocumentIssue as issue:
            raise self._as_domain_error(issue) from issue
        raw = (
            json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        try:
            type(model).model_validate_json(raw)
        except ValidationError as exc:
            raise PromptLibraryError.invalid_document(self._locator(path), str(exc)) from exc

        temporary_path: Path | None = None
        try:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._assert_safe_directory(path.parent, self._locator(path.parent))
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
            except OSError:
                raise
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        with self._cache_lock:
            self._cache.pop(path, None)
        return sha256_bytes(raw)

    def _domain_read(
        self, path: Path, model_type: type[DocumentModel]
    ) -> StoredDocument[DocumentModel]:
        try:
            return self._read_document(path, model_type)
        except _DocumentIssue as issue:
            raise self._as_domain_error(issue) from issue

    def _read_document(
        self, path: Path, model_type: type[DocumentModel]
    ) -> StoredDocument[DocumentModel]:
        path = Path(path).absolute()
        with self._cache_lock:
            raw, mtime_ns, size = self._stable_snapshot(path)
            etag = sha256_bytes(raw)
            cached = self._cache.get(path)
            if (
                cached is not None
                and type(cached.model) is model_type
                and (cached.mtime_ns, cached.size, cached.etag) == (mtime_ns, size, etag)
            ):
                return cached  # type: ignore[return-value]
            model = self._parse(path, raw, model_type)
            document = StoredDocument(
                model=model, etag=etag, path=path, mtime_ns=mtime_ns, size=size
            )
            self._cache[path] = document
            return document

    def _stable_snapshot(self, path: Path) -> tuple[bytes, int, int]:
        locator = self._locator(path)
        for _ in range(_SNAPSHOT_ATTEMPTS):
            self._assert_safe_file(path, locator)
            try:
                before = path.stat()
                first_raw = path.read_bytes()
                self._assert_safe_file(path, locator)
                middle = path.stat()
                second_raw = path.read_bytes()
                self._assert_safe_file(path, locator)
                after = path.stat()
            except FileNotFoundError as exc:
                raise _DocumentIssue("not_found", locator, "document was not found", {}) from exc
            except OSError as exc:
                raise _DocumentIssue("io_error", locator, str(exc), {}) from exc
            if (
                first_raw == second_raw
                and before.st_mtime_ns == middle.st_mtime_ns == after.st_mtime_ns
                and before.st_size == middle.st_size == after.st_size
                and after.st_size == len(second_raw)
            ):
                return second_raw, after.st_mtime_ns, after.st_size
        raise _DocumentIssue(
            "unstable_snapshot",
            locator,
            "file changed while it was being read; retry the operation",
            {},
        )

    def _parse(
        self, path: Path, raw: bytes, model_type: type[DocumentModel]
    ) -> DocumentModel:
        try:
            return model_type.model_validate_json(raw)
        except ValidationError as exc:
            code = "invalid_json" if any(
                error["type"] == "json_invalid" for error in exc.errors()
            ) else "invalid_document"
            message = "invalid JSON" if code == "invalid_json" else str(exc)
            raise _DocumentIssue(code, self._locator(path), message, {}) from exc

    def _enumerate_json(self, parent: Path) -> list[tuple[Path | None, _DocumentIssue | None]]:
        locator = self._locator(parent)
        try:
            self._assert_safe_directory(parent, locator)
            if not parent.exists():
                return []
            files = sorted(parent.glob("*.json"), key=lambda item: item.name)
        except _DocumentIssue as issue:
            return [(None, issue)]
        except OSError as exc:
            return [(None, _DocumentIssue("io_error", locator, str(exc), {}))]
        return [(path, None) for path in files]

    def _confined(self, parent: Path, resource_id: str) -> Path:
        if re.fullmatch(SLUG_PATTERN, resource_id) is None:
            raise PromptLibraryError.invalid_locator(resource_id)
        candidate = parent / f"{resource_id}.json"
        try:
            self._assert_safe_directory(parent, self._locator(parent))
            self._assert_lexically_within_root(candidate)
        except _DocumentIssue as issue:
            raise self._as_domain_error(issue) from issue
        return candidate.absolute()

    def _validate_category_location(
        self, category: PromptCategory, path: Path, polarity: Polarity
    ) -> None:
        if category.id != path.stem:
            raise _DocumentIssue(
                "id_filename_mismatch",
                self._locator(path),
                "document id does not match its filename",
                {"document_id": category.id, "filename_id": path.stem},
            )
        if category.polarity != polarity:
            raise _DocumentIssue(
                "polarity_mismatch",
                self._locator(path),
                "document polarity does not match its directory",
                {"document_polarity": category.polarity, "directory_polarity": polarity},
            )

    def _validate_combination_location(
        self, combination: PromptCombination, path: Path
    ) -> None:
        if combination.id != path.stem:
            raise _DocumentIssue(
                "id_filename_mismatch",
                self._locator(path),
                "document id does not match its filename",
                {"document_id": combination.id, "filename_id": path.stem},
            )

    def _assert_safe_write_path(self, path: Path) -> None:
        self._assert_lexically_within_root(path)
        self._assert_safe_directory(path.parent, self._locator(path.parent))
        if path.exists():
            self._assert_safe_file(path, self._locator(path))

    def _assert_safe_file(self, path: Path, locator: str) -> None:
        self._assert_safe_directory(path.parent, self._locator(path.parent))
        try:
            status = path.lstat()
        except FileNotFoundError as exc:
            raise _DocumentIssue("not_found", locator, "document was not found", {}) from exc
        except OSError as exc:
            raise _DocumentIssue("io_error", locator, str(exc), {}) from exc
        if self._is_reparse_point(path, status):
            raise _DocumentIssue("unsafe_path", locator, "symbolic links are not allowed", {})
        try:
            if not path.is_file():
                raise _DocumentIssue("not_found", locator, "document was not found", {})
            path.resolve(strict=True).relative_to(self._resolved_root)
        except _DocumentIssue:
            raise
        except (OSError, ValueError) as exc:
            raise _DocumentIssue("unsafe_path", locator, "path escapes the Prompt Library root", {}) from exc

    def _assert_safe_directory(self, path: Path, locator: str) -> None:
        path = Path(path).absolute()
        self._assert_lexically_within_root(path)
        try:
            relative_parts = path.relative_to(self.root).parts
        except ValueError as exc:  # pragma: no cover - guarded above
            raise _DocumentIssue("unsafe_path", locator, "path escapes the Prompt Library root", {}) from exc

        current = self.root
        for part in relative_parts:
            current /= part
            try:
                status = current.lstat()
            except FileNotFoundError:
                try:
                    current.resolve(strict=False).relative_to(self._resolved_root)
                except (OSError, ValueError) as exc:
                    raise _DocumentIssue(
                        "unsafe_path", locator, "path escapes the Prompt Library root", {}
                    ) from exc
                continue
            except OSError as exc:
                raise _DocumentIssue("io_error", locator, str(exc), {}) from exc
            if self._is_reparse_point(current, status):
                raise _DocumentIssue(
                    "unsafe_path", locator, "linked directories are not allowed", {}
                )
            try:
                if not current.is_dir():
                    raise _DocumentIssue("unsafe_path", locator, "expected a directory", {})
                current.resolve(strict=True).relative_to(self._resolved_root)
            except _DocumentIssue:
                raise
            except (OSError, ValueError) as exc:
                raise _DocumentIssue(
                    "unsafe_path", locator, "path escapes the Prompt Library root", {}
                ) from exc

    @staticmethod
    def _is_reparse_point(path: Path, status: os.stat_result) -> bool:
        return path.is_symlink() or bool(
            getattr(status, "st_file_attributes", 0) & _REPARSE_POINT
        )

    def _assert_lexically_within_root(self, path: Path) -> None:
        try:
            path.absolute().relative_to(self.root)
        except ValueError as exc:
            raise _DocumentIssue(
                "unsafe_path", self._locator(path), "path escapes the Prompt Library root", {}
            ) from exc

    def _locator(self, path: Path) -> str:
        try:
            return path.absolute().relative_to(self.root).as_posix()
        except ValueError:
            return path.name

    @staticmethod
    def _as_domain_error(issue: _DocumentIssue) -> PromptLibraryError:
        if issue.code == "not_found":
            return PromptLibraryError.not_found("document", issue.path)
        error = PromptLibraryError.invalid_document(issue.path, issue.message)
        error.details.update(issue.details)
        error.details["diagnostic_code"] = issue.code
        return error

    @staticmethod
    def _diagnostic(issue: _DocumentIssue) -> PromptLibraryDiagnostic:
        return PromptLibraryDiagnostic(
            code=issue.code,
            message=issue.message,
            hint="Correct this file without changing unrelated Prompt Library documents.",
            path=issue.path,
            details=issue.details,
        )
