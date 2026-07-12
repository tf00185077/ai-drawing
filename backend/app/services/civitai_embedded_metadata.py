"""Offline embedded metadata extraction for CIV-B Civitai acquisition.

The extractor keeps raw containers first and derives A1111 / ComfyUI interpretations
from that retained evidence. It performs no network, database, or workflow calls.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from io import BytesIO
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from PIL import ExifTags, Image


_LORA_RE = re.compile(r"<lora:([^:>]+):([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))>")


@dataclass(frozen=True)
class EmbeddedMetadataResult:
    """Raw image metadata plus conservative derived interpretations."""

    image_sha256: str
    format: str
    raw: dict[str, Any]
    a1111: dict[str, Any] | None = None
    comfyui_prompt: dict[str, Any] | None = None
    comfyui_workflow: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_json_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _decode_text(value: Any) -> str:
    if isinstance(value, bytes):
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                return value.decode(encoding).rstrip("\x00")
            except UnicodeDecodeError:
                continue
        return value.hex()
    return str(value)


def _json_or_none(value: str) -> dict[str, Any] | list[Any] | None:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _coerce_int(value: str) -> int | None:
    stripped = value.strip()
    return int(stripped) if re.fullmatch(r"[0-9]+", stripped) else None


def _coerce_float(value: str) -> float | None:
    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError:
        return None


def _split_a1111_settings(settings_text: str) -> dict[str, str]:
    settings: dict[str, str] = {}
    for part in re.split(r",\s*(?=[A-Za-z][A-Za-z0-9 _-]*:)", settings_text.strip()):
        key, separator, value = part.partition(":")
        if not separator:
            continue
        settings[key.strip()] = value.strip()
    return settings


def parse_a1111_parameters(value: str) -> dict[str, Any] | None:
    """Parse the common AUTOMATIC1111 parameters text block."""

    if "Steps:" not in value or "Seed:" not in value:
        return None
    prompt_text = value.strip()
    settings_match = re.search(r"(?:^|\n)Steps:\s*", prompt_text)
    if settings_match is None:
        return None
    prompt_part = prompt_text[: settings_match.start()].strip()
    settings_part = prompt_text[settings_match.start() :].strip()

    negative_prompt = None
    negative_marker = "\nNegative prompt:"
    if negative_marker in prompt_part:
        prompt, negative = prompt_part.split(negative_marker, 1)
        prompt_part = prompt.strip()
        negative_prompt = negative.strip()
    elif prompt_part.startswith("Negative prompt:"):
        negative_prompt = prompt_part.removeprefix("Negative prompt:").strip()
        prompt_part = ""

    raw_settings = _split_a1111_settings(settings_part)
    normalized: dict[str, Any] = {}
    key_map = {
        "steps": "steps",
        "sampler": "sampler",
        "schedule type": "scheduler",
        "scheduler": "scheduler",
        "cfg scale": "cfg",
        "seed": "seed",
        "clip skip": "clip_skip",
        "model": "model",
        "model hash": "model_hash",
    }
    for key, raw_value in raw_settings.items():
        normalized_key = key_map.get(key.strip().lower())
        if normalized_key is None:
            continue
        if normalized_key in {"steps", "seed", "clip_skip"}:
            parsed_int = _coerce_int(raw_value)
            if parsed_int is not None:
                normalized[normalized_key] = parsed_int
        elif normalized_key == "cfg":
            parsed_float = _coerce_float(raw_value)
            if parsed_float is not None:
                normalized[normalized_key] = parsed_float
        else:
            normalized[normalized_key] = raw_value

    size = raw_settings.get("Size") or raw_settings.get("size")
    if size:
        match = re.fullmatch(r"\s*([1-9][0-9]*)\s*x\s*([1-9][0-9]*)\s*", size)
        if match:
            normalized["width"] = int(match.group(1))
            normalized["height"] = int(match.group(2))

    loras = [
        {"name": match.group(1).strip(), "strength_model": float(match.group(2))}
        for match in _LORA_RE.finditer(prompt_part)
    ]
    return {
        "prompt": prompt_part,
        "negative_prompt": negative_prompt,
        "parameters": normalized,
        "raw_parameters": raw_settings,
        "loras": loras,
    }


def _append_text_container(
    containers: list[dict[str, Any]],
    *,
    container: str,
    key: str,
    value: Any,
) -> None:
    decoded = _decode_text(value)
    item: dict[str, Any] = {"container": container, "key": key, "value": decoded}
    parsed_json = _json_or_none(decoded)
    if parsed_json is not None:
        item["json"] = parsed_json
    containers.append(item)


def _jpeg_segments(data: bytes) -> list[tuple[int, bytes]]:
    if not data.startswith(b"\xff\xd8"):
        return []
    segments: list[tuple[int, bytes]] = []
    index = 2
    while index < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index : index + 2], "big")
        index += 2
        payload_length = max(length - 2, 0)
        payload = data[index : index + payload_length]
        segments.append((marker, payload))
        index += payload_length
        if marker == 0xDA:
            break
    return segments


def _webp_chunks(data: bytes) -> list[tuple[str, bytes]]:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return []
    chunks: list[tuple[str, bytes]] = []
    index = 12
    while index + 8 <= len(data):
        fourcc = data[index : index + 4].decode("ascii", errors="replace")
        size = int.from_bytes(data[index + 4 : index + 8], "little")
        start = index + 8
        payload = data[start : start + size]
        chunks.append((fourcc, payload))
        index = start + size + (size % 2)
    return chunks


def _extract_exif_containers(image: Image.Image, container_name: str) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    try:
        exif = image.getexif()
    except Exception:
        return containers
    for tag, value in exif.items():
        name = ExifTags.TAGS.get(tag, str(tag))
        if isinstance(value, bytes):
            value = _decode_text(value)
        containers.append({"container": container_name, "key": str(name), "value": value})
    return containers


def extract_embedded_metadata(path: str | Path | bytes) -> EmbeddedMetadataResult:
    """Extract raw PNG/JPEG/WebP metadata and known generation metadata blocks."""

    if isinstance(path, bytes):
        data = path
        stream = BytesIO(data)
        source_name = None
    else:
        source = Path(path)
        data = source.read_bytes()
        stream = BytesIO(data)
        source_name = str(source)

    digest = hashlib.sha256(data).hexdigest()
    with Image.open(stream) as image:
        image_format = (image.format or "UNKNOWN").upper()
        containers: list[dict[str, Any]] = []
        if image_format == "PNG":
            for key, value in (getattr(image, "text", {}) or {}).items():
                _append_text_container(containers, container="png_text", key=str(key), value=value)
        elif image_format == "JPEG":
            containers.extend(_extract_exif_containers(image, "jpeg_exif"))
            for marker, payload in _jpeg_segments(data):
                if marker == 0xFE:
                    _append_text_container(containers, container="jpeg_comment", key="Comment", value=payload)
                elif marker == 0xE1 and payload.startswith(b"http://ns.adobe.com/xap/1.0/\x00"):
                    _append_text_container(
                        containers,
                        container="jpeg_xmp",
                        key="XMP",
                        value=payload.split(b"\x00", 1)[1],
                    )
        elif image_format == "WEBP":
            containers.extend(_extract_exif_containers(image, "webp_exif"))
            for fourcc, payload in _webp_chunks(data):
                if fourcc == "XMP ":
                    _append_text_container(containers, container="webp_xmp", key="XMP", value=payload)
                elif fourcc == "EXIF" and not any(item["container"] == "webp_exif" for item in containers):
                    _append_text_container(containers, container="webp_exif_raw", key="EXIF", value=payload)

    a1111 = None
    comfyui_prompt = None
    comfyui_workflow = None
    for container in containers:
        value = container.get("value")
        if not isinstance(value, str):
            continue
        if a1111 is None:
            a1111 = parse_a1111_parameters(value)
        key = str(container.get("key", "")).lower()
        parsed_json = container.get("json")
        if key == "prompt" and isinstance(parsed_json, dict):
            comfyui_prompt = parsed_json
        elif key == "workflow" and isinstance(parsed_json, dict):
            comfyui_workflow = parsed_json

    raw = {
        "source_path": source_name,
        "image_sha256": digest,
        "format": image_format,
        "containers": containers,
    }
    if a1111 is not None:
        raw["a1111"] = a1111
    if comfyui_prompt is not None:
        raw["comfyui_prompt"] = comfyui_prompt
    if comfyui_workflow is not None:
        raw["comfyui_workflow"] = comfyui_workflow
    return EmbeddedMetadataResult(
        image_sha256=digest,
        format=image_format,
        raw=raw,
        a1111=a1111,
        comfyui_prompt=comfyui_prompt,
        comfyui_workflow=comfyui_workflow,
    )


def embedded_metadata_to_recipe_payload(
    metadata: EmbeddedMetadataResult,
    *,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Map supported embedded metadata into a GenerationRecipe-compatible payload."""

    embedded_snapshot = metadata.to_dict()
    embedded_snapshot.update(deepcopy(metadata.raw))
    payload: dict[str, Any] = {
        "source": dict(source or {"provider": "civitai"}),
        "raw": {
            "embedded_metadata": embedded_snapshot,
        },
    }
    if metadata.a1111 is not None:
        payload["base_prompt"] = metadata.a1111.get("prompt")
        payload["negative_prompt"] = metadata.a1111.get("negative_prompt")
        parameters = metadata.a1111.get("parameters") or {}
        sampling = {
            key: parameters[key]
            for key in ("seed", "steps", "cfg", "sampler", "scheduler", "width", "height")
            if key in parameters
        }
        if sampling:
            payload["sampling"] = sampling
        resources = []
        for item in metadata.a1111.get("loras") or []:
            if not isinstance(item, Mapping) or not item.get("name"):
                continue
            resources.append(
                {
                    "kind": "lora",
                    "name": str(item["name"]),
                    "strength_model": item.get("strength_model"),
                }
            )
        if resources:
            payload["resources"] = resources
    if metadata.comfyui_workflow is not None:
        payload["workflow"] = {
            "reference": f"embedded_metadata:{metadata.image_sha256}:workflow",
            "snapshot": metadata.comfyui_workflow,
            "snapshot_sha256": _canonical_json_sha256(metadata.comfyui_workflow),
        }
    return payload
