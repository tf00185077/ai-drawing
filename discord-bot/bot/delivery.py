"""Shared, constrained delivery of completed generation results to Discord."""
from __future__ import annotations

import asyncio
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import discord

from .api_client import ApiClient, BackendError

DISCORD_UPLOAD_LIMIT_BYTES = 24 * 1024 * 1024
DISCORD_MAX_FILES_PER_MESSAGE = 10
DISCORD_MESSAGE_LIMIT = 2000
MAX_FAILED_MEMBER_DETAILS = 4
MAX_FAILURE_REASON_CHARS = 160

SendMessage = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class DeliveryReceipt:
    job_id: str
    destination: str
    message_ids: tuple[str, ...]
    artifact_count: int
    deduplicated: bool


class DeliveryError(Exception):
    """Safe result-delivery failure suitable for slash and operator responses."""

    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def mixed_batch_warning(outcome: dict) -> str | None:
    raw_failed = outcome.get("batch_failed")
    failed = raw_failed if isinstance(raw_failed, int) and not isinstance(raw_failed, bool) else 0
    if failed <= 0:
        return None
    raw_total = outcome.get("batch_total")
    total = raw_total if isinstance(raw_total, int) and not isinstance(raw_total, bool) else 0
    raw_completed = outcome.get("batch_completed")
    completed = raw_completed if isinstance(raw_completed, int) and not isinstance(raw_completed, bool) else 0
    raw_members = outcome.get("failed_members")
    members = [item for item in raw_members if isinstance(item, dict)] if isinstance(raw_members, list) else []
    members = sorted(
        enumerate(members),
        key=lambda pair: (
            pair[1].get("batch_index") if type(pair[1].get("batch_index")) is int else 2**31,
            pair[0],
        ),
    )
    details: list[str] = []
    for _, member in members[:MAX_FAILED_MEMBER_DETAILS]:
        batch_index = member.get("batch_index")
        ordinal = batch_index + 1 if type(batch_index) is int else "?"
        raw_reason = member.get("message") or member.get("code")
        reason = (raw_reason if isinstance(raw_reason, str) else "未知錯誤")[:MAX_FAILURE_REASON_CHARS]
        details.append(f"第 {ordinal} 張：{reason}")
    omitted = max(failed - len(details), len(members) - len(details), 0)
    if omitted:
        details.append(f"其餘 {omitted} 張失敗已省略")
    suffix = f"（{'；'.join(details)}）" if details else ""
    return (
        f"⚠️ 本輪已完成：成功 {completed}/{total}；失敗 {failed}/{total}{suffix}"
    )[:DISCORD_MESSAGE_LIMIT]


class DeliveryLedger:
    """Small atomic ledger used only to suppress completed duplicate sends."""

    def __init__(self, path: Path):
        self._path = path

    def get(self, key: str) -> tuple[tuple[str, ...], int] | None:
        data = self._read()
        value = data.get(key)
        # Backward-compatible read of the original list-only ledger format.
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return tuple(value), 0
        if not isinstance(value, dict):
            return None
        message_ids = value.get("message_ids")
        artifact_count = value.get("artifact_count")
        if (
            not isinstance(message_ids, list)
            or not all(isinstance(item, str) for item in message_ids)
            or type(artifact_count) is not int
            or artifact_count < 0
        ):
            return None
        return tuple(message_ids), artifact_count

    def put(self, key: str, message_ids: tuple[str, ...], artifact_count: int) -> None:
        data = self._read()
        data[key] = {
            "message_ids": list(message_ids),
            "artifact_count": artifact_count,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self._path)

    def _read(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}


