"""Canonical runtime names shared by recipe compatibility and compilation.

Civitai generation metadata uses A1111-style sampler labels ("DPM++ 2M Karras");
ComfyUI splits these into a sampler identifier and a scheduler. Unknown labels
pass through unchanged so native ComfyUI names keep working.
"""
from __future__ import annotations


_A1111_TO_COMFYUI_SAMPLER = {
    "euler a": "euler_ancestral",
    "euler": "euler",
    "lms": "lms",
    "heun": "heun",
    "dpm2": "dpm_2",
    "dpm2 a": "dpm_2_ancestral",
    "dpm++ 2s a": "dpmpp_2s_ancestral",
    "dpm++ 2m": "dpmpp_2m",
    "dpm++ sde": "dpmpp_sde",
    "dpm++ 2m sde": "dpmpp_2m_sde",
    "dpm++ 3m sde": "dpmpp_3m_sde",
    "dpm fast": "dpm_fast",
    "dpm adaptive": "dpm_adaptive",
    "ddim": "ddim",
    "ddpm": "ddpm",
    "uni pc": "uni_pc",
    "unipc": "uni_pc",
    "lcm": "lcm",
}

_SCHEDULER_SUFFIXES = {
    "karras": "karras",
    "exponential": "exponential",
    "sgm uniform": "sgm_uniform",
}


def runtime_sampler_name(source_name: str) -> str:
    """Translate audited source labels to ComfyUI's stable sampler identifiers."""
    return _A1111_TO_COMFYUI_SAMPLER.get(source_name.strip().casefold(), source_name)


def split_sampler_scheduler(source_name: str) -> tuple[str, str | None]:
    """Split one A1111-style sampler label into (comfyui_sampler, scheduler | None).

    "DPM++ 2M Karras" -> ("dpmpp_2m", "karras"); unknown labels pass through
    as (source_name, None) so callers can submit native ComfyUI names directly.
    """
    normalized = " ".join(source_name.strip().casefold().split())
    scheduler: str | None = None
    for suffix, canonical in _SCHEDULER_SUFFIXES.items():
        if normalized.endswith(" " + suffix):
            scheduler = canonical
            normalized = normalized[: -len(suffix) - 1].strip()
            break
    mapped = _A1111_TO_COMFYUI_SAMPLER.get(normalized)
    if mapped is None:
        return (source_name if scheduler is None else normalized, scheduler)
    return (mapped, scheduler)
