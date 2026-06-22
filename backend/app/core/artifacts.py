"""
Generic generated artifact helpers.

ComfyUI output shapes vary across image and video nodes, so this module keeps
extension-based detection and history extraction in one place.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


SUPPORTED_ARTIFACT_EXTENSIONS: dict[str, tuple[str, str]] = {
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".webp": ("image", "image/webp"),
    ".gif": ("video", "image/gif"),
    ".mp4": ("video", "video/mp4"),
    ".webm": ("video", "video/webm"),
}


def detect_artifact_type(filename: str) -> tuple[str, str] | None:
    """Return (artifact_type, mime_type) for supported generated output files."""
    suffix = Path(filename).suffix.lower()
    return SUPPORTED_ARTIFACT_EXTENSIONS.get(suffix)


def _workflow_dict(workflow: Any) -> Mapping[str, Any]:
    """Normalize ComfyUI API or history prompt structures to a workflow mapping."""
    if isinstance(workflow, Mapping):
        return workflow
    if isinstance(workflow, list):
        if len(workflow) > 2 and isinstance(workflow[2], Mapping):
            return workflow[2]
        if workflow and isinstance(workflow[0], Mapping):
            return workflow[0]
    return {}


def _node_type(workflow: Any, node_id: str) -> str | None:
    wf = _workflow_dict(workflow)
    node = wf.get(str(node_id)) or wf.get(node_id)
    if isinstance(node, Mapping):
        value = node.get("class_type")
        if value:
            return str(value)
    return None


def _iter_output_items(node_out: Any) -> list[tuple[str, Mapping[str, Any]]]:
    """Yield output-key/file-metadata pairs from common ComfyUI node output shapes."""
    if not isinstance(node_out, Mapping):
        return []

    items: list[tuple[str, Mapping[str, Any]]] = []
    if "filename" in node_out:
        items.append(("file", node_out))

    for key, value in node_out.items():
        if isinstance(value, Mapping) and "filename" in value:
            items.append((str(key), value))
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, Mapping) and "filename" in entry:
                    items.append((str(key), entry))
    return items


def get_output_artifacts(
    history: Mapping[str, Any],
    prompt_id: str,
    workflow: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Collect supported image/video artifacts from a ComfyUI history entry.

    The collector does not rely on a fixed output key. It accepts any history
    output item with a filename whose extension is in the supported set.
    """
    prompt_data = history.get(prompt_id, {}) if isinstance(history, Mapping) else {}
    if not isinstance(prompt_data, Mapping):
        return []
    outputs = prompt_data.get("outputs", {})
    if not isinstance(outputs, Mapping):
        return []
    wf = workflow if workflow is not None else prompt_data.get("prompt")

    artifacts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for node_id, node_out in outputs.items():
        for output_key, item in _iter_output_items(node_out):
            filename = item.get("filename")
            if not filename:
                continue
            detected = detect_artifact_type(str(filename))
            if detected is None:
                continue
            artifact_type, mime_type = detected
            subfolder = str(item.get("subfolder", "") or "")
            ftype = str(item.get("type", "output") or "output")
            dedupe_key = (str(node_id), str(filename), subfolder, ftype)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            artifacts.append(
                {
                    "filename": str(filename),
                    "subfolder": subfolder,
                    "type": ftype,
                    "artifact_type": artifact_type,
                    "mime_type": mime_type,
                    "source_node_id": str(node_id),
                    "source_node_type": _node_type(wf, str(node_id)),
                    "output_key": output_key,
                }
            )
    return artifacts


def get_output_images(history: Mapping[str, Any], prompt_id: str) -> list[dict[str, Any]]:
    """Backward-compatible image-only projection used by legacy callers."""
    return [
        {
            "filename": artifact["filename"],
            "subfolder": artifact.get("subfolder", ""),
            "type": artifact.get("type", "output"),
        }
        for artifact in get_output_artifacts(history, prompt_id)
        if artifact.get("artifact_type") == "image"
    ]
