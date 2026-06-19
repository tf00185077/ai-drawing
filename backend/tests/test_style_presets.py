"""風格預設目錄（style preset catalog）provider 單元測試"""
import pytest

from app.core.style_presets import (
    FileStylePresetProvider,
    PresetNotFoundError,
    ProfileNotFoundError,
    ResourceInventory,
    compose_prompt,
    merge_negative_prompt,
)


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
            "negative_prompt": "low quality, bad anatomy",
            "default_params": {"steps": 28, "cfg": 6.5, "width": 1024, "height": 1024},
            "profiles": {
                "portrait": {
                    "prompt_prefix": "upper body, looking at viewer",
                    "negative_prompt": "extra limbs",
                    "params": {"steps": 32},
                },
                "full-body": {"prompt_prefix": "full body, standing pose"},
            },
        },
        {
            "id": "anima-b",
            "name": "Anima B",
            "template": "anima",
            "diffusion_model": "anima_unet.safetensors",
            "text_encoder": "anima_clip.safetensors",
            "vae": "anima_vae.safetensors",
            "base_prompt": "anima_style",
        },
    ]
}


def _provider() -> FileStylePresetProvider:
    return FileStylePresetProvider.from_data(SAMPLE_CATALOG)


class TestPromptComposition:
    def test_compose_prompt_order(self) -> None:
        """最終 prompt 依固定順序合併：base, prefix, content, suffix。"""
        result = compose_prompt("base_style", "prefix_part", "a girl", "suffix_part")
        assert result == "base_style, prefix_part, a girl, suffix_part"

    def test_compose_prompt_skips_blank_parts(self) -> None:
        result = compose_prompt("base_style", "", "a girl", "")
        assert result == "base_style, a girl"

    def test_merge_negative_prompt(self) -> None:
        assert (
            merge_negative_prompt("low quality", "extra limbs")
            == "low quality, extra limbs"
        )
        assert merge_negative_prompt("low quality", "") == "low quality"


class TestCatalogLoading:
    def test_empty_catalog_loads(self) -> None:
        provider = FileStylePresetProvider.from_data({"presets": []})
        assert provider.list_presets() == []

    def test_list_presets_returns_entries(self) -> None:
        provider = _provider()
        presets = provider.list_presets()
        assert {p.id for p in presets} == {"creator-a", "anima-b"}

    def test_get_preset_returns_full_recipe(self) -> None:
        preset = _provider().get_preset("creator-a")
        assert preset is not None
        assert preset.name == "Creator A"
        assert preset.checkpoint == "model.safetensors"
        assert preset.lora == "creator-a.safetensors"
        assert preset.profile_names == ["portrait", "full-body"]
        assert preset.note_path == "Obsidian/Creators/creator-a.md"

    def test_get_unknown_preset_returns_none(self) -> None:
        assert _provider().get_preset("nope") is None


class TestCompose:
    def test_default_profile_composition(self) -> None:
        result = _provider().compose("creator-a", "a girl in a raincoat")
        gen = result.generation
        assert result.preset_id == "creator-a"
        assert result.profile is None
        assert gen["checkpoint"] == "model.safetensors"
        assert gen["lora"] == "creator-a.safetensors"
        assert gen["lora_strength"] == 0.75
        assert gen["template"] == "default_lora"
        assert gen["prompt"] == (
            "creator_a_style, anime illustration, a girl in a raincoat"
        )
        assert gen["negative_prompt"] == "low quality, bad anatomy"
        assert gen["steps"] == 28
        assert gen["cfg"] == 6.5

    def test_named_profile_modifies_prompt_and_overrides_params(self) -> None:
        result = _provider().compose(
            "creator-a", "a girl in a raincoat", profile="portrait"
        )
        gen = result.generation
        assert result.profile == "portrait"
        assert gen["prompt"] == (
            "creator_a_style, anime illustration, "
            "upper body, looking at viewer, a girl in a raincoat"
        )
        # profile negative merges with preset negative
        assert gen["negative_prompt"] == "low quality, bad anatomy, extra limbs"
        # profile param overrides preset default only for explicitly set fields
        assert gen["steps"] == 32
        assert gen["cfg"] == 6.5  # unchanged

    def test_diffusion_family_preset_composes_components(self) -> None:
        gen = _provider().compose("anima-b", "a girl").generation
        assert gen["template"] == "anima"
        assert gen["diffusion_model"] == "anima_unet.safetensors"
        assert gen["text_encoder"] == "anima_clip.safetensors"
        assert gen["vae"] == "anima_vae.safetensors"
        assert "checkpoint" not in gen

    def test_overrides_take_highest_priority(self) -> None:
        gen = _provider().compose(
            "creator-a", "a girl", overrides={"steps": 40, "seed": 123}
        ).generation
        assert gen["steps"] == 40
        assert gen["seed"] == 123

    def test_unknown_preset_raises(self) -> None:
        with pytest.raises(PresetNotFoundError):
            _provider().compose("nope", "a girl")

    def test_unknown_profile_raises_with_available(self) -> None:
        with pytest.raises(ProfileNotFoundError) as exc:
            _provider().compose("creator-a", "a girl", profile="nope")
        assert exc.value.available == ["portrait", "full-body"]


