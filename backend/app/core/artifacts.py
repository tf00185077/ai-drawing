"""
Generic generated artifact helpers.

ComfyUI output shapes vary across image and video nodes, so this module keeps
extension-based detection and history extraction in one place.
"""
from __future__ import annotations

from pathlib import Path


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
