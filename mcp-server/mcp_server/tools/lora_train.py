"""
LoRA 訓練 MCP Tools

對應：POST /api/lora-train/start、GET /api/lora-train/status
"""
from mcp_server.server import _get_client, mcp


@mcp.tool()
def lora_train_start(
    folder: str,
    checkpoint: str | None = None,
    epochs: int | None = None,
) -> str:
    """手動觸發 LoRA 訓練。folder 為必填（相對於 lora_train_dir），checkpoint、epochs 可選。"""
    try:
        client = _get_client()
        body = {"folder": folder}
        if checkpoint:
            body["checkpoint"] = checkpoint
        if epochs is not None:
            body["epochs"] = epochs
        resp = client.post("lora-train/start", json=body)
        job_id = resp.get("job_id", "unknown")
        return f"已加入訓練佇列: job_id={job_id}"
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def lora_train_status() -> str:
    """取得 LoRA 訓練進度與佇列狀態。"""
    try:
        client = _get_client()
        resp = client.get("lora-train/status")
        status = resp.get("status", "unknown")
        current = resp.get("current_job")
        queue = resp.get("queue", [])
        lines = [f"狀態: {status}"]
        if current:
            lines.append(
                f"目前任務: {current.get('folder', '?')} - "
                f"epoch {current.get('epoch', '?')}/{current.get('total_epochs', '?')} "
                f"(progress {current.get('progress', 0):.0%})"
            )
        if queue:
            lines.append(f"等候中: {len(queue)} 筆")
            for q in queue:
                lines.append(f"  - {q.get('folder', '?')}")
        return "\n".join(lines) if lines else "無訓練任務"
    except Exception as e:
        return f"error: {e}"
