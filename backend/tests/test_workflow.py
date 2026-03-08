"""Workflow JSON 管理單元測試"""
import pytest

from app.core.workflow import apply_params, get_seed_from_workflow, load_template


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


def test_apply_params_replaces_width_height_sampler() -> None:
    """apply_params 正確替換 EmptyLatentImage 與 KSampler 的 width、height、sampler_name、scheduler"""
    wf = load_template("default")
    result = apply_params(
        wf,
        prompt="test",
        width=768,
        height=768,
        batch_size=2,
        sampler_name="dpmpp_2m",
        scheduler="karras",
    )
    assert result["5"]["inputs"]["width"] == 768
    assert result["5"]["inputs"]["height"] == 768
    assert result["5"]["inputs"]["batch_size"] == 2
    assert result["3"]["inputs"]["sampler_name"] == "dpmpp_2m"
    assert result["3"]["inputs"]["scheduler"] == "karras"


def test_apply_params_keeps_template_values_when_param_none() -> None:
    """width/height/sampler 為 None 時保留模板原有值"""
    wf = load_template("default")
    orig_w, orig_h = wf["5"]["inputs"]["width"], wf["5"]["inputs"]["height"]
    result = apply_params(wf, prompt="test")
    assert result["5"]["inputs"]["width"] == orig_w
    assert result["5"]["inputs"]["height"] == orig_h


def test_get_seed_from_workflow_returns_seed_when_ksampler_present() -> None:
    """有 KSampler 時回傳其 seed"""
    wf = load_template("default")
    result = apply_params(wf, prompt="test", seed=99999)
    assert get_seed_from_workflow(result) == 99999


def test_get_seed_from_workflow_returns_none_when_no_ksampler() -> None:
    """無 KSampler 時回傳 None"""
    assert get_seed_from_workflow({}) is None
    assert get_seed_from_workflow({"1": {"class_type": "OtherNode", "inputs": {}}}) is None


def test_load_template_controlnet_pose() -> None:
    """controlnet_pose 模板含 LoadImage、DWPreprocessor、ControlNetApply"""
    wf = load_template("controlnet_pose")
    assert wf["10"]["class_type"] == "LoadImage"
    assert wf["11"]["class_type"] == "LoadImage"
    assert wf["13"]["class_type"] == "DWPreprocessor"
    assert wf["14"]["class_type"] == "ControlNetLoader"
    assert wf["15"]["class_type"] == "ControlNetApply"


def test_apply_params_replaces_image_and_denoise_in_controlnet_pose() -> None:
    """apply_params 在 controlnet_pose 中正確替換 LoadImage.image 與 KSampler.denoise"""
    wf = load_template("controlnet_pose")
    result = apply_params(
        wf,
        prompt="1girl, standing",
        image="my_photo.png",
        denoise=0.65,
    )
    assert result["10"]["inputs"]["image"] == "my_photo.png"
    assert result["11"]["inputs"]["image"] == "my_photo.png"
    assert result["3"]["inputs"]["denoise"] == 0.65


def test_apply_params_image_pose_overrides_second_loadimage() -> None:
    """image_pose 單獨設定時，第二個 LoadImage 使用 pose 圖"""
    wf = load_template("controlnet_pose")
    result = apply_params(
        wf,
        prompt="test",
        image="subject.png",
        image_pose="pose_ref.png",
    )
    assert result["10"]["inputs"]["image"] == "subject.png"
    assert result["11"]["inputs"]["image"] == "pose_ref.png"


def test_apply_params_controlnet_traces_prompt_to_clip_text_encode() -> None:
    """ControlNet 流程中，prompt/negative_prompt 應正確替換上游 CLIPTextEncode"""
    wf = load_template("controlnet_pose")
    result = apply_params(
        wf,
        prompt="honoka, 1girl",
        negative_prompt="blur, bad hands",
    )
    assert result["6"]["inputs"]["text"] == "honoka, 1girl"
    assert result["7"]["inputs"]["text"] == "blur, bad hands"


def test_apply_params_controlnet_keeps_original_when_negative_prompt_none() -> None:
    """negative_prompt 為 None 時保留 workflow 原始負向提示詞"""
    wf = load_template("controlnet_pose")
    orig_neg = wf["7"]["inputs"]["text"]
    result = apply_params(wf, prompt="test", negative_prompt=None)
    assert result["7"]["inputs"]["text"] == orig_neg


def test_apply_params_sets_bbox_detector_on_dwpreprocessor() -> None:
    """apply_params 預設將 DWPreprocessor.bbox_detector 設為 yolo_nas_s_fp16.onnx"""
    wf = load_template("controlnet_pose")
    result = apply_params(wf, prompt="test")
    assert result["13"]["inputs"]["bbox_detector"] == "yolo_nas_s_fp16.onnx"


def test_apply_params_overrides_bbox_detector_when_provided() -> None:
    """apply_params 可覆寫 bbox_detector"""
    wf = load_template("honoka_pose_controlnet")
    result = apply_params(wf, prompt="test", bbox_detector="yolo_nas_s_fp16.onnx")
    assert result["6"]["inputs"]["bbox_detector"] == "yolo_nas_s_fp16.onnx"
