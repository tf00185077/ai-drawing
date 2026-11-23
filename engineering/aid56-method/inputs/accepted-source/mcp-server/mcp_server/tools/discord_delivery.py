"""Constrained operator escape-hatch for Discord generation-result delivery."""
from __future__ import annotations

from typing import Any

import httpx

from mcp_server.config import get_mcp_settings
from mcp_server.server import mcp


@mcp.tool()
def deliver_generation_result_to_discord(
    job_id: str,
    destination_alias: str,
    force_resend: bool = False,
) -> dict[str, Any]:
    """Deliver one completed generation job to an allowlisted Discord destination alias.

    This cannot send arbitrary files, text, or channel IDs, and never regenerates or
    mutates the job. Repeated requests are deduplicated unless force_resend is true.
    Success returns the Discord message IDs reported by the bot.
    """
    settings = get_mcp_settings()
    if settings.discord_operator_token is None:
        return _error(
            "operator_not_configured",
            "Discord operator delivery is not configured",
            "set MCP_DISCORD_OPERATOR_TOKEN in the MCP server environment",
        )
    payload = {
        "job_id": job_id,
        "destination_alias": destination_alias,
        "force_resend": force_resend,
    }
    try:
        response = httpx.post(
            f"{settings.discord_operator_url.rstrip('/')}/operator/v1/deliver-result",
            json=payload,
            headers={
                "Authorization": (
                    f"Bearer {settings.discord_operator_token.get_secret_value()}"
                )
            },
            timeout=30.0,
        )
    except httpx.HTTPError:
        return _error(
            "operator_unavailable",
            "Discord operator endpoint is unavailable",
            "ensure the Discord bot operator endpoint is running on loopback",
        )

    try:
        body = response.json()
    except ValueError:
        return _error(
            "invalid_operator_response",
            "Discord operator returned an invalid response",
            "inspect the Discord bot logs",
        )
    if not isinstance(body, dict):
        return _error(
            "invalid_operator_response",
            "Discord operator returned an invalid response",
            "inspect the Discord bot logs",
        )
    if response.is_success and body.get("ok") is True:
        message_ids = body.get("message_ids")
        if not isinstance(message_ids, list) or not all(
            isinstance(item, str) for item in message_ids
        ):
            return _error(
                "invalid_operator_response",
                "Discord operator omitted verifiable message IDs",
                "inspect the Discord bot logs",
            )
        artifact_count = body.get("artifact_count")
        if type(artifact_count) is not int or artifact_count < 0:
            return _error(
                "invalid_operator_response",
                "Discord operator omitted the delivered artifact count",
                "inspect the Discord bot logs",
            )
        return {
            "ok": True,
            "tool": "deliver_generation_result_to_discord",
            "job_id": body.get("job_id"),
            "destination_alias": body.get("destination_alias"),
            "message_ids": message_ids,
            "artifact_count": artifact_count,
            "deduplicated": body.get("deduplicated") is True,
        }

    remote_error = body.get("error")
    code = remote_error.get("code") if isinstance(remote_error, dict) else None
    message = remote_error.get("message") if isinstance(remote_error, dict) else None
    return _error(
        code if isinstance(code, str) else "operator_request_failed",
        message if isinstance(message, str) else "Discord operator rejected delivery",
        "correct the job ID or use a configured destination alias, then retry",
        status_code=response.status_code,
    )


def _error(
    code: str,
    message: str,
    hint: str,
    *,
    status_code: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "tool": "deliver_generation_result_to_discord",
        "error": {"code": code, "message": message, "hint": hint},
    }
    if status_code is not None:
        result["status_code"] = status_code
    return result
