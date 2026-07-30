from types import SimpleNamespace

import httpx
from pydantic import SecretStr

from mcp_server.tools import discord_delivery


def test_discord_delivery_forwards_only_constrained_fields_and_returns_ids(monkeypatch) -> None:
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "job_id": "job-id",
                "destination_alias": "results",
                "message_ids": ["111", "222"],
                "artifact_count": 4,
                "deduplicated": False,
            },
        )

    monkeypatch.setattr(
        discord_delivery,
        "get_mcp_settings",
        lambda: SimpleNamespace(
            discord_operator_url="http://127.0.0.1:8765",
            discord_operator_token=SecretStr("server-secret"),
        ),
    )
    monkeypatch.setattr(discord_delivery.httpx, "post", fake_post)

    result = discord_delivery.deliver_generation_result_to_discord(
        "job-id", "results", force_resend=True
    )

    assert result == {
        "ok": True,
        "tool": "deliver_generation_result_to_discord",
        "job_id": "job-id",
        "destination_alias": "results",
        "message_ids": ["111", "222"],
        "artifact_count": 4,
        "deduplicated": False,
    }
    assert captured["json"] == {
        "job_id": "job-id",
        "destination_alias": "results",
        "force_resend": True,
    }
    assert set(captured["json"]) == {"job_id", "destination_alias", "force_resend"}


def test_discord_delivery_errors_never_expose_operator_token(monkeypatch) -> None:
    secret = "do-not-return-this-secret"
    monkeypatch.setattr(
        discord_delivery,
        "get_mcp_settings",
        lambda: SimpleNamespace(
            discord_operator_url="http://127.0.0.1:8765",
            discord_operator_token=SecretStr(secret),
        ),
    )

    def fail(*args, **kwargs):
        raise httpx.ConnectError("connection failed")

    monkeypatch.setattr(discord_delivery.httpx, "post", fail)
    result = discord_delivery.deliver_generation_result_to_discord("job", "results")

    assert result["ok"] is False
    assert result["error"]["code"] == "operator_unavailable"
    assert secret not in repr(result)
