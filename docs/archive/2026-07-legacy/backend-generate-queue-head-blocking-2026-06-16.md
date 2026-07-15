# ai-drawing backend 生圖 queue 卡住紀錄（2026-06-16）

## 摘要

OpenClaw / MCP 測試期間，`ai-drawing` backend 的生圖 queue 出現「pending job 長時間不前進」現象。

實際調查後確認：

- 不是 ComfyUI 整體掛掉
- 不是 queue worker 完全沒跑
- 高機率是 **隊首 job 提交失敗後被無限插回 queue 最前面重試**，造成 **head-of-line blocking**，讓後面的 job 永遠排不到

## 觀察到的現象

### 當時 queue 狀態
backend queue 曾出現：

- `3a0bdbe2-4b7b-4bb5-a933-b3a9b7ceb58a`
- `57a16b2a-ff3b-41aa-b776-2a07380a8111`

狀態表現為：

- `/api/generate/queue` 有 `queue_pending`
- `queue_running` 為空
- ComfyUI `/queue` 也是空

這表示 job 停在 backend queue，尚未真正派發到 ComfyUI。

### 關鍵驗證
當人工刪除隊首 job `3a0bdbe2-4b7b-4bb5-a933-b3a9b7ceb58a` 後：

- 後一筆 `57a16b2a-ff3b-41aa-b776-2a07380a8111` 立刻從 `queued` 轉成 `running`
- 並成功取得 ComfyUI `prompt_id`：
  - `a0fa60ad-ba3e-48b0-87b0-dbf92de63258`

這證明：

- queue worker 並非完全失效
- 問題集中在 **隊首 job 堵住後續 job**

## 程式碼層面的可疑根因

檔案：`backend/app/core/queue.py`

### 1. queue 狀態完全在記憶體內

使用模組全域變數：

- `_pending`
- `_running`
- `_worker_thread`
- `_stop_event`

也就是說目前 queue 不是持久化設計，而是 process-local in-memory queue。

### 2. submit 失敗會把 job 插回隊首

關鍵邏輯：

- `queue.py:191-198`：worker 每次從 `_pending` 取最前面的 job
- `queue.py:299-304`：若 `ComfyUIError` 或 `FileNotFoundError`，會把該 job 用 `_pending.insert(0, job)` 插回最前面

也就是：

1. 取出隊首 job
2. 嘗試 submit 到 ComfyUI
3. 若失敗
4. 立刻塞回 queue 最前面
5. 下一輪再重試同一筆

若同一筆永遠失敗，就會形成無限重試 + 隊首阻塞。

## 目前缺口

### 缺少失敗可觀測性
外部 API 目前只能看到：

- `queued`
- `running`
- `completed`

但看不到：

- retry 次數
- last error
- 是否為 repeated submit failure
- 是否正在阻塞後續 job

### 缺少失敗隔離機制
目前沒有：

- retry 上限
- backoff
- failed/dead-letter queue
- 自動跳過壞 job 的策略

### `--reload` 模式增加判讀複雜度
backend 當時以：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

運行，並確認存在 reloader parent + worker child 兩個 Python process。

由於 queue 與 worker thread 都是記憶體內狀態，`--reload` 會讓排錯更難。

雖然這次主要根因仍較像 head-of-line blocking，但 `--reload` 對這種 queue/thread 設計並不友善。

## 這次實際清理過程

1. 成功取消 pending job：
   - `3a0bdbe2-4b7b-4bb5-a933-b3a9b7ceb58a`
2. 第二筆 job 在清理時被 worker 撿起，轉成 running：
   - `57a16b2a-ff3b-41aa-b776-2a07380a8111`
3. 對應 ComfyUI prompt：
   - `a0fa60ad-ba3e-48b0-87b0-dbf92de63258`
4. 之後以 ComfyUI `/interrupt` 中止，最終清空 backend queue 與 ComfyUI queue

## 建議修正方向

### 最低限度先補這些
1. 為 queue job 增加 `retry_count`
2. 為 job 狀態增加 `last_error`
3. 設定 retry 上限（例如 3 次）
4. 超過上限後標記為 `failed`，不要再插回隊首
5. `/api/generate/queue` 或 `/api/generate/job/{job_id}` 暴露更多錯誤資訊

### 更穩定的方向
1. 將 queue 狀態持久化（至少不要完全只靠 process-memory）
2. 將 failed job 與 pending/running 分開管理
3. 開發/排錯時避免用 `uvicorn --reload` 驗證 queue thread 行為

## 這次調查的結論

這不是「ComfyUI 很慢」或「OpenClaw session 卡住」而已。

更精確的說法是：

> `ai-drawing` backend 的 queue worker 對 submit failure 的處理方式，可能造成壞 job 無限佔據隊首，進而讓後續 job 看起來永遠 pending。

這個問題屬於 queue failure-handling 設計缺口，建議優先修。