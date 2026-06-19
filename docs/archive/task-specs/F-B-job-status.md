# F-B：Job 狀態查詢

**功能**：agent 提交生圖後可用 job_id 查詢狀態（queued / running / completed），completed 時能取得圖片 DB id。

**完成定義**：呼叫 `get_job_status(job_id)` MCP tool 回傳當前狀態；job 完成後仍可查詢（DB 有 job_id 欄位）。

---

## 現況確認

- `queue.get_job_status(job_id)` 函式已存在，但只查 in-memory（running / pending），job 完成後即消失
- `GeneratedImage` model 沒有 `job_id` 欄位，無法從 DB 查已完成的 job
- 沒有 API endpoint 暴露單一 job 查詢
- 沒有 MCP tool

---

## Steps

### Step 1：DB 加 job_id 欄位
**檔案**：`backend/app/db/models.py`

`GeneratedImage` 加：
```python
job_id = Column(String(64), nullable=True, index=True)
```

執行 migration（或刪 DB 重建）：
```bash
python backend/scripts/init_db.py
```

**Verify**：`GeneratedImage.__table__.columns` 含 `job_id`。

### Step 2：recording.save() 接受 job_id
**檔案**：`backend/app/core/recording.py`

`save()` 函式簽名補 `job_id: str | None = None`，寫入時帶入：
```python
record = GeneratedImage(..., job_id=job_id)
```

**Verify**：`recording.save("path.png", job_id="test-id")` → DB 查 `job_id == "test-id"` 可找到該記錄。

### Step 3：queue 完成時傳入 job_id
**檔案**：`backend/app/core/queue.py`

`_check_running_complete()` 呼叫 `recording_save(...)` 時補傳 `job_id=job.job_id`。

**Verify**：完整生圖後，DB `generated_images` 表中該記錄的 `job_id` 欄位有值。

### Step 4：API endpoint
**檔案**：`backend/app/api/generate.py`

新增：
```python
@router.get("/job/{job_id}")
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
```

邏輯：
1. 先查 in-memory queue（`queue.get_job_status(job_id)`）→ 若有，回傳 `{status: "running"/"queued", job_id}`
2. 再查 DB（`db.query(GeneratedImage).filter_by(job_id=job_id).first()`）→ 若有，回傳 `{status: "completed", image_id, job_id}`
3. 都沒有 → 404

**Verify**：
```bash
curl -X POST http://localhost:8000/api/generate/ -d '{"prompt":"test"}'
# 取得 job_id
curl http://localhost:8000/api/generate/job/{job_id}
# 回傳 {"status": "queued"/"running"/"completed", "job_id": "..."}
```

### Step 5：MCP tool
**檔案**：`mcp-server/mcp_server/tools/generate.py`

新增：
```python
@mcp.tool()
def get_job_status(job_id: str) -> str:
    """查詢生圖 job 狀態（queued / running / completed）。completed 時回傳 image_id 可用 gallery_detail 查看結果。"""
```
呼叫 `GET /api/generate/job/{job_id}`。

**Verify**：`uv run pytest tests/ -k job_status`

---

## End-to-End Verify

```bash
# 1. 提交 job
# 2. get_job_status(job_id) → {"status": "queued"}
# 3. 等完成後
# 4. get_job_status(job_id) → {"status": "completed", "image_id": 42}
# 5. gallery_detail(42) → 看到圖片參數
```
