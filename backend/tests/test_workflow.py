"""Workflow JSON 管理單元測試"""
import pytest

from app.core.workflow import load_template, apply_params


def test_load_template_loads_default() -> None:
    """載入 default 模板應回傳有效 ComfyUI workflow 結構"""
    wf = load_template("default")
    assert isinstance(wf, dict)
    assert "3" in wf  # KSampler
    assert "4" in wf  # CheckpointLoaderSimple
    assert "6" in wf  # CLIPTextEncode positive
    assert "7" in wf  # CLIPTextEncode negative
    assert wf["4"]["class_type"] == "CheckpointLoaderSimple"
    assert wf["3"]["class_type"] == "KSampler"


def test_load_template_with_extension() -> None:
    """支援帶副檔名或不帶副檔名的模板名稱"""
    wf1 = load_template("default")
    wf2 = load_template("default.json")
    assert wf1 == wf2


def test_load_template_raises_when_not_found() -> None:
    """模板不存在時拋出 FileNotFoundError"""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_template("nonexistent_template_xyz")
    assert "nonexistent_template_xyz" in str(exc_info.value)


def test_apply_params_replaces_checkpoint_prompt_seed() -> None:
    """apply_params 正確替換 checkpoint、prompt、seed"""
    wf = load_template("default")
    result = apply_params(
        wf,
        checkpoint="my_model.safetensors",
        prompt="1girl, solo",
        negative_prompt="blur",
        seed=12345,
        steps=25,
        cfg=8.0,
    )
    assert result["4"]["inputs"]["ckpt_name"] == "my_model.safetensors"
    assert result["6"]["inputs"]["text"] == "1girl, solo"
    assert result["7"]["inputs"]["text"] == "blur"
    assert result["3"]["inputs"]["seed"] == 12345
    assert result["3"]["inputs"]["steps"] == 25
    assert result["3"]["inputs"]["cfg"] == 8.0


def test_apply_params_does_not_modify_original() -> None:
    """apply_params 不修改原始 workflow（深拷貝）"""
    wf = load_template("default")
    original_ckpt = wf["4"]["inputs"]["ckpt_name"]
    apply_params(wf, checkpoint="replaced.safetensors", prompt="x")
    assert wf["4"]["inputs"]["ckpt_name"] == original_ckpt


def test_apply_params_seed_random_when_none() -> None:
    """seed 為 None 時使用隨機值"""
    wf = load_template("default")
    result = apply_params(wf, prompt="test")
    seed = result["3"]["inputs"]["seed"]
    assert isinstance(seed, int)
    assert 0 <= seed <= 2**32 - 1


def test_load_template_default_lora_has_loraloader() -> None:
    """default_lora 模板含 LoraLoader，供訓練完成產圖 Pipeline 使用"""
    wf = load_template("default_lora")
    assert "10" in wf
    assert wf["10"]["class_type"] == "LoraLoader"
    assert "lora_name" in wf["10"]["inputs"]


def test_apply_params_replaces_lora_in_default_lora() -> None:
    """apply_params 在 default_lora 模板中正確替換 LoraLoader.lora_name"""
    wf = load_template("default_lora")
    result = apply_params(wf, prompt="test", lora="/path/to/my_lora.safetensors")
    assert result["10"]["inputs"]["lora_name"] == "/path/to/my_lora.safetensors"
