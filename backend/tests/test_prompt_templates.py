"""Prompt 模板庫單元測試"""
import pytest
from fastapi.testclient import TestClient

from app.core.prompt_templates import (
    DefaultPromptTemplateProvider,
    apply_variables,
    extract_variables,
)
from app.main import app


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


class TestDefaultProvider:
    """DefaultPromptTemplateProvider 測試"""

    def test_list_all_returns_builtin_templates(self) -> None:
        """list_all 回傳內建模板"""
        provider = DefaultPromptTemplateProvider()
        templates = provider.list_all()
        assert len(templates) >= 1
        assert all(t.id and t.name and t.template for t in templates)

    def test_get_returns_template_by_id(self) -> None:
        """get 依 id 回傳模板"""
        provider = DefaultPromptTemplateProvider()
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
