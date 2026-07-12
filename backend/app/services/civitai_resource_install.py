"""CIV-V-D guarded Civitai resource inspect/select/install service.

The service deliberately has no caller credentials or caller destination paths.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, cast
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.db.models import DownloadedResource
from app.services.civitai_acquisition import redact_secrets
from app.services.civitai_safe_download import CivitaiFileMetadata, safe_download

_ALLOWED_KINDS = frozenset({"checkpoint", "lora", "vae", "embedding", "controlnet", "upscaler"})
_CLEAN = frozenset({"clean", "success", "passed"})
_DESCRIPTOR_FIELDS = frozenset({
    "civitai_model_id", "civitai_model_version_id", "civitai_file_id", "resource_kind",
    "name", "download_url_identity", "sha256", "byte_size", "availability", "scan_status",
    "license", "usage_restrictions", "air", "model_family",
})
_DOWNLOAD_PATH = re.compile(r"/api/download/models/[1-9][0-9]*$")


def _number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdecimal() and int(value) > 0:
        return int(value)
    return None


def _kind(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    return {
        "lora": "lora", "checkpoint": "checkpoint", "model": "checkpoint", "vae": "vae",
        "embedding": "embedding", "textualinversion": "embedding", "controlnet": "controlnet",
        "upscaler": "upscaler",
    }.get(text, "other")


def _model_id(value: Mapping[str, Any]) -> int | None:
    model = value.get("model")
    nested = model.get("id") if isinstance(model, Mapping) else None
    return _number(value.get("modelId")) or _number(nested)


def _download_url_identity(value: Any) -> str | None:
    """Return only a canonical public Civitai download identity, never a bearer URL."""
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"civitai.com", "www.civitai.com"}
        or parsed.username
        or parsed.password
        or parsed.port is not None
        or not _DOWNLOAD_PATH.fullmatch(parsed.path)
    ):
        return None
    return urlunsplit(("https", "civitai.com", parsed.path, "", ""))


def _scan(value: Any) -> str:
    return str(value or "unknown").strip().lower() or "unknown"


def _availability(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"public", "available", "true"}


def _model_policy(payload: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Normalize Civitai model-level permission fields without inventing policy."""
    no_credit = payload.get("allowNoCredit")
    different_license = payload.get("allowDifferentLicense")
    derivatives = payload.get("allowDerivatives")
    commercial = payload.get("allowCommercialUse")
    if not all(isinstance(value, bool) for value in (no_credit, different_license, derivatives)):
        return None, None
    if isinstance(commercial, str):
        text = commercial.strip()
        if text.startswith("{") and text.endswith("}"):
            commercial = sorted(part.strip() for part in text[1:-1].split(",") if part.strip())
    if not isinstance(commercial, list) or not commercial or not all(
        isinstance(value, str) and value.strip() for value in commercial
    ):
        return None, None
    return (
        {
            "source": "civitai_model_permissions",
            "allow_no_credit": no_credit,
            "allow_different_license": different_license,
        },
        {
            "allow_commercial_use": list(commercial),
            "allow_derivatives": derivatives,
        },
    )


def _size(file: Mapping[str, Any]) -> int | None:
    raw = file.get("size")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
        return int(raw)
    raw = file.get("sizeKB")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
        return int(raw * 1024)
    return None


def _resource_type(payload: Mapping[str, Any], version: Mapping[str, Any], file: Mapping[str, Any]) -> str:
    model = version.get("model")
    return _kind(
        payload.get("type")
        or version.get("type")
        or (model.get("type") if isinstance(model, Mapping) else None)
        or file.get("type")
    )


