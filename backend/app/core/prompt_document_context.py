"""Opaque, fail-safe tokens for blocked Prompt Library document resolution."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import Literal

from app.core.prompt_library_errors import PromptLibraryError
from app.schemas.prompt_library_migration import BlockingDocumentDiagnostic


class PromptDocumentContextCodec:
    """Process-local signer; restart invalidates outstanding tokens fail-safely."""

    def __init__(self, key: bytes | None = None) -> None:
        self._key = key or secrets.token_bytes(32)

    def issue_document_context(
        self, diagnostics: list[BlockingDocumentDiagnostic]
    ) -> str:
        if not diagnostics:
            raise ValueError("document context requires blocking diagnostics")
        first = diagnostics[0]
        return self._encode(
            {
                "kind": "document_context",
                "combination_id": first.combination_id,
                "revision": first.revision,
                "etag": first.etag,
                "diagnostic_ids": [item.id for item in diagnostics],
                "atom_hashes": [
                    digest
                    for item in diagnostics
                    for digest in item.fallback_atom_hashes
                ],
            }
        )

    def issue_literal_conversion(
        self,
        document_context_token: str,
        diagnostics: list[BlockingDocumentDiagnostic],
    ) -> str:
        context = self.validate_document_context(
            document_context_token, diagnostics
        )
        return self._encode(
            {
                "kind": "literal_conversion",
                "document_context_sha256": hashlib.sha256(
                    document_context_token.encode("utf-8")
                ).hexdigest(),
                **{
                    key: context[key]
                    for key in (
                        "combination_id",
                        "revision",
                        "etag",
                        "diagnostic_ids",
                        "atom_hashes",
                    )
                },
            }
        )

    def validate_document_context(
        self,
        token: str,
        diagnostics: list[BlockingDocumentDiagnostic],
    ) -> dict[str, object]:
        payload = self._decode(token, expected_kind="document_context")
        self._validate_bound_payload(payload, diagnostics)
        return payload

    def validate_literal_conversion(
        self,
        token: str,
        document_context_token: str,
        diagnostics: list[BlockingDocumentDiagnostic],
    ) -> None:
        self.validate_document_context(document_context_token, diagnostics)
        payload = self._decode(token, expected_kind="literal_conversion")
        self._validate_bound_payload(payload, diagnostics)
        expected_context_hash = hashlib.sha256(
            document_context_token.encode("utf-8")
        ).hexdigest()
        if payload.get("document_context_sha256") != expected_context_hash:
            raise self._invalid_token()

    def _encode(self, payload: dict[str, object]) -> str:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        signature = hmac.new(self._key, raw, hashlib.sha256).digest()
        return ".".join((self._b64(raw), self._b64(signature)))

    def _decode(
        self,
        token: str,
        *,
        expected_kind: Literal["document_context", "literal_conversion"],
    ) -> dict[str, object]:
        try:
            raw_token, raw_signature = token.split(".", 1)
            raw = self._unb64(raw_token)
            signature = self._unb64(raw_signature)
            expected = hmac.new(self._key, raw, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("signature mismatch")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or payload.get("kind") != expected_kind:
                raise ValueError("token kind mismatch")
            return payload
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise self._invalid_token() from exc

    @staticmethod
    def _validate_bound_payload(
        payload: dict[str, object],
        diagnostics: list[BlockingDocumentDiagnostic],
    ) -> None:
        if not diagnostics:
            raise PromptDocumentContextCodec._invalid_token()
        first = diagnostics[0]
        expected = {
            "combination_id": first.combination_id,
            "revision": first.revision,
            "etag": first.etag,
            "diagnostic_ids": [item.id for item in diagnostics],
            "atom_hashes": [
                digest
                for item in diagnostics
                for digest in item.fallback_atom_hashes
            ],
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise PromptDocumentContextCodec._invalid_token()

    @staticmethod
    def _b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @staticmethod
    def _unb64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    @staticmethod
    def _invalid_token() -> PromptLibraryError:
        return PromptLibraryError(
            code="invalid_document_resolution_token",
            message="The Prompt Library document resolution token is invalid or stale.",
            hint="Reload the blocked document and repeat the explicit resolution action.",
            status_code=409,
        )
