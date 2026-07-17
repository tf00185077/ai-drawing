"""Prompt 模板庫單元測試"""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.prompt_templates import (
    DefaultPromptTemplateProvider,
    apply_variables,
    extract_variables,
)
from app.core.prompt_library import FilePromptLibraryProvider
from app.main import app
from app.api import prompt_templates as prompt_templates_api


class TestExtractVariables:
    """extract_variables 純函數測試"""

    def test_extracts_unique_variables_preserving_order(self) -> None:
        """萃取變數、去重、保留首次出現順序"""
        assert extract_variables("1girl, {人物}, {風格}, solo") == ("人物", "風格")
        assert extract_variables("{a} {b} {a}") == ("a", "b")

    def test_empty_template_returns_empty_tuple(self) -> None:
        """無變數時回傳空 tuple"""
        assert extract_variables("1girl, solo") == ()
        assert extract_variables("") == ()


class TestApplyVariables:
    """apply_variables 純函數測試"""

    def test_replaces_provided_variables(self) -> None:
        """替換已提供的變數"""
        tpl = "1girl, {人物}, {風格}, solo"
        assert apply_variables(tpl, {"人物": "sks", "風格": "anime"}) == "1girl, sks, anime, solo"

    def test_missing_variables_replaced_with_empty(self) -> None:
        """未提供的變數以空字串取代"""
        tpl = "1girl, {人物}, solo"
        assert apply_variables(tpl, {}) == "1girl, , solo"
        assert apply_variables(tpl, {"風格": "anime"}) == "1girl, , solo"


@pytest.fixture
def tmp_prompt_library(tmp_path: Path) -> FilePromptLibraryProvider:
    source = Path(__file__).resolve().parents[2] / "prompt_library"
    root = tmp_path / "prompt_library"
    shutil.copytree(source, root)
    ordinary = json.loads(
        (root / "combinations" / "portrait.json").read_text(encoding="utf-8")
    )
    ordinary.update(
        id="ordinary-combination",
        name_zh="一般組合",
        description_zh="不提供給舊版 API",
        legacy_template=False,
    )
    (root / "combinations" / "ordinary-combination.json").write_text(
        json.dumps(ordinary, ensure_ascii=False), encoding="utf-8"
    )
    return FilePromptLibraryProvider(root)


class TestDefaultProvider:
    """DefaultPromptTemplateProvider 測試"""

    def test_legacy_provider_lists_only_flagged_combinations(
        self, tmp_prompt_library: FilePromptLibraryProvider
    ) -> None:
        provider = DefaultPromptTemplateProvider(prompt_library=tmp_prompt_library)
        ids = [item.id for item in provider.list_all()]
        assert ids == ["character", "portrait", "portrait-detail"]
        assert "ordinary-combination" not in ids

    def test_legacy_provider_reflects_external_combination_correction(
        self, tmp_prompt_library: FilePromptLibraryProvider
    ) -> None:
        provider = DefaultPromptTemplateProvider(prompt_library=tmp_prompt_library)
        path = tmp_prompt_library.root / "combinations" / "portrait.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        corrected = "1person, {人物}, {風格}, solo"
        document["positive"][0]["snapshot"] = corrected
        document["positive_prompt_snapshot"] = corrected
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        assert provider.get("portrait").template == corrected

    def test_get_returns_template_by_id(
        self, tmp_prompt_library: FilePromptLibraryProvider
    ) -> None:
        """get 依 id 回傳模板"""
        provider = DefaultPromptTemplateProvider(prompt_library=tmp_prompt_library)
        t = provider.get("portrait")
        assert t is not None
        assert t.id == "portrait"
        assert "人物" in t.variables or "風格" in t.variables
        assert provider.get("nonexistent") is None


class TestPromptTemplatesAPI:
    """API 端點測試"""

    def test_list_templates_returns_200(self) -> None:
        """GET /api/prompt-templates/ 回傳 200"""
        client = TestClient(app)
        res = client.get("/api/prompt-templates/")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_apply_returns_rendered_prompt(self) -> None:
        """POST /api/prompt-templates/apply 回傳替換後的 prompt"""
        client = TestClient(app)
        res = client.post(
            "/api/prompt-templates/apply",
            json={"template_id": "portrait", "variables": {"人物": "sks", "風格": "anime"}},
        )
        assert res.status_code == 200
        data = res.json()
        assert "prompt" in data
        assert "sks" in data["prompt"] and "anime" in data["prompt"]

    def test_apply_404_for_unknown_template(self) -> None:
        """POST apply 對不存在的 template_id 回傳 404"""
        client = TestClient(app)
        res = client.post(
            "/api/prompt-templates/apply",
            json={"template_id": "nonexistent", "variables": {}},
        )
        assert res.status_code == 404

    def test_underlying_prompt_library_dependency_can_be_overridden(
        self, tmp_prompt_library: FilePromptLibraryProvider
    ) -> None:
        app.dependency_overrides[prompt_templates_api._prompt_library_provider] = (
            lambda: tmp_prompt_library
        )
        try:
            response = TestClient(app).get("/api/prompt-templates/")
        finally:
            app.dependency_overrides.pop(
                prompt_templates_api._prompt_library_provider, None
            )
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == [
            "character",
            "portrait",
            "portrait-detail",
        ]
