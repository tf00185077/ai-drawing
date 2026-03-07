"""
生圖 MCP Tools

對應：POST /api/generate/、GET /api/generate/queue
"""
from mcp_server.server import _get_client, mcp


@mcp.tool()
def generate_image(
    prompt: str,
    checkpoint: str | None = None,
    lora: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
) -> str:
    """觸發圖片生成。prompt 為必填，其他參數可選。回傳 job_id 或錯誤訊息。"""
    try:
        client = _get_client()
        body = {"prompt": prompt}
        if checkpoint:
            body["checkpoint"] = checkpoint
        if lora:
            body["lora"] = lora
        if negative_prompt is not None:
            body["negative_prompt"] = negative_prompt
        if seed is not None:
            body["seed"] = seed
        if steps is not None:
            body["steps"] = steps
        if cfg is not None:
            body["cfg"] = cfg
        resp = client.post("generate/", json=body)
        job_id = resp.get("job_id", "unknown")
        status = resp.get("status", "queued")
        return f"已加入生圖佇列: job_id={job_id}, status={status}"
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def generate_queue_status() -> str:
    """取得生圖佇列狀態（執行中與等候中的任務）。"""
    try:
        client = _get_client()
        resp = client.get("generate/queue")
        running = resp.get("queue_running", [])
        pending = resp.get("queue_pending", [])
        lines = [
            f"執行中: {len(running)} 筆",
            *[f"  - {r.get('job_id', '?')}: {r.get('status', '?')}" for r in running],
            f"等候中: {len(pending)} 筆",
            *[f"  - {p.get('job_id', '?')}: {p.get('status', '?')}" for p in pending],
        ]
        return "\n".join(lines) if lines else "佇列為空"
    except Exception as e:
        return f"error: {e}"
