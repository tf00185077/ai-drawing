"""Frozen compatibility adapters. Never use as Phase 2 metadata inference."""
from typing import Any

def normalize_model_family(base_model: Any) -> str | None:
    """Frozen pre-Phase-2 recipe/AIR and Anima package compatibility only."""
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

