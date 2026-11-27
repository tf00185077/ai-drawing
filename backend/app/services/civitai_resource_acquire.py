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
import re
import os
from pathlib import Path
import threading
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import SessionLocal
from app.db.models import DownloadedResource
from app.services.civitai_acquisition import AcquisitionError, parse_civitai_locator, redact_secrets
from app.services.civitai_safe_download import (CivitaiFileMetadata, safe_download, preflight_download, verified_existing, _matches)
from app.services.resource_records import download_context, publish_download_state, bounded_resource_admission
from app.services import download_jobs as durable
from app.services.civitai_download_policy import DownloadPolicy, selected_size, download_error

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


# Keep the established public exception name and transport adapters.
from app.services.civitai_provider import (
    CivitaiProviderError as AcquireError, ProviderOperation, ProviderDownloadTransport, resolve_credentials,
)


class _JsonTransport:
    def __init__(self, operation: ProviderOperation):
        self.operation = operation

    def get_json(self, url: str, *, headers=None):
        return self.operation.get_json(url)


class _StreamingDownloadTransport(ProviderDownloadTransport):
    pass


# Public import retained for frozen recipe/AIR callers and Anima package routing.
from app.services.civitai_resource_legacy import normalize_model_family
from app.schemas.resources import ResourceMetadata
from app.services.resource_records import (assert_identity, measured_evidence, metadata_for, publish_metadata, safe_evidence,
    provider_snapshot, ResourceIdentityConflict)


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
    authorization = resolve_credentials(get_settings())
    return {"Authorization": authorization} if authorization else {}


def _fetch_json(transport: Any, url: str, headers: dict[str, str]) -> Any:
    status, payload = transport.get_json(url, headers=headers)
    if status == 404:
        raise AcquireError("not_found", "Civitai resource was not found")
    if status == 401 or status == 403:
        raise AcquireError(
            "unauthorized",
            f"Civitai 拒絕存取（HTTP {status}）",
            hint="Check Backend CIVITAI_API_KEY_FILE or legacy CIVITAI_AUTHORIZATION; provider access restrictions still apply.",
        )
    if not 200 <= status < 300:
        raise AcquireError("civitai_api_error", f"Civitai API 回應 HTTP {status}，可稍後重試", hint="Check provider availability/access limits, then inspect the same acquisition ID before retrying.")
    return payload


def resolve_version_metadata(locator: int | str, *, transport: Any | None = None) -> dict[str, Any]:
    """Resolve any reasonable locator to one Civitai model version payload.

    Accepts: full model URL (with or without modelVersionId), bare model-version
    ID, bare model ID (uses its latest version). Image/post URLs get a hint to
    supply the model page instead.
    """
    with ProviderOperation('metadata', settings=get_settings()) as operation:
        result = _resolve_version_metadata(locator, transport=transport or _JsonTransport(operation), headers=operation.headers)
        return operation.metadata(result)


def _resolve_version_metadata(locator, *, transport, headers):
    model_id: int | None = None
    version_id: int | None = None

    raw = str(locator).strip()
    if raw.isdecimal():
        # A bare number is ambiguous: try model-version first, then model.
        candidate = int(raw)
        try:
            version_payload = _fetch_json(transport, f"https://civitai.com/api/v1/model-versions/{candidate}", headers)
            if isinstance(version_payload, dict) and version_payload.get("id") == candidate:
                model_payload = _maybe_fetch_model(transport, version_payload.get("modelId"), headers)
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
        version_payload = _fetch_json(transport, f"https://civitai.com/api/v1/model-versions/{version_id}", headers)
        model_payload = _maybe_fetch_model(transport, version_payload.get("modelId") if isinstance(version_payload, dict) else None, headers)
        return {"version": version_payload, "model": model_payload}
    if model_id is None:
        raise AcquireError("unsupported_locator", "無法從輸入解析出模型 ID")
    model_payload = _fetch_json(transport, f"https://civitai.com/api/v1/models/{model_id}", headers)
    versions = model_payload.get("modelVersions") if isinstance(model_payload, dict) else None
    if not isinstance(versions, list) or not versions or not isinstance(versions[0], dict):
        raise AcquireError("no_versions", "此模型沒有可用版本")
    return {"version": versions[0], "model": model_payload}


