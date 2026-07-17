"""
Prompt 模板庫（Phase 5b）
儲存常用 prompt 組合，支援變數替換（人物名稱、風格等）
契約：docs/api-contract.md 模組 5
"""
import re
from dataclasses import dataclass
from typing import Protocol

from app.core.prompt_library import (
    PromptLibraryProvider,
    get_default_prompt_library_provider,
)
from app.core.prompt_library_models import PromptCombination


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
    """將 Prompt Library 中標記為 legacy 的組合轉為舊版模板。"""

    def __init__(self, prompt_library: PromptLibraryProvider | None = None) -> None:
        self.prompt_library = prompt_library or get_default_prompt_library_provider()

    def list_all(self) -> list[PromptTemplate]:
        combinations = self.prompt_library.catalog().combinations
        return sorted(
            (
                self._to_template(
                    self.prompt_library.get_combination(item.id).combination
                )
                for item in combinations
                if item.legacy_template and not item.archived
            ),
            key=lambda item: item.id,
        )

    def get(self, template_id: str) -> PromptTemplate | None:
        return next((item for item in self.list_all() if item.id == template_id), None)

    @staticmethod
    def _to_template(combination: PromptCombination) -> PromptTemplate:
        text = combination.positive_prompt_snapshot
        return PromptTemplate(
            id=combination.id,
            name=combination.name_zh,
            template=text,
            variables=extract_variables(text),
        )


def get_default_provider() -> PromptTemplateProvider:
    """DI 工廠：回傳預設 Provider，便於測試時 override"""
    return DefaultPromptTemplateProvider()
