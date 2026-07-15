"""One-call best-effort Civitai resource acquisition.

Given a model URL, model ID, or model-version ID, this service inspects the
Civitai API, picks the downloadable file(s), downloads them in a background
thread to the configured storage roots (the external model disk), and records
each file in the ``downloaded_resources`` ledger.

Split packages: Anima checkpoints ship as separate diffusion / text-encoder /
VAE files under one version. One call downloads the whole set, routing each
file to its own ComfyUI directory by filename convention.

Policy: real safety gates stay hard — the virus scan must be clean and the
downloaded bytes must match the published SHA-256 and size. Incomplete
license metadata is recorded as a warning (``license_verified: false``)
instead of blocking a personal-use download.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import threading
from typing import Any, Callable

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import SessionLocal
from app.db.models import DownloadedResource
from app.services.civitai_acquisition import AcquisitionError, parse_civitai_locator, redact_secrets
from app.services.civitai_safe_download import CivitaiFileMetadata, DownloadResponse, safe_download

_CLEAN_SCAN_STATUSES = frozenset({"success", "clean", "passed"})
_ACTIVE_STATUSES = frozenset({"downloading"})
_INSTALLED_STATUSES = frozenset({"installed", "available"})

# Civitai model "type" → (settings storage root, ledger resource_type)
_MODEL_TYPE_ROOTS: dict[str, tuple[str, str]] = {
    "checkpoint": ("checkpoints", "checkpoint"),
    "lora": ("loras", "lora"),
    "locon": ("loras", "lora"),
    "dora": ("loras", "lora"),
    "lycoris": ("loras", "lora"),
    "textualinversion": ("embeddings", "embedding"),
    "vae": ("vae", "vae"),
    "controlnet": ("controlnet", "controlnet"),
    "upscaler": ("upscale_models", "upscaler"),
}

_LICENSE_FIELDS = ("allowNoCredit", "allowCommercialUse", "allowDerivatives", "allowDifferentLicense")


class AcquireError(Exception):
    """Structured acquisition failure with an actionable hint for the agent."""

    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        detail: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.hint:
            detail["hint"] = self.hint
        return detail


class _JsonTransport:
    def get_json(self, url: str, *, headers: dict[str, str] | None = None) -> tuple[int, Any]:
        response = httpx.get(url, headers=headers or {}, timeout=30.0, follow_redirects=True)
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {}
        return response.status_code, payload


class _StreamingDownloadTransport:
    def get(self, url: str, *, headers: dict[str, str] | None = None) -> Any:
        stream = httpx.stream(
            "GET", url, headers=headers,
            timeout=httpx.Timeout(connect=60.0, read=None, write=60.0, pool=60.0),
            follow_redirects=True,
        )
        response = stream.__enter__()
        if not 200 <= response.status_code < 300:
            stream.__exit__(None, None, None)
            return DownloadResponse(response.status_code, b"", dict(response.headers))

        def chunks():
            try:
                yield from response.iter_bytes(chunk_size=1024 * 1024)
            finally:
                stream.__exit__(None, None, None)

        return DownloadResponse(response.status_code, chunks(), dict(response.headers))


def normalize_model_family(base_model: Any) -> str | None:
    """Best-effort architecture family from Civitai's baseModel label."""
    if not isinstance(base_model, str):
        return None
    lowered = base_model.casefold()
    if "illustrious" in lowered:
        return "illustrious"
    if "sdxl" in lowered or "pony" in lowered:
        return "sdxl"
    if "anima" in lowered:
        return "anima"
    return None


def _anima_component(file_name: str) -> tuple[str, str]:
    """Route one Anima split-package file by filename convention.

    Civitai labels the whole package "Checkpoint", but the files are split:
    the text encoder carries "_txt", the VAE carries "vae"; the remaining
    large file is the diffusion weight for UNETLoader.
    """
    lowered = file_name.casefold()
    if "_txt" in lowered or "text_encoder" in lowered or "textencoder" in lowered:
        return ("text_encoders", "text_encoder")
    if "vae" in lowered:
        return ("vae", "vae")
    return ("diffusion_models", "diffusion_model")


def _auth_headers() -> dict[str, str]:
    authorization = get_settings().civitai_authorization
    if not authorization:
        return {}
    value = authorization.strip()
    if not value.lower().startswith("bearer "):
        value = f"Bearer {value}"
    return {"Authorization": value}


