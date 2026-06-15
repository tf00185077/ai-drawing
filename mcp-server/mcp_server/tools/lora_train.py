"""
LoRA Training MCP Tools

Corresponds to: POST /api/lora-train/start, GET /api/lora-train/status
"""
from mcp_server.server import _get_client, mcp


@mcp.tool()
def caption_image(image_path: str) -> str:
    """Call LLM to auto-generate a caption for an image in the training folder and write it to a same-named .txt file. image_path is relative to lora_train_dir, e.g. "character/miku/img1.png". Returns the generated caption text."""
    try:
        client = _get_client()
        resp = client.post(f"lora-docs/caption-llm/{image_path}")
        caption_text = resp.get("content", "")
        if not caption_text:
            return "error: LLM 回傳空 caption"
        return caption_text
    except Exception as e:
        return f"error: {e}"


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
    """Manually trigger LoRA training. folder is required. After training completes, call generate_image separately to use the new LoRA."""
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
    """Get LoRA training progress and queue status. When idle, shows the last training result (including the output LoRA path on success)."""
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
