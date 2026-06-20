"""
Workflow JSON 管理
可動態替換：checkpoint、LoRA、prompt、negative_prompt、seed、steps、cfg

對應 docs/internal-interfaces.md workflow 介面
"""
from __future__ import annotations

import json
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent.parent / "workflows"


def load_template(name: str) -> dict:
    """
    載入 workflow JSON 模板
    從 backend/workflows/{name}.json 讀取，若 name 已含副檔名則不重複加。

    Args:
        name: 模板名稱，如 "default" 或 "default.json"

    Returns:
        ComfyUI API 格式的 workflow dict

    Raises:
        FileNotFoundError: 模板不存在
    """
    path = WORKFLOWS_DIR / name
    if not path.suffix:
        path = path.with_suffix(".json")
    if not path.exists():
        raise FileNotFoundError(f"Workflow template not found: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def apply_params(
    workflow: dict,
    *,
    checkpoint: str | None = None,
    lora: str | None = None,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
    batch_size: int | None = None,
    sampler_name: str | None = None,
    scheduler: str | None = None,
    image: str | None = None,
    image_pose: str | None = None,
    mask: str | None = None,
    denoise: float | None = None,
    lora_strength: float | None = None,
    loras: list[dict] | None = None,
    diffusion_model: str | None = None,
    text_encoder: str | None = None,
    vae: str | None = None,
    bbox_detector: str | None = "yolo_nas_s_fp16.onnx",
) -> dict:
    """
    將參數替換進 workflow，回傳可提交的 prompt dict。
    ComfyUI prompt 格式為 { "node_id": { "inputs": {...}, "class_type": "..." }, ... }

    透過 class_type 與連線關係自動定位要替換的節點：
    - CheckpointLoaderSimple.ckpt_name <- checkpoint
    - UNETLoader.unet_name <- diffusion_model（退回 checkpoint）；diffusion-model 家族，如 Anima
    - CLIPLoader.clip_name <- text_encoder
    - VAELoader.vae_name <- vae
    - LoraLoader / LoraLoaderModelOnly.lora_name <- lora
    - CLIPTextEncode (接 KSampler.positive).text <- prompt
    - CLIPTextEncode (接 KSampler.negative).text <- negative_prompt
    - KSampler.seed, steps, cfg, sampler_name, scheduler, denoise
    - EmptyLatentImage / EmptySD3LatentImage.width, height, batch_size
    - LoadImage.image <- image / image_pose（依節點順序：第一為 subject，第二為 pose）
    - LoadImageMask.image <- mask（inpaint 遮罩，獨立 class_type，無位置衝突）
    - DWPreprocessor.bbox_detector <- bbox_detector（ControlNet 預處理器，預設 yolo_nas_s_fp16.onnx）

    steps/cfg/seed 僅在明確提供時覆寫（None 則保留 workflow JSON 原值）；
    template 路徑的預設值/隨機 seed 由呼叫端（queue）決定，不在此函式內處理。

    Args:
        workflow: 原始 workflow（會複製，不修改原物件）
        其餘: 生圖參數，None 表示不替換

    Returns:
        已替換參數的 workflow 深拷貝
    """
    import copy

    wf = copy.deepcopy(workflow)

    # 1. 尋找 KSampler → positive/negative 對應的 CLIPTextEncode node_id
    # 若中間有 ControlNetApply，需再追蹤其 positive/negative 輸入
    ksampler_ids: list[str] = []
    positive_node_ids: set[str] = set()
    negative_node_ids: set[str] = set()

    def _resolve_to_clip(nid: str) -> str | None:
        """追蹤到 CLIPTextEncode，若為 ControlNetApply 則再往上游找"""
        node = wf.get(nid)
        if not isinstance(node, dict):
            return None
        ct = node.get("class_type")
        if ct == "CLIPTextEncode":
            return nid
        if ct == "ControlNetApply":
            pos_in = node.get("inputs", {}).get("positive") or node.get("inputs", {}).get("conditioning")
            if isinstance(pos_in, list) and len(pos_in) >= 1:
                return _resolve_to_clip(str(pos_in[0]))
        return None

    def _resolve_neg_to_clip(nid: str) -> str | None:
        """追蹤 negative 到 CLIPTextEncode"""
        node = wf.get(nid)
        if not isinstance(node, dict):
            return None
        ct = node.get("class_type")
        if ct == "CLIPTextEncode":
            return nid
        if ct == "ControlNetApply":
            neg_in = node.get("inputs", {}).get("negative")
            if isinstance(neg_in, list) and len(neg_in) >= 1:
                return _resolve_neg_to_clip(str(neg_in[0]))
        return None

    for nid, node in wf.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type")
        inputs = node.get("inputs", {})
        if ct == "KSampler":
            ksampler_ids.append(nid)
            pos_link = inputs.get("positive")
            neg_link = inputs.get("negative")
            if isinstance(pos_link, list) and len(pos_link) >= 1:
                resolved = _resolve_to_clip(str(pos_link[0]))
                if resolved:
                    positive_node_ids.add(resolved)
                else:
                    positive_node_ids.add(str(pos_link[0]))
            if isinstance(neg_link, list) and len(neg_link) >= 1:
                resolved = _resolve_neg_to_clip(str(neg_link[0]))
                if resolved:
                    negative_node_ids.add(resolved)
                else:
                    negative_node_ids.add(str(neg_link[0]))

    # 1b. 找出 LoadImage 節點（依 node id 排序，第一為 subject、第二為 pose）
    load_image_ids = sorted(
        nid for nid, node in wf.items()
        if isinstance(node, dict) and node.get("class_type") == "LoadImage"
    )

    # 1c. 多 lora：依 workflow JSON 出現順序收集 LoraLoader 節點，供 loras 逐一對應。
    lora_loader_ids = [
        nid for nid, node in wf.items()
        if isinstance(node, dict) and node.get("class_type") in ("LoraLoader", "LoraLoaderModelOnly")
    ]

    # 2. 替換各類節點
    for nid, node in wf.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type")
        inputs = node.get("inputs", {})

        if ct == "CheckpointLoaderSimple" and checkpoint is not None:
            inputs["ckpt_name"] = checkpoint

        # Diffusion-model 家族（如 Anima）的元件以獨立節點載入：
        #   UNETLoader.unet_name / CLIPLoader.clip_name / VAELoader.vae_name
        # 僅在明確指定時覆寫，否則沿用模板既有檔名（一般生圖即走此路）。
        # diffusion_model 優先；未提供時退回 checkpoint，維持舊呼叫相容。
        if ct == "UNETLoader":
            unet_value = diffusion_model or checkpoint
            if unet_value is not None:
                inputs["unet_name"] = unet_value
        if ct == "CLIPLoader" and text_encoder is not None:
            inputs["clip_name"] = text_encoder
        if ct == "VAELoader" and vae is not None:
            inputs["vae_name"] = vae

        # 單一 lora：僅在未提供 loras 時套用（維持「同一 lora 灌入所有 loader」舊行為）。
        # 提供 loras 時走下方逐節點對應，loras 優先。
        if loras is None and ct in ("LoraLoader", "LoraLoaderModelOnly"):
            if lora is not None:
                inputs["lora_name"] = lora
            if lora_strength is not None:
                inputs["strength_model"] = lora_strength
                # LoraLoaderModelOnly only exposes strength_model; the regular
                # LoraLoader also needs strength_clip for CLIP-side LoRAs.
                if ct == "LoraLoader":
                    inputs["strength_clip"] = lora_strength

        if ct == "KSampler":
            if seed is not None:
                inputs["seed"] = seed
            if steps is not None:
                inputs["steps"] = steps
            if cfg is not None:
                inputs["cfg"] = cfg
            if sampler_name is not None:
                inputs["sampler_name"] = sampler_name
            if scheduler is not None:
                inputs["scheduler"] = scheduler
            if denoise is not None:
                inputs["denoise"] = denoise

        if ct == "LoadImage" and (image is not None or image_pose is not None):
            idx = load_image_ids.index(nid) if nid in load_image_ids else -1
            # image_pose 用於第二個 LoadImage，或僅有一個 LoadImage（ControlNet pose）時
            if image_pose is not None and (idx == 1 or len(load_image_ids) == 1):
                inputs["image"] = image_pose
            elif image is not None:
                inputs["image"] = image

        if ct == "LoadImageMask" and mask is not None:
            inputs["image"] = mask

        if ct == "DWPreprocessor" and bbox_detector is not None:
            inputs["bbox_detector"] = bbox_detector

        # EmptyLatentImage（傳統）與 EmptySD3LatentImage（SD3 / Anima 家族）
        # 的 width / height / batch_size 介面相同，一併處理。
        if ct in ("EmptyLatentImage", "EmptySD3LatentImage"):
            if width is not None:
                inputs["width"] = width
            if height is not None:
                inputs["height"] = height
            if batch_size is not None:
                inputs["batch_size"] = batch_size

        if ct == "CLIPTextEncode":
            if nid in positive_node_ids and prompt is not None:
                inputs["text"] = prompt
            if nid in negative_node_ids and negative_prompt is not None:
                inputs["text"] = negative_prompt

    # 3. 多 lora 逐節點對應：loras[i] → 第 i 個 LoraLoader 節點（依 workflow JSON 順序）。
    # zip 以較短者為準：loras 多於節點則忽略多出的；少於則其餘 loader 維持模板原值。
    if loras:
        for spec, nid in zip(loras, lora_loader_ids):
            node = wf.get(nid)
            if not isinstance(node, dict):
                continue
            inputs = node.setdefault("inputs", {})
            name = spec.get("name")
            if name is not None:
                inputs["lora_name"] = name
            strength_model = spec.get("strength_model", 1.0)
            inputs["strength_model"] = strength_model
            if node.get("class_type") == "LoraLoader":
                strength_clip = spec.get("strength_clip")
                inputs["strength_clip"] = strength_model if strength_clip is None else strength_clip

    return wf