class TestValidation:
    def test_valid_preset_reports_checked_resources(self) -> None:
        inventory = ResourceInventory(
            checkpoints=("model.safetensors",),
            loras=("creator-a.safetensors",),
            workflows=("default_lora", "anima"),
            diffusion_models=("anima_unet.safetensors",),
            text_encoders=("anima_clip.safetensors",),
            vaes=("anima_vae.safetensors",),
        )
        results = {v.preset_id: v for v in _provider().validate_presets(inventory)}
        assert results["creator-a"].valid is True
        assert results["creator-a"].checked["checkpoint"] == "model.safetensors"
        assert results["creator-a"].missing == ()
        assert results["anima-b"].valid is True

    def test_missing_resource_reported_without_hiding_preset(self) -> None:
        inventory = ResourceInventory(
            checkpoints=(),
            loras=(),
            workflows=("default_lora",),
        )
        results = {v.preset_id: v for v in _provider().validate_presets(inventory)}
        # preset 仍然列出
        assert "creator-a" in results
        assert results["creator-a"].valid is False
        missing_types = {m.resource_type for m in results["creator-a"].missing}
        assert "checkpoint" in missing_types
        assert "lora" in missing_types

    def test_missing_note_path_is_reported(self, tmp_path) -> None:
        provider = FileStylePresetProvider.from_data(
            {
                "presets": [
                    {
                        "id": "creator-a",
                        "name": "Creator A",
                        "note_path": "docs/style-presets/creator-a.md",
                    }
                ]
            },
            project_root=tmp_path,
        )
        result = provider.validate_presets(ResourceInventory())[0]
        missing = {(m.resource_type, m.name) for m in result.missing}
        assert result.valid is False
        assert ("note_path", "docs/style-presets/creator-a.md") in missing

    def test_note_frontmatter_preset_id_must_match_catalog_id(self, tmp_path) -> None:
        note = tmp_path / "docs" / "style-presets" / "creator-a.md"
        note.parent.mkdir(parents=True)
        note.write_text(
            "---\npreset_id: wrong-id\n---\n# Creator A\n",
            encoding="utf-8",
        )
        provider = FileStylePresetProvider.from_data(
            {
                "presets": [
                    {
                        "id": "creator-a",
                        "name": "Creator A",
                        "note_path": "docs/style-presets/creator-a.md",
                    }
                ]
            },
            project_root=tmp_path,
        )
        result = provider.validate_presets(ResourceInventory())[0]
        missing_types = {m.resource_type for m in result.missing}
        assert result.valid is False
        assert "note_preset_id" in missing_types

    def test_matching_note_frontmatter_keeps_preset_valid(self, tmp_path) -> None:
        note = tmp_path / "docs" / "style-presets" / "creator-a.md"
        note.parent.mkdir(parents=True)
        note.write_text(
            "---\npreset_id: creator-a\n---\n# Creator A\n",
            encoding="utf-8",
        )
        provider = FileStylePresetProvider.from_data(
            {
                "presets": [
                    {
                        "id": "creator-a",
                        "name": "Creator A",
                        "note_path": "docs/style-presets/creator-a.md",
                    }
                ]
            },
            project_root=tmp_path,
        )
        result = provider.validate_presets(ResourceInventory())
        assert result[0].valid is True
        assert result[0].missing == ()
