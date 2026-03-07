"""
生圖 MCP Tools

對應：POST /api/generate/、GET /api/generate/queue
支援角色與風格語意對應（character_style）。
"""
from mcp_server.character_style import resolve_to_prompt
from mcp_server.server import _get_client, mcp


@mcp.tool()
def generate_image(
    prompt: str = "1girl, solo",
    character: str | None = None,
    style: str | None = None,
    checkpoint: str | None = None,
    lora: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
) -> str:
    """觸發圖片生成。可用 character、style 自然語言描述（如「初音」「動漫」），或直接給 prompt。回傳 job_id 或錯誤訊息。"""
    try:
        client = _get_client()
        final_prompt = prompt
        resolved_lora = lora

        if character or style:
            base = prompt if prompt else "1girl, solo"
            final_prompt, style_lora = resolve_to_prompt(
                character=character, style=style, base_prompt=base
            )
            if style_lora and not resolved_lora:
                resolved_lora = style_lora

        body = {"prompt": final_prompt}
        if checkpoint:
            body["checkpoint"] = checkpoint
        if resolved_lora:
            body["lora"] = resolved_lora
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
