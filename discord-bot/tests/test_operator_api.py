from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from bot.delivery import DeliveryReceipt
from bot.operator_api import OperatorConfig, OperatorDeliveryServer

JOB_ID = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"


@pytest.mark.asyncio
async def test_operator_endpoint_requires_auth_and_allowlisted_alias() -> None:
    channel = SimpleNamespace(guild=SimpleNamespace(id=123), send=AsyncMock())
    client = SimpleNamespace(get_channel=lambda channel_id: channel, fetch_channel=AsyncMock())
    delivery = SimpleNamespace(deliver=AsyncMock())
    server = OperatorDeliveryServer(
        client,
        delivery,
        OperatorConfig(token="operator-secret", destinations={"results": 456}, port=8765),
        guild_id=123,
    )
    app = __import__("aiohttp").web.Application(client_max_size=4096)
    app.router.add_post("/operator/v1/deliver-result", server._handle_delivery)

    async with TestClient(TestServer(app)) as http:
        unauthorized = await http.post(
            "/operator/v1/deliver-result",
            json={"job_id": JOB_ID, "destination_alias": "results"},
        )
        forbidden = await http.post(
            "/operator/v1/deliver-result",
            headers={"Authorization": "Bearer operator-secret"},
            json={"job_id": JOB_ID, "destination_alias": "raw-channel-id"},
        )

    assert unauthorized.status == 401
    assert forbidden.status == 403
    delivery.deliver.assert_not_awaited()


@pytest.mark.asyncio
async def test_operator_endpoint_returns_verifiable_message_ids() -> None:
    channel = SimpleNamespace(guild=SimpleNamespace(id=123), send=AsyncMock())
    client = SimpleNamespace(get_channel=lambda channel_id: channel, fetch_channel=AsyncMock())
    delivery = SimpleNamespace(
        deliver=AsyncMock(
            return_value=DeliveryReceipt(
                JOB_ID, "alias:results", ("111", "222"), 4, False
            )
        )
    )
    server = OperatorDeliveryServer(
        client,
        delivery,
        OperatorConfig(token="operator-secret", destinations={"results": 456}, port=8765),
        guild_id=123,
    )
    app = __import__("aiohttp").web.Application(client_max_size=4096)
    app.router.add_post("/operator/v1/deliver-result", server._handle_delivery)

    async with TestClient(TestServer(app)) as http:
        response = await http.post(
            "/operator/v1/deliver-result",
            headers={"Authorization": "Bearer operator-secret"},
            json={
                "job_id": JOB_ID,
                "destination_alias": "results",
                "force_resend": False,
            },
        )
        body = await response.json()

    assert response.status == 200
    assert body == {
        "ok": True,
        "job_id": JOB_ID,
        "destination_alias": "results",
        "message_ids": ["111", "222"],
        "artifact_count": 4,
        "deduplicated": False,
    }
    delivery.deliver.assert_awaited_once()
    assert delivery.deliver.await_args.args[:2] == (JOB_ID, "alias:results")
    assert delivery.deliver.await_args.kwargs["force_resend"] is False
