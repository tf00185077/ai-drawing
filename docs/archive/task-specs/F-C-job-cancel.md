# F-C：Job 取消

**功能**：agent 可取消尚未執行的 pending job。

**完成定義**：呼叫 `cancel_job(job_id)` MCP tool 後，該 job 從 pending 佇列移除，不再被處理。

**限制**：只能取消 pending 狀態的 job。running 中的 job（已送至 ComfyUI）不支援取消。

---

## 現況確認

- `queue.py` 沒有 cancel 函式
- 沒有 API endpoint
- 沒有 MCP tool

---

## Steps

### Step 1：queue 加 cancel 函式
**檔案**：`backend/app/core/queue.py`

新增：
```python
def cancel(job_id: str) -> bool:
    """
    取消 pending 中的 job。
    Returns:
        True: 取消成功
        False: 找不到（不在 pending 中）
    Raises:
        ValueError: job 正在執行中（running），無法取消
    """
    with _lock:
        if _running and _running.job_id == job_id:
            raise ValueError(f"Job {job_id} 正在執行中，無法取消")
        for i, j in enumerate(_pending):
            if j.job_id == job_id:
                _pending.pop(i)
                return True
    return False
```

**Verify**：
```python
job_id = submit({"prompt": "test"})
assert cancel(job_id) == True
assert get_job_status(job_id) is None
```

### Step 2：API endpoint
**檔案**：`backend/app/api/generate.py`

新增：
```python
@router.delete("/queue/{job_id}", status_code=200)
async def cancel_job(job_id: str):
    """取消 pending 中的生圖 job"""
```

邏輯：
- 呼叫 `queue.cancel(job_id)`
- `True` → `{"message": "已取消", "job_id": job_id}`
- `False` (找不到) → 404
- `ValueError` (running 中) → 409 `{"detail": "job 正在執行中，無法取消"}`

**Verify**：
```bash
curl -X POST http://localhost:8000/api/generate/ -d '{"prompt":"test"}'
# 取得 job_id
curl -X DELETE http://localhost:8000/api/generate/queue/{job_id}
# 200 {"message": "已取消"}
```

### Step 3：MCP tool
**檔案**：`mcp-server/mcp_server/tools/generate.py`

新增：
```python
@mcp.tool()
def cancel_job(job_id: str) -> str:
    """取消尚未執行的生圖 job（pending 狀態）。執行中的 job 無法取消。"""
```
呼叫 `DELETE /api/generate/queue/{job_id}`。

**Verify**：`uv run pytest tests/ -k cancel`

---

## End-to-End Verify

```bash
# 1. 提交 job → 取得 job_id
# 2. cancel_job(job_id) → "已取消"
# 3. generate_queue_status() → pending 清單中不再有該 job
# 4. 嘗試取消不存在的 job → "找不到該 job"
# 5. 嘗試取消 running job → "job 正在執行中，無法取消"
```
