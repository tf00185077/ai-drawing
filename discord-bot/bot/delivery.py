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
from .attempt_store import AttemptStore, StoreError
from .config import ledger_binding
from .maintenance import Admission, MaintenanceClosed

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


class DeliveryLedger(AttemptStore):
    """Required bound history; explicit provisioning never occurs during load."""
    def __init__(self, path: Path, *, binding=None):
        super().__init__(path, binding=binding or ledger_binding(path=path))

    @classmethod
    def provision(cls, path, *, binding=None):
        return super().provision(path, binding=binding or ledger_binding(path=path))


class ResultDeliveryService:
    """The sole implementation used by both ``/result`` and operator delivery."""

    def __init__(self, api: ApiClient, ledger: DeliveryLedger | None, admission: Admission | None = None):
        self._api = api
        self._ledger = ledger
        self._lock = asyncio.Lock()
        self.admission = admission or Admission(owner='delivery',epoch=str(__import__('uuid').uuid4()),version='maintenance-v1')
        if ledger is None:
            self.admission.hold('ledger')
        else:
            try:
                count=ledger.uncertain_count
                if count:self.admission.set_hold('delivery_attempt',count)
            except StoreError:self.admission.hold('ledger')

    def status(self):
        # Integrity failures become visible without waiting for another send.
        try:
            if self._ledger is None:raise StoreError('ledger unavailable')
            count=self._ledger.uncertain_count
            if count and not self.admission.status()['active']:
                self.admission.set_hold('delivery_attempt',count)
        except Exception:
            # An unavailable inspection is unknown, including unexpected I/O errors.
            # Keep the safe projection free of exception text and private paths.
            self.admission.set_hold('ledger',1)
        return self.admission.status()

    async def deliver(
        self,
        job_id: str,
        destination: str,
        send: SendMessage,
        *,
        force_resend: bool = False,
    ) -> DeliveryReceipt:
        # Registration includes collection, lock waiters and every chunk send.
        try:
            with self.admission.enter('delivery'):
                async with self._lock:
                    try:
                        return await self._deliver(job_id, destination, send, force_resend)
                    except DeliveryError as exc:
                        known_error = exc  # pre-send status/validation is a known rejection
            raise known_error
        except MaintenanceClosed as exc:
            raise DeliveryError('maintenance_closed','交付維護暫停；請保留 job id，勿盲重送',status_code=503) from exc
        except StoreError as exc:
            self.admission.hold('ledger')
            raise DeliveryError('delivery_uncertain','交付回執不完整；需由 owner 核對，勿重送',status_code=409) from exc

    async def _deliver(self, job_id, destination, send, force_resend):
        if self._ledger is None:raise StoreError('ledger unavailable')
        key = f"{destination}:{job_id}"
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

        attempt = None
        async def recorded_send(*args, **kwargs):
            nonlocal attempt
            if attempt is None:
                attempt = self._ledger.begin(key,job_id=job_id,destination=destination,
                                             epoch=self.admission.epoch,force=force_resend)
            # Durable intent exists BEFORE the external await, including no-return.
            message = await send(*args, **kwargs)
            mid=getattr(message,'id',None)
            if not isinstance(mid,(str,int)) or isinstance(mid,bool):
                raise StoreError('missing external receipt; hold')
            self._ledger.receipt(attempt,str(mid))
            return message
        messages, artifact_count = await self._deliver_outcome(outcome, recorded_send)
        message_ids = tuple(str(message.id) for message in messages)
        if attempt is None:raise StoreError('missing attempt; hold')
        self._ledger.complete(attempt,artifact_count)
        return DeliveryReceipt(job_id,destination,message_ids,artifact_count,False)

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

        artifacts = outcome.get("artifacts") or outcome.get("images") or []
        if not isinstance(artifacts, list) or not artifacts:
            raise DeliveryError("artifacts_missing", "完成，但找不到結果檔", status_code=409)
        if not all(
            isinstance(item, (tuple, list))
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], bytes)
            for item in artifacts
        ):
            raise DeliveryError("invalid_artifacts", "後端回傳無效的圖檔", status_code=502)

        video_extensions = (".mp4", ".webm", ".mov")
        if all(name.lower().endswith(video_extensions) for name, _ in artifacts):
            count_text = f"{len(artifacts)} 支影片"
        elif all(not name.lower().endswith(video_extensions) for name, _ in artifacts):
            count_text = f"{len(artifacts)} 張"
        else:
            count_text = f"{len(artifacts)} 個結果"

        sent: list[object] = []
        if any(len(data) > DISCORD_UPLOAD_LIMIT_BYTES for _, data in artifacts):
            urls = outcome.get("urls") or []
            if not isinstance(urls, list) or len(urls) < len(artifacts) or not all(isinstance(url, str) for url in urls):
                raise DeliveryError("artifacts_too_large", "圖檔超過 Discord 限制且沒有完整下載連結", status_code=409)
            prefix = f"✅ 完成，共 {count_text}（檔案過大，改附連結）："
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
            for chunk in self._attachment_chunks(artifacts):
                files = [discord.File(io.BytesIO(data), filename=name) for name, data in chunk]
                sent.append(await send(f"✅ 完成，共 {count_text}", files=files))

        warning = mixed_batch_warning(outcome)
        if warning:
            sent.append(await send(warning))
        return sent, len(artifacts)

    @staticmethod
    def _attachment_chunks(artifacts: list) -> list[list]:
        chunks: list[list] = []
        current: list = []
        current_bytes = 0
        for image in artifacts:
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
