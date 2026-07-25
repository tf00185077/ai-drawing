"""Fail-closed control plane for the comma-atomic Prompt Library migration."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from filelock import FileLock, Timeout

from app.core.prompt_library_errors import PromptLibraryError
from app.schemas.prompt_library_migration import (
    CommaAtomicMarker,
    CommaAtomicMigrationStatus,
)


MARKER_NAME = ".comma-atomic-migration.json"
LOCK_NAME = ".prompt-library.lock"
LOCK_DIRECTORY = "ai-drawing-prompt-library-locks"


@dataclass(frozen=True)
class MigrationPrivilege:
    """Opaque in-process capability created only by the local migration CLI."""

    nonce: str


def issue_local_migration_privilege() -> MigrationPrivilege:
    return MigrationPrivilege(nonce=secrets.token_urlsafe(32))


class CommaAtomicMigrationControl:
    def __init__(self, root: Path, *, lock_timeout: float = 5.0) -> None:
        self.root = root.resolve()
        self.marker_path = self.root / MARKER_NAME
        root_digest = hashlib.sha256(
            os.fsencode(self.root)
        ).hexdigest()
        self.lock_path = (
            Path(tempfile.gettempdir())
            / LOCK_DIRECTORY
            / f"{root_digest}{LOCK_NAME}"
        )
        self.lock_timeout = lock_timeout
        self._issued_privileges: set[str] = set()

    def issue_privilege(self) -> MigrationPrivilege:
        privilege = issue_local_migration_privilege()
        self._issued_privileges.add(privilege.nonce)
        return privilege

    def bootstrap(self) -> CommaAtomicMigrationStatus:
        """Create the marker before provider initialization for every legacy manifest."""
        if self.marker_path.exists():
            return self.status()
        manifest_path = self.root / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return CommaAtomicMigrationStatus(
                state="finalized",
                marker_present=False,
                comma_atomic_ready=False,
                atomic_enforcement_active=False,
            )
        if (
            manifest.get("comma_atomic_migration_required") is True
            or manifest.get("schema_version") == 1
        ):
            self.write_marker(
                CommaAtomicMarker(state="required"),
                bootstrap=True,
            )
            return self.status()
        ready = (
            manifest.get("schema_version") == 2
            and manifest.get("comma_atomic_version") == 1
            and manifest.get("comma_atomic_migration_required") is False
        )
        return CommaAtomicMigrationStatus(
            state="finalized",
            marker_present=False,
            comma_atomic_ready=ready,
            atomic_enforcement_active=ready,
            data_validated=ready,
        )

    def status(self) -> CommaAtomicMigrationStatus:
        if self.marker_path.exists():
            marker = self.read_marker()
            return CommaAtomicMigrationStatus(
                state=marker.state,
                marker_present=True,
                comma_atomic_ready=False,
                atomic_enforcement_active=marker.atomic_enforcement_active,
                run_id=marker.run_id,
                data_validated=marker.data_validated,
            )
        manifest_path = self.root / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            manifest = {}
        ready = (
            manifest.get("schema_version") == 2
            and manifest.get("comma_atomic_version") == 1
            and manifest.get("comma_atomic_migration_required") is False
        )
        return CommaAtomicMigrationStatus(
            state="finalized",
            marker_present=False,
            comma_atomic_ready=ready,
            atomic_enforcement_active=ready,
            data_validated=ready,
        )

    def guard_ordinary_operation(self) -> None:
        """Reject before an ordinary caller can touch catalog documents or caches."""
        if not self.marker_path.exists():
            return
        marker = self.read_marker()
        raise PromptLibraryError.migration_unavailable(
            state=marker.state,
            run_id=marker.run_id,
            atomic_enforcement_active=marker.atomic_enforcement_active,
        )

    def read_marker(self) -> CommaAtomicMarker:
        try:
            return CommaAtomicMarker.model_validate_json(
                self.marker_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise PromptLibraryError(
                code="comma_atomic_migration_control_invalid",
                message="The comma-atomic migration control marker is invalid.",
                hint="Use the privileged migration recovery command; ordinary access remains blocked.",
                status_code=503,
                details={"marker": MARKER_NAME},
            ) from exc

    @contextmanager
    def locked(
        self, privilege: MigrationPrivilege
    ) -> Generator[CommaAtomicMarker | None, None, None]:
        if privilege.nonce not in self._issued_privileges:
            raise PromptLibraryError(
                code="migration_privilege_required",
                message="Operator migration privilege is required.",
                hint="Run the local comma-atomic migration CLI as an authorized operator.",
                status_code=403,
            )
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self.lock_path), timeout=self.lock_timeout)
        try:
            with lock:
                marker = self.read_marker() if self.marker_path.exists() else None
                yield marker
        except Timeout as exc:
            raise PromptLibraryError.lock_timeout(self.lock_timeout) from exc

    def write_marker(
        self,
        marker: CommaAtomicMarker,
        *,
        privilege: MigrationPrivilege | None = None,
        bootstrap: bool = False,
    ) -> None:
        if not bootstrap:
            if privilege is None or privilege.nonce not in self._issued_privileges:
                raise PromptLibraryError(
                    code="migration_privilege_required",
                    message="Operator migration privilege is required.",
                    hint="Run the local comma-atomic migration CLI as an authorized operator.",
                    status_code=403,
                )
        self.root.mkdir(parents=True, exist_ok=True)
        raw = (
            json.dumps(marker.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n"
        ).encode("utf-8")
        temporary = self.root / f".{MARKER_NAME}.{os.getpid()}.tmp"
        try:
            with temporary.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.marker_path)
        finally:
            temporary.unlink(missing_ok=True)
