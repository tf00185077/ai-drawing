"""
Workflow 模板能力 manifest

每個 workflow 模板（backend/workflows/<name>.json）可附一份能力 manifest
（backend/workflows/<name>.meta.json），以「受控詞彙的二元/離散標籤」描述它能解決
什麼，讓 agent 不必展開整份 workflow JSON 即可判斷模板是否適用（見 #3 二元 reuse 匹配）。

設計：
- 標籤一律取自受控詞彙（CONTROLLED_VOCABULARY），不在詞彙內者視為 invalid，避免
  「同義不同名」造成的標籤腐化（如 controlnet_pose vs pose_control）。
- modality / model_family 單值；conditioning / io 為集合。
- description 僅供人閱讀，不參與匹配決策。
契約：openspec/specs/workflow-template-catalog/spec.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
import json

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent.parent / "workflows"

# 受控詞彙：欄位 -> 允許值集合。新增標籤須在此登錄，不得自由發明。
CONTROLLED_VOCABULARY: dict[str, set[str]] = {
    "modality": {"txt2img", "img2img", "inpaint", "txt2video", "img2video"},
    # conditioning captures optional graph capabilities beyond the base modality.
    # `lora_model_only` is used by split-model families such as Anima where a
    # LoRA is injected into MODEL via LoraLoaderModelOnly without touching CLIP.
    # `multi_lora` distinguishes chained LoRA graphs from single-LoRA templates;
    # use it when a preset/source page requires multiple LoRAs to be wired in order.
    "conditioning": {"controlnet_pose", "lora_model_only", "multi_lora", "pose_transfer"},
    "io": {"text", "image_ref", "pose_ref", "mask", "first_frame", "last_frame", "video_ref", "audio_ref"},
    "model_family": {"sdxl", "sd15", "anima", "qwen_image", "qwen_image_edit", "wan", "ltx_video", "hunyuan_video", "animatediff", "svd", "mochi"},
}
SINGLE_VALUED = {"modality", "model_family"}  # 其餘為集合
SET_VALUED = {"conditioning", "io"}
# modality 與 model_family 皆必填——刻意不允許 None/省略，維持嚴謹：每個模板都得明確
# 宣告它綁哪個模型家族（checkpoint 型模板亦須指明，如 sdxl），匹配才不會落入「未知」灰帶。
REQUIRED_FIELDS = {"modality", "model_family"}


@dataclass(frozen=True)
class WorkflowManifest:
    """單一模板的能力 manifest。"""

    id: str
    modality: str
    model_family: str = ""
    conditioning: tuple[str, ...] = ()
    io: tuple[str, ...] = ()
    description: str = ""
    deprecated: bool = False  # 版本化淘汰：不再被 reuse 匹配，但檔案保留供追溯

    def tags(self) -> dict[str, Any]:
        """供索引輸出的標籤（不含 description 的決策語意，但一併附給人看）。"""
        return {
            "modality": self.modality,
            "model_family": self.model_family,
            "conditioning": list(self.conditioning),
            "io": list(self.io),
        }


def parse_manifest(template_id: str, raw: Mapping[str, Any]) -> WorkflowManifest:
    """從 raw dict 解析成 WorkflowManifest（不做詞彙驗證，驗證見 validate_manifest）。"""
    def _as_tuple(v: Any) -> tuple[str, ...]:
        if v is None:
            return ()
        if isinstance(v, str):
            return (v,)
        return tuple(str(x) for x in v)

    return WorkflowManifest(
        id=str(raw.get("id", template_id)),
        modality=str(raw.get("modality", "")),
        model_family=str(raw.get("model_family", "")),
        conditioning=_as_tuple(raw.get("conditioning")),
        io=_as_tuple(raw.get("io")),
        description=str(raw.get("description", "")),
        deprecated=bool(raw.get("deprecated", False)),
    )


def validate_manifest(
    manifest: WorkflowManifest, *, expected_id: str | None = None
) -> list[str]:
    """
    驗證 manifest：必填欄位齊、所有標籤在受控詞彙內、id 與檔名一致。
    回傳問題清單（空清單代表通過）；invalid 以資料回報，不拋例外。
    """
    problems: list[str] = []

    if expected_id is not None and manifest.id != expected_id:
        problems.append(f"id mismatch: manifest id={manifest.id!r}, expected {expected_id!r}")

    # 必填欄位（modality、model_family 皆不得省略）
    if "modality" in REQUIRED_FIELDS and not manifest.modality:
        problems.append("missing required field: modality")
    if "model_family" in REQUIRED_FIELDS and not manifest.model_family:
        problems.append("missing required field: model_family")

    # 單值欄位詞彙
    if manifest.modality and manifest.modality not in CONTROLLED_VOCABULARY["modality"]:
        problems.append(f"modality not in vocabulary: {manifest.modality!r}")
    if manifest.model_family and manifest.model_family not in CONTROLLED_VOCABULARY["model_family"]:
        problems.append(f"model_family not in vocabulary: {manifest.model_family!r}")

    # 集合欄位
    for val in manifest.conditioning:
        if val not in CONTROLLED_VOCABULARY["conditioning"]:
            problems.append(f"conditioning not in vocabulary: {val!r}")
    for val in manifest.io:
        if val not in CONTROLLED_VOCABULARY["io"]:
            problems.append(f"io not in vocabulary: {val!r}")

    return problems


@dataclass(frozen=True)
class CapabilityRequest:
    """agent 表達「這次生圖需要的能力」。modality 必填；其餘為選用約束。"""

    modality: str
    model_family: str | None = None
    conditioning: tuple[str, ...] = ()
    io: tuple[str, ...] = ()


def manifest_covers(manifest: WorkflowManifest, request: CapabilityRequest) -> bool:
    """
    二元判定：模板能力是否「涵蓋」需求（superset 測試）。逐欄位皆需成立（AND）：
    - modality 必須相等（必填、必比）
    - model_family：需求若指定則須相等；未指定代表不限制家族
    - conditioning / io：需求集合須是模板集合的子集（模板要做得到至少需求那些）
    無模糊分數，純集合運算。
    """
    if request.modality != manifest.modality:
        return False
    if request.model_family is not None and request.model_family != manifest.model_family:
        return False
    if not set(request.conditioning) <= set(manifest.conditioning):
        return False
    if not set(request.io) <= set(manifest.io):
        return False
    return True


def find_matching_templates(
    loaded: list["LoadedManifest"], request: CapabilityRequest
) -> list[str]:
    """回傳能涵蓋需求的模板 id（依 id 排序）。只有通過驗證、且未 deprecated 的 manifest 才可
    被匹配——壞掉/詞彙不合/已淘汰的模板不該被 reuse。無命中回空清單（agent 應改為自組）。"""
    return sorted(
        lm.manifest.id
        for lm in loaded
        if lm.valid and not lm.manifest.deprecated and manifest_covers(lm.manifest, request)
    )


def capability_key(
    modality: str, model_family: str, conditioning, io
) -> tuple[str, str, frozenset, frozenset]:
    """能力標籤集合的正規化 key，用於回填去重（集合無序、可雜湊）。"""
    return (modality, model_family, frozenset(conditioning), frozenset(io))


def manifest_key(m: "WorkflowManifest") -> tuple[str, str, frozenset, frozenset]:
    return capability_key(m.modality, m.model_family, m.conditioning, m.io)


@dataclass
class LoadedManifest:
    """載入結果：manifest 本體 + 驗證問題 + 對應 workflow 是否存在。"""

    manifest: WorkflowManifest
    problems: list[str] = field(default_factory=list)
    workflow_exists: bool = True

    @property
    def valid(self) -> bool:
        return not self.problems and self.workflow_exists


def load_manifests(workflows_dir: Path | None = None) -> list[LoadedManifest]:
    """
    掃描 workflows 目錄下所有 *.meta.json，解析、驗證，並檢查對應 <name>.json 是否存在。
    僅讀小的 meta 檔，不讀完整 workflow JSON（滿足索引「不展開 workflow」要求）。
    依 id 排序。
    """
    wf_dir = workflows_dir or WORKFLOWS_DIR
    results: list[LoadedManifest] = []
    if not wf_dir.exists():
        return results
    for meta_path in sorted(wf_dir.glob("*.meta.json")):
        template_id = meta_path.name[: -len(".meta.json")]
        with meta_path.open(encoding="utf-8") as f:
            raw = json.load(f)
        manifest = parse_manifest(template_id, raw)
        problems = validate_manifest(manifest, expected_id=template_id)
        workflow_exists = (wf_dir / f"{template_id}.json").exists()
        if not workflow_exists:
            problems = problems + [f"workflow file missing: {template_id}.json"]
        results.append(
            LoadedManifest(
                manifest=manifest, problems=problems, workflow_exists=workflow_exists
            )
        )
    return sorted(results, key=lambda r: r.manifest.id)


# --- 回填：把一份驗證過成功的 workflow 晉升為可重用模板 -------------------


def strip_workflow_to_shape(workflow: Mapping[str, Any]) -> dict[str, Any]:
    """剝去一次性內容（content prompt、固定 seed），留下可重用形狀。
    重用 apply_params 的節點定位（positive/negative CLIPTextEncode、KSampler.seed），
    把 seed 歸零、prompt/negative 文字清空；其餘圖結構不動。"""
    import copy

    from app.core.workflow import apply_params

    return apply_params(
        copy.deepcopy(dict(workflow)),
        seed=0,
        prompt="",
        negative_prompt="",
        bbox_detector=None,
    )


def _backfill_base_id(
    modality: str, model_family: str, conditioning, io
) -> str:
    """由能力 key 產生可讀且編入家族（modality）的 base id。"""
    parts = ["gen", modality, model_family]
    parts += sorted(conditioning)
    parts += sorted(set(io) - {"text"})  # text 為基本，不入名以免冗長
    return "_".join(p for p in parts if p)


def _available_id(wf_dir: Path, base: str) -> str:
    """回傳未被占用的 id：base 可用就用 base，否則 base_v2 / v3 ...（版本化、不覆寫）。"""
    if not (wf_dir / f"{base}.json").exists() and not (wf_dir / f"{base}.meta.json").exists():
        return base
    n = 2
    while (wf_dir / f"{base}_v{n}.json").exists() or (wf_dir / f"{base}_v{n}.meta.json").exists():
        n += 1
    return f"{base}_v{n}"


def _mark_deprecated(wf_dir: Path, template_id: str) -> None:
    """把既有模板的 meta 標記 deprecated（只動 metadata，不碰 graph）。"""
    meta = wf_dir / f"{template_id}.meta.json"
    if not meta.exists():
        return
    with meta.open(encoding="utf-8") as f:
        raw = json.load(f)
    raw["deprecated"] = True
    with meta.open("w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
        f.write("\n")


def backfill_template(
    workflow: Mapping[str, Any],
    *,
    modality: str,
    model_family: str,
    conditioning,
    io,
    description: str = "",
    workflows_dir: Path | None = None,
) -> dict[str, Any]:
    """
    把一份「已驗證成功」的 workflow 晉升為模板（呼叫端負責 DB 成功閘門）。
    - 標籤須通過受控詞彙驗證。
    - 以能力 key 去重：已有有效同 key 模板 → 不新增（回 reused）。
    - 無同 key → 新增，依 modality 家族命名歸檔，存「形狀」（剝 prompt/seed）。
    - 同 key 但既有模板已壞 → 出新版本並把舊的標 deprecated（永不就地改 graph、不合併圖）。
    """
    wf_dir = workflows_dir or WORKFLOWS_DIR
    conditioning = tuple(conditioning or ())
    io = tuple(io or ())

    candidate = WorkflowManifest(
        id="(pending)",
        modality=modality,
        model_family=model_family,
        conditioning=conditioning,
        io=io,
        description=description,
    )
    problems = validate_manifest(candidate)
    if problems:
        return {"ok": False, "error": "invalid_tags", "problems": problems}

    key = capability_key(modality, model_family, conditioning, io)
    existing = load_manifests(wf_dir)
    same_key = [
        lm for lm in existing
        if manifest_key(lm.manifest) == key and not lm.manifest.deprecated
    ]
    valid_same = [lm for lm in same_key if lm.valid]
    if valid_same:
        return {
            "ok": True,
            "created": False,
            "reused": valid_same[0].manifest.id,
            "reason": "capability already covered by an existing template",
        }

    base_id = _backfill_base_id(modality, model_family, conditioning, io)
    deprecated_id = None
    broken_same = [lm for lm in same_key if not lm.valid]
    if broken_same:
        _mark_deprecated(wf_dir, broken_same[0].manifest.id)
        deprecated_id = broken_same[0].manifest.id

    new_id = _available_id(wf_dir, base_id)
    shape = strip_workflow_to_shape(workflow)

    wf_dir.mkdir(parents=True, exist_ok=True)
    with (wf_dir / f"{new_id}.json").open("w", encoding="utf-8") as f:
        json.dump(shape, f, ensure_ascii=False, indent=2)
        f.write("\n")
    manifest_doc = {
        "id": new_id,
        "modality": modality,
        "model_family": model_family,
        "conditioning": list(conditioning),
        "io": list(io),
        "description": description,
    }
    with (wf_dir / f"{new_id}.meta.json").open("w", encoding="utf-8") as f:
        json.dump(manifest_doc, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return {
        "ok": True,
        "created": True,
        "template_id": new_id,
        "deprecated": deprecated_id,
    }


def consolidate_templates(workflows_dir: Path | None = None) -> dict[str, Any]:
    """清理（retire）已 deprecated 的模板：刪除其 sidecar（<id>.json + <id>.meta.json）。
    deprecated 本就不被 reuse；此為週期性／手動的家務整理，避免庫長期堆積。回傳被移除的 id。"""
    wf_dir = workflows_dir or WORKFLOWS_DIR
    removed: list[str] = []
    for lm in load_manifests(wf_dir):
        if not lm.manifest.deprecated:
            continue
        tid = lm.manifest.id
        for suffix in (".json", ".meta.json"):
            p = wf_dir / f"{tid}{suffix}"
            if p.exists():
                p.unlink()
        removed.append(tid)
    return {"removed": sorted(removed), "count": len(removed)}
