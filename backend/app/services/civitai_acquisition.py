"""Offline-safe Civitai acquisition boundary for CIV-B.

All HTTP behavior is injected through a transport object. This module normalizes
public Civitai locators, fetches Images API payloads with provenance, merges optional
embedded metadata conservatively, and constructs recipes through CIV-A trusted
evidence capabilities.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from copy import deepcopy
import hashlib
import json
import re
import time
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.schemas.generation_recipe import (
    EvidenceRecord,
    EvidenceSource,
    GenerationRecipe,
    MissingCriticality,
    ResourceKind,
    _build_recipe_from_trusted_evidence,
    _issue_trusted_provenance_capability,
    normalize_recipe_payload,
)
from app.services.civitai_embedded_metadata import (
    EmbeddedMetadataResult,
    embedded_metadata_to_recipe_payload,
    extract_embedded_metadata,
    parse_a1111_parameters,
)


_BROWSER_HOSTS = frozenset({"civitai.com", "www.civitai.com"})
_CDN_HOSTS = frozenset({"image.civitai.com", "images.civitai.com"})
_IDENTITY_QUERY = {
    "imageId": "image_id",
    "postId": "post_id",
    "modelId": "model_id",
    "modelVersionId": "model_version_id",
}
_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "token",
    "secret",
    "password",
}


class CivitaiTransport(Protocol):
    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        ...


@dataclass(frozen=True)
class CivitaiLocator:
    kind: str
    canonical_url: str
    image_id: int | None = None
    post_id: int | None = None
    model_id: int | None = None
    model_version_id: int | None = None
    media_url: str | None = None


@dataclass(frozen=True)
class CivitaiTransportResponse:
    status_code: int
    payload: Any
    headers: Mapping[str, str] | None = None

    @property
    def status(self) -> int:
        return self.status_code


@dataclass
class AcquisitionResult:
    status: str
    locator: CivitaiLocator
    image_id: int | None
    recipe: GenerationRecipe | None
    raw_api_payload: dict[str, Any] | None
    media_url: str | None
    media_sha256: str | None
    provenance: dict[str, Any]
    conflicts: list[dict[str, Any]]
    errors: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "locator": asdict(self.locator),
            "image_id": self.image_id,
            "recipe": self.recipe.model_dump() if self.recipe is not None else None,
            "raw_api_payload": self.raw_api_payload,
            "media_url": self.media_url,
            "media_sha256": self.media_sha256,
            "provenance": self.provenance,
            "conflicts": self.conflicts,
            "errors": self.errors,
        }


class AcquisitionError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        provenance: Mapping[str, Any] | None = None,
        secrets: tuple[str, ...] = (),
    ) -> None:
        self.code = code
        self.provenance = redact_secrets(dict(provenance or {}), secrets=secrets)
        super().__init__(f"{code}: {redact_secrets(message, secrets=secrets)}")


def _canonical_json_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _secrets_from_authorization(authorization: str | None) -> tuple[str, ...]:
    if not authorization:
        return ()
    parts = [authorization]
    pieces = [piece for piece in re.split(r"\s+", authorization.strip()) if piece]
    if len(pieces) > 1:
        parts.extend(pieces[1:])
    return tuple(dict.fromkeys(parts))


def redact_secrets(value: Any, *, secrets: tuple[str, ...] = ()) -> Any:
    """Redact authorization-like keys and supplied secret substrings recursively."""

    if isinstance(value, Mapping):
        output = {}
        for key, item in value.items():
            if str(key).lower().replace("-", "_") in _SENSITIVE_KEYS:
                output[key] = "[REDACTED]"
            else:
                output[key] = redact_secrets(item, secrets=secrets)
        return output
    if isinstance(value, list):
        return [redact_secrets(item, secrets=secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item, secrets=secrets) for item in value)
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    return value


def _positive_int(raw: Any, field: str) -> int:
    if isinstance(raw, bool):
        raise ValueError(f"{field} must be a positive integer")
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str) and re.fullmatch(r"[1-9][0-9]*", raw.strip()):
        value = int(raw.strip())
    else:
        raise ValueError(f"{field} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _query_identity(parsed_query: str) -> dict[str, int]:
    query = parse_qs(parsed_query, keep_blank_values=True)
    identities: dict[str, int] = {}
    unknown = sorted(set(query) - set(_IDENTITY_QUERY))
    if unknown:
        raise ValueError("unsupported Civitai identity query parameter: " + ", ".join(unknown))
    for query_name, field in _IDENTITY_QUERY.items():
        values = query.get(query_name)
        if not values:
            continue
        if len(values) != 1:
            raise ValueError(f"{query_name} must appear exactly once")
        identities[field] = _positive_int(values[0], query_name)
    return identities


def _canonical_query(identities: Mapping[str, int], *, path_fields: set[str]) -> str:
    query_items = []
    for query_name, field in _IDENTITY_QUERY.items():
        if field in identities and field not in path_fields:
            query_items.append((query_name, str(identities[field])))
    return urlencode(query_items)


def _parse_civitai_locator(locator: int | str) -> CivitaiLocator:
    """Parse and canonicalize one supported Civitai locator."""

    if isinstance(locator, int) and not isinstance(locator, bool):
        image_id = _positive_int(locator, "image_id")
        return CivitaiLocator(kind="image", image_id=image_id, canonical_url=f"https://civitai.com/images/{image_id}")
    if not isinstance(locator, str):
        raise ValueError("locator must be a positive image ID or supported Civitai URL")
    raw = locator.strip()
    if re.fullmatch(r"[+-]?[0-9]+", raw):
        image_id = _positive_int(raw, "image_id")
        return CivitaiLocator(kind="image", image_id=image_id, canonical_url=f"https://civitai.com/images/{image_id}")
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL port is invalid") from exc
    if parsed.scheme != "https" or parsed.username or parsed.password or port is not None:
        raise ValueError("locator URL must be HTTPS without userinfo or port")
    if host in _CDN_HOSTS:
        if not parsed.path or parsed.path == "/":
            raise ValueError("Civitai CDN URL must include a media path")
        canonical = urlunparse(("https", host, parsed.path, "", parsed.query, ""))
        return CivitaiLocator(kind="cdn", canonical_url=canonical, media_url=canonical)
    if host not in _BROWSER_HOSTS:
        raise ValueError("locator host is not allowlisted")

    path = parsed.path.rstrip("/")
    identities = _query_identity(parsed.query)
    path_fields: set[str] = set()
    kind = ""
    match = re.fullmatch(r"/images/([1-9][0-9]*)", path)
    if match:
        kind = "image"
        identities.setdefault("image_id", int(match.group(1)))
        if identities["image_id"] != int(match.group(1)):
            raise ValueError("image_id conflicts between URL path and query")
        path_fields.add("image_id")
    match = match or re.fullmatch(r"/posts/([1-9][0-9]*)", path)
    if match and not kind:
        kind = "post"
        identities.setdefault("post_id", int(match.group(1)))
        if identities["post_id"] != int(match.group(1)):
            raise ValueError("post_id conflicts between URL path and query")
        path_fields.add("post_id")
    model_match = None if kind else re.fullmatch(r"/models/([1-9][0-9]*)(?:/([A-Za-z0-9][A-Za-z0-9._~-]*))?", path)
    if model_match:
        kind = "model"
        identities.setdefault("model_id", int(model_match.group(1)))
        if identities["model_id"] != int(model_match.group(1)):
            raise ValueError("model_id conflicts between URL path and query")
        path_fields.add("model_id")
    download_match = None if kind else re.fullmatch(r"/api/download/models/([1-9][0-9]*)", path)
    if download_match:
        kind = "model"
        identities.setdefault("model_version_id", int(download_match.group(1)))
        if identities["model_version_id"] != int(download_match.group(1)):
            raise ValueError("model_version_id conflicts between URL path and query")
        path_fields.add("model_version_id")
    if not kind:
        raise ValueError("unsupported Civitai locator path")
    allowed_identity_fields = {
        "image": {"image_id"},
        "post": {"post_id"},
        "model": {"model_id", "model_version_id"},
    }[kind]
    cross_kind_fields = sorted(set(identities) - allowed_identity_fields)
    if cross_kind_fields:
        raise ValueError(
            f"{kind} locator cannot carry cross-kind identity query fields: "
            + ", ".join(cross_kind_fields)
        )

    canonical_host = "civitai.com"
    canonical = urlunparse(
        ("https", canonical_host, path, "", _canonical_query(identities, path_fields=path_fields), "")
    )
    return CivitaiLocator(
        kind=kind,
        canonical_url=canonical,
        image_id=identities.get("image_id"),
        post_id=identities.get("post_id"),
        model_id=identities.get("model_id"),
        model_version_id=identities.get("model_version_id"),
    )


def parse_civitai_locator(locator: int | str) -> CivitaiLocator:
    """Public locator boundary: unsupported input is always a redacted structured error."""
    try:
        return _parse_civitai_locator(locator)
    except AcquisitionError:
        raise
    except (TypeError, ValueError) as exc:
        raise AcquisitionError("unsupported_locator", str(exc)) from exc


def _coerce_response(value: Any) -> CivitaiTransportResponse:
    if isinstance(value, CivitaiTransportResponse):
        return value
    if isinstance(value, tuple) and len(value) in {2, 3}:
        status, payload, *headers = value
        return CivitaiTransportResponse(int(status), payload, headers[0] if headers else {})
    status = getattr(value, "status_code", getattr(value, "status", None))
    if status is not None:
        payload = value.json() if callable(getattr(value, "json", None)) else getattr(value, "payload", None)
        headers = getattr(value, "headers", {})
        return CivitaiTransportResponse(int(status), payload, headers)
    if isinstance(value, Mapping) and "status_code" in value:
        return CivitaiTransportResponse(int(value["status_code"]), value.get("payload"), value.get("headers") or {})
    raise TypeError("transport must return CivitaiTransportResponse, tuple, response-like object, or mapping")


def _retry_delay(
    attempt: int,
    response: CivitaiTransportResponse,
    backoff: Callable[[int, CivitaiTransportResponse], float | int | None] | None,
) -> float:
    headers = {str(key).lower(): str(value) for key, value in (response.headers or {}).items()}
    retry_after = headers.get("retry-after")
    if retry_after is not None:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            return 0.0
    if backoff is None:
        return 0.0
    delay = backoff(attempt, response)
    return max(float(delay or 0), 0.0)


def _request_json(
    url: str,
    *,
    params: dict[str, Any],
    transport: CivitaiTransport,
    authorization: str | None,
    provenance: dict[str, Any],
    backoff: Callable[[int, CivitaiTransportResponse], float | int | None] | None,
    sleep: Callable[[float], None],
    secrets: tuple[str, ...],
) -> Any:
    headers = {"Authorization": authorization} if authorization else {}
    for attempt in range(1, 4):
        try:
            response = _coerce_response(transport.get_json(url, params=params, headers=headers))
        except Exception as exc:
            provenance["requests"].append(
                {
                    "attempt": attempt,
                    "url": url,
                    "params": dict(params),
                    "status": None,
                    "raw": {"error": redact_secrets(str(exc), secrets=secrets)},
                }
            )
            raise AcquisitionError("invalid_payload", str(exc), provenance=provenance, secrets=secrets) from exc
        sanitized_payload = redact_secrets(response.payload, secrets=secrets)
        provenance["requests"].append(
            {
                "attempt": attempt,
                "url": url,
                "params": dict(params),
                "status": response.status_code,
                "raw": sanitized_payload,
            }
        )
        if 200 <= response.status_code < 300:
            return response.payload
        retryable = response.status_code == 429 or 500 <= response.status_code <= 599
        if not retryable:
            # The frozen acquisition contract only exposes structured failure codes.
            # 404 is an absence; every other non-retryable response is malformed or
            # unusable acquisition evidence rather than a transport detail.
            code = "not_found" if response.status_code == 404 else "invalid_payload"
            raise AcquisitionError(
                code,
                f"Civitai request failed with status {response.status_code}",
                provenance=provenance,
                secrets=secrets,
            )
        if attempt == 3:
            raise AcquisitionError(
                "retry_exhausted",
                f"Civitai transient request retry budget exhausted at status {response.status_code}",
                provenance=provenance,
                secrets=secrets,
            )
        delay = _retry_delay(attempt, response, backoff)
        if delay > 0:
            sleep(delay)
    raise AssertionError("unreachable retry loop exit")


def _fetch_media_evidence(
    transport: CivitaiTransport,
    media_url: str | None,
    *,
    provenance: dict[str, Any],
    secrets: tuple[str, ...],
) -> tuple[str | None, EmbeddedMetadataResult | None]:
    """Acquire bytes and extract embedded evidence from those exact bytes only."""
    if not media_url or not hasattr(transport, "get_bytes"):
        return None, None
    try:
        value = getattr(transport, "get_bytes")(media_url)
        response = _coerce_response(value)
    except Exception as exc:
        raise AcquisitionError("media_decode_error", str(exc), provenance=provenance, secrets=secrets) from exc
    provenance["requests"].append({
        "attempt": 1, "url": media_url, "params": {}, "status": response.status_code,
        "raw": {"media_sha256": hashlib.sha256(response.payload).hexdigest()} if isinstance(response.payload, bytes) else {"error": "non-bytes media payload"},
    })
    if not (200 <= response.status_code < 300) or not isinstance(response.payload, bytes):
        raise AcquisitionError("media_decode_error", "Civitai media response was not successful bytes", provenance=provenance, secrets=secrets)
    try:
        metadata = extract_embedded_metadata(response.payload)
    except Exception as exc:
        raise AcquisitionError("media_decode_error", "Civitai media bytes could not be decoded", provenance=provenance, secrets=secrets) from exc
    return metadata.image_sha256, metadata


def _api_request_for(locator: CivitaiLocator) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {"withMeta": "true"}
    if locator.kind == "image" and locator.image_id is not None:
        params["imageId"] = locator.image_id
        return "https://civitai.com/api/v1/images", params
    if locator.kind == "post" and locator.post_id is not None:
        params["postId"] = locator.post_id
    elif locator.kind == "model":
        if locator.model_id is not None:
            params["modelId"] = locator.model_id
        if locator.model_version_id is not None:
            params["modelVersionId"] = locator.model_version_id
    elif locator.kind == "cdn" and locator.media_url is not None:
        params["url"] = locator.media_url
    else:
        raise ValueError("unsupported locator")
    return "https://civitai.com/api/v1/images", params


def _candidate_id(candidate: Mapping[str, Any], key: str) -> int | None:
    value = candidate.get(key)
    if value is None and key == "modelId" and isinstance(candidate.get("model"), Mapping):
        value = candidate["model"].get("id")
    if value is None and key == "modelVersionId" and isinstance(candidate.get("modelVersion"), Mapping):
        value = candidate["modelVersion"].get("id")
    try:
        return _positive_int(value, key) if value is not None else None
    except ValueError:
        return None


def _candidate_matches(locator: CivitaiLocator, candidate: Mapping[str, Any]) -> bool:
    if locator.kind == "post" and locator.post_id is not None:
        post_id = _candidate_id(candidate, "postId")
        return post_id is None or post_id == locator.post_id
    if locator.kind == "model":
        model_id = _candidate_id(candidate, "modelId")
        version_id = _candidate_id(candidate, "modelVersionId")
        if locator.model_id is not None and model_id is not None and model_id != locator.model_id:
            return False
        if locator.model_version_id is not None and version_id is not None and version_id != locator.model_version_id:
            return False
        return True
    if locator.kind == "cdn" and locator.media_url is not None:
        return candidate.get("url") in {None, locator.media_url}
    return True


def resolve_image_payload(locator: CivitaiLocator, payload: Any) -> dict[str, Any]:
    """Resolve an Images API payload to exactly one image payload."""

    if isinstance(payload, Mapping) and isinstance(payload.get("id"), int):
        image_id = payload["id"]
        if locator.image_id is not None and image_id != locator.image_id:
            raise AcquisitionError("ambiguous_locator", "image payload ID conflicts with locator")
        return deepcopy(dict(payload))
    if isinstance(payload, Mapping):
        raw_candidates = payload.get("items") or payload.get("images") or payload.get("candidates") or []
    elif isinstance(payload, list):
        raw_candidates = payload
    else:
        raw_candidates = []
    candidates = [
        dict(candidate)
        for candidate in raw_candidates
        if isinstance(candidate, Mapping) and _candidate_matches(locator, candidate)
    ]
    if not candidates:
        raise AcquisitionError("not_found", "Civitai locator did not resolve to any image candidates")
    unique_ids = {candidate.get("id") for candidate in candidates if candidate.get("id") is not None}
    if len(candidates) == 1 or len(unique_ids) == 1:
        return deepcopy(candidates[0])
    raise AcquisitionError("ambiguous_locator", "Civitai locator resolved to multiple image candidates")


def _as_int(value: Any) -> int | None:
    try:
        return _positive_int(value, "value") if value is not None else None
    except ValueError:
        return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_sha256(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if re.fullmatch(r"[0-9a-f]{64}", normalized) else None


def _first_mapping(*values: Any) -> Mapping[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return value
    return {}


def _first_text(mapping: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_size(value: Any) -> tuple[int | None, int | None]:
    if not isinstance(value, str):
        return None, None
    match = re.fullmatch(r"\s*([1-9][0-9]*)\s*x\s*([1-9][0-9]*)\s*", value)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _resource_kind(raw_type: Any) -> str:
    normalized = str(raw_type or "").strip().lower().replace("-", "_")
    if normalized in {"checkpoint", "model", "base_model"}:
        return ResourceKind.CHECKPOINT.value
    if normalized in {"lora", "locon", "lycoris"}:
        return ResourceKind.LORA.value
    if normalized == "vae":
        return ResourceKind.VAE.value
    if normalized in {"embedding", "textual_inversion"}:
        return ResourceKind.EMBEDDING.value
    if normalized in {"controlnet", "control_net"}:
        return ResourceKind.CONTROLNET.value
    if normalized in {"upscaler", "upscale"}:
        return ResourceKind.UPSCALER.value
    return ResourceKind.OTHER.value


def _resources_from_api_meta(meta: Mapping[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for item in meta.get("resources") or []:
        if not isinstance(item, Mapping):
            continue
        name = _first_text(item, "name", "modelName", "filename", "fileName")
        if not name:
            continue
        resource: dict[str, Any] = {
            "kind": _resource_kind(item.get("type") or item.get("kind")),
            "name": name,
        }
        for source_key, target_key in (
            ("modelId", "civitai_model_id"),
            ("modelVersionId", "civitai_model_version_id"),
            ("fileId", "civitai_file_id"),
        ):
            parsed = _as_int(item.get(source_key) or item.get(target_key))
            if parsed is not None:
                resource[target_key] = parsed
        sha = _as_sha256(
            item.get("hash")
            or item.get("sha256")
            or _first_mapping(item.get("hashes")).get("SHA256")
            or _first_mapping(item.get("hashes")).get("sha256")
        )
        if sha is not None:
            resource["sha256"] = sha
        weight = _as_float(item.get("weight") or item.get("strength") or item.get("strength_model"))
        if weight is not None and resource["kind"] == ResourceKind.LORA.value:
            resource["strength_model"] = weight
        resources.append(resource)
    return resources


def _api_generation_meta(image_payload: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    """Return generation fields while preserving the live API's nested meta shape raw."""

    outer = _first_mapping(image_payload.get("meta"))
    nested = _first_mapping(outer.get("meta"))
    if nested:
        merged = dict(outer)
        merged.update(nested)
        return merged, "/meta/meta"
    return dict(outer), "/meta"