def _maybe_fetch_model(transport: Any, model_id: Any, headers: dict[str, str]) -> dict[str, Any] | None:
    if not isinstance(model_id, int):
        return None
    try:
        payload = _fetch_json(transport, f"https://civitai.com/api/v1/models/{model_id}", headers)
    except AcquireError as exc:
        if exc.code != "not_found":
            raise
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_file(chosen: dict[str, Any]) -> dict[str, Any]:
    """Validate one Civitai file entry; the virus-scan gate stays hard."""
    name = Path(str(chosen.get("name", ""))).name
    hashes = chosen.get("hashes")
    raw_sha = hashes.get("SHA256") if isinstance(hashes, dict) else None
    sha256 = raw_sha.strip().lower() if isinstance(raw_sha, str) else ""
    size_bytes = selected_size(chosen)
    download_url = chosen.get("downloadUrl")
    scan = str(chosen.get("virusScanResult") or "").strip().lower()
    if not name or not name.lower().endswith((".safetensors", ".ckpt", ".pt", ".pth", ".bin")):
        raise AcquireError("unsafe_filename", f"檔名不可用：{name!r}")
    if scan not in _CLEAN_SCAN_STATUSES:
        raise AcquireError(
            "virus_scan_not_clean",
            f"病毒掃描狀態為 {safe_evidence(chosen.get('virusScanResult')) or 'unknown'}，拒絕下載",
            hint="這是硬性安全檢查，不提供繞過；請改用其他掃描通過的版本",
        )
    if size_bytes is None or not isinstance(download_url, str):
        raise AcquireError("incomplete_file_metadata", "檔案缺少 SHA-256、大小或下載網址，無法安全下載")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise AcquireError("incomplete_file_metadata", "Selected file requires a valid SHA-256")
    return {
        "name": name,
        "sha256": sha256,
        "size_bytes": size_bytes,
        "download_url": download_url,
        "civitai_file_id": chosen.get("id"),
        "scan_status": scan,
        "provider_file": chosen,
    }


def choose_file(version_payload: dict[str, Any], *, safetensors_only: bool = False) -> dict[str, Any]:
    """Pick the primary downloadable file."""
    files = version_payload.get("files")
    if not isinstance(files, list) or not files:
        raise AcquireError("no_files", "此模型版本沒有檔案清單")
    candidates = [item for item in files if isinstance(item, dict)]
    if safetensors_only:
        primary = next((item for item in candidates if item.get("primary") is True), None)
        if primary is not None and not str(primary.get("name", "")).lower().endswith((".safetensors", ".ckpt", ".pt", ".pth", ".bin")):
            _normalize_file(primary)  # retain malformed-primary refusal and diagnostics
        candidates = [item for item in candidates if str(item.get("name", "")).lower().endswith(".safetensors")]
        if not candidates:
            raise AcquireError("civitai_unsafe_format", "Checkpoint and LoRA files must use safetensors")
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
    return safe_evidence(snapshot), warnings


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
    from sqlalchemy import inspect
    session = inspect(row).session
    linkage = durable.resource_link(session, row.id) if session is not None else {"job_id": None}
    notes: dict[str, Any] = {}
    if row.notes:
        try:
            parsed = json.loads(row.notes)
            if isinstance(parsed, dict):
                notes = parsed
        except ValueError:
            pass
    snapshot, _ = metadata_for(row)
    operation = snapshot.source_evidence.get("acquisition") if snapshot else None
    current_error = operation.get("error") if isinstance(operation, dict) else notes.get("error")
    total = row.file_size or notes.get("expected_size_bytes")
    progress: dict[str, Any] = {}
    progress = linkage.get("progress") or {}
    return safe_evidence({
        **linkage,
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
        "error": current_error,
    })


def _new_notes_json(notes: dict[str, Any]) -> str:
    """Normalize new source-derived notes; retained note bytes are never replaced."""
    return json.dumps(safe_evidence(notes), ensure_ascii=False)


