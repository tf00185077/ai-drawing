"""風格預設目錄 API 端點測試 + 一般生圖 forwarding diffusion 元件欄位測試"""
from unittest.mock import patch

import pytest

from app.api import style_presets as style_presets_api
from app.core.queue import _reset_for_test
from app.core.style_presets import DirStylePresetProvider, FileStylePresetProvider, ResourceInventory
from app.main import app

SAMPLE_CATALOG = {
    "presets": [
        {
            "id": "creator-a",
            "name": "Creator A",
            "note_path": "Obsidian/Creators/creator-a.md",
            "template": "default_lora",
            "checkpoint": "model.safetensors",
            "lora": "creator-a.safetensors",
            "lora_strength": 0.75,
            "base_prompt": "creator_a_style, anime illustration",
            "negative_prompt": "low quality",
            "default_params": {"steps": 28, "cfg": 6.5},
            "profiles": {
                "portrait": {"prompt_prefix": "upper body", "params": {"steps": 32}},
            },
        }
    ]
}


@pytest.fixture
def preset_client(client):
    provider = FileStylePresetProvider.from_data(SAMPLE_CATALOG)
    app.dependency_overrides[style_presets_api._provider] = lambda: provider
    yield client
    app.dependency_overrides.pop(style_presets_api._provider, None)


class TestStylePresetEndpoints:
    def test_list_returns_summaries(self, preset_client) -> None:
        r = preset_client.get("/api/style-presets/")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == "creator-a"
        assert items[0]["profiles"] == ["portrait"]

    def test_get_detail_returns_full_recipe(self, preset_client) -> None:
        r = preset_client.get("/api/style-presets/creator-a")
        assert r.status_code == 200
        data = r.json()
        assert data["checkpoint"] == "model.safetensors"
        assert data["base_prompt"] == "creator_a_style, anime illustration"
        assert data["profiles"][0]["name"] == "portrait"

    def test_get_unknown_returns_404(self, preset_client) -> None:
        r = preset_client.get("/api/style-presets/nope")
        assert r.status_code == 404

    def test_compose_returns_generation_payload(self, preset_client) -> None:
        r = preset_client.post(
            "/api/style-presets/creator-a/compose",
            json={"content_prompt": "a girl in a raincoat"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["preset_id"] == "creator-a"
        gen = data["generation"]
        assert gen["checkpoint"] == "model.safetensors"
        assert "a girl in a raincoat" in gen["prompt"]
        assert gen["prompt"].startswith("creator_a_style")
        assert gen["steps"] == 28

    def test_compose_with_profile(self, preset_client) -> None:
        r = preset_client.post(
            "/api/style-presets/creator-a/compose",
            json={"content_prompt": "a girl", "profile": "portrait"},
        )
        assert r.status_code == 200
        gen = r.json()["generation"]
        assert "upper body" in gen["prompt"]
        assert gen["steps"] == 32

    def test_compose_unknown_profile_returns_422(self, preset_client) -> None:
        r = preset_client.post(
            "/api/style-presets/creator-a/compose",
            json={"content_prompt": "a girl", "profile": "nope"},
        )
        assert r.status_code == 422
        assert "portrait" in r.json()["detail"]

    def test_compose_unknown_preset_returns_404(self, preset_client) -> None:
        r = preset_client.post(
            "/api/style-presets/nope/compose",
            json={"content_prompt": "a girl"},
        )
        assert r.status_code == 404

    def test_validate_reports_missing_without_hiding(self, preset_client) -> None:
        inventory = ResourceInventory(checkpoints=(), loras=(), workflows=("default_lora",))
        with patch.object(
            style_presets_api, "_current_inventory", return_value=inventory
        ):
            r = preset_client.get("/api/style-presets/validate")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["preset_id"] == "creator-a"
        assert items[0]["valid"] is False
        missing_types = {m["resource_type"] for m in items[0]["missing"]}
        assert "checkpoint" in missing_types
        assert "lora" in missing_types

    def test_create_detail_list_and_compose_preserve_loras(self, client, tmp_path) -> None:
        agent_dir = tmp_path / "style_presets" / "agent"
        provider = DirStylePresetProvider(agent_dir, project_root=tmp_path)
        app.dependency_overrides[style_presets_api._provider] = lambda: provider
        loras = [
            {"name": "line.safetensors", "strength_model": 0.8},
            {"name": "color.safetensors", "strength_model": 0.5, "strength_clip": 0.4},
        ]
        try:
            inventory = ResourceInventory(loras=("line.safetensors", "color.safetensors"), workflows=("multi",))
            with patch.object(style_presets_api, "_current_inventory", return_value=inventory):
                r = client.post(
                    "/api/style-presets/",
                    json={
                        "id": "multi-a",
                        "name": "Multi A",
                        "template": "multi",
                        "lora": "legacy.safetensors",
                        "lora_strength": 0.7,
                        "loras": loras,
                        "base_prompt": "multi style",
                    },
                )
            assert r.status_code == 201

            detail = client.get("/api/style-presets/multi-a").json()
            assert detail["lora"] == "legacy.safetensors"
            assert detail["lora_strength"] == 0.7
            assert detail["loras"] == loras

            items = client.get("/api/style-presets/").json()["items"]
            assert items[0]["id"] == "multi-a"
            assert items[0]["loras"] == loras

            composed = client.post(
                "/api/style-presets/multi-a/compose",
                json={"content_prompt": "a girl"},
            ).json()["generation"]
            assert composed["template"] == "multi"
            assert composed["loras"] == loras
            assert "lora" not in composed
            assert "lora_strength" not in composed
        finally:
            app.dependency_overrides.pop(style_presets_api._provider, None)


class TestGenerateForwardsDiffusionFields:
    def setup_method(self) -> None:
        _reset_for_test()

    def test_diffusion_fields_forwarded_to_queue(self, client) -> None:
        with patch("app.api.generate.submit", return_value="job-1") as mock_submit:
            r = client.post(
                "/api/generate/",
                json={
                    "prompt": "1girl",
                    "template": "anima",
                    "diffusion_model": "anima_unet.safetensors",
                    "text_encoder": "anima_clip.safetensors",
                    "vae": "anima_vae.safetensors",
                },
            )
        assert r.status_code == 201
        params = mock_submit.call_args[0][0]
        assert params["diffusion_model"] == "anima_unet.safetensors"
        assert params["text_encoder"] == "anima_clip.safetensors"
        assert params["vae"] == "anima_vae.safetensors"

    def test_diffusion_fields_omitted_when_not_provided(self, client) -> None:
        with patch("app.api.generate.submit", return_value="job-2") as mock_submit:
            r = client.post("/api/generate/", json={"prompt": "1girl"})
        assert r.status_code == 201
        params = mock_submit.call_args[0][0]
        for key in ("diffusion_model", "text_encoder", "vae"):
            assert key not in params
