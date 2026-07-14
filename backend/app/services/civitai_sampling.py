"""Canonical runtime names shared by recipe compatibility and compilation."""
from __future__ import annotations


_A1111_TO_COMFYUI_SAMPLER = {
    "euler a": "euler_ancestral",
}


def runtime_sampler_name(source_name: str) -> str:
    """Translate audited source labels to ComfyUI's stable sampler identifiers."""
    return _A1111_TO_COMFYUI_SAMPLER.get(source_name.strip().casefold(), source_name)
