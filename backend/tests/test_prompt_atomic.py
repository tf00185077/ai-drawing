from __future__ import annotations

import pytest

from app.core.prompt_atomic import (
    atomize_nonblank,
    render_prompt_atom,
    render_prompt_lane,
    split_prompt_atoms,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a,,b,", ["a", "", "b", ""]),
        ('"a,b"', ['"a', 'b"']),
        ("(a,b:1.2)", ["(a", "b:1.2)"]),
        ("a，b", ["a，b"]),
    ],
)
def test_split_prompt_atoms_is_exact_u002c_split(
    raw: str, expected: list[str]
) -> None:
    assert split_prompt_atoms(raw) == expected


def test_weighted_model_preserves_exact_unweighted_snapshot() -> None:
    assert render_prompt_atom(" detail ", 1.0) == " detail "
    assert render_prompt_atom(" detail ", 1.2) == "( detail :1.2)"
    assert render_prompt_lane([("a", 1.2), (" b ", 1.0)]) == "(a:1.2), b "


@pytest.mark.parametrize("raw", ["", " ", "a,,b", ",a", "a,"])
def test_atomize_nonblank_rejects_every_blank_atom(raw: str) -> None:
    with pytest.raises(ValueError, match="blank"):
        atomize_nonblank(raw)
