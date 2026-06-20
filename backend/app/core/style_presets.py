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
import re
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


class PresetExistsError(Exception):
    """建立時 preset id 已存在且未指定覆寫。"""

    def __init__(self, preset_id: str) -> None:
        self.preset_id = preset_id
        super().__init__(preset_id)


_ID_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def is_valid_preset_id(preset_id: str) -> bool:
    """preset id 須為簡單 slug（英數開頭，僅含英數／底線／連字號，無路徑分隔或空白）。"""
    return bool(preset_id) and bool(_ID_SLUG.match(preset_id))


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
    chinese_name: str | None = None
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

    def list_summaries(self) -> list[dict[str, Any]]: ...

    def reindex(self) -> dict[str, Any]: ...

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
        chinese_name=raw.get("chinese_name"),
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


# --- 共用：摘要 / 驗證 / compose（兩種 provider 共用）---------------------

_SUMMARY_REFS = ("template", "checkpoint", "lora", "diffusion_model")


def _note_stub(preset: StylePreset) -> str:
    """產生人類 note 初稿，frontmatter preset_id 對齊 catalog id（通過 note 驗證）。"""
    return (
        "---\n"
        f"preset_id: {preset.id}\n"
        f"catalog_path: style_presets/agent/presets/{preset.id}.json\n"
        f"checkpoint: {preset.checkpoint or ''}\n"
        f"lora: {preset.lora or ''}\n"
        "source_url:\n"
        "---\n\n"
        f"# {preset.name}\n\n"
        "（由 create_style_preset 產生的初始筆記，可自行補充來源 / 授權 / 試驗心得）\n\n"
        "## Resource Pairing\n\n"
        f"- Checkpoint: {preset.checkpoint or ''}\n"
        f"- LoRA: {preset.lora or ''}\n"
        f"- Template: {preset.template or ''}\n"
    )


def build_summary(preset: StylePreset) -> dict[str, Any]:
    """由完整 preset 產生輕量索引條目（list 用，不含 prompt/params/profile 內文）。"""
    return {
        "id": preset.id,
        "name": preset.name,
        "chinese_name": preset.chinese_name,
        "profiles": preset.profile_names,
        "note_path": preset.note_path,
        "template": preset.template,
        "checkpoint": preset.checkpoint,
        "lora": preset.lora,
        "diffusion_model": preset.diffusion_model,
    }


def _validate_note(
    preset: StylePreset, project_root: Path | None, missing: list[MissingResource]
) -> None:
    if not preset.note_path or project_root is None:
        return
    note_path = (project_root / preset.note_path).resolve()
    try:
        note_path.relative_to(project_root.resolve())
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


def validate_preset_against(
    preset: StylePreset, inventory: ResourceInventory, project_root: Path | None
) -> PresetValidation:
    """驗證單一 preset 的資源參照與 note（純函式，兩種 provider 共用）。"""
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
    _validate_note(preset, project_root, missing)
    return PresetValidation(
        preset_id=preset.id, valid=not missing, checked=checked, missing=tuple(missing)
    )