def _fetch_json(transport: Any, url: str) -> Any:
    status, payload = transport.get_json(url, headers=_auth_headers())
    if status == 404:
        raise AcquireError("not_found", f"Civitai 找不到資源：{url}")
    if status == 401 or status == 403:
        raise AcquireError(
            "unauthorized",
            f"Civitai 拒絕存取（HTTP {status}）",
            hint="部分資源需要 API key：在 .env 設定 CIVITAI_AUTHORIZATION=<你的 Civitai API key> 後重試",
        )
    if not 200 <= status < 300:
        raise AcquireError("civitai_api_error", f"Civitai API 回應 HTTP {status}，可稍後重試")
    return payload


def resolve_version_metadata(locator: int | str, *, transport: Any | None = None) -> dict[str, Any]:
    """Resolve any reasonable locator to one Civitai model version payload.

    Accepts: full model URL (with or without modelVersionId), bare model-version
    ID, bare model ID (uses its latest version). Image/post URLs get a hint to
    supply the model page instead.
    """
    transport = transport or _JsonTransport()
    model_id: int | None = None
    version_id: int | None = None

    raw = str(locator).strip()
    if raw.isdecimal():
        # A bare number is ambiguous: try model-version first, then model.
        candidate = int(raw)
        try:
            version_payload = _fetch_json(transport, f"https://civitai.com/api/v1/model-versions/{candidate}")
            if isinstance(version_payload, dict) and version_payload.get("id") == candidate:
                model_payload = _maybe_fetch_model(transport, version_payload.get("modelId"))
                return {"version": version_payload, "model": model_payload}
        except AcquireError as exc:
            if exc.code != "not_found":
                raise
        model_id = candidate
    else:
        try:
            parsed = parse_civitai_locator(raw)
        except AcquisitionError as exc:
            raise AcquireError(
                "unsupported_locator",
                str(exc),
                hint="接受：civitai.com/models/<id> 連結（可含 modelVersionId）、模型 ID 或 model-version ID 數字",
            ) from exc
        if parsed.kind in {"image", "post", "cdn"}:
            raise AcquireError(
                "locator_is_not_a_model",
                "這是圖片/貼文連結，不是模型頁",
                hint="要下載模型請提供 civitai.com/models/… 連結（圖片頁右側資源卡可連到模型頁），"
                     "或改用 civitai_generate_like 直接參考該圖片生圖",
            )
        model_id, version_id = parsed.model_id, parsed.model_version_id

    if version_id is not None:
        version_payload = _fetch_json(transport, f"https://civitai.com/api/v1/model-versions/{version_id}")
        model_payload = _maybe_fetch_model(transport, version_payload.get("modelId") if isinstance(version_payload, dict) else None)
        return {"version": version_payload, "model": model_payload}
    if model_id is None:
        raise AcquireError("unsupported_locator", "無法從輸入解析出模型 ID")
    model_payload = _fetch_json(transport, f"https://civitai.com/api/v1/models/{model_id}")
    versions = model_payload.get("modelVersions") if isinstance(model_payload, dict) else None
    if not isinstance(versions, list) or not versions or not isinstance(versions[0], dict):
        raise AcquireError("no_versions", "此模型沒有可用版本")
    return {"version": versions[0], "model": model_payload}


def _maybe_fetch_model(transport: Any, model_id: Any) -> dict[str, Any] | None:
    if not isinstance(model_id, int):
        return None
    try:
        payload = _fetch_json(transport, f"https://civitai.com/api/v1/models/{model_id}")
    except AcquireError:
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_file(chosen: dict[str, Any]) -> dict[str, Any]:
    """Validate one Civitai file entry; the virus-scan gate stays hard."""
    name = Path(str(chosen.get("name", ""))).name
    sha256 = ((chosen.get("hashes") or {}).get("SHA256") or "").strip().lower()
    size_kb = chosen.get("sizeKB")
    download_url = chosen.get("downloadUrl")
    scan = str(chosen.get("virusScanResult") or "").strip().lower()
    if not name or not name.lower().endswith((".safetensors", ".ckpt", ".pt", ".pth", ".bin")):
        raise AcquireError("unsafe_filename", f"檔名不可用：{name!r}")
    if scan not in _CLEAN_SCAN_STATUSES:
        raise AcquireError(
            "virus_scan_not_clean",
            f"病毒掃描狀態為 {scan or 'unknown'}，拒絕下載",
            hint="這是硬性安全檢查，不提供繞過；請改用其他掃描通過的版本",
        )
    if not sha256 or not isinstance(size_kb, (int, float)) or not isinstance(download_url, str):
        raise AcquireError("incomplete_file_metadata", "檔案缺少 SHA-256、大小或下載網址，無法安全下載")
    return {
        "name": name,
        "sha256": sha256,
        "size_bytes": int(round(float(size_kb) * 1024)),
        "download_url": download_url,
        "civitai_file_id": chosen.get("id"),
        "scan_status": scan,
    }


