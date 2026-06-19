"""
ComfyUI 節點 schema API

代理 ComfyUI /object_info，提供「單點查」介面讓 agent 認識本實例實際可用的節點：
- GET /api/comfyui/nodes?query=&category=  依名稱／類別搜尋 node type（回 {name, category}，不含完整 schema）
- GET /api/comfyui/node-categories         列出所有節點類別與數量
- GET /api/comfyui/nodes/{node_type}       取單一 node 的 input/output 規格

供 agent 自組 workflow 時 grounding 用，避免整包 dump /object_info。
契約：openspec/specs/comfyui-node-schema/spec.md
"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.comfyui import (
    ComfyUIClient,
    extract_node_schema,
    get_comfy_client,
    list_node_categories,
    search_node_types,
)

router = APIRouter(prefix="/api/comfyui", tags=["ComfyUI 節點"])


# 搜尋結果預設上限：防止無條件查詢一次回傳全部節點而灌爆 agent context。
# 命中數仍以 total 回報，並以 truncated 提示需縮小條件。
DEFAULT_NODE_SEARCH_LIMIT = 50
MAX_NODE_SEARCH_LIMIT = 200


@router.get("/nodes")
async def search_nodes(
    query: str = "",
    category: str = "",
    limit: int = DEFAULT_NODE_SEARCH_LIMIT,
    offset: int = 0,
    refresh: bool = False,
    comfy: ComfyUIClient = Depends(get_comfy_client),
):
    """依名稱（query）與／或類別（category）搜尋 node type，回 {name, category} 清單。query 與 category 至少要給一個（皆空回 400，避免無條件 dump 全部節點灌爆 context）；先用 /node-categories 瀏覽分類再縮小。每頁上限 limit（預設 50，上限 200）；命中以名稱排序，offset 可翻頁取得後續（next_offset 為下一頁起點）。total 為實際命中數，truncated 表示本頁之後仍有；優先縮小條件，必要時才翻頁。無相符回空清單。"""
    if not query.strip() and not category.strip():
        raise HTTPException(
            400,
            "search_nodes 需要 query 或 category 至少一個；先呼叫 /api/comfyui/node-categories 瀏覽分類再縮小搜尋",
        )
    object_info = comfy.get_object_info(force_refresh=refresh)
    matches = search_node_types(object_info, query, category)
    capped = max(1, min(limit, MAX_NODE_SEARCH_LIMIT))
    start = max(0, offset)
    nodes = matches[start:start + capped]
    has_more = start + len(nodes) < len(matches)
    return {
        "query": query,
        "category": category,
        "nodes": nodes,
        "total": len(matches),
        "offset": start,
        "returned": len(nodes),
        "truncated": has_more,
        "next_offset": start + len(nodes) if has_more else None,
    }


@router.get("/node-categories")
async def get_node_categories(
    refresh: bool = False,
    comfy: ComfyUIClient = Depends(get_comfy_client),
):
    """列出所有節點類別與其節點數量，供 agent 先瀏覽分類再用 category 縮小搜尋。"""
    object_info = comfy.get_object_info(force_refresh=refresh)
    categories = list_node_categories(object_info)
    return {"categories": categories, "total": len(categories)}


@router.get("/nodes/{node_type}")
async def get_node_schema(
    node_type: str,
    refresh: bool = False,
    comfy: ComfyUIClient = Depends(get_comfy_client),
):
    """取單一 node type 的 input/output 規格；本實例不存在則 404。"""
    object_info = comfy.get_object_info(force_refresh=refresh)
    schema = extract_node_schema(object_info, node_type)
    if schema is None:
        raise HTTPException(404, f"ComfyUI node type not found: {node_type}")
    return schema