def start_acquisition(
    locator: int | str,
    *,
    db: Session,
    idempotency_key: str | None = None,
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
    key = durable.key_digest(idempotency_key)
    settings = get_settings()
    policy = DownloadPolicy.from_settings(settings)
    resolved = resolve_version_metadata(locator, transport=metadata_transport)
    version = resolved["version"]
    model = resolved["model"]

    model_type = str((model or {}).get("type") or (version.get("model") or {}).get("type") or "").strip().casefold()
    if model_type not in _MODEL_TYPE_ROOTS:
        supported = ", ".join(sorted({key for key in _MODEL_TYPE_ROOTS}))
        raise AcquireError(
            "unsupported_model_type",
            f"不支援的模型類型：{safe_evidence((model or {}).get('type') or (version.get('model') or {}).get('type')) or 'unknown'}",
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
        components = [(choose_file(version, safetensors_only=resource_type in {"checkpoint", "lora"}), root_key, resource_type)]

    # Validate every selected package component before any row is mutated.
    for chosen, _, comp_type in components:
        policy.validate(chosen["size_bytes"], chosen["sha256"])
        policy.validate_format(comp_type, chosen["name"])

    with ProviderOperation('download', settings=settings) as admission, bounded_resource_admission(admission):
        token = durable.owner_for(db.get_bind(), admission)
        version_id = version.get("id")
        model_id = version.get("modelId") or (model or {}).get("id")
        existing = (
            db.query(DownloadedResource)
            .filter(DownloadedResource.provider == "civitai")
            .filter(DownloadedResource.version_id == str(version_id))
            .populate_existing()
            .order_by(DownloadedResource.id.desc())
            .all()
        )

        roots = _storage_roots(settings)
        selected = []
        keys = []
        for chosen, comp_root, comp_type in components:
            identity = {"provider": "civitai", "resource_type": comp_type,
                "model_id": str(model_id) if model_id is not None else None,
                "version_id": str(version_id) if version_id is not None else None,
                "civitai_file_id": str(chosen["civitai_file_id"]) if chosen["civitai_file_id"] is not None else None,
                "sha256": chosen["sha256"], "size": chosen["size_bytes"],
                "air": chosen["provider_file"].get("air") or version.get("air")}
            # Bind the effective configured destination as well as the retained
            # authority path; changing either must not silently rebind a key.
            selected.append({**identity, "destination": str(roots[comp_root] / chosen["name"])})
            matched = next((row for row in existing if row.resource_name == chosen["name"] or
                (row.civitai_file_id is not None and row.civitai_file_id == identity["civitai_file_id"])), None)
            target = Path(matched.local_path) if matched is not None and matched.local_path else roots[comp_root] / chosen["name"]
            keys.extend(durable.claim_keys(identity, target))
        selection = durable.selection_digest(selected)
        known = durable.replay(db, selection, key)
        if known is None:
            known = durable.active_claim(db, keys, selection)
            if known is not None and key is not None:
                raise durable.error("civitai_resource_active", "This selection already has an active download job", job_id=known.id)
        if known is not None:
            return _operation_response(db, known.id, warnings=warnings, replay=True)
        if len(components) > durable.MAX_COMPONENTS:
            raise durable.error("download_package_limit", "Selected package exceeds the bounded component limit")
        adoptions = {}
        # Destination-space/partial/identity admission is package-wide and read-only.
        for chosen, comp_root, comp_type in components:
            matched = next((row for row in existing if row.resource_name == chosen["name"] or
                           (row.civitai_file_id is not None and row.civitai_file_id == str(chosen["civitai_file_id"]))), None)
            if matched is not None and matched.status in _ACTIVE_STATUSES:
                raise durable.error("download_legacy_untracked", "The resource has legacy downloading state without a durable operation", resource_id=matched.id)
            target = Path(matched.local_path) if matched is not None and matched.local_path else roots[comp_root] / chosen["name"]
            metadata = CivitaiFileMetadata(chosen["download_url"], chosen["sha256"], chosen["size_bytes"], scan_status=chosen["scan_status"])
            if os.path.lexists(target):
                _, _, adoptions[str(target)] = verified_existing(target, metadata, admission)
            else:
                association, resume = download_context(matched, metadata.size, metadata.sha256) if matched else (None, None)
                preflight_download(metadata, target, policy, association=association, resume=resume, operation=admission)

        admission.remaining()

        with durable.transaction(db, admission):
            existing = (db.query(DownloadedResource).filter_by(provider="civitai", version_id=str(version_id))
                        .populate_existing().order_by(DownloadedResource.id.desc()).all())
            known = durable.replay(db, selection, key) or durable.active_claim(db, keys, selection)
            if known is not None:
                if key is not None and known.idempotency_digest != key:
                    raise durable.error("civitai_resource_active", "This selection already has an active download job", job_id=known.id)
                return _operation_response(db, known.id, warnings=warnings, replay=True)
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
            operation_rows = []

            for chosen, comp_root, comp_type in components:
                matched = next((row for row in existing if row.resource_name == chosen["name"] or
                                (row.civitai_file_id is not None and row.civitai_file_id == str(chosen["civitai_file_id"]))), None)
                snapshot = provider_snapshot(version, model, chosen["provider_file"])
                identity = {"provider": "civitai", "resource_type": comp_type,
                            "model_id": str(model_id) if model_id is not None else None,
                            "version_id": str(version_id) if version_id is not None else None,
                            "civitai_file_id": str(chosen["civitai_file_id"]) if chosen["civitai_file_id"] is not None else None,
                            "sha256": chosen["sha256"],
                            "air": chosen["provider_file"].get("air") or version.get("air")}
                if matched is not None:
                    try:
                        assert_identity(matched, identity)
                        if matched.status not in _ACTIVE_STATUSES:
                            publish_metadata(matched, snapshot, identity=identity)
                    except ResourceIdentityConflict:
                        db.rollback()
                        raise AcquireError("resource_identity_conflict", "Recorded resource identity conflicts with the selected provider file",
                                           hint="Inspect the existing resource ID; choose a distinct provider file without rebinding it.") from None
                if matched is not None and matched.status in _INSTALLED_STATUSES and matched.local_path and Path(matched.local_path).is_file():
                    done_rows.append(matched)
                    operation_rows.append((matched, identity, Path(matched.local_path), True))
                    continue
                if matched is not None and matched.status in _ACTIVE_STATUSES:
                    active_rows.append(matched)
                    continue
                notes = {**common_notes, "expected_size_bytes": chosen["size_bytes"]}
                target = Path(matched.local_path) if matched is not None and matched.local_path else roots[comp_root] / chosen["name"]
                row = matched or DownloadedResource(
                    resource_name=chosen["name"],
                    resource_type=comp_type,
                    provider="civitai",
                    source_url=f"https://civitai.com/models/{model_id}?modelVersionId={version_id}" if model_id else str(locator),
                    resolved_download_url=safe_evidence(chosen["download_url"]),
                    local_path=str(target),
                    storage_root=comp_root,
                    file_size=chosen["size_bytes"],
                    sha256=chosen["sha256"],
                    model_id=str(model_id) if model_id is not None else None,
                    version_id=str(version_id) if version_id is not None else None,
                    civitai_file_id=str(chosen["civitai_file_id"]) if chosen["civitai_file_id"] is not None else None,
                    status="downloading",
                    notes=_new_notes_json(notes),
                )
                if matched is not None:
                    row.status = "downloading"
                publish_metadata(row, snapshot, identity=identity)
                db.add(row)
                _publish_acquisition_outcome(row, "downloading")
                operation_rows.append((row, identity, target, False))
                jobs.append({"chosen": chosen, "target": target, "notes": notes, "row": row, "identity": identity,
                             "preserve_notes": matched is not None})

            public_job = durable.admit(db, selection=selection, key=key, token=token, policy=policy, rows=operation_rows)
            public_job_id = public_job.id
            db.flush()
            for job in jobs:
                job["acquisition_id"] = job["row"].id

    # No callable is launched until the surrounding durable transaction commits.
    if not jobs:
        return _operation_response(db, public_job_id, warnings=warnings)

    transport = download_transport
    job_specs = [
        {
            "job_id": public_job_id, "owner_token": token,
            "acquisition_id": job["acquisition_id"],
            "adoption": adoptions.get(str(job["target"])),
            "identity": job["identity"],
            "preserve_notes": job["preserve_notes"],
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
                _run_one(session, spec, transport=transport, settings=settings)
        finally:
            session.close()

    if run_in_background:
        factory = thread_factory or (lambda **kwargs: threading.Thread(**kwargs))
        try:
            thread = factory(target=_run, name=f"civitai-acquire-{public_job_id}", daemon=True)
            thread.start()
        except Exception:
            durable.fail_unstarted(db, public_job_id, token, {"code": "download_launch_failed", "message": "The admitted worker could not start", "hint": "Read the same job before retrying."})
            return _operation_response(db, public_job_id, warnings=warnings)
    else:
        _run()
        db.expire_all()
        return _operation_response(db, public_job_id, warnings=warnings)

    return _operation_response(db, public_job_id, warnings=warnings)


def _operation_response(db, job_id, *, warnings=(), replay=False):
    value = durable.status(db, job_id)
    rows = [db.get(DownloadedResource, rid) for rid in value["resource_ids"]]
    state = value["status"]
    legacy = "already_installed" if state == "completed" and (replay or all(c["result"] and c["result"].get("code") == "verified_existing" for c in value["components"])) else ("installed" if state == "completed" else "failed" if state == "failed" else "downloading")
    return safe_evidence({"job_id": job_id, "job_domain": "download", "job_status": state,
        "status": legacy, "resource": _resource_summary(rows[0]),
        "resources": [_resource_summary(row) for row in rows], "warnings": list(warnings),
        "next_step": f"Read download job {job_id} with wait_for_job; resource IDs still identify resources."})


def _publish_acquisition_outcome(row: DownloadedResource, status: str, error: Any = None, *, measured=None) -> None:
    """Current operation state augments metadata; historical notes stay evidence."""
    publish_download_state(row, status, error, measured=measured)


def _run_one(session: Session, spec: dict[str, Any], *, transport: Any, settings: Any) -> None:
    """Download one file and record the outcome; never let one failure stop the batch."""
    acquisition_id = spec["acquisition_id"]
    notes = spec["notes"]
    job_id, token = spec["job_id"], spec["owner_token"]
    try:
        with ProviderOperation('download', settings=settings) as operation:
            durable.begin_component(session, job_id, acquisition_id, token, operation)
            fresh = session.get(DownloadedResource, acquisition_id)
            association, resume = download_context(fresh, spec["metadata"].size, spec["metadata"].sha256)
            def record_partial(proof):
                with durable.publication(session, job_id, acquisition_id, token, operation) as (current, component):
                    measured = proof["identity"]["size"]
                    if not 0 <= measured <= component.selected_size:
                        raise download_error("download_invalid_progress", "Measured progress exceeds the selected size")
                    component.downloaded_bytes = measured
                    publish_download_state(current, "downloading", partial=proof)
            assert_identity(fresh, spec["identity"])
            if spec.get("adoption") is not None:
                if not _matches(spec["target"], spec["adoption"]):
                    raise download_error("civitai_file_changed", "Admitted existing file changed")
                size, sha, owned = verified_existing(spec["target"], spec["metadata"], operation)
                from app.services.civitai_safe_download import DownloadResult
                result = DownloadResult("completed", str(spec["target"]), sha, size, False, {"code": "adopted_existing"}, owned)
            else:
                result = safe_download(spec["metadata"], spec["target"], transport=transport or _StreamingDownloadTransport(operation),
                    authorization=operation.authorization, operation=operation, policy=DownloadPolicy.from_settings(settings),
                    association=association, resume=resume, record_partial=record_partial)
            if result.status != "completed":
                reason = {key: result.diagnostics[key] for key in ("code", "message", "hint") if key in result.diagnostics}
                if not reason:
                    reason = {"code": "civitai_download_failed", "message": "Download failed"}
                with durable.publication(session, job_id, acquisition_id, token, operation) as (fresh, component):
                    if not spec.get("preserve_notes", False):
                        fresh.notes = _new_notes_json({**notes, "error": reason})
                durable.terminal_component(session, job_id, acquisition_id, token, reason=reason)
                return
            if not _matches(Path(result.final_path), result.publication):
                raise download_error("civitai_file_changed", "Final changed before resource publication")
            with durable.publication(session, job_id, acquisition_id, token, operation) as (fresh, component):
                assert_identity(fresh, spec["identity"])
                stat = Path(result.final_path).stat()
                fresh.status = "installed"
                fresh.local_path = result.final_path
                fresh.file_size = result.bytes
                fresh.sha256 = result.actual_sha256
                fresh.downloaded_at = datetime.utcnow()
                _publish_acquisition_outcome(fresh, "installed", measured=measured_evidence(Path(result.final_path), result.bytes, result.actual_sha256, identity=result.publication))
                if not spec.get("preserve_notes", False):
                    fresh.notes = _new_notes_json({**notes, "file_identity": {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "inode": stat.st_ino}})
            operation.remaining()
            if not _matches(Path(result.final_path), result.publication):
                raise download_error("civitai_file_changed", "Final changed during resource publication")
            durable.terminal_component(session, job_id, acquisition_id, token, result={
                "code": result.diagnostics.get("code", "download_verified"), "byte_size": result.bytes,
                "sha256": result.actual_sha256, "resume_used": result.resume_used})
    except BaseException as exc:
        session.rollback()
        try:
            reason = exc.to_dict() if isinstance(exc, AcquireError) else {"code": "civitai_download_failed", "message": "Civitai download failed", "hint": "Read the same download job before retrying."}
            with durable.publication(session, job_id, acquisition_id, token) as (fresh, component):
                if not spec.get("preserve_notes", False):
                    fresh.notes = _new_notes_json({**notes, "error": reason})
            durable.terminal_component(session, job_id, acquisition_id, token, reason=reason)
        except Exception:
            session.rollback()
        if not isinstance(exc, Exception):
            raise


def acquisition_status(db: Session, *, acquisition_id: int | None = None, limit: int = 10) -> dict[str, Any]:
    query = db.query(DownloadedResource).filter(DownloadedResource.provider == "civitai")
    if acquisition_id is not None:
        row = query.filter(DownloadedResource.id == acquisition_id).one_or_none()
        if row is None:
            raise AcquireError("not_found", f"找不到 acquisition_id={acquisition_id}")
        return {"resources": [_resource_summary(row)]}
    rows = query.order_by(DownloadedResource.id.desc()).limit(max(1, min(limit, 50))).all()
    return {"resources": [_resource_summary(row) for row in rows]}
