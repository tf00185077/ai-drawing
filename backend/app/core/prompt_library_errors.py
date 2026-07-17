"""Domain errors returned by the Prompt Library service."""

from __future__ import annotations


class PromptLibraryError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        hint: str,
        status_code: int,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.status_code = status_code
        self.details = details or {}

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "details": self.details,
        }

    @classmethod
    def not_found(cls, resource_type: str, resource_id: str) -> "PromptLibraryError":
        return cls(
            code="not_found",
            message=f"{resource_type} '{resource_id}' was not found",
            hint="Reload the prompt library and choose an existing resource.",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )

    @classmethod
    def invalid_locator(cls, resource_id: str) -> "PromptLibraryError":
        return cls(
            code="invalid_locator",
            message="Prompt Library resource id must be a lowercase kebab-case slug",
            hint="Use a lowercase id containing only letters, digits, and single hyphens.",
            status_code=400,
            details={"resource_id": resource_id},
        )

    @classmethod
    def revision_conflict(
        cls, expected_revision: int, actual_revision: int | None
    ) -> "PromptLibraryError":
        return cls(
            code="revision_conflict",
            message="The Prompt Library revision no longer matches the requested revision",
            hint="Reload the resource, merge the latest changes, and retry.",
            status_code=409,
            details={
                "expected_revision": expected_revision,
                "actual_revision": actual_revision,
            },
        )

    @classmethod
    def external_change(
        cls, expected_etag: str | None, actual_etag: str | None
    ) -> "PromptLibraryError":
        return cls(
            code="external_change",
            message="Prompt Library file bytes changed outside this request",
            hint="Reload the resource before retrying the write.",
            status_code=409,
            details={"expected_etag": expected_etag, "actual_etag": actual_etag},
        )

    @classmethod
    def invalid_document(cls, path: str, reason: str) -> "PromptLibraryError":
        return cls(
            code="invalid_document",
            message=f"Prompt Library document '{path}' is invalid: {reason}",
            hint="Correct the JSON document and validate it against the Prompt Library schema.",
            status_code=422,
            details={"path": path, "reason": reason},
        )

    @classmethod
    def lock_timeout(cls, timeout: float) -> "PromptLibraryError":
        return cls(
            code="lock_timeout",
            message="Timed out waiting for the Prompt Library write lock",
            hint="Retry after the current Prompt Library write completes.",
            status_code=423,
            details={"timeout": timeout},
        )
