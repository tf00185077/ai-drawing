"""Pure comma-atomic prompt primitives shared by migration and runtime code."""

from __future__ import annotations

import math


def format_prompt_weight(weight: float) -> str:
    return f"{weight:.3f}".rstrip("0").rstrip(".")


def render_prompt_atom(snapshot_raw: str, weight: float) -> str:
    """Render one exact unweighted snapshot without trimming or parsing it."""
    if not snapshot_raw.strip():
        raise ValueError("fragment snapshot cannot be empty")
    if math.isclose(weight, 1.0):
        return snapshot_raw
    return f"({snapshot_raw}:{format_prompt_weight(weight)})"


def split_prompt_atoms(raw: str) -> list[str]:
    """Split at every U+002C and preserve empty strings and all whitespace."""
    return raw.split(",")


def atomize_nonblank(raw: str) -> list[str]:
    atoms = split_prompt_atoms(raw)
    blanks = [index + 1 for index, atom in enumerate(atoms) if not atom.strip()]
    if blanks:
        positions = ", ".join(str(position) for position in blanks)
        raise ValueError(f"blank comma-atomic fragment at position(s): {positions}")
    return atoms


def render_prompt_lane(atoms: list[tuple[str, float]]) -> str:
    return ",".join(render_prompt_atom(snapshot, weight) for snapshot, weight in atoms)