def inspect_civitai_resource(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an offline model/version payload into deterministic redacted descriptors."""
    model_versions = payload.get("modelVersions")
    is_model_payload = isinstance(model_versions, list)
    declared_model_id = _number(payload.get("id")) if is_model_payload else _model_id(payload)
    versions = model_versions if is_model_payload else ([payload] if payload.get("files") else [])
    policy_license, policy_usage = _model_policy(payload)
    candidates: list[dict[str, Any]] = []
    for version in versions:
        if not isinstance(version, Mapping):
            continue
        version_id = _number(version.get("id"))
        model_id = _model_id(version) or declared_model_id
        for file in version.get("files") or []:
            if not isinstance(file, Mapping):
                continue
            raw_hashes = file.get("hashes")
            hashes: Mapping[str, Any] = raw_hashes if isinstance(raw_hashes, Mapping) else {}
            raw_sha = hashes.get("SHA256") or hashes.get("sha256") or file.get("sha256")
            sha = str(raw_sha).lower() if isinstance(raw_sha, str) and re.fullmatch(r"[0-9a-fA-F]{64}", raw_sha) else None
            candidate = {
                "civitai_model_id": model_id,
                "civitai_model_version_id": version_id,
                "civitai_file_id": _number(file.get("id")),
                "resource_kind": _resource_type(payload, version, file),
                "name": str(file.get("name") or ""),
                "download_url_identity": _download_url_identity(file.get("downloadUrl") or file.get("download_url")),
                "sha256": sha,
                "byte_size": _size(file),
                "availability": _availability(file.get("availability", version.get("availability", payload.get("availability")))),
                "scan_status": _scan(file.get("virusScanResult") or file.get("scanStatus")),
                "license": file.get("license") or payload.get("license") or policy_license,
                "usage_restrictions": file.get("usage") or payload.get("usage") or policy_usage,
                "air": file.get("air") or version.get("air"),
                "model_family": version.get("baseModel") or payload.get("baseModel"),
            }
            candidates.append(redact_secrets(candidate))
    candidates.sort(key=lambda item: (
        item["civitai_model_id"] or 0, item["civitai_model_version_id"] or 0,
        item["civitai_file_id"] or 0, item["name"],
    ))
    return redact_secrets({
        "status": "completed",
        "source": {"provider": "civitai", "civitai_model_id": declared_model_id},
        "model_family": payload.get("baseModel"),
        "candidates": candidates,
    })


def _safe(candidate: Mapping[str, Any]) -> bool:
    return (
        isinstance(candidate.get("sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", candidate["sha256"]) is not None
        and isinstance(candidate.get("byte_size"), int)
        and not isinstance(candidate.get("byte_size"), bool)
        and candidate["byte_size"] > 0
        and candidate.get("availability") is True
        and str(candidate.get("scan_status") or "").lower() in _CLEAN
        and candidate.get("license") is not None
        and candidate.get("usage_restrictions") is not None
    )


def select_civitai_resource(inspected: Mapping[str, Any], selectors: Mapping[str, Any]) -> dict[str, Any]:
    permitted = {"civitai_model_id", "civitai_model_version_id", "civitai_file_id", "sha256", "resource_kind"}
    if not selectors or set(selectors) - permitted:
        return {"status": "blocked", "diagnostic": {"code": "invalid_selectors"}}
    raw_candidates = inspected.get("candidates")
    candidates: list[Any] = list(raw_candidates) if isinstance(raw_candidates, list) else []

    def matches(candidate: Mapping[str, Any]) -> bool:
        for key, value in selectors.items():
            actual = candidate.get(key)
            if key in {"civitai_model_id", "civitai_model_version_id", "civitai_file_id"}:
                # Compare identity text here so a forged string ID is selected then rejected
                # by canonical descriptor validation rather than being laundered as not-found.
                if str(actual) != str(value):
                    return False
            elif key == "sha256":
                if not isinstance(actual, str) or actual.lower() != str(value).lower():
                    return False
            elif actual != value:
                return False
        return True

    matches_found = [
        cast(Mapping[str, Any], candidate)
        for candidate in candidates
        if isinstance(candidate, Mapping) and matches(cast(Mapping[str, Any], candidate))
    ]
    if not matches_found:
        identities = {key: value for key, value in selectors.items() if key != "resource_kind"}
        code = "conflicting_identity" if identities and any(
            any(str(candidate.get(key)) == str(value) for candidate in candidates if isinstance(candidate, Mapping))
            for key, value in identities.items()
        ) else "not_found"
        return {"status": "blocked", "diagnostic": {"code": code}}
    if len(matches_found) != 1:
        return {"status": "blocked", "diagnostic": {"code": "ambiguous", "count": len(matches_found)}}
    selected, validation_error = _validated_descriptor(matches_found[0])
    if selected is None:
        return {"status": "blocked", "diagnostic": {"code": "unsafe_metadata", "reason": validation_error}}
    return {"status": "completed", "selected": selected}


def _safe_filename(name: str) -> bool:
    return bool(name) and Path(name).name == name and name not in {".", ".."} and "\x00" not in name


def _validated_descriptor(selected: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Require exactly the inspect-produced canonical descriptor before transport."""
    if set(selected) != _DESCRIPTOR_FIELDS:
        return None, "invalid_selected_descriptor"
    descriptor = dict(selected)
    if descriptor.get("resource_kind") not in _ALLOWED_KINDS:
        return None, "invalid_selected_descriptor"
    if any(_number(descriptor.get(field)) is None or descriptor[field] != _number(descriptor[field]) for field in (
        "civitai_model_id", "civitai_model_version_id", "civitai_file_id",
    )):
        return None, "invalid_selected_descriptor"
    if not isinstance(descriptor.get("name"), str) or not _safe_filename(descriptor["name"]):
        return None, "unsafe_destination"
    canonical_url = _download_url_identity(descriptor.get("download_url_identity"))
    if canonical_url is None or descriptor.get("download_url_identity") != canonical_url:
        return None, "unsafe_metadata"
    if not _safe(descriptor):
        return None, "unsafe_metadata"
    if descriptor.get("air") is not None and not isinstance(descriptor["air"], str):
        return None, "invalid_selected_descriptor"
    if descriptor.get("model_family") is not None and not isinstance(descriptor["model_family"], str):
        return None, "invalid_selected_descriptor"
    return descriptor, ""


def _stream_file_identity(path: Path) -> tuple[int, str]:
    """Read a regular final once; callers must have rejected symlinks first."""
    digest = hashlib.sha256()
    byte_size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            byte_size += len(chunk)
            digest.update(chunk)
    return byte_size, digest.hexdigest()


def _has_conflicting_ledger_identity(descriptor: Mapping[str, Any], target: Path, *, db: Session) -> bool:
    """Do not overwrite an installed identity that contradicts this exact file."""
    by_file = db.query(DownloadedResource).filter_by(
        provider="civitai", civitai_file_id=str(descriptor["civitai_file_id"]),
    ).all()
    by_path = db.query(DownloadedResource).filter_by(local_path=str(target)).all()
    expected = {
        "provider": "civitai", "resource_type": descriptor["resource_kind"],
        "model_id": str(descriptor["civitai_model_id"]),
        "version_id": str(descriptor["civitai_model_version_id"]),
        "civitai_file_id": str(descriptor["civitai_file_id"]), "sha256": descriptor["sha256"],
        "local_path": str(target),
    }
    for row in {row.id: row for row in [*by_file, *by_path]}.values():
        if row.status != "installed":
            continue
        if any(getattr(row, field) != value for field, value in expected.items()):
            return True
    return False


def _persist_ledger_identity(
    descriptor: Mapping[str, Any], storage_root: str, target: Path, byte_size: int, sha256: str,
    *, db: Session, authorization: str | None,
) -> int:
    """Persist only an exact Civitai file identity; no file operation is performed here."""
    row = db.query(DownloadedResource).filter_by(
        provider="civitai", civitai_file_id=str(descriptor["civitai_file_id"]),
    ).one_or_none()
    metadata_snapshot = redact_secrets({
        "source_identity": descriptor["download_url_identity"], "license": descriptor["license"],
        "usage_restrictions": descriptor["usage_restrictions"], "model_family": descriptor["model_family"],
    }, secrets=tuple((authorization or "").split()))
    values = {
        "resource_name": descriptor["name"], "resource_type": descriptor["resource_kind"], "provider": "civitai",
        "source_url": descriptor["download_url_identity"], "resolved_download_url": descriptor["download_url_identity"],
        "local_path": str(target), "storage_root": storage_root, "file_size": byte_size,
        "sha256": sha256, "model_id": str(descriptor["civitai_model_id"]),
        "version_id": str(descriptor["civitai_model_version_id"]), "civitai_file_id": str(descriptor["civitai_file_id"]),
        "air": descriptor["air"], "status": "installed", "notes": json.dumps(metadata_snapshot, sort_keys=True),
        "downloaded_at": datetime.utcnow(),
    }
    if row is None:
        row = DownloadedResource(**values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    db.commit()
    return row.id


def install_civitai_resource(
    selected: Mapping[str, Any], storage_root: str, *, db: Session, storage_roots: Mapping[str, Path],
    transport: Any, authorization: str | None = None,
) -> dict[str, Any]:
    descriptor, error = _validated_descriptor(selected)
    if descriptor is None:
        return {"status": "blocked", "diagnostic": {"code": error}}
    expected_root = {
        "checkpoint": "checkpoints", "lora": "loras", "vae": "vae", "embedding": "embeddings",
        "controlnet": "controlnet", "upscaler": "upscale_models",
    }[descriptor["resource_kind"]]
    if storage_root != expected_root or storage_root not in storage_roots:
        return {"status": "blocked", "diagnostic": {"code": "unsafe_destination"}}
    root = Path(storage_roots[storage_root]).resolve()
    candidate_target = root / descriptor["name"]
    if candidate_target.parent != root:
        return {"status": "blocked", "diagnostic": {"code": "unsafe_destination"}}
    # Never resolve/follow a final symlink.  Existing non-regular finals retain the
    # original already_exists result without transport, filesystem, or ledger effects.
    if candidate_target.is_symlink() or (candidate_target.exists() and not candidate_target.is_file()):
        return {"status": "blocked", "diagnostic": {"code": "already_exists"}}
    target = candidate_target.resolve()
    if target.parent != root:
        return {"status": "blocked", "diagnostic": {"code": "unsafe_destination"}}
    if target.exists():
        try:
            actual_size, actual_sha256 = _stream_file_identity(target)
        except OSError:
            return {"status": "blocked", "diagnostic": {"code": "already_exists"}}
        if actual_size != descriptor["byte_size"] or actual_sha256 != descriptor["sha256"]:
            return {"status": "blocked", "diagnostic": {"code": "already_exists"}}
        if _has_conflicting_ledger_identity(descriptor, target, db=db):
            return {"status": "blocked", "diagnostic": {"code": "already_exists"}}
        try:
            ledger_id = _persist_ledger_identity(
                descriptor, storage_root, target, actual_size, actual_sha256,
                db=db, authorization=authorization,
            )
        except Exception:
            db.rollback()
            # This final predates the invocation and must never be compensated away.
            return {"status": "failed", "diagnostic": {"code": "ledger_persistence_failed"}}
        return redact_secrets({
            "status": "completed", "final_path": str(target), "byte_size": actual_size,
            "sha256": actual_sha256, "ledger_id": ledger_id,
            "diagnostic": {"code": "adopted_existing"},
        }, secrets=tuple((authorization or "").split()))

    metadata = CivitaiFileMetadata(
        download_url=descriptor["download_url_identity"], sha256=descriptor["sha256"], size=descriptor["byte_size"],
        availability=True, scan_status=descriptor["scan_status"], license=descriptor["license"],
        usage=descriptor["usage_restrictions"],
    )
    result = safe_download(metadata, target, transport=transport, authorization=authorization, sleep=lambda _: None)
    if result.status != "completed":
        return redact_secrets({
            "status": result.status, "final_path": str(target), "byte_size": result.bytes,
            "sha256": result.actual_sha256, "diagnostic": result.diagnostics,
        }, secrets=tuple((authorization or "").split()))

    # safe_download only returns completed after os.replace; this invocation established target absent above.
    try:
        ledger_id = _persist_ledger_identity(
            descriptor, storage_root, target, result.bytes, cast(str, result.actual_sha256),
            db=db, authorization=authorization,
        )
    except Exception:
        db.rollback()
        # Compensation is limited to this invocation's newly atomically published file.
        target.unlink(missing_ok=True)
        return {"status": "failed", "diagnostic": {"code": "ledger_persistence_failed"}}
    return redact_secrets({
        "status": "completed", "final_path": str(target), "byte_size": result.bytes,
        "sha256": result.actual_sha256, "ledger_id": ledger_id, "diagnostic": result.diagnostics,
    }, secrets=tuple((authorization or "").split()))
