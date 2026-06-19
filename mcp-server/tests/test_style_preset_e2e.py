"""
End-to-end dry path（無真實 ComfyUI）：
compose_style_preset 產出 generation payload → 將該 payload 餵給 generate_image。
驗證 compose-then-generate 的交接：composed 欄位完整轉送到 generate_image 的提交 body。
"""
import json
from unittest.mock import MagicMock, patch

from mcp_server.tools.generate import generate_image
from mcp_server.tools.style_presets import compose_style_preset


def test_compose_then_generate_forwards_full_payload() -> None:
    # --- Step 1: compose（mock backend 回傳一個 diffusion-family preset 的 generation payload）
    composed_generation = {
        "template": "anima",
        "diffusion_model": "anima_unet.safetensors",
        "text_encoder": "anima_clip.safetensors",
        "vae": "anima_vae.safetensors",
        "prompt": "anima_style, upper body, a girl in a raincoat",
        "negative_prompt": "low quality, bad anatomy",
        "steps": 28,
        "cfg": 6.5,
        "width": 1024,
        "height": 1024,
    }
    compose_client = MagicMock()
    compose_client.post.return_value = {
        "preset_id": "anima-creator",
        "profile": "portrait",
        "generation": composed_generation,
    }

    with patch(
        "mcp_server.tools.style_presets._get_client", return_value=compose_client
    ):
        compose_result = json.loads(
            compose_style_preset(
                "anima-creator",
                content_prompt="a girl in a raincoat",
                profile="portrait",
            )
        )

    assert compose_result["ok"] is True
    generation = compose_result["generation"]
    assert generation == composed_generation
    assert "generate_image" in compose_result["next"]

    # --- Step 2: 把 generation payload 餵給 generate_image（mock backend 回傳 job_id）
    generate_client = MagicMock()
    generate_client.post.return_value = {"job_id": "e2e-job-1", "status": "queued"}

    with patch(
        "mcp_server.tools.generate._get_client", return_value=generate_client
    ):
        generate_result = json.loads(generate_image(**generation))

    assert generate_result["ok"] is True
    assert generate_result["job_id"] == "e2e-job-1"

    submitted = generate_client.post.call_args[1]["json"]
    # compose 出來的每個欄位都應原樣轉送至 backend generate 端點
    for key, value in composed_generation.items():
        assert submitted[key] == value, f"{key} 未正確轉送"
    # generate_image 預設帶 batch_size=1
    assert submitted["batch_size"] == 1
