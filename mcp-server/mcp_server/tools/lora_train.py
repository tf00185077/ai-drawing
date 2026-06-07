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
    class_tokens: str | None = None,
    resolution: int | None = None,
    keep_tokens: int | None = None,
    mixed_precision: str | None = None,   # fp16 | bf16 | fp32
    network_dim: int | None = None,
    network_alpha: int | None = None,
    num_repeats: int | None = None,
    learning_rate: str | None = None,
) -> str:
    """手動觸發 LoRA 訓練。folder 為必填。訓練完成後請另行呼叫 generate_image 使用新 LoRA。"""
    try:
        client = _get_client()
        body = {"folder": folder}
        if checkpoint:
            body["checkpoint"] = checkpoint
        if epochs is not None:
            body["epochs"] = epochs
        if class_tokens:
            body["class_tokens"] = class_tokens.strip()
        if resolution is not None:
            body["resolution"] = resolution
        if keep_tokens is not None:
            body["keep_tokens"] = keep_tokens
        if mixed_precision:
            body["mixed_precision"] = mixed_precision
        if network_dim is not None:
            body["network_dim"] = network_dim
        if network_alpha is not None:
            body["network_alpha"] = network_alpha
        if num_repeats is not None:
            body["num_repeats"] = num_repeats
        if learning_rate:
            body["learning_rate"] = learning_rate
        resp = client.post("lora-train/start", json=body)
        job_id = resp.get("job_id", "unknown")
        return f"已加入訓練佇列: job_id={job_id}"
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def lora_train_status() -> str:
    """取得 LoRA 訓練進度與佇列狀態。idle 時顯示上次訓練結果（成功則含輸出 LoRA 路徑）。"""
    try:
        client = _get_client()
        resp = client.get("lora-train/status")
        status = resp.get("status", "unknown")
        current = resp.get("current_job")
        queue = resp.get("queue", [])
        last = resp.get("last_result")
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
        if last and status == "idle":
            if last.get("success"):
                path = last.get("path", "")
                name = path.split("\\")[-1].split("/")[-1] if path else "?"
                lines.append(f"上次完成: {last.get('folder', '?')} → LoRA: {name}")
            else:
                lines.append(f"上次失敗: {last.get('folder', '?')} - {last.get('error', '')[:80]}")
        return "\n".join(lines) if lines else "無訓練任務"
    except Exception as e:
        return f"error: {e}"
