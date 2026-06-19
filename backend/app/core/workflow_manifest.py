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
    "modality": {"txt2img", "img2img", "inpaint"},
    "conditioning": {"controlnet_pose"},
    "io": {"text", "image_ref", "mask"},
    "model_family": {"sdxl", "sd15", "anima"},
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