def choose_file(version_payload: dict[str, Any]) -> dict[str, Any]:
    """Pick the primary downloadable file."""
    files = version_payload.get("files")
    if not isinstance(files, list) or not files:
        raise AcquireError("no_files", "此模型版本沒有檔案清單")
    candidates = [item for item in files if isinstance(item, dict)]
    chosen = next((item for item in candidates if item.get("primary") is True), None)
    if chosen is None:
        chosen = next(
            (item for item in candidates if str(item.get("name", "")).lower().endswith(".safetensors")),
            candidates[0],
        )
    return _normalize_file(chosen)


def downloadable_files(version_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """All valid files of a version (for split packages), plus skip warnings."""
    files = version_payload.get("files")
    if not isinstance(files, list) or not files:
        raise AcquireError("no_files", "此模型版本沒有檔案清單")
    valid: list[dict[str, Any]] = []
    warnings: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        try:
            valid.append(_normalize_file(item))
        except AcquireError as exc:
            warnings.append(f"檔案「{item.get('name')}」跳過：{exc.message}")
    if not valid:
        raise AcquireError("no_files", "此版本沒有任何可安全下載的檔案")
    return valid, warnings


def license_snapshot(model_payload: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """License completeness is recorded, not enforced."""
    warnings: list[str] = []
    snapshot: dict[str, Any] = {}
    if not isinstance(model_payload, dict):
        warnings.append("無法取得模型授權資訊；已標記 license_verified=false（個人使用通常無礙，公開發布前請自行確認）")
        return {"license_verified": False}, warnings
    missing = [field for field in _LICENSE_FIELDS if model_payload.get(field) is None]
    for field in _LICENSE_FIELDS:
        if model_payload.get(field) is not None:
            snapshot[field] = model_payload[field]
    snapshot["license_verified"] = not missing
    if missing:
        warnings.append(
            "模型授權欄位不完整（缺 " + ", ".join(missing) + "）；已照常下載並標記 license_verified=false，"
            "若要商用或公開發布請先自行到模型頁確認授權"
        )
    return snapshot, warnings


def _storage_roots(settings: Any) -> dict[str, Path]:
    # All roots come from the configured COMFYUI_*_DIR settings, which point at
    # the external model disk; the tool only picks the right subdirectory.
    return {
        "checkpoints": Path(settings.comfyui_checkpoints_dir.split(",")[0]),
        "loras": Path(settings.comfyui_loras_dir.split(",")[0]),
        "vae": Path(settings.comfyui_vae_dir.split(",")[0]),
        "embeddings": Path(settings.comfyui_embeddings_dir.split(",")[0]),
        "controlnet": Path(settings.comfyui_controlnet_dir.split(",")[0]),
        "upscale_models": Path(settings.comfyui_upscale_models_dir.split(",")[0]),
        "diffusion_models": Path(settings.comfyui_diffusion_models_dir.split(",")[0]),
        "text_encoders": Path(settings.comfyui_text_encoders_dir.split(",")[0]),
    }


def _resource_summary(row: DownloadedResource) -> dict[str, Any]:
    notes: dict[str, Any] = {}
    if row.notes:
        try:
            parsed = json.loads(row.notes)
            if isinstance(parsed, dict):
                notes = parsed
        except ValueError:
            pass
    total = row.file_size or notes.get("expected_size_bytes")
    progress: dict[str, Any] = {}
    if row.status in _ACTIVE_STATUSES and row.local_path:
        part = Path(row.local_path + ".part")
        downloaded = part.stat().st_size if part.exists() else 0
        progress = {"downloaded_bytes": downloaded, "total_bytes": total}
        if isinstance(total, int) and total > 0:
            progress["percent"] = round(downloaded * 100 / total, 1)
    return redact_secrets({
        "acquisition_id": row.id,
        "resource_name": row.resource_name,
        "resource_type": row.resource_type,
        "status": row.status,
        "local_path": row.local_path,
        "storage_root": row.storage_root,
        "civitai_model_id": row.model_id,
        "civitai_model_version_id": row.version_id,
        "sha256": row.sha256,
        "model_family": notes.get("model_family"),
        "base_model": notes.get("base_model"),
        "license": notes.get("license"),
        "progress": progress or None,
        "error": notes.get("error"),
    })


def start_acquisition(
    locator: int | str,
    *,
    db: Session,
    metadata_transport: Any | None = None,
    download_transport: Any | None = None,
    thread_factory: Callable[..., threading.Thread] | None = None,
    run_in_background: bool = True,
    session_factory: Callable[[], Session] | None = None,
) -> dict[str, Any]:
    """Inspect, dedupe, and start downloading one Civitai resource.

    Returns immediately with an acquisition_id; the download continues in a
    background thread and progress is visible via ``acquisition_status``.
    """
    settings = get_settings()
    resolved = resolve_version_metadata(locator, transport=metadata_transport)
    version = resolved["version"]
    model = resolved["model"]

    model_type = str((model or {}).get("type") or (version.get("model") or {}).get("type") or "").strip().casefold()
    if model_type not in _MODEL_TYPE_ROOTS:
        supported = ", ".join(sorted({key for key in _MODEL_TYPE_ROOTS}))
        raise AcquireError(
            "unsupported_model_type",
            f"不支援的模型類型：{model_type or 'unknown'}",
            hint=f"目前支援：{supported}",
        )
    root_key, resource_type = _MODEL_TYPE_ROOTS[model_type]
    license_info, warnings = license_snapshot(model)
    base_model = version.get("baseModel")
    family = normalize_model_family(base_model)

    # Components to install: (file, storage root, ledger resource_type).
    # Anima "checkpoints" are split packages — grab the whole set and route
    # each file to its own directory; everything else is a single file.
    if model_type == "checkpoint" and family == "anima":
        files, skip_warnings = downloadable_files(version)
        warnings.extend(skip_warnings)
        components = [(item, *_anima_component(item["name"])) for item in files]
    else:
        components = [(choose_file(version), root_key, resource_type)]

    version_id = version.get("id")
    model_id = version.get("modelId") or (model or {}).get("id")
    existing = (
        db.query(DownloadedResource)
        .filter(DownloadedResource.provider == "civitai")
        .filter(DownloadedResource.version_id == str(version_id))
        .order_by(DownloadedResource.id.desc())
        .all()
    )

    roots = _storage_roots(settings)
    common_notes = {
        "base_model": base_model,
        "model_family": family,
        "license": license_info,
        "version_name": version.get("name"),
        "model_name": (model or {}).get("name") or (version.get("model") or {}).get("name"),
    }
    done_rows: list[DownloadedResource] = []
    active_rows: list[DownloadedResource] = []
    jobs: list[dict[str, Any]] = []

    for chosen, comp_root, comp_type in components:
        matched = next((row for row in existing if row.resource_name == chosen["name"]), None)
        if matched is not None and matched.status in _INSTALLED_STATUSES and matched.local_path and Path(matched.local_path).is_file():
            done_rows.append(matched)
            continue
        if matched is not None and matched.status in _ACTIVE_STATUSES:
            active_rows.append(matched)
            continue
        notes = {**common_notes, "expected_size_bytes": chosen["size_bytes"]}
        target = roots[comp_root] / chosen["name"]
        row = DownloadedResource(
            resource_name=chosen["name"],
            resource_type=comp_type,
            provider="civitai",
            source_url=f"https://civitai.com/models/{model_id}?modelVersionId={version_id}" if model_id else str(locator),
            resolved_download_url=chosen["download_url"],
            local_path=str(target),
            storage_root=comp_root,
            file_size=chosen["size_bytes"],
            sha256=chosen["sha256"],
            model_id=str(model_id) if model_id is not None else None,
            version_id=str(version_id) if version_id is not None else None,
            civitai_file_id=str(chosen["civitai_file_id"]) if chosen["civitai_file_id"] is not None else None,
            status="downloading",
            notes=json.dumps(redact_secrets(notes), ensure_ascii=False),
        )
        db.add(row)
        jobs.append({"chosen": chosen, "target": target, "notes": notes, "row": row})

    if not jobs:
        rows = done_rows + active_rows
        status = "downloading" if active_rows else "already_installed"
        return {
            "status": status,
            "resource": _resource_summary(rows[0]),
            "resources": [_resource_summary(row) for row in rows],
            "warnings": warnings,
        }

    db.commit()
    for job in jobs:
        db.refresh(job["row"])
        job["acquisition_id"] = job["row"].id

    authorization = _auth_headers().get("Authorization")
    transport = download_transport or _StreamingDownloadTransport()
    job_specs = [
        {
            "acquisition_id": job["acquisition_id"],
            "target": job["target"],
            "notes": job["notes"],
            "metadata": CivitaiFileMetadata(
                download_url=job["chosen"]["download_url"],
                sha256=job["chosen"]["sha256"],
                size=job["chosen"]["size_bytes"],
                availability=True,
                scan_status=job["chosen"]["scan_status"],
                license=license_info,
                usage=None,
            ),
        }
        for job in jobs
    ]

    def _run() -> None:
        # Sequential on purpose: one big file at a time is gentler on the
        # external disk and keeps per-file progress readable.
        session = (session_factory or SessionLocal)()
        try:
            for spec in job_specs:
                _run_one(session, spec, transport=transport, authorization=authorization)
        finally:
            session.close()

    if run_in_background:
        factory = thread_factory or (lambda **kwargs: threading.Thread(**kwargs))
        thread = factory(target=_run, name=f"civitai-acquire-{job_specs[0]['acquisition_id']}", daemon=True)
        thread.start()
    else:
        _run()
        db.expire_all()
        ids = [spec["acquisition_id"] for spec in job_specs]
        fresh_rows = (
            db.query(DownloadedResource).filter(DownloadedResource.id.in_(ids)).order_by(DownloadedResource.id).all()
        )
        statuses = {row.status for row in fresh_rows} | {row.status for row in done_rows}
        status = "installed" if statuses <= _INSTALLED_STATUSES else ("failed" if "failed" in statuses else fresh_rows[0].status)
        return {
            "status": status,
            "resource": _resource_summary(fresh_rows[0]),
            "resources": [_resource_summary(row) for row in done_rows + fresh_rows],
            "warnings": warnings,
        }

    started_rows = done_rows + active_rows + [job["row"] for job in jobs]
    return {
        "status": "downloading",
        "resource": _resource_summary(jobs[0]["row"]),
        "resources": [_resource_summary(row) for row in started_rows],
        "warnings": warnings,
        "next_step": "下載已在背景進行；用 civitai_resource_status 查進度，installed 之後即可用於生圖",
    }


def _run_one(session: Session, spec: dict[str, Any], *, transport: Any, authorization: str | None) -> None:
    """Download one file and record the outcome; never let one failure stop the batch."""
    acquisition_id = spec["acquisition_id"]
    notes = spec["notes"]
    try:
        result = safe_download(spec["metadata"], spec["target"], transport=transport, authorization=authorization)
        fresh = session.query(DownloadedResource).filter(DownloadedResource.id == acquisition_id).one()
        fresh_notes = dict(notes)
        if result.status == "completed":
            stat = Path(result.final_path).stat()
            fresh_notes["file_identity"] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "inode": stat.st_ino}
            fresh.status = "installed"
            fresh.local_path = result.final_path
            fresh.file_size = result.bytes
            fresh.sha256 = result.actual_sha256
            fresh.downloaded_at = datetime.utcnow()
        else:
            fresh.status = "failed"
            fresh_notes["error"] = result.diagnostics.get("reason") or f"download {result.status}"
        fresh.notes = json.dumps(redact_secrets(fresh_notes), ensure_ascii=False)
        session.commit()
    except Exception as exc:  # noqa: BLE001 — the thread must record any failure
        session.rollback()
        try:
            fresh = session.query(DownloadedResource).filter(DownloadedResource.id == acquisition_id).one()
            fresh.status = "failed"
            fresh.notes = json.dumps(redact_secrets({**notes, "error": exc.__class__.__name__}), ensure_ascii=False)
            session.commit()
        except Exception:
            session.rollback()


def acquisition_status(db: Session, *, acquisition_id: int | None = None, limit: int = 10) -> dict[str, Any]:
    query = db.query(DownloadedResource).filter(DownloadedResource.provider == "civitai")
    if acquisition_id is not None:
        row = query.filter(DownloadedResource.id == acquisition_id).one_or_none()
        if row is None:
            raise AcquireError("not_found", f"找不到 acquisition_id={acquisition_id}")
        return {"resources": [_resource_summary(row)]}
    rows = query.order_by(DownloadedResource.id.desc()).limit(max(1, min(limit, 50))).all()
    return {"resources": [_resource_summary(row) for row in rows]}
