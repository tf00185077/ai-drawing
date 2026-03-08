"""
生圖 MCP Tools

對應：POST /api/generate/、GET /api/generate/queue、POST /api/generate/custom
支援角色與風格語意對應（character_style）。
支援自訂 workflow，可由 AI 根據使用者描述動態產生。
"""
import json

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
def list_workflow_templates() -> str:
    """列出可用的 workflow 模板名稱。AI 可依使用者描述選擇模板，再呼叫 get_workflow_template 取得 JSON。"""
    try:
        client = _get_client()
        resp = client.get("generate/workflow-templates")
        templates = resp.get("templates", [])
        if not templates:
            return "目前無 workflow 模板"
        return "可用模板: " + ", ".join(templates)
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def get_workflow_template(template_name: str) -> str:
    """取得指定 workflow 模板的完整 JSON。回傳 JSON 字串，可傳入 generate_image_custom_workflow 的 workflow 參數。"""
    try:
        client = _get_client()
        workflow = client.get(f"generate/workflow-templates/{template_name}")
        return json.dumps(workflow, ensure_ascii=False)
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def generate_image_custom_workflow(
    workflow: str,
    prompt: str = "1girl, solo",
    character: str | None = None,
    style: str | None = None,
    checkpoint: str | None = None,
    lora: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """
    使用自訂 workflow 觸發圖片生成。AI 可根據使用者描述：
    1. 先呼叫 list_workflow_templates 看有哪些模板
    2. 呼叫 get_workflow_template(name) 取得 JSON
    3. 可選：修改 workflow JSON（如調整節點、參數）
    4. 傳入此 tool，workflow 為 JSON 字串；prompt/character/style 會套用至 workflow
    """
    try:
        client = _get_client()
        wf_obj = json.loads(workflow)
        final_prompt = prompt
        resolved_lora = lora
        if character or style:
            base = prompt if prompt else "1girl, solo"
            final_prompt, style_lora = resolve_to_prompt(
                character=character, style=style, base_prompt=base
            )
            if style_lora and not resolved_lora:
                resolved_lora = style_lora
        body = {
            "workflow": wf_obj,
            "prompt": final_prompt,
        }
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
        if width is not None:
            body["width"] = width
        if height is not None:
            body["height"] = height
        resp = client.post("generate/custom", json=body)
        job_id = resp.get("job_id", "unknown")
        status = resp.get("status", "queued")
        return f"已加入生圖佇列（自訂 workflow）: job_id={job_id}, status={status}"
    except json.JSONDecodeError as e:
        return f"error: workflow 必須為合法 JSON: {e}"
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
