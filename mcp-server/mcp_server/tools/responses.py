"""Shared response helpers for MCP tools that return JSON strings."""
from __future__ import annotations

import json
from typing import Any


def error_payload(
    tool: str,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "tool": tool,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
    payload.update(extra)
    return payload


def exception_error_payload(
    tool: str,
    exc: Exception,
    *,
    where: str,
    details: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    merged_details = dict(details or {})
    merged_details.setdefault("where", where)
    return error_payload(
        tool,
        exc.__class__.__name__,
        str(exc),
        details=merged_details,
        **extra,
    )


def error_json(
    tool: str,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    **extra: Any,
) -> str:
    return json.dumps(
        error_payload(tool, code, message, details=details, **extra),
        ensure_ascii=False,
    )


def exception_error_json(
    tool: str,
    exc: Exception,
    *,
    where: str,
    details: dict[str, Any] | None = None,
    **extra: Any,
) -> str:
    return json.dumps(
        exception_error_payload(tool, exc, where=where, details=details, **extra),
        ensure_ascii=False,
    )