def get_seed_from_workflow(workflow: dict) -> int | None:
    """
    從 workflow 中提取 KSampler 的 seed。
    用於 recording 時取得「實際使用」的 seed（含 apply_params 產生的隨機值）。

    Returns:
        KSampler 的 seed，若無則 None
    """
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "KSampler":
            seed = node.get("inputs", {}).get("seed")
            if isinstance(seed, int):
                return seed
    return None


def extract_model_files_from_workflow(workflow: dict) -> dict:
    """
    從（已套用參數的）workflow 反解實際使用的模型檔名，供 recording 記錄、之後重生。
    涵蓋傳統 checkpoint 與 diffusion-model 家族（Anima）的元件。

    Returns:
        {
            "checkpoint": str | None,        # CheckpointLoaderSimple.ckpt_name
            "lora": str | None,              # LoraLoader / LoraLoaderModelOnly.lora_name
            "diffusion_model": str | None,   # UNETLoader.unet_name
            "text_encoder": str | None,      # CLIPLoader.clip_name
            "vae": str | None,               # VAELoader.vae_name
        }
    """
    result: dict = {
        "checkpoint": None,
        "lora": None,
        "diffusion_model": None,
        "text_encoder": None,
        "vae": None,
    }
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type")
        inputs = node.get("inputs", {})
        if ct == "CheckpointLoaderSimple":
            result["checkpoint"] = inputs.get("ckpt_name")
        elif ct in ("LoraLoader", "LoraLoaderModelOnly"):
            result["lora"] = inputs.get("lora_name")
        elif ct == "UNETLoader":
            result["diffusion_model"] = inputs.get("unet_name")
        elif ct == "CLIPLoader":
            result["text_encoder"] = inputs.get("clip_name")
        elif ct == "VAELoader":
            result["vae"] = inputs.get("vae_name")
    return result


