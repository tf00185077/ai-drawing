"""add-multi-lora-support：apply_params 逐節點套用 + preset compose 帶 loras"""
from copy import deepcopy

import pytest

from app.core.workflow import apply_params
from app.core.style_presets import _parse_preset, compose_preset


def _wf_two_loras():
    # 兩個 LoraLoader 節點，JSON 順序 a → b
    return {
        "base": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
        "a": {"class_type": "LoraLoader", "inputs": {"model": ["base", 0], "clip": ["base", 1], "lora_name": "old1.safetensors", "strength_model": 1.0, "strength_clip": 1.0}},
        "b": {"class_type": "LoraLoader", "inputs": {"model": ["a", 0], "clip": ["a", 1], "lora_name": "old2.safetensors", "strength_model": 1.0, "strength_clip": 1.0}},
        "k": {"class_type": "KSampler", "inputs": {"model": ["b", 0]}},
        "text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["b", 1], "text": "test"}},
    }


def test_loras_map_positionally_with_strengths() -> None:
    wf = apply_params(
        _wf_two_loras(),
        loras=[
            {"name": "style.safetensors", "strength_model": 0.8},
            {"name": "char.safetensors", "strength_model": 0.6, "strength_clip": 0.4},
        ],
    )
    assert wf["a"]["inputs"]["lora_name"] == "style.safetensors"
    assert wf["a"]["inputs"]["strength_model"] == 0.8
    assert wf["a"]["inputs"]["strength_clip"] == 0.8  # clip 預設 = model
    assert wf["b"]["inputs"]["lora_name"] == "char.safetensors"
    assert wf["b"]["inputs"]["strength_model"] == 0.6
    assert wf["b"]["inputs"]["strength_clip"] == 0.4


def test_single_lora_still_applies_when_loras_omitted() -> None:
    wf = apply_params(_wf_two_loras(), lora="solo.safetensors", lora_strength=0.7)
    # 舊行為：單一 lora 灌入所有 loader
    assert wf["a"]["inputs"]["lora_name"] == "solo.safetensors"
    assert wf["b"]["inputs"]["lora_name"] == "solo.safetensors"


def test_loras_takes_precedence_over_single_lora() -> None:
    original = _wf_two_loras()
    before = deepcopy(original)
    wf = apply_params(
        original,
        lora="ignored.safetensors",
        loras=[{"name": "win.safetensors", "strength_model": 0.5}],
    )
    assert wf["a"]["inputs"]["lora_name"] == "win.safetensors"
    # Explicit list replaces the entire set: no hidden template LoRA survives.
    assert "b" not in wf
    assert wf["k"]["inputs"]["model"] == ["a", 0]
    assert wf["text"]["inputs"]["clip"] == ["a", 1]
    assert original == before


def test_extra_loras_rejected_without_mutating_input() -> None:
    original = _wf_two_loras()
    before = deepcopy(original)
    with pytest.raises(ValueError, match="defines 3 LoRAs but workflow has 2 loader"):
        apply_params(original, loras=[{"name": f"{i}.safetensors"} for i in (1, 2, 3)])
    assert original == before


def test_model_only_loader_skips_clip() -> None:
    wf = {"a": {"class_type": "LoraLoaderModelOnly", "inputs": {}}}
    out = apply_params(wf, loras=[{"name": "m.safetensors", "strength_model": 0.9, "strength_clip": 0.3}])
    assert out["a"]["inputs"]["strength_model"] == 0.9
    assert "strength_clip" not in out["a"]["inputs"]  # model-only 不設 clip


# --- preset compose ---


def test_compose_emits_loras_list() -> None:
    preset = _parse_preset({
        "id": "x", "name": "X", "template": "multi",
        "loras": [{"name": "a.safetensors", "strength_model": 0.8}, {"name": "b.safetensors", "strength_model": 0.5}],
    })
    gen = compose_preset(preset, "a girl").generation
    assert gen["loras"] == [
        {"name": "a.safetensors", "strength_model": 0.8},
        {"name": "b.safetensors", "strength_model": 0.5},
    ]
    assert "lora" not in gen  # 多 lora 時不帶單一 lora


def test_compose_single_lora_unchanged() -> None:
    preset = _parse_preset({"id": "y", "name": "Y", "lora": "solo.safetensors", "lora_strength": 0.7})
    gen = compose_preset(preset, "a girl").generation
    assert gen["lora"] == "solo.safetensors" and gen["lora_strength"] == 0.7
    assert "loras" not in gen