def _enrich_single_checkpoint_identity(
    image_payload: dict[str, Any],
    *,
    transport: CivitaiTransport,
    authorization: str | None,
    provenance: dict[str, Any],
    backoff: Callable[[int, CivitaiTransportResponse], float | int | None] | None,
    sleep: Callable[[float], None],
    secrets: tuple[str, ...],
) -> None:
    """Resolve an API-supplied short hash only through its sole model version."""
    version_ids = image_payload.get("modelVersionIds")
    meta, _ = _api_generation_meta(image_payload)
    resources = [item for item in meta.get("resources") or [] if isinstance(item, dict)]
    checkpoints = [
        item for item in resources
        if _resource_kind(item.get("type") or item.get("kind")) == ResourceKind.CHECKPOINT.value
    ]
    if not (isinstance(version_ids, list) and len(version_ids) == 1 and len(checkpoints) == 1):
        return
    version_id = _as_int(version_ids[0])
    short_hash = checkpoints[0].get("hash")
    if version_id is None or not isinstance(short_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{10,63}", short_hash.strip()):
        return
    payload = _request_json(
        f"https://civitai.com/api/v1/model-versions/{version_id}",
        params={}, transport=transport, authorization=authorization, provenance=provenance,
        backoff=backoff, sleep=sleep, secrets=secrets,
    )
    files = payload.get("files") if isinstance(payload, Mapping) else None
    matches: list[tuple[Mapping[str, Any], str]] = []
    for item in files if isinstance(files, list) else []:
        if not isinstance(item, Mapping):
            continue
        digest = _as_sha256(_first_mapping(item.get("hashes")).get("SHA256") or item.get("sha256"))
        if digest and digest.startswith(short_hash.strip().lower()):
            matches.append((item, digest))
    if len(matches) != 1:
        return
    matched, digest = matches[0]
    checkpoints[0]["hash"] = digest
    checkpoints[0]["modelVersionId"] = version_id
    file_id = _as_int(matched.get("id"))
    if file_id is not None:
        checkpoints[0]["fileId"] = file_id


def _api_payload_to_recipe_payload(image_payload: Mapping[str, Any], locator: CivitaiLocator) -> dict[str, Any]:
    meta, meta_path = _api_generation_meta(image_payload)
    image_id = _as_int(image_payload.get("id")) or locator.image_id
    source: dict[str, Any] = {"provider": "civitai"}
    if image_id is not None:
        source["image_id"] = image_id
        source["url"] = f"https://civitai.com/images/{image_id}"
    post_id = _as_int(image_payload.get("postId")) or locator.post_id
    model_id = _as_int(image_payload.get("modelId")) or locator.model_id
    version_id = _as_int(image_payload.get("modelVersionId")) or locator.model_version_id
    if post_id is not None:
        source["post_id"] = post_id
    if model_id is not None:
        source["model_id"] = model_id
    if version_id is not None:
        source["model_version_id"] = version_id
    media_url = _first_text(image_payload, "url")
    if media_url:
        source["media_url"] = media_url

    payload: dict[str, Any] = {
        "source": source,
        "raw": {
            "civitai_api": {
                "payload": deepcopy(dict(image_payload)),
                "field_references": _api_field_references(image_payload),
            }
        },
    }
    prompt = _first_text(meta, "prompt", "Prompt")
    negative = _first_text(meta, "negativePrompt", "negative_prompt", "Negative prompt")
    if prompt is not None:
        payload["base_prompt"] = prompt
    if negative is not None:
        payload["negative_prompt"] = negative

    sampling: dict[str, Any] = {}
    seed = _as_int(meta.get("seed") or meta.get("Seed"))
    steps = _as_int(meta.get("steps") or meta.get("Steps"))
    cfg = _as_float(meta.get("cfgScale") or meta.get("cfg_scale") or meta.get("CFG scale"))
    sampler = _first_text(meta, "sampler", "Sampler")
    scheduler = _first_text(meta, "scheduler", "Schedule type")
    width = _as_int(image_payload.get("width")) or _as_int(meta.get("width"))
    height = _as_int(image_payload.get("height")) or _as_int(meta.get("height"))
    if width is None or height is None:
        parsed_width, parsed_height = _parse_size(meta.get("Size") or meta.get("size"))
        width = width or parsed_width
        height = height or parsed_height
    for key, value in (
        ("seed", seed),
        ("steps", steps),
        ("cfg", cfg),
        ("sampler", sampler),
        ("scheduler", scheduler),
        ("width", width),
        ("height", height),
    ):
        if value is not None:
            sampling[key] = value
    if sampling:
        payload["sampling"] = sampling
        payload["passes"] = [{"name": "base", "inherits_from": "recipe.sampling"}]
    resources = _resources_from_api_meta(meta)
    model_version_ids = image_payload.get("modelVersionIds")
    checkpoint_resources = [
        resource for resource in resources if resource["kind"] == ResourceKind.CHECKPOINT.value
    ]
    if (
        isinstance(model_version_ids, list)
        and len(model_version_ids) == 1
        and len(checkpoint_resources) == 1
        and "civitai_model_version_id" not in checkpoint_resources[0]
    ):
        model_version_id = _as_int(model_version_ids[0])
        if model_version_id is not None:
            checkpoint_resources[0]["civitai_model_version_id"] = model_version_id
    if resources:
        payload["resources"] = resources
    api_workflow = _first_mapping(meta.get("workflow"), meta.get("Workflow"), image_payload.get("workflow"))
    if api_workflow:
        payload["workflow"] = {
            "reference": f"civitai_api:images:{image_id or 'unknown'}:{meta_path}/workflow",
            "snapshot": deepcopy(dict(api_workflow)),
            "snapshot_sha256": _canonical_json_sha256(api_workflow),
        }
    return payload


def _api_field_references(image_payload: Mapping[str, Any]) -> dict[str, str]:
    """Point conflicts at the actual Civitai response key selected during mapping."""
    meta, meta_path = _api_generation_meta(image_payload)
    image_id = _as_int(image_payload.get("id")) or "unknown"
    prefix = f"civitai_api:images:{image_id}:"
    references: dict[str, str] = {}
    for canonical_field, keys in (
        ("base_prompt", ("prompt", "Prompt")),
        ("negative_prompt", ("negativePrompt", "negative_prompt", "Negative prompt")),
        ("sampling.seed", ("seed", "Seed")),
        ("sampling.steps", ("steps", "Steps")),
        ("sampling.cfg", ("cfgScale", "cfg_scale", "CFG scale")),
        ("sampling.sampler", ("sampler", "Sampler")),
        ("sampling.scheduler", ("scheduler", "Schedule type")),
        ("workflow", ("workflow", "Workflow")),
    ):
        for key in keys:
            if key in meta and meta[key] is not None:
                references[canonical_field] = f"{prefix}{meta_path}/{key}"
                break
    for canonical_field, key in (("sampling.width", "width"), ("sampling.height", "height")):
        if image_payload.get(key) is not None:
            references[canonical_field] = f"{prefix}/{key}"
        elif meta.get(key) is not None:
            references[canonical_field] = f"{prefix}{meta_path}/{key}"
    if "workflow" not in references and image_payload.get("workflow") is not None:
        references["workflow"] = f"{prefix}/workflow"
    return references


def _embedded_field_references(metadata: EmbeddedMetadataResult) -> dict[str, str]:
    """Locate parsed A1111/ComfyUI fields in the raw container that supplied them."""
    references: dict[str, str] = {}
    containers = metadata.raw.get("containers") if isinstance(metadata.raw, Mapping) else None
    if not isinstance(containers, list):
        return references
    a1111_container: Mapping[str, Any] | None = None
    workflow_container: Mapping[str, Any] | None = None
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        prefix = f"embedded_metadata:{container.get('container')}:{container.get('key')}"
        if a1111_container is None and metadata.a1111 is not None:
            value = container.get("value")
            if isinstance(value, str) and parse_a1111_parameters(value) == metadata.a1111:
                a1111_container = container
                for canonical_field, suffix in (
                    ("base_prompt", "/a1111/prompt"),
                    ("negative_prompt", "/a1111/negative_prompt"),
                    ("sampling.seed", "/a1111/parameters/seed"),
                    ("sampling.steps", "/a1111/parameters/steps"),
                    ("sampling.cfg", "/a1111/parameters/cfg"),
                    ("sampling.sampler", "/a1111/parameters/sampler"),
                    ("sampling.scheduler", "/a1111/parameters/scheduler"),
                    ("sampling.width", "/a1111/parameters/width"),
                    ("sampling.height", "/a1111/parameters/height"),
                ):
                    references[canonical_field] = prefix + ":" + suffix
        if workflow_container is None and metadata.comfyui_workflow is not None and container.get("json") == metadata.comfyui_workflow:
            workflow_container = container
            references["workflow"] = prefix + "/json"
    return references


def _merge_raw(payload: dict[str, Any], key: str, value: Any) -> None:
    raw = payload.setdefault("raw", {})
    raw[key] = deepcopy(value)


def _record_conflict(
    conflicts: list[dict[str, Any]],
    *,
    field: str,
    kept_value: Any,
    kept_reference: str,
    incoming_value: Any,
    incoming_reference: str,
) -> None:
    conflicts.append(
        {
            "field": field,
            "kept": {"value": deepcopy(kept_value), "reference": kept_reference},
            "incoming": {"value": deepcopy(incoming_value), "reference": incoming_reference},
        }
    )


def _merge_known_field(
    payload: dict[str, Any],
    *,
    field: str,
    incoming: Any,
    kept_reference: str,
    incoming_reference: str,
    conflicts: list[dict[str, Any]],
) -> bool:
    if incoming is None:
        return False
    kept = payload.get(field)
    if kept is None:
        payload[field] = deepcopy(incoming)
        return True
    if kept != incoming:
        _record_conflict(
            conflicts,
            field=field,
            kept_value=kept,
            kept_reference=kept_reference,
            incoming_value=incoming,
            incoming_reference=incoming_reference,
        )
    return False


def _merge_sampling(
    payload: dict[str, Any],
    embedded_payload: Mapping[str, Any],
    *,
    api_references: Mapping[str, str],
    embedded_references: Mapping[str, str],
    conflicts: list[dict[str, Any]],
) -> set[str]:
    confirmed_fields: set[str] = set()
    incoming_sampling = embedded_payload.get("sampling")
    if not isinstance(incoming_sampling, Mapping):
        return confirmed_fields
    sampling = payload.setdefault("sampling", {})
    if not isinstance(sampling, dict):
        return confirmed_fields
    for key, incoming in incoming_sampling.items():
        if key not in sampling or sampling[key] is None:
            sampling[key] = deepcopy(incoming)
            confirmed_fields.add("sampling")
        elif sampling[key] != incoming:
            _record_conflict(
                conflicts,
                field=f"sampling.{key}",
                kept_value=sampling[key],
                kept_reference=api_references.get(
                    f"sampling.{key}",
                    f"civitai_api:images:{payload.get('source', {}).get('image_id')}:unknown",
                ),
                incoming_value=incoming,
                incoming_reference=embedded_references.get(
                    f"sampling.{key}",
                    f"embedded_metadata:{embedded_payload.get('raw', {}).get('embedded_metadata', {}).get('image_sha256', 'unknown')}:unknown",
                ),
            )
    return confirmed_fields


def _merge_resources(payload: dict[str, Any], embedded_payload: Mapping[str, Any]) -> None:
    incoming_resources = embedded_payload.get("resources")
    if not isinstance(incoming_resources, list):
        return
    resources = payload.setdefault("resources", [])
    if not isinstance(resources, list):
        return
    seen = {
        (str(item.get("kind")), str(item.get("name")))
        for item in resources
        if isinstance(item, Mapping)
    }
    for item in incoming_resources:
        if not isinstance(item, Mapping):
            continue
        key = (str(item.get("kind")), str(item.get("name")))
        if key not in seen:
            resources.append(deepcopy(dict(item)))
            seen.add(key)


def _merge_embedded_metadata(
    payload: dict[str, Any],
    embedded_metadata: EmbeddedMetadataResult | None,
    *,
    conflicts: list[dict[str, Any],],
    can_confirm: bool,
) -> set[str]:
    if embedded_metadata is None:
        return set()
    embedded_payload = embedded_metadata_to_recipe_payload(
        embedded_metadata,
        source=payload.get("source") if isinstance(payload.get("source"), Mapping) else None,
    )
    _merge_raw(payload, "embedded_metadata", embedded_metadata.to_dict())
    api_references = _first_mapping(
        _first_mapping(payload.get("raw")).get("civitai_api")
    ).get("field_references", {})
    if not isinstance(api_references, Mapping):
        api_references = {}
    embedded_references = _embedded_field_references(embedded_metadata)
    confirmed_fields: set[str] = set()
    if _merge_known_field(
        payload,
        field="base_prompt",
        incoming=embedded_payload.get("base_prompt"),
        kept_reference=str(api_references.get(
            "base_prompt",
            f"civitai_api:images:{payload.get('source', {}).get('image_id')}:unknown",
        )),
        incoming_reference=embedded_references.get(
            "base_prompt", f"embedded_metadata:{embedded_metadata.image_sha256}:unknown"
        ),
        conflicts=conflicts,
    ) and can_confirm:
        confirmed_fields.add("conditioning")
    if _merge_known_field(
        payload,
        field="negative_prompt",
        incoming=embedded_payload.get("negative_prompt"),
        kept_reference=str(api_references.get(
            "negative_prompt",
            f"civitai_api:images:{payload.get('source', {}).get('image_id')}:unknown",
        )),
        incoming_reference=embedded_references.get(
            "negative_prompt", f"embedded_metadata:{embedded_metadata.image_sha256}:unknown"
        ),
        conflicts=conflicts,
    ):
        confirmed_fields.add("conditioning")
    confirmed_fields.update(
        _merge_sampling(
            payload,
            embedded_payload,
            api_references=api_references,
            embedded_references=embedded_references,
            conflicts=conflicts,
        )
    )
    _merge_resources(payload, embedded_payload)
    workflow = embedded_payload.get("workflow")
    if isinstance(workflow, Mapping):
        existing_workflow = payload.get("workflow")
        if existing_workflow is None:
            payload["workflow"] = deepcopy(dict(workflow))
            if can_confirm:
                confirmed_fields.add("workflow")
        elif isinstance(existing_workflow, Mapping) and existing_workflow.get("snapshot") != workflow.get("snapshot"):
            _record_conflict(
                conflicts,
                field="workflow",
                kept_value=existing_workflow.get("snapshot"),
                kept_reference=str(existing_workflow.get("reference", "civitai_api:workflow")),
                incoming_value=workflow.get("snapshot"),
                incoming_reference=str(workflow.get("reference", "embedded_metadata:workflow")),
            )
    if not can_confirm:
        return set()
    return confirmed_fields


def _canonical_value_for_recipe(recipe: GenerationRecipe, field: str) -> Any:
    if field == "source.identity":
        if recipe.source.image_id is not None:
            return {"image_id": recipe.source.image_id}
        return {
            key: value
            for key, value in recipe.source.model_dump(exclude_none=True).items()
            if key in {"url", "media_url"}
        }
    if field == "workflow":
        return recipe.workflow.snapshot if recipe.workflow else None
    if field == "sampling":
        return recipe.sampling.model_dump(exclude_none=True) if recipe.sampling else None
    if field == "conditioning":
        return {"base_prompt": recipe.base_prompt, "negative_prompt": recipe.negative_prompt}
    match = re.fullmatch(r"resources\[([0-9]+)\]\.identity", field)
    if match:
        index = int(match.group(1))
        return recipe.resources[index].model_dump(exclude_none=True) if index < len(recipe.resources) else None
    return None


def _trusted_recipe_from_payload(
    payload: dict[str, Any],
    *,
    api_snapshot: Mapping[str, Any],
    api_resource_count: int,
    embedded_confirmed_fields: set[str],
    acquired_embedded_metadata: EmbeddedMetadataResult | None,
) -> GenerationRecipe:
    """Issue CIV-A capability only for snapshot-bound evidence acquired in this boundary."""
    draft = GenerationRecipe.model_validate(normalize_recipe_payload({**payload, "confirmed": [], "evidence_manifest": []}))
    confirmed: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []

    def add_manifest(
        *, source: EvidenceSource, reference: str, identity: str, snapshot: dict[str, Any], fields: list[str]
    ) -> None:
        assertions: list[dict[str, Any]] = []
        for index, field in enumerate(fields):
            value = _canonical_value_for_recipe(draft, field)
            if value is None:
                continue
            key = f"field_{index}"
            snapshot["extractions"][key] = deepcopy(value)
            assertions.append({"canonical_field": field, "path": f"/extractions/{key}", "extractor": "json_pointer"})
        if not assertions:
            return
        manifest = {"identity": identity, "reference": reference, "payload": snapshot, "assertions": assertions}
        manifest["sha256"] = _canonical_json_sha256({
            "identity": identity, "reference": reference, "payload": snapshot, "assertions": assertions,
        })
        manifests.append(manifest)
        for assertion in assertions:
            confirmed.append({
                "canonical_field": assertion["canonical_field"], "source": source.value,
                "reference": reference, "snapshot_sha256": manifest["sha256"],
            })

    image_id = draft.source.image_id or "unknown"
    api_fields = ["source.identity", *[f"resources[{index}].identity" for index in range(min(api_resource_count, len(draft.resources)))]]
    add_manifest(
        source=EvidenceSource.CIVITAI_API,
        reference=f"civitai_api:images:{image_id}:response",
        identity=f"civitai_api:images:{image_id}:response:manifest",
        snapshot={"response": deepcopy(dict(api_snapshot)), "extractions": {}},
        fields=api_fields,
    )
    if acquired_embedded_metadata is not None:
        add_manifest(
            source=EvidenceSource.EMBEDDED_METADATA,
            reference=f"embedded_metadata:{acquired_embedded_metadata.image_sha256}:snapshot",
            identity=f"embedded_metadata:{acquired_embedded_metadata.image_sha256}:manifest",
            snapshot={
                "image_sha256": acquired_embedded_metadata.image_sha256,
                "metadata": acquired_embedded_metadata.to_dict(),
                "extractions": {},
            },
            fields=[field for field in ("conditioning", "sampling", "workflow") if field in embedded_confirmed_fields],
        )
    trusted_payload = deepcopy(payload)
    trusted_payload["evidence_manifest"] = manifests
    trusted_payload["confirmed"] = confirmed
    capability = _issue_trusted_provenance_capability(EvidenceRecord.model_validate(item) for item in confirmed)
    return _build_recipe_from_trusted_evidence(trusted_payload, capability=capability)


def acquire_civitai_recipe(
    locator: int | str,
    *,
    transport: CivitaiTransport,
    authorization: str | None = None,
    backoff: Callable[[int, CivitaiTransportResponse], float | int | None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    embedded_metadata: EmbeddedMetadataResult | None = None,
) -> AcquisitionResult:
    """Acquire an image payload and return a conservative recipe snapshot."""

    parsed_locator = parse_civitai_locator(locator)
    url, params = _api_request_for(parsed_locator)
    secrets = _secrets_from_authorization(authorization)
    provenance: dict[str, Any] = {"locator": asdict(parsed_locator), "requests": []}
    api_payload = _request_json(
        url,
        params=params,
        transport=transport,
        authorization=authorization,
        provenance=provenance,
        backoff=backoff,
        sleep=sleep,
        secrets=secrets,
    )
    try:
        image_payload = resolve_image_payload(parsed_locator, api_payload)
    except AcquisitionError as exc:
        exc.provenance = redact_secrets({**provenance, **exc.provenance}, secrets=secrets)
        raise
    _enrich_single_checkpoint_identity(
        image_payload,
        transport=transport,
        authorization=authorization,
        provenance=provenance,
        backoff=backoff,
        sleep=sleep,
        secrets=secrets,
    )
    media_url = _first_text(image_payload, "url")
    media_sha256, acquired_embedded_metadata = _fetch_media_evidence(
        transport, media_url, provenance=provenance, secrets=secrets
    )
    # A caller may retain a prior extraction for audit, but it cannot become trusted.
    # When bytes were acquired we always normalize the extraction performed here.
    effective_embedded = acquired_embedded_metadata or embedded_metadata
    conflicts: list[dict[str, Any]] = []
    recipe_payload = _api_payload_to_recipe_payload(image_payload, parsed_locator)
    api_resource_count = len(recipe_payload.get("resources") or [])
    embedded_confirmed = _merge_embedded_metadata(
        recipe_payload,
        effective_embedded,
        conflicts=conflicts,
        can_confirm=acquired_embedded_metadata is not None,
    )
    if embedded_metadata is not None and acquired_embedded_metadata is None:
        recipe_payload.setdefault("raw", {})["untrusted_caller_embedded_metadata"] = embedded_metadata.to_dict()
    if conflicts:
        recipe_payload.setdefault("raw", {}).setdefault("normalization", {})["conflicts"] = conflicts
        recipe_payload["missing"] = [
            {
                "canonical_field": conflict["field"],
                "criticality": MissingCriticality.IMPORTANT.value,
                "reason": "conflicting Civitai API and embedded metadata values",
            }
            for conflict in conflicts
        ]
    recipe_payload.setdefault("raw", {})["acquisition"] = {
        "locator": asdict(parsed_locator),
        "provenance": deepcopy(provenance),
    }
    recipe = _trusted_recipe_from_payload(
        recipe_payload,
        api_snapshot=image_payload,
        api_resource_count=api_resource_count,
        embedded_confirmed_fields=embedded_confirmed,
        acquired_embedded_metadata=acquired_embedded_metadata,
    )
    if conflicts:
        recipe.raw.setdefault("normalization", {})["conflicts"] = deepcopy(conflicts)
    sanitized_payload = redact_secrets(deepcopy(dict(image_payload)), secrets=secrets)
    sanitized_provenance = redact_secrets(provenance, secrets=secrets)
    return AcquisitionResult(
        status="ok",
        locator=parsed_locator,
        image_id=recipe.source.image_id,
        recipe=recipe,
        raw_api_payload=sanitized_payload,
        media_url=media_url,
        media_sha256=media_sha256,
        provenance=sanitized_provenance,
        conflicts=redact_secrets(conflicts, secrets=secrets),
        errors=[],
    )
