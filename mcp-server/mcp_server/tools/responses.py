"""Common MCP envelopes and Backend error projection, with adapter serializers."""
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
    result = backend_error_payload(tool, exc, where=where)
    result["error"]["details"].update(details or {})
    result.update(extra)
    return result


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


# Public MCP envelopes. Adapters can keep their domain projections; registration
# applies this contract once, after the real adapter has run.
ERROR_HINTS = {
    "backend_http_error": "Inspect the HTTP status and correct the request before retrying.",
    "backend_unavailable": "Check service availability; inspect an existing job ID before resubmitting a timed-out request.",
    "request_validation_failed": "Correct the listed arguments and retry.",
    "invalid_json": "Provide a valid JSON workflow object string.",
    "generation_failed": "Inspect job and node errors before submitting a corrected request; never fall back from worker to local automatically.",
    "job_not_found": "Check the existing job ID and its status before submitting another request.",
    "tool_execution_failed": "Inspect the operation failure before retrying; admission may be uncertain for a write.",
}


def backend_error_payload(tool: str, exc: Exception, *, where: str = "backend") -> dict[str, Any]:
    """Common HTTP/connection projection; domain adapters may further restrict it."""
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            body = exc.response.json()
        except (ValueError, RecursionError):
            body = None
        detail = body.get("detail", body) if isinstance(body, dict) else None
        code, message, hint, details = "backend_http_error", f"HTTP {status}: service request failed", ERROR_HINTS["backend_http_error"], {}
        # Structured Backend contracts use code/message/hint/details. Do not
        # project arbitrary legacy `error` strings (revision has an allowlist).
        if isinstance(detail, dict) and isinstance(detail.get("code"), str):
            code = detail["code"]
            message = str(detail.get("message") or message)
            hint = str(detail.get("hint") or hint)
            details = dict(detail.get("details") or {}) if isinstance(detail.get("details", {}), dict) else {"backend_details": detail.get("details")}
        elif status == 422 and isinstance(detail, list):
            code = "request_validation_failed"
            hint = ERROR_HINTS[code]
            details = {"validation_errors": [{k: entry[k] for k in ("loc", "msg", "type") if k in entry} for entry in detail if isinstance(entry, dict)]}
        result = error_payload(tool, code, message, details=details if isinstance(details, dict) else {"backend_details": details})
        result["error"]["hint"] = hint
        result["status_code"] = status
        return result
    code = "backend_unavailable" if isinstance(exc, httpx.RequestError) else "tool_execution_failed"
    result = error_payload(tool, code, "Service connection failed" if code == "backend_unavailable" else str(exc), details={"where": where})
    result["error"]["hint"] = ERROR_HINTS[code]
    return result


def envelope(result: Any) -> dict[str, Any]:
    """Normalize adapter results without dropping metadata or recovery state."""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return {"ok": True, "data": result}
    if not isinstance(result, dict):
        return {"ok": True, "data": result}
    if result.get("ok") is False:
        error = dict(result.get("error") or {})
        details = dict(error.get("details") or {})
        details.update({key: value for key, value in result.items() if key not in {"ok", "tool", "error"}})
        code = error.get("code") or "tool_execution_failed"
        if isinstance(code, str) and code.startswith("http_") and code[5:].isdigit():
            code = "backend_http_error"
        status = details.get("status_code")
        if status is not None and str(status) not in str(error.get("message", "")):
            error["message"] = f"HTTP {status}: {error.get('message') or 'service request failed'}"
        error.update(code=code, message=str(error.get("message") or "Operation failed"),
                     hint=error.get("hint") or details.get("hint") or ERROR_HINTS.get(code, "Inspect the error details and correct the request before retrying."))
        if details:
            error["details"] = details
        return {"ok": False, "error": error}
    data = {key: value for key, value in result.items() if key not in {"ok", "tool"}}
    if set(data) == {"data"}:
        data = data["data"]
    return {"ok": True, "data": data}
