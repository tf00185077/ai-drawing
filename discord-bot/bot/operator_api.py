"""Loopback-only operator API for constrained generation-result delivery."""
from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Mapping, cast

import discord
from aiohttp import web

from .delivery import DeliveryError, ResultDeliveryService, SendMessage
from .main_types import normalize_job_id


@dataclass(frozen=True)
class OperatorConfig:
    token: str
    destinations: Mapping[str, int]
    port: int


class OperatorDeliveryServer:
    """Accept only authenticated job+alias delivery requests; no generic send API."""

    def __init__(
        self,
        client: discord.Client,
        delivery: ResultDeliveryService,
        config: OperatorConfig,
        guild_id: int,
    ) -> None:
        self._client = client
        self._delivery = delivery
        self._config = config
        self._guild_id = guild_id
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        if self._runner is not None:
            return
        app = web.Application(client_max_size=4096)
        app.router.add_post("/operator/v1/deliver-result", self._handle_delivery)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self._config.port)
        await site.start()

    async def close(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _handle_delivery(self, request: web.Request) -> web.Response:
        supplied = request.headers.get("Authorization", "")
        expected = f"Bearer {self._config.token}"
        if not hmac.compare_digest(supplied, expected):
            return self._error("unauthorized", "operator authentication failed", 401)
        try:
            payload = await request.json()
        except Exception:
            return self._error("invalid_request", "request body must be JSON", 400)
        if not isinstance(payload, dict) or set(payload) - {"job_id", "destination_alias", "force_resend"}:
            return self._error("invalid_request", "only job_id, destination_alias, and force_resend are accepted", 400)

        job_id = normalize_job_id(payload.get("job_id")) if isinstance(payload.get("job_id"), str) else None
        alias = payload.get("destination_alias")
        force_resend = payload.get("force_resend", False)
        if job_id is None:
            return self._error("invalid_job_id", "job_id must be exactly one UUID", 400)
        if not isinstance(alias, str) or alias not in self._config.destinations:
            return self._error("destination_not_allowed", "destination alias is not allowlisted", 403)
        if not isinstance(force_resend, bool):
            return self._error("invalid_request", "force_resend must be a boolean", 400)

        channel_id = self._config.destinations[alias]
        channel = self._client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self._client.fetch_channel(channel_id)
            except discord.DiscordException:
                return self._error("destination_unavailable", "allowlisted destination is unavailable", 503)
        guild = getattr(channel, "guild", None)
        send = getattr(channel, "send", None)
        if guild is None or guild.id != self._guild_id or not callable(send):
            return self._error("destination_invalid", "allowlisted destination is not a text destination in the configured guild", 503)

        try:
            receipt = await self._delivery.deliver(
                job_id,
                f"alias:{alias}",
                cast(SendMessage, send),
                force_resend=force_resend,
            )
        except DeliveryError as exc:
            return self._error(exc.code, str(exc), exc.status_code)
        except discord.DiscordException:
            return self._error("discord_delivery_failed", "Discord rejected result delivery", 502)

        return web.json_response(
            {
                "ok": True,
                "job_id": receipt.job_id,
                "destination_alias": alias,
                "message_ids": list(receipt.message_ids),
                "artifact_count": receipt.artifact_count,
                "deduplicated": receipt.deduplicated,
            }
        )

    @staticmethod
    def _error(code: str, message: str, status: int) -> web.Response:
        return web.json_response({"ok": False, "error": {"code": code, "message": message}}, status=status)
