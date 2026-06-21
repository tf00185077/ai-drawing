"""add-multi-lora-support：apply_params 逐節點套用 + preset compose 帶 loras"""
from app.core.workflow import apply_params
from app.core.style_presets import _parse_preset, compose_preset


def _wf_two_loras():
    # 兩個 LoraLoader 節點，JSON 順序 a → b
    return {
        "a": {"class_type": "LoraLoader", "inputs": {"lora_name": "old1.safetensors", "strength_model": 1.0, "strength_clip": 1.0}},
        "b": {"class_type": "LoraLoader", "inputs": {"lora_name": "old2.safetensors", "strength_model": 1.0, "strength_clip": 1.0}},
        "k": {"class_type": "KSampler", "inputs": {}},
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
    wf = apply_params(
        _wf_two_loras(),
        lora="ignored.safetensors",
        loras=[{"name": "win.safetensors", "strength_model": 0.5}],
    )
    assert wf["a"]["inputs"]["lora_name"] == "win.safetensors"
    # 第二個 loader 無對應 loras 條目 → 維持模板原值（未被單一 lora 覆寫）
    assert wf["b"]["inputs"]["lora_name"] == "old2.safetensors"


def test_extra_loras_ignored_without_error() -> None:
    wf = apply_params(
        _wf_two_loras(),
        loras=[
            {"name": "1.safetensors"},
            {"name": "2.safetensors"},
            {"name": "3.safetensors"},  # 第三個無對應節點 → 忽略
        ],
    )
    assert wf["a"]["inputs"]["lora_name"] == "1.safetensors"
    assert wf["b"]["inputs"]["lora_name"] == "2.safetensors"


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