def extract_params_from_workflow(workflow: dict) -> dict:
    """
    從已執行的 workflow 中提取生圖參數。
    用於 ComfyUI 直接生成（非本系統提交）時，從 history 的 prompt 推回參數以記錄。

    Returns:
        {
            "checkpoint": str | None,
            "lora": str | None,
            "prompt": str | None,
            "negative_prompt": str | None,
            "seed": int | None,
            "steps": int | None,
            "cfg": float | None,
        }
    """
    result: dict = {
        "checkpoint": None,
        "lora": None,
        "prompt": None,
        "negative_prompt": None,
        "seed": None,
        "steps": None,
        "cfg": None,
    }

    # ComfyUI history 的 prompt 格式： [index, prompt_id, workflow_dict, extra, output_ids]
    # workflow 在 index 2
    wf = workflow
    if isinstance(workflow, list) and len(workflow) > 2:
        wf = workflow[2] if isinstance(workflow[2], dict) else {}
    elif isinstance(workflow, list) and workflow and isinstance(workflow[0], dict):
        wf = workflow[0]
    if not isinstance(wf, dict):
        return result

    positive_node_ids: set[str] = set()
    negative_node_ids: set[str] = set()

    def _resolve_to_clip(nid: str) -> str | None:
        node = wf.get(nid) if isinstance(wf, dict) else {}
        if not isinstance(node, dict):
            return None
        ct = node.get("class_type")
        if ct == "CLIPTextEncode":
            return nid
        if ct == "ControlNetApply":
            pos_in = node.get("inputs", {}).get("positive") or node.get("inputs", {}).get("conditioning")
            if isinstance(pos_in, list) and len(pos_in) >= 1:
                return _resolve_to_clip(str(pos_in[0]))
        return None

    def _resolve_neg_to_clip(nid: str) -> str | None:
        node = wf.get(nid) if isinstance(wf, dict) else {}
        if not isinstance(node, dict):
            return None
        ct = node.get("class_type")
        if ct == "CLIPTextEncode":
            return nid
        if ct == "ControlNetApply":
            neg_in = node.get("inputs", {}).get("negative")
            if isinstance(neg_in, list) and len(neg_in) >= 1:
                return _resolve_neg_to_clip(str(neg_in[0]))
        return None

    # 第一遍：從 KSampler 找出 positive/negative 對應的 CLIPTextEncode node id
    for nid, node in (wf.items() if isinstance(wf, dict) else []):
        if not isinstance(node, dict):
            continue
        if node.get("class_type") != "KSampler":
            continue
        inputs = node.get("inputs", {})
        pos_link = inputs.get("positive")
        neg_link = inputs.get("negative")
        if isinstance(pos_link, list) and len(pos_link) >= 1:
            resolved = _resolve_to_clip(str(pos_link[0]))
            if resolved:
                positive_node_ids.add(resolved)
        if isinstance(neg_link, list) and len(neg_link) >= 1:
            resolved = _resolve_neg_to_clip(str(neg_link[0]))
            if resolved:
                negative_node_ids.add(resolved)

    # 第二遍：提取各節點參數
    for nid, node in (wf.items() if isinstance(wf, dict) else []):
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type")
        inputs = node.get("inputs", {})

        if ct == "CheckpointLoaderSimple":
            result["checkpoint"] = inputs.get("ckpt_name")
        if ct in ("LoraLoader", "LoraLoaderModelOnly"):
            result["lora"] = inputs.get("lora_name")
        if ct == "KSampler":
            seed = inputs.get("seed")
            if isinstance(seed, int):
                result["seed"] = seed
            result["steps"] = inputs.get("steps")
            result["cfg"] = inputs.get("cfg")
        if ct == "CLIPTextEncode":
            text = inputs.get("text")
            if isinstance(text, str):
                if nid in positive_node_ids:
                    result["prompt"] = text
                if nid in negative_node_ids:
                    result["negative_prompt"] = text

    return result
