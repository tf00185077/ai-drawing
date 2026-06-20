"""
風格預設目錄（Style Preset Catalog）

以檔案為來源（JSON）載入創作者 / 風格「食譜」，提供 list / get / validate / compose。
- 執行期來源為 JSON，便於後端與 MCP 工具驗證與解析（見 design.md Decision 1）。
- Obsidian / Markdown 筆記僅作為人類文件，透過 note_path 參照，不在每次請求時解析。
- compose 產出與 generate_image 相容的 generation payload，但不會送出生圖任務
  （compose first, generate second，見 design.md Decision 3）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol


# --- 例外 -----------------------------------------------------------------


class PresetNotFoundError(KeyError):
    """找不到指定的 preset id。"""

    def __init__(self, preset_id: str) -> None:
        self.preset_id = preset_id
        super().__init__(preset_id)


class ProfileNotFoundError(KeyError):
    """preset 存在但找不到指定 profile。"""

    def __init__(self, preset_id: str, profile: str, available: list[str]) -> None:
        self.preset_id = preset_id
        self.profile = profile
        self.available = available
        super().__init__(profile)


# --- 型別模型 -------------------------------------------------------------


@dataclass(frozen=True)
class StyleProfile:
    """preset 下的具名 profile，可調整 prompt 與覆寫部分生成參數。"""

    name: str
    prompt_prefix: str = ""
    prompt_suffix: str = ""
    negative_prompt: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StylePreset:
    """單一創作者 / 風格食譜。"""

    id: str
    name: str
    note_path: str | None = None
    template: str | None = None
    checkpoint: str | None = None
    lora: str | None = None
    lora_strength: float | None = None
    diffusion_model: str | None = None
    text_encoder: str | None = None
    vae: str | None = None
    base_prompt: str = ""
    negative_prompt: str = ""
    default_params: Mapping[str, Any] = field(default_factory=dict)
    profiles: Mapping[str, StyleProfile] = field(default_factory=dict)

    @property
    def profile_names(self) -> list[str]:
        return list(self.profiles.keys())


@dataclass(frozen=True)
class ResourceInventory:
    """目前已安裝的 ComfyUI 資源與 workflow 模板，用於驗證 preset 參照。"""

    checkpoints: tuple[str, ...] = ()
    loras: tuple[str, ...] = ()
    diffusion_models: tuple[str, ...] = ()
    text_encoders: tuple[str, ...] = ()
    vaes: tuple[str, ...] = ()
    workflows: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ResourceInventory":
        def _t(key: str) -> tuple[str, ...]:
            return tuple(data.get(key) or ())

        return cls(
            checkpoints=_t("checkpoints"),
            loras=_t("loras"),
            diffusion_models=_t("diffusion_models"),
            text_encoders=_t("text_encoders"),
            vaes=_t("vaes"),
            workflows=_t("workflows"),
        )


@dataclass(frozen=True)
class MissingResource:
    """驗證時找不到的單一資源。"""

    resource_type: str  # checkpoint / lora / diffusion_model / text_encoder / vae / template
    name: str


@dataclass(frozen=True)
class PresetValidation:
    """單一 preset 的驗證結果。"""

    preset_id: str
    valid: bool
    checked: Mapping[str, str]  # resource_type -> name（preset 有參照的項目）
    missing: tuple[MissingResource, ...]


@dataclass(frozen=True)
class ComposeResult:
    """compose 結果：可直接交給 generate_image 的 generation payload。"""

    preset_id: str
    profile: str | None
    generation: dict[str, Any]


# --- Provider 介面 --------------------------------------------------------


class StylePresetProvider(Protocol):
    """preset 來源抽象，可替換為檔案、DB 等實作。"""

    def list_presets(self) -> list[StylePreset]: ...

    def get_preset(self, preset_id: str) -> StylePreset | None: ...

    def validate_presets(
        self, inventory: ResourceInventory
    ) -> list[PresetValidation]: ...

    def compose(
        self,
        preset_id: str,
        content_prompt: str,
        profile: str | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> ComposeResult: ...


# --- 純函式：prompt 組裝 --------------------------------------------------


def join_prompt_parts(*parts: str) -> str:
    """以逗號合併非空 prompt 片段，已 strip 兩端空白；空白片段略過。"""
    cleaned = [p.strip() for p in parts if p and p.strip()]
    return ", ".join(cleaned)


def compose_prompt(
    base_prompt: str,
    prompt_prefix: str,
    content_prompt: str,
    prompt_suffix: str,
) -> str:
    """
    依固定順序組裝最終 prompt（見 design.md Decision 4）：
    1. preset base_prompt
    2. profile prompt_prefix
    3. user content_prompt
    4. profile prompt_suffix
    """
    return join_prompt_parts(base_prompt, prompt_prefix, content_prompt, prompt_suffix)


def merge_negative_prompt(preset_negative: str, profile_negative: str) -> str:
    """合併 preset 與 profile 層級的負面 prompt。"""
    return join_prompt_parts(preset_negative, profile_negative)


# --- 解析 -----------------------------------------------------------------


def _parse_profile(name: str, raw: Mapping[str, Any]) -> StyleProfile:
    return StyleProfile(
        name=name,
        prompt_prefix=raw.get("prompt_prefix", "") or "",
        prompt_suffix=raw.get("prompt_suffix", "") or "",
        negative_prompt=raw.get("negative_prompt", "") or "",
        params=dict(raw.get("params") or {}),
    )


def _parse_preset(raw: Mapping[str, Any]) -> StylePreset:
    if "id" not in raw or "name" not in raw:
        raise ValueError("style preset 需要 id 與 name 欄位")
    profiles = {
        pname: _parse_profile(pname, praw or {})
        for pname, praw in (raw.get("profiles") or {}).items()
    }
    return StylePreset(
        id=str(raw["id"]),
        name=str(raw["name"]),
        note_path=raw.get("note_path"),
        template=raw.get("template"),
        checkpoint=raw.get("checkpoint"),
        lora=raw.get("lora"),
        lora_strength=raw.get("lora_strength"),
        diffusion_model=raw.get("diffusion_model"),
        text_encoder=raw.get("text_encoder"),
        vae=raw.get("vae"),
        base_prompt=raw.get("base_prompt", "") or "",
        negative_prompt=raw.get("negative_prompt", "") or "",
        default_params=dict(raw.get("default_params") or {}),
        profiles=profiles,
    )


def _read_frontmatter_value(path: Path, key: str) -> str | None:
    """Read a simple `key: value` from YAML-like Markdown frontmatter."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if ":" not in line:
            continue
        found_key, value = line.split(":", 1)
        if found_key.strip() == key:
            return value.strip().strip('"').strip("'") or None
    return None


