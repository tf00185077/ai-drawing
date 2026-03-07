"""
Prompt 模板庫（Phase 5b）
儲存常用 prompt 組合，支援變數替換（人物名稱、風格等）
契約：docs/api-contract.md 模組 5
"""
import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PromptTemplate:
    """單一 prompt 模板"""

    id: str
    name: str
    template: str  # 如 "1girl, {人物}, {風格}, solo"
    variables: tuple[str, ...]  # 如 ("人物", "風格")


class PromptTemplateProvider(Protocol):
    """模板來源抽象，可替換為檔案、DB 等實作"""

    def list_all(self) -> list[PromptTemplate]:
        """取得所有模板"""
        ...

    def get(self, template_id: str) -> PromptTemplate | None:
        """依 id 取得單一模板"""
        ...


def extract_variables(template: str) -> tuple[str, ...]:
    """
    從模板字串萃取變數名。
    範例: "1girl, {人物}, {風格}" -> ("人物", "風格")
    重複的變數只保留一次，順序依首次出現。
    """
    found = re.findall(r"\{(\w+)\}", template)
    seen: set[str] = set()
    result: list[str] = []
    for name in found:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return tuple(result)


def apply_variables(template: str, variables: dict[str, str]) -> str:
    """
    將變數替換進模板。
    variables: {"人物": "sks", "風格": "anime"}
    未提供的變數以空字串取代。
    """
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    result = re.sub(r"\{\w+\}", "", result)
    return result


class DefaultPromptTemplateProvider:
    """內建預設模板，無外部依賴"""

    def __init__(self) -> None:
        raw = [
            ("portrait", "人像基礎", "1girl, {人物}, {風格}, solo"),
            ("portrait-detail", "人像詳述", "1girl, {人物}, {風格}, solo, {細節}"),
            ("character", "角色風格", "{trigger} {人物}, {風格}"),
        ]
        self._templates: list[PromptTemplate] = []
        for tid, name, tpl in raw:
            vars_ = extract_variables(tpl)
            self._templates.append(
                PromptTemplate(id=tid, name=name, template=tpl, variables=vars_)
            )

    def list_all(self) -> list[PromptTemplate]:
        return list(self._templates)

    def get(self, template_id: str) -> PromptTemplate | None:
        for t in self._templates:
            if t.id == template_id:
                return t
        return None


def get_default_provider() -> PromptTemplateProvider:
    """DI 工廠：回傳預設 Provider，便於測試時 override"""
    return DefaultPromptTemplateProvider()
