"""Offline CIV-C safe Civitai download contract tests."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.services.civitai_safe_download import (
    CivitaiFileMetadata,
    DownloadResponse,
    safe_download,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class FakeTransport:
    responses: list[DownloadResponse | Exception]

    def __post_init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> DownloadResponse:
        self.calls.append({"url": url, "headers": dict(headers or {})})
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def _metadata(data: bytes, **overrides: object) -> CivitaiFileMetadata:
    payload: dict[str, object] = {
        "download_url": "https://download.example/file",
        "sha256": _sha(data),
        "size": len(data),
        "availability": True,
        "scan_status": "clean",
        "license": {"name": "Civitai test license"},
        "usage": {"commercial": "unknown"},
    }
    payload.update(overrides)
    return CivitaiFileMetadata(**payload)


def test_206_resumes_from_part_offset_and_atomically_publishes_only_after_hash_and_size(tmp_path: Path) -> None:
    data = b"abcdefghij"
    target = tmp_path / "models" / "file.safetensors"
    part = target.with_name(target.name + ".part")
    target.parent.mkdir()
    part.write_bytes(data[:4])
    transport = FakeTransport([DownloadResponse(206, data[4:], {"Content-Range": "bytes 4-9/10"})])

    result = safe_download(_metadata(data), target, transport=transport)

    assert result.status == "completed"
    assert result.resume_used is True
    assert result.bytes == len(data)
    assert result.actual_sha256 == _sha(data)
    assert target.read_bytes() == data
    assert not part.exists()
    assert transport.calls[0]["headers"]["Range"] == "bytes=4-"


def test_200_ignoring_range_overwrites_part_safely_instead_of_concatenating(tmp_path: Path) -> None:
    data = b"abcdefghij"
    target = tmp_path / "file.safetensors"
    part = target.with_name(target.name + ".part")
    part.write_bytes(b"stale")
    transport = FakeTransport([DownloadResponse(200, data, {})])

    result = safe_download(_metadata(data), target, transport=transport)

    assert result.status == "completed"
    assert result.resume_used is False
    assert target.read_bytes() == data
    assert not part.exists()
    assert transport.calls[0]["headers"]["Range"] == "bytes=5-"


def test_hash_or_size_mismatch_never_replaces_existing_final_target(tmp_path: Path) -> None:
    expected = b"expected"
    target = tmp_path / "file.safetensors"
    target.write_bytes(b"previous completed file")
    transport = FakeTransport([DownloadResponse(200, b"wrong", {})])

    result = safe_download(_metadata(expected), target, transport=transport)

    assert result.status == "failed"
    assert target.read_bytes() == b"previous completed file"
    assert not (tmp_path / "file.safetensors.part").exists()


def test_part_symlink_cannot_damage_existing_final_target_on_failure(tmp_path: Path) -> None:
    expected = b"expected"
    target = tmp_path / "file.safetensors"
    target.write_bytes(b"known-good-final")
    part = target.with_name(target.name + ".part")
    part.symlink_to(target.name)
    transport = FakeTransport([DownloadResponse(200, b"bad", {})])

    result = safe_download(_metadata(expected), target, transport=transport)

    assert result.status == "failed"
    assert target.read_bytes() == b"known-good-final"


def test_retry_is_bounded_to_three_requests_for_429_5xx_and_transport_failure(tmp_path: Path) -> None:
    data = b"retried"
    response_sets = (
        [DownloadResponse(429, b"", {}), DownloadResponse(503, b"", {}), DownloadResponse(500, b"", {})],
        [OSError("network down"), OSError("network down"), OSError("network down")],
    )
    for index, responses in enumerate(response_sets):
        sleeps: list[float] = []
        transport = FakeTransport(responses)
        result = safe_download(
            _metadata(data),
            tmp_path / f"{index}.safetensors",
            transport=transport,
            backoff=lambda attempt, _: attempt,
            sleep=sleeps.append,
        )
        assert result.status == "failed"
        assert len(transport.calls) == 3
        assert sleeps == [1.0, 2.0]


def test_unavailable_or_non_clean_scan_blocks_without_download_and_preserves_license_usage(tmp_path: Path) -> None:
    data = b"blocked"
    for metadata in (
        _metadata(data, availability=False),
        _metadata(data, scan_status="pending"),
    ):
        transport = FakeTransport([])
        result = safe_download(metadata, tmp_path / "blocked.safetensors", transport=transport)
        assert result.status == "blocked"
        assert transport.calls == []
        assert result.diagnostics["license"] == {"name": "Civitai test license"}
        assert result.diagnostics["usage"] == {"commercial": "unknown"}


def test_download_results_and_transport_failures_never_serialize_authorization_or_token(tmp_path: Path) -> None:
    secret = "DOWNLOAD_TEST_TOKEN"
    data = b"payload"
    transport = FakeTransport([OSError(f"Authorization: Bearer {secret}") for _ in range(3)])

    result = safe_download(
        _metadata(data),
        tmp_path / "secret.safetensors",
        transport=transport,
        authorization=f"Bearer {secret}",
        sleep=lambda _: None,
    )

    assert result.status == "failed"
    assert secret not in json.dumps(result.to_dict(), sort_keys=True)
    assert secret not in json.dumps(result.diagnostics, sort_keys=True)