class ResultDeliveryService:
    """The sole implementation used by both ``/result`` and operator delivery."""

    def __init__(self, api: ApiClient, ledger: DeliveryLedger):
        self._api = api
        self._ledger = ledger
        self._lock = asyncio.Lock()

    async def deliver(
        self,
        job_id: str,
        destination: str,
        send: SendMessage,
        *,
        force_resend: bool = False,
    ) -> DeliveryReceipt:
        key = f"{destination}:{job_id}"
        async with self._lock:
            prior = self._ledger.get(key)
            if prior is not None and not force_resend:
                return DeliveryReceipt(job_id, destination, prior[0], prior[1], True)

            try:
                outcome = await self._api.collect_job_result(job_id)
            except BackendError as exc:
                if exc.status_code == 404:
                    raise DeliveryError("job_not_found", "找不到這個 job id", status_code=404) from exc
                raise DeliveryError("backend_error", f"後端錯誤：{exc}", status_code=502) from exc
            except Exception as exc:
                raise DeliveryError("backend_unavailable", "後端連不上，請確認 backend 有啟動", status_code=502) from exc

            messages, artifact_count = await self._deliver_outcome(outcome, send)
            message_ids = tuple(str(message.id) for message in messages)
            self._ledger.put(key, message_ids, artifact_count)
            return DeliveryReceipt(
                job_id, destination, message_ids, artifact_count, False
            )

    async def _deliver_outcome(
        self, outcome: dict, send: SendMessage
    ) -> tuple[list[object], int]:
        status = outcome.get("status")
        if status in ("queued", "running"):
            raise DeliveryError("job_not_completed", f"狀態：{status}，尚未完成", status_code=409)
        if status == "failed":
            detail = self._failure_detail(outcome)
            raise DeliveryError("generation_failed", f"生圖失敗：{detail}", status_code=409)
        if status != "completed":
            raise DeliveryError("invalid_job_status", "後端回傳未知的 job 狀態", status_code=502)

        images = outcome.get("images") or []
        if not isinstance(images, list) or not images:
            raise DeliveryError("artifacts_missing", "完成，但找不到圖檔", status_code=409)
        if not all(
            isinstance(item, (tuple, list))
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], bytes)
            for item in images
        ):
            raise DeliveryError("invalid_artifacts", "後端回傳無效的圖檔", status_code=502)

        sent: list[object] = []
        if any(len(data) > DISCORD_UPLOAD_LIMIT_BYTES for _, data in images):
            urls = outcome.get("urls") or []
            if not isinstance(urls, list) or len(urls) < len(images) or not all(isinstance(url, str) for url in urls):
                raise DeliveryError("artifacts_too_large", "圖檔超過 Discord 限制且沒有完整下載連結", status_code=409)
            prefix = f"✅ 完成，共 {len(images)} 張（檔案過大，改附連結）："
            current = prefix
            for url in urls:
                line = f"\n{url}"
                if len(current) + len(line) > DISCORD_MESSAGE_LIMIT:
                    sent.append(await send(current))
                    current = url
                else:
                    current += line
            if current:
                sent.append(await send(current))
        else:
            for chunk in self._attachment_chunks(images):
                files = [discord.File(io.BytesIO(data), filename=name) for name, data in chunk]
                sent.append(await send(f"✅ 完成，共 {len(images)} 張", files=files))

        warning = mixed_batch_warning(outcome)
        if warning:
            sent.append(await send(warning))
        return sent, len(images)

    @staticmethod
    def _attachment_chunks(images: list) -> list[list]:
        chunks: list[list] = []
        current: list = []
        current_bytes = 0
        for image in images:
            size = len(image[1])
            if current and (
                len(current) >= DISCORD_MAX_FILES_PER_MESSAGE
                or current_bytes + size > DISCORD_UPLOAD_LIMIT_BYTES
            ):
                chunks.append(current)
                current = []
                current_bytes = 0
            current.append(image)
            current_bytes += size
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _failure_detail(outcome: dict) -> str:
        batch_detail = mixed_batch_warning(outcome)
        if batch_detail:
            return batch_detail.removeprefix("⚠️ 本輪已完成：")
        raw_node_errors = outcome.get("node_errors")
        reasons: list[str] = []
        if isinstance(raw_node_errors, list):
            for item in raw_node_errors[:MAX_FAILED_MEMBER_DETAILS]:
                reason = item.get("reason") if isinstance(item, dict) else item
                if isinstance(reason, str):
                    reasons.append(reason[:MAX_FAILURE_REASON_CHARS])
        return "；".join(reasons) or outcome.get("error") or "未知錯誤"
