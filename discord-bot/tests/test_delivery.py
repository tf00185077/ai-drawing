from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.delivery import DeliveryError, DeliveryLedger, ResultDeliveryService


@pytest.mark.asyncio
async def test_batch_delivery_sends_every_artifact_and_deduplicates(tmp_path: Path) -> None:
    api = SimpleNamespace(
        collect_job_result=AsyncMock(
            return_value={
                "status": "completed",
                "images": [(f"image-{index}.png", bytes([index])) for index in range(12)],
                "urls": [f"http://gallery/{index}" for index in range(12)],
            }
        )
    )
    sent_files: list[str] = []
    counter = 100

    async def send(content: str, files=None):
        nonlocal counter
        counter += 1
        sent_files.extend(file.filename for file in (files or []))
        return SimpleNamespace(id=counter)

    ledger = DeliveryLedger(tmp_path / "ledger.json")
    service = ResultDeliveryService(api, ledger)
    first = await service.deliver("job", "alias:results", send)
    second = await service.deliver("job", "alias:results", send)

    assert sent_files == [f"image-{index}.png" for index in range(12)]
    assert first.message_ids == ("101", "102")
    assert first.artifact_count == 12
    assert first.deduplicated is False
    assert second.message_ids == first.message_ids
    assert second.artifact_count == 12
    assert second.deduplicated is True
    api.collect_job_result.assert_awaited_once()


@pytest.mark.asyncio
async def test_force_resend_bypasses_completed_delivery_ledger(tmp_path: Path) -> None:
    api = SimpleNamespace(
        collect_job_result=AsyncMock(
            return_value={"status": "completed", "images": [("one.png", b"one")]}
        )
    )
    send = AsyncMock(side_effect=[SimpleNamespace(id=1), SimpleNamespace(id=2)])
    service = ResultDeliveryService(api, DeliveryLedger(tmp_path / "ledger.json"))

    await service.deliver("job", "alias:results", send)
    receipt = await service.deliver("job", "alias:results", send, force_resend=True)

    assert receipt.message_ids == ("2",)
    assert receipt.artifact_count == 1
    assert receipt.deduplicated is False
    assert api.collect_job_result.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["queued", "running", "failed"])
async def test_non_completed_jobs_are_never_sent_or_recorded(tmp_path: Path, status: str) -> None:
    outcome = {"status": status, "error": "safe failure"}
    api = SimpleNamespace(collect_job_result=AsyncMock(return_value=outcome))
    send = AsyncMock()
    service = ResultDeliveryService(api, DeliveryLedger(tmp_path / "ledger.json"))

    with pytest.raises(DeliveryError):
        await service.deliver("job", "alias:results", send)

    send.assert_not_awaited()
    assert not (tmp_path / "ledger.json").exists()


@pytest.mark.asyncio
async def test_video_result_is_delivered_as_discord_attachment(tmp_path: Path) -> None:
    api = SimpleNamespace(collect_job_result=AsyncMock(return_value={
        "status": "completed", "artifacts": [("motion_film.mp4", b"video")],
        "urls": ["http://gallery/motion_film.mp4"],
    }))
    send = AsyncMock(return_value=SimpleNamespace(id=7))
    service = ResultDeliveryService(api, DeliveryLedger(tmp_path / "ledger.json"))

    receipt = await service.deliver("video-job", "alias:results", send)

    assert receipt.artifact_count == 1
    assert "1 支影片" in send.await_args.args[0]
    assert send.await_args.kwargs["files"][0].filename == "motion_film.mp4"