def compose_preset(
    preset: StylePreset,
    content_prompt: str,
    profile: str | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> ComposeResult:
    """把 preset + content_prompt 組成 generate_image 相容的 generation payload（純函式）。"""
    selected_profile: StyleProfile | None = None
    if profile is not None:
        selected_profile = preset.profiles.get(profile)
        if selected_profile is None:
            raise ProfileNotFoundError(preset.id, profile, preset.profile_names)

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

    merged_params: dict[str, Any] = dict(preset.default_params)
    if selected_profile:
        merged_params.update(selected_profile.params)
    generation.update(merged_params)

    if overrides:
        for key, value in overrides.items():
            if value is not None:
                generation[key] = value

    return ComposeResult(preset_id=preset.id, profile=profile, generation=generation)


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

    def list_summaries(self) -> list[dict[str, Any]]:
        return [build_summary(p) for p in self._presets]

    def reindex(self) -> dict[str, Any]:
        # 記憶體 provider 無檔案可掃，回傳目前摘要即可（no-op）
        return {"presets": self.list_summaries()}

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
        return [
            validate_preset_against(p, inventory, self._project_root)
            for p in self._presets
        ]

    def validate_preset(
        self, preset_id: str, inventory: ResourceInventory
    ) -> PresetValidation:
        return validate_preset_against(
            self._require_preset(preset_id), inventory, self._project_root
        )

    def compose(
        self,
        preset_id: str,
        content_prompt: str,
        profile: str | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> ComposeResult:
        return compose_preset(
            self._require_preset(preset_id), content_prompt, profile, overrides
        )


# --- 目錄分層實作（index + 單檔 detail）----------------------------------


def reindex(agent_dir: Path) -> dict[str, Any]:
    """掃描 agent_dir/presets/*.json，重建 agent_dir/index.json（輕量摘要）。回傳寫入的 index。"""
    presets_dir = agent_dir / "presets"
    summaries: list[dict[str, Any]] = []
    if presets_dir.exists():
        for p in sorted(presets_dir.glob("*.json")):
            with p.open(encoding="utf-8") as f:
                preset = _parse_preset(json.load(f))
            summaries.append(build_summary(preset))
    agent_dir.mkdir(parents=True, exist_ok=True)
    index = {"presets": summaries}
    with (agent_dir / "index.json").open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return index


class DirStylePresetProvider:
    """目錄分層 provider：index.json（輕量，list 用）+ presets/<id>.json（完整，detail 用）。"""

    def __init__(self, agent_dir: Path, project_root: Path | None = None) -> None:
        self._agent_dir = agent_dir
        self._presets_dir = agent_dir / "presets"
        self._index_path = agent_dir / "index.json"
        self._project_root = project_root
        self._cache: dict[str, StylePreset] = {}

    # --- 索引（輕量）---
    def list_summaries(self) -> list[dict[str, Any]]:
        if not self._index_path.exists():
            reindex(self._agent_dir)  # 自我修復：index 不存在時由 detail 重建
        if not self._index_path.exists():
            return []
        with self._index_path.open(encoding="utf-8") as f:
            return json.load(f).get("presets", [])

    def reindex(self) -> dict[str, Any]:
        self._cache.clear()
        return reindex(self._agent_dir)

    def validate_preset(
        self, preset_id: str, inventory: ResourceInventory
    ) -> PresetValidation:
        return validate_preset_against(
            self._require_preset(preset_id), inventory, self._project_root
        )

    def create_preset(
        self,
        fields: Mapping[str, Any],
        *,
        create_note: bool = True,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """從欄位建立 preset：寫 detail JSON + 人類 note stub（frontmatter 對齊 id）+ reindex。
        id/name 必填、id 須為合法 slug；detail 已存在且未 overwrite 則 raise PresetExistsError。"""
        pid = str(fields.get("id", "")).strip()
        name = str(fields.get("name", "")).strip()
        if not is_valid_preset_id(pid):
            raise ValueError(f"invalid preset id: {pid!r}（需英數開頭、僅含英數/底線/連字號）")
        if not name:
            raise ValueError("preset 需要 name")

        detail_path = self._presets_dir / f"{pid}.json"
        if detail_path.exists() and not overwrite:
            raise PresetExistsError(pid)

        recipe = dict(fields)
        recipe["id"] = pid
        recipe["name"] = name

        note_rel: str | None = None
        if create_note and self._project_root is not None:
            human_dir = self._agent_dir.parent / "human"
            note_abs = human_dir / f"{pid}.md"
            note_rel = note_abs.resolve().relative_to(self._project_root.resolve()).as_posix()
            recipe["note_path"] = note_rel

        # 解析驗證（確保結構合法，並讓 None 欄位乾淨）
        preset = _parse_preset(recipe)

        self._presets_dir.mkdir(parents=True, exist_ok=True)
        with detail_path.open("w", encoding="utf-8") as f:
            json.dump(recipe, f, ensure_ascii=False, indent=2)
            f.write("\n")

        if note_rel is not None:
            human_dir.mkdir(parents=True, exist_ok=True)
            note_abs.write_text(_note_stub(preset), encoding="utf-8")

        self.reindex()
        return {
            "id": pid,
            "created": True,
            "overwritten": detail_path.exists() and overwrite,
            "note_path": note_rel,
        }

    def _index_ids(self) -> set[str]:
        return {e.get("id") for e in self.list_summaries() if e.get("id")}

    def _file_ids(self) -> set[str]:
        if not self._presets_dir.exists():
            return set()
        return {p.stem for p in self._presets_dir.glob("*.json")}

    # --- detail（單檔，按需）---
    def get_preset(self, preset_id: str) -> StylePreset | None:
        if preset_id in self._cache:
            return self._cache[preset_id]
        path = self._presets_dir / f"{preset_id}.json"
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as f:
            preset = _parse_preset(json.load(f))
        self._cache[preset_id] = preset
        return preset

    def _require_preset(self, preset_id: str) -> StylePreset:
        preset = self.get_preset(preset_id)
        if preset is None:
            raise PresetNotFoundError(preset_id)
        return preset

    def list_presets(self) -> list[StylePreset]:
        # 完整載入（validate 等少數情境用），不在 list 熱路徑
        return [p for pid in sorted(self._file_ids()) if (p := self.get_preset(pid))]

    def validate_presets(self, inventory: ResourceInventory) -> list[PresetValidation]:
        results: list[PresetValidation] = []
        file_ids = self._file_ids()
        index_ids = self._index_ids()
        for pid in sorted(file_ids):
            preset = self.get_preset(pid)
            if preset is None:
                continue
            res = validate_preset_against(preset, inventory, self._project_root)
            # index↔detail 漂移：detail 檔存在但 index 沒列
            if pid not in index_ids:
                missing = list(res.missing) + [MissingResource("index_entry", pid)]
                res = PresetValidation(pid, False, res.checked, tuple(missing))
            results.append(res)
        # index 列了但 detail 檔不存在
        for pid in sorted(index_ids - file_ids):
            results.append(
                PresetValidation(
                    pid, False, {}, (MissingResource("detail_file", f"presets/{pid}.json"),)
                )
            )
        return results

    def compose(
        self,
        preset_id: str,
        content_prompt: str,
        profile: str | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> ComposeResult:
        return compose_preset(
            self._require_preset(preset_id), content_prompt, profile, overrides
        )


# --- 預設來源（執行期）----------------------------------------------------

# 專案根目錄 style_presets/agent/（index.json + presets/<id>.json）；人類筆記在 style_presets/human/。
# project_root = agent_dir.parent.parent = repo root，note_path 以 repo-root 相對解析。
DEFAULT_AGENT_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "style_presets" / "agent"
)


def get_default_provider() -> StylePresetProvider:
    """DI 工廠：回傳目錄分層 Provider，便於測試時 override。"""
    return DirStylePresetProvider(
        DEFAULT_AGENT_DIR, project_root=DEFAULT_AGENT_DIR.parent.parent
    )