# --- 檔案實作 -------------------------------------------------------------


class FileStylePresetProvider:
    """以 JSON 檔案為來源的 preset provider。"""

    def __init__(self, presets: list[StylePreset], project_root: Path | None = None) -> None:
        self._presets = presets
        self._by_id = {p.id: p for p in presets}
        self._project_root = project_root

    @classmethod
    def from_data(
        cls,
        data: Mapping[str, Any],
        project_root: Path | None = None,
    ) -> "FileStylePresetProvider":
        raw_presets = data.get("presets") or []
        return cls([_parse_preset(p) for p in raw_presets], project_root=project_root)

    @classmethod
    def from_file(cls, path: Path) -> "FileStylePresetProvider":
        if not path.exists():
            return cls([])
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        project_root = path.resolve().parent.parent.parent
        return cls.from_data(data, project_root=project_root)

    def list_presets(self) -> list[StylePreset]:
        return list(self._presets)

    def get_preset(self, preset_id: str) -> StylePreset | None:
        return self._by_id.get(preset_id)

    def _require_preset(self, preset_id: str) -> StylePreset:
        preset = self._by_id.get(preset_id)
        if preset is None:
            raise PresetNotFoundError(preset_id)
        return preset

    def validate_presets(
        self, inventory: ResourceInventory
    ) -> list[PresetValidation]:
        return [self._validate_one(p, inventory) for p in self._presets]

    def validate_preset(
        self, preset_id: str, inventory: ResourceInventory
    ) -> PresetValidation:
        return self._validate_one(self._require_preset(preset_id), inventory)

    def _validate_one(
        self, preset: StylePreset, inventory: ResourceInventory
    ) -> PresetValidation:
        # (resource_type, preset 值, 可用清單)
        refs: list[tuple[str, str | None, tuple[str, ...]]] = [
            ("checkpoint", preset.checkpoint, inventory.checkpoints),
            ("lora", preset.lora, inventory.loras),
            ("diffusion_model", preset.diffusion_model, inventory.diffusion_models),
            ("text_encoder", preset.text_encoder, inventory.text_encoders),
            ("vae", preset.vae, inventory.vaes),
            ("template", preset.template, inventory.workflows),
        ]
        checked: dict[str, str] = {}
        missing: list[MissingResource] = []
        for rtype, value, available in refs:
            if not value:
                continue
            checked[rtype] = value
            if value not in available:
                missing.append(MissingResource(resource_type=rtype, name=value))
        self._validate_note(preset, missing)
        return PresetValidation(
            preset_id=preset.id,
            valid=not missing,
            checked=checked,
            missing=tuple(missing),
        )

    def _validate_note(
        self,
        preset: StylePreset,
        missing: list[MissingResource],
    ) -> None:
        if not preset.note_path or self._project_root is None:
            return
        note_path = (self._project_root / preset.note_path).resolve()
        try:
            note_path.relative_to(self._project_root.resolve())
        except ValueError:
            missing.append(MissingResource(resource_type="note_path", name=preset.note_path))
            return
        if not note_path.exists():
            missing.append(MissingResource(resource_type="note_path", name=preset.note_path))
            return
        note_preset_id = _read_frontmatter_value(note_path, "preset_id")
        if note_preset_id != preset.id:
            missing.append(
                MissingResource(
                    resource_type="note_preset_id",
                    name=f"{preset.note_path}: expected {preset.id}, got {note_preset_id or '(missing)'}",
                )
            )

    def compose(
        self,
        preset_id: str,
        content_prompt: str,
        profile: str | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> ComposeResult:
        preset = self._require_preset(preset_id)

        selected_profile: StyleProfile | None = None
        if profile is not None:
            selected_profile = preset.profiles.get(profile)
            if selected_profile is None:
                raise ProfileNotFoundError(
                    preset_id, profile, preset.profile_names
                )

        prompt_prefix = selected_profile.prompt_prefix if selected_profile else ""
        prompt_suffix = selected_profile.prompt_suffix if selected_profile else ""
        profile_negative = selected_profile.negative_prompt if selected_profile else ""

        final_prompt = compose_prompt(
            preset.base_prompt, prompt_prefix, content_prompt, prompt_suffix
        )
        final_negative = merge_negative_prompt(preset.negative_prompt, profile_negative)

        generation: dict[str, Any] = {}
        if preset.template:
            generation["template"] = preset.template
        if preset.checkpoint:
            generation["checkpoint"] = preset.checkpoint
        if preset.lora:
            generation["lora"] = preset.lora
        if preset.lora_strength is not None:
            generation["lora_strength"] = preset.lora_strength
        if preset.diffusion_model:
            generation["diffusion_model"] = preset.diffusion_model
        if preset.text_encoder:
            generation["text_encoder"] = preset.text_encoder
        if preset.vae:
            generation["vae"] = preset.vae

        generation["prompt"] = final_prompt
        if final_negative:
            generation["negative_prompt"] = final_negative

        # 參數優先序：preset default_params < profile params < overrides
        merged_params: dict[str, Any] = dict(preset.default_params)
        if selected_profile:
            merged_params.update(selected_profile.params)
        generation.update(merged_params)

        if overrides:
            for key, value in overrides.items():
                if value is not None:
                    generation[key] = value

        return ComposeResult(
            preset_id=preset.id,
            profile=profile,
            generation=generation,
        )


# --- 預設來源（執行期 catalog 檔） ----------------------------------------

# 專案根目錄 style_presets/agent/catalog.json（機器可讀來源；人類筆記在 style_presets/human/）
# 注意：from_file 以 path.parent.parent.parent 推 project_root，此路徑（root/style_presets/agent）
# 三層回到 repo root，note_path 仍以 repo-root 相對路徑解析。
DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "style_presets" / "agent" / "catalog.json"
)


def get_default_provider() -> StylePresetProvider:
    """DI 工廠：回傳以執行期 catalog 檔為來源的 Provider，便於測試時 override。"""
    return FileStylePresetProvider.from_file(DEFAULT_CATALOG_PATH)
