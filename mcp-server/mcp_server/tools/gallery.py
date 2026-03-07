"""
圖庫 MCP Tools

對應：GET /api/gallery/、GET /api/gallery/{id}、POST /api/gallery/{id}/rerun
"""
from mcp_server.server import _get_client, mcp


@mcp.tool()
def gallery_list(
    checkpoint: str | None = None,
    lora: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> str:
    """取得圖庫列表，支援篩選 checkpoint、lora、日期範圍。"""
    try:
        client = _get_client()
        params = {"limit": limit, "offset": offset}
        if checkpoint:
            params["checkpoint"] = checkpoint
        if lora:
            params["lora"] = lora
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        resp = client.get("gallery/", params=params)
        items = resp.get("items", [])
        total = resp.get("total", 0)
        if not items:
            return f"共 {total} 筆，無符合條件的圖片"
        lines = [f"共 {total} 筆，顯示 {len(items)} 筆:"]
        for it in items[:10]:  # 最多列 10 筆
            lines.append(
                f"  id={it.get('id')} | {it.get('prompt', '')[:50]}... | {it.get('created_at', '')}"
            )
        if len(items) > 10:
            lines.append("  ...")
        return "\n".join(lines)
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def gallery_detail(image_id: int) -> str:
    """取得單張圖片的完整參數（checkpoint、lora、prompt、seed 等）。"""
    try:
        client = _get_client()
        resp = client.get(f"gallery/{image_id}")
        lines = [
            f"id: {resp.get('id')}",
            f"prompt: {resp.get('prompt', '')}",
            f"negative_prompt: {resp.get('negative_prompt', '')}",
            f"checkpoint: {resp.get('checkpoint', '')}",
            f"lora: {resp.get('lora', '')}",
            f"seed: {resp.get('seed')}",
            f"steps: {resp.get('steps')}",
            f"cfg: {resp.get('cfg')}",
            f"created_at: {resp.get('created_at')}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def gallery_rerun(image_id: int) -> str:
    """一鍵重現：載入該圖參數再次生成，回傳 job_id。"""
    try:
        client = _get_client()
        resp = client.post(f"gallery/{image_id}/rerun")
        job_id = resp.get("job_id", "unknown")
        return f"已加入生圖佇列: job_id={job_id}"
    except Exception as e:
        return f"error: {e}"
