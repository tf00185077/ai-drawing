"""Intent-level Prompt Library MCP tools."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote
import httpx

from mcp_server.server import _get_client, mcp


_CJK = re.compile(r"[㐀-䶿一-鿿]")


def _has_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))


def _norm(text: str) -> str:
    return " ".join((text or "").split()).casefold()


def _bilingual_warnings(resource_type: str, payload: dict) -> list[dict[str, Any]]:
    """偵測 name_zh 是否缺少有意義中文對照；只回 warning，永不擋。"""
    name_zh = str(payload.get("name_zh", ""))
    prompt = str(payload.get("prompt", ""))
    if resource_type == "entry" and prompt and _norm(name_zh) == _norm(prompt):
        return [{"code": "name_zh_echoes_prompt", "message": "name_zh 只是照抄英文 prompt", "hint": "建議填實際中文意思，方便日後用中文檢索", "details": {"name_zh": name_zh}}]
    if not _has_cjk(name_zh):
        return [{"code": "name_zh_missing_chinese", "message": "name_zh 看起來沒有中文對照", "hint": "建議補上中文翻譯，方便日後用中文檢索", "details": {"name_zh": name_zh}}]
    return []


def _error(tool: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        try: body = exc.response.json()
        except ValueError: body = {}
        detail = body.get("detail", body) if isinstance(body, dict) else {}
        if not isinstance(detail, dict): detail = {"message": str(detail)}
        return {"ok": False, "tool": tool, "error": {"code": str(detail.get("code", "backend_http_error")), "message": str(detail.get("message", exc)), "hint": str(detail.get("hint", "Reload, correct the request, and retry.")), "details": detail.get("details", {})}, "status_code": exc.response.status_code}
    return {"ok": False, "tool": tool, "error": {"code": exc.__class__.__name__, "message": str(exc), "hint": "Confirm the backend is running, then retry.", "details": {"where": "backend"}}}


def _locator(resource_type: str, resource_id: str, polarity: str | None, category_id: str | None) -> tuple[str | None, dict | None]:
    q = lambda value: quote(str(value), safe="")
    if resource_type == "category" and polarity:
        return f"prompt-library/categories/{q(polarity)}/{q(resource_id)}", None
    if resource_type == "entry" and polarity and category_id:
        return f"prompt-library/categories/{q(polarity)}/{q(category_id)}/entries/{q(resource_id)}", None
    if resource_type == "combination" and not polarity and not category_id:
        return f"prompt-library/combinations/{q(resource_id)}", None
    return None, {"ok": False, "error": {"code": "invalid_resource_locator", "message": "resource locator is incomplete", "hint": "category needs polarity; entry needs polarity and category_id; combination needs only resource_id", "details": {}}}


@mcp.tool()
def prompt_library_search(query: str = "", polarity: str | None = None, resource_types: list[str] | None = None, category_id: str | None = None, threshold: int = 45, limit: int = 50, include_archived: bool = False) -> dict[str, Any]:
    tool = "prompt_library_search"
    try:
        client = _get_client(); query = query.strip()
        if not query and category_id:
            if not polarity: return {"ok": False, "tool": tool, "error": {"code": "invalid_resource_locator", "message": "polarity is required", "hint": "provide positive or negative", "details": {}}}
            response = client.get(f"prompt-library/categories/{quote(polarity, safe='')}/{quote(category_id, safe='')}")
        elif not query:
            response = client.get("prompt-library/catalog")
        else:
            params: dict[str, Any] = {"q": query, "threshold": threshold, "limit": limit, "include_archived": include_archived}
            if polarity: params["polarity"] = polarity
            if resource_types: params["resource_types"] = resource_types
            if category_id: params["category_id"] = category_id
            response = client.get("prompt-library/search", params=params)
        return {"ok": True, "tool": tool, **response, "next": "compose selected entry refs or inspect diagnostics"}
    except Exception as exc: return _error(tool, exc)


@mcp.tool()
def prompt_library_save(resource_type: str, resource_id: str, payload: dict, expected_revision: int = 0, expected_etag: str | None = None, polarity: str | None = None, category_id: str | None = None) -> dict[str, Any]:
    """建立或更新 Prompt Library 的 entry／category／combination。

    payload 內的 name_zh 必須是英文 prompt 的「有意義中文對照」（翻譯或說明），
    不是照抄英文、也不是機械拼接——這是給中文使用者日後用中文檢索、回想此詞
    用途的依據。若 name_zh 沒填好，本工具仍會照常儲存，但回傳 warnings 提示補件。
    """
    tool = "prompt_library_save"; path, problem = _locator(resource_type, resource_id, polarity, category_id)
    if problem: return {"tool": tool, **problem}
    body = dict(payload); body.pop("expected_revision", None); body.pop("expected_etag", None); body["expected_revision"] = expected_revision
    if expected_etag is not None: body["expected_etag"] = expected_etag
    try:
        result = {"ok": True, "tool": tool, **_get_client().put(path, json=body), "next": "reload the resource and use its new revision and etag"}
        warnings = _bilingual_warnings(resource_type, payload)
        if warnings: result["warnings"] = warnings
        return result
    except Exception as exc: return _error(tool, exc)


@mcp.tool()
def prompt_library_compose(combination_id: str | None = None, positive: list[dict] | None = None, negative: list[dict] | None = None, save_as: dict | None = None) -> dict[str, Any]:
    tool = "prompt_library_compose"; body: dict[str, Any] = {"positive": positive or [], "negative": negative or []}
    if combination_id: body["combination_id"] = combination_id
    if save_as: body["save_as"] = save_as
    try:
        response = _get_client().post("prompt-library/compose", json=body)
        return {"ok": True, "tool": tool, **response, "generation": {"prompt": response.get("positive_prompt", ""), "negative_prompt": response.get("negative_prompt", "")}, "next": "call generate_image with generation"}
    except Exception as exc: return _error(tool, exc)


@mcp.tool()
def prompt_library_archive(resource_type: str, resource_id: str, expected_revision: int, expected_etag: str, polarity: str | None = None, category_id: str | None = None) -> dict[str, Any]:
    tool = "prompt_library_archive"; _, problem = _locator(resource_type, resource_id, polarity, category_id)
    if problem: return {"tool": tool, **problem}
    body = {"resource_type": resource_type, "resource_id": resource_id, "expected_revision": expected_revision, "expected_etag": expected_etag}
    if polarity: body["polarity"] = polarity
    if category_id: body["category_id"] = category_id
    try: return {"ok": True, "tool": tool, **_get_client().post("prompt-library/archive", json=body), "next": "reload catalog"}
    except Exception as exc: return _error(tool, exc)
