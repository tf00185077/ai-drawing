# Discord MiniMax H3 Argus MLX I2V Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 只將 Discord `/minimax_h3_i2v` 與既有 `POST /api/generate/video/minimax-h3-i2v` 改接本機 Argus MiniMax H3 Apple MLX I2V；保留既有 queue/job/`GeneratedArtifact`/`/result` 契約，且 `/animegen_i2v`、`/wan22_animate`、ComfyUI 與 Windows Worker 行為不變。

**Architecture:** FastAPI 驗證並安全 staging 圖片後，以 `execution_engine="argus_mlx_i2v"` 將 server-owned payload 放進現有 in-memory generation queue。Queue worker 先依 engine 分流；Argus 分支同步呼叫 Backend-owned `ArgusMlxI2VRunner`，以無 shell argv 啟動獨立 process group、在外接碟 job work dir 產生並驗證 muxed MP4，成功才 atomic move 至 Gallery 並寫入 `GeneratedArtifact(source_node_type="SaveVideo")`。Discord Bot 維持兩階段 UI，但 H3 指令固定 Mac MLX、modal 只送 prompt/1–5 秒；其他生成指令仍保留 execution target。

**Tech Stack:** Python 3.11 Backend/FastAPI/Pydantic/SQLAlchemy、Python 3.11 Discord Bot/discord.py/httpx、Argus PR #4 Python 3.12 MLX runtime、`subprocess.Popen`、ffprobe/ffmpeg、pytest/pytest-asyncio。

---

## 實作前固定事實與全域約束

- 核准設計：`docs/superpowers/specs/2026-09-01-discord-minimax-h3-argus-mlx-i2v-design.md`。
- 現有 queue 是 `backend/app/core/queue.py` 的單一 `_pending`/`_running`/worker thread；completed 狀態由 DB artifact 推導，不另建 durable running-job migration。
- 現有 artifact 寫入介面是 `app.core.recording.save_artifact(...)`；`GET /api/generate/job/{job_id}` 已序列化 `GeneratedArtifact`，Discord `collect_job_result()` 已接受 `SaveVideo`。
- 現有 H3 fixed-video 修改尚未提交，且目標檔案與本計畫高度重疊。開始每個 Task 前執行 `git status --short` 及 `git diff -- <本 Task 檔案>`；不得 stash、reset、checkout、restore、revert 或刪除既有 dirty work。
- 規劃時已存在的 dirty set 至少包括 `backend/app/api/generate.py`、`backend/app/core/fixed_video_workflows.py`、`backend/app/core/queue.py`、fixed-video Backend/Discord 測試與 Bot 的 `api_client.py/main.py/validation.py/views.py`；另有 untracked `backend/workflows/discord_minimax_h3_i2v_fixed.json`、`backend/tests/test_film_audio_mux.py`、`scripts/tmux-services.sh`。後三者不得因本功能被刪除、覆寫或順手加入 commit。
- 每個 commit 都先用 `git diff --cached --name-only` 與 `git diff --cached` 查核；重疊 dirty 檔案只用 `git add -p -- <paths>` 選取本 Task 新增 hunks。絕不使用 `git add .`、`git add -A` 或整包 `git commit -a`。
- 本計畫中的 commit 是實作者逐 Task 的 TDD checkpoint；撰寫本計畫本身不 commit、不 push。若使用者當次執行指示仍禁止 commit，則保留同一個 staging/diff 自檢步驟並略過實際 `git commit`，不得自行放寬禁令。
- H3 不回退 PyTorch/MPS、ComfyUI、Windows Worker；Argus 失敗就是 job failed。
- H3 prompt 上限固定 4000 字元（與 Discord TextInput 相同）；附件上限沿用 20 MiB；尺寸 256–1024、32 倍數且 `width * height <= 786432`；秒數只接受整數 1–5。
- 時序唯一公式：`requested_frames = round(total_seconds * 24)`，`native_frames = requested_frames + ((5 - requested_frames) % 17)`，`timeline_span_seconds=(native_frames-1)/24`，`container_duration_seconds=native_frames/24`。
- Public API 不接受 64×64（最小 256×256）。因此 live 驗證分成「runner 64×64 integration smoke」與「public API 256×256 E2E」；不得為 smoke 加隱藏 API bypass。這是對核准設計中「64×64 API smoke」與 public validation 互斥之處的 fail-closed 落地。

## 固定設定與 Argus argv 契約

`Settings` 新欄位及預設值如下，均可用同名大寫環境變數覆寫：

- `argus_mlx_runtime_root=/Volumes/AI-Drawing-16T/ai-drawing/runtimes/minimax-h3-mac-pr4`
- `argus_mlx_python=/Volumes/AI-Drawing-16T/ai-drawing/runtimes/minimax-h3-mac-pr4/.venv/bin/python`
- `argus_mlx_generate_script=/Volumes/AI-Drawing-16T/ai-drawing/runtimes/minimax-h3-mac-pr4/scripts/generate.py`
- `argus_mlx_checkpoint=/Volumes/AI-Drawing-16T/ai-drawing/models/minimax_h3_mlx/MiniMax-H3/FL2VA`
- `argus_mlx_transformer=/Volumes/AI-Drawing-16T/ai-drawing/models/minimax_h3_mlx/MiniMax-H3-MLX-Argus-Calibrated-INT8`
- `argus_mlx_turbo_lora=/Volumes/AI-Drawing-16T/ai-drawing/models/minimax_h3_mlx/MiniMax-H3-Turbo-v4-step600-EMA-MLX`
- `argus_mlx_work_root=/Volumes/AI-Drawing-16T/ai-drawing/staging/argus-minimax-h3`
- `argus_mlx_hf_cache=/Volumes/AI-Drawing-16T/ai-drawing/cache/huggingface`
- `argus_mlx_max_concurrency=1`（Pydantic 限定只能等於 1）
- `argus_mlx_timeout_seconds=3600`（positive finite；高於已量測 41 分鐘）
- `argus_mlx_ffmpeg=/opt/homebrew/bin/ffmpeg`
- `argus_mlx_ffprobe=/opt/homebrew/bin/ffprobe`

每筆 production job 的 argv 必須逐項等於以下 list；prompt 是單一 argv element，絕不經 shell：

```python
[
    settings.argus_mlx_python,
    settings.argus_mlx_generate_script,
    prompt,
    "--checkpoint", settings.argus_mlx_checkpoint,
    "--transformer", settings.argus_mlx_transformer,
    "--turbo-lora", settings.argus_mlx_turbo_lora,
    "--turbo-lora-scale", "1.0",
    "--profile", "quality",
    "--low-memory",
    "--stream-blocks",
    "--image", str(staged_image),
    "--anchor", "first",
    "--resolution", f"{width}x{height}",
    "--duration", str(total_seconds),
    "--steps", "9",
    "--seed", str(seed),
    "--memory-pressure-guard",
    "--no-block-cache",
    "--dense-dequant-profile", "off",
    "--require-muxed-mp4",
    "--ffmpeg", settings.argus_mlx_ffmpeg,
    "--forward-profile-json", str(profile_path),
    "--output", str(output_path),
]
```

Runner child env 只從 Backend env 複製 runtime 必需值，並明確覆寫 `HF_HOME`、`HUGGINGFACE_HUB_CACHE` 到 `argus_mlx_hf_cache`；不得 dump env、不得自動下載、不得在缺設定時改用 `$HOME`/內建 SSD。

---

### Task 1: H3 時序、設定正規化與 Argus runner 純契約

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/core/fixed_video_workflows.py`（只保留/收斂 H3 validation 與 timing；AnimeGen/Wan builder 不變）
- Create: `backend/app/services/argus_mlx_i2v.py`
- Modify: `backend/tests/test_config_paths.py`
- Modify: `backend/tests/test_fixed_video_workflows.py`
- Create: `backend/tests/test_argus_mlx_i2v.py`

**Interfaces:**
- `MiniMaxH3Timing(requested_seconds: int, source_frames: int, source_fps: float, timeline_span_seconds: float, container_duration_seconds: float)`；移除 H3 的 `film_frames/output_fps` 語意。
- `validate_minimax_h3_timing(total_seconds: int) -> MiniMaxH3Timing`。
- `validate_minimax_h3_dimensions(width: int, height: int) -> tuple[int, int]`。
- `ArgusMlxI2VRequest(job_id, staged_image, prompt, width, height, total_seconds, native_frames, seed)` frozen dataclass。
- `ArgusMlxI2VResult(output_path, profile_path, log_tail, fps, frame_count, duration, width, height)` frozen dataclass。
- `ArgusMlxI2VError(code: str, safe_message: str, *, exit_code: int | None = None, log_tail: str = "")`；`str(error)` 只回 bounded sanitized 安全文字。
- `ArgusMlxI2VRunner(settings).build_argv(request, work_dir) -> list[str]` 與 `.validate_prerequisites() -> None`。

- [ ] **Step 1: 寫 RED tests 固定設定與 timing**

在 `test_config_paths.py` 驗證所有 Argus path 即使 cwd 改變仍保持絕對路徑，env override 被 `_resolve_project_path` 正規化；`argus_mlx_max_concurrency=2`、timeout `0/-1/nan/inf/True` 皆 Pydantic validation fail。在 `test_fixed_video_workflows.py` table-test 秒數 1–5 對應 native frames 39、56、73、107、124，並精確驗證 span/container；拒絕 float、bool、0、6，以及越界/非 32 倍數/超過 786432 像素。

- [ ] **Step 2: 執行並確認 RED**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing/backend
python -m pytest tests/test_config_paths.py tests/test_fixed_video_workflows.py -k 'argus or minimax_h3' -vv
```

Expected: FAIL，缺少新 Settings 欄位、舊 timing 仍要求 `film_frames`，或尚未檢查像素上限；不得把 import/fixture 錯誤誤認成需求 RED。

- [ ] **Step 3: 寫 RED tests 固定 runner prerequisites 與 argv**

`test_argus_mlx_i2v.py` 使用 tmp paths 建立 fake executable/files/model dirs，驗證：缺 runtime/python/script/checkpoint/transformer/turbo/work root parent/HF cache/ffmpeg/ffprobe 時，錯誤 `code` 分別穩定且列出設定欄位；不可寫 work root 回 `storage_unavailable`。精確比對上方完整 argv，另以 prompt `hello; touch /tmp/pwned $(id)` 證明它仍是一個 element，並 patch `subprocess.Popen` contract 預期 `shell` 未傳或為 `False`。

- [ ] **Step 4: 執行並確認 RED**

Run: `cd /Users/USER/Desktop/ai-drawing/backend && python -m pytest tests/test_argus_mlx_i2v.py -k 'prerequisite or argv' -vv`

Expected: FAIL with `ModuleNotFoundError: app.services.argus_mlx_i2v` 或缺少介面。

- [ ] **Step 5: 最小 GREEN 實作**

新增上述 Settings/validators/path normalization；把 H3 timing 與 dimensions 改成新契約，但不動 AnimeGen/Wan 常數與 builder。建立 runner dataclasses/error、fail-closed prerequisites、job-specific work dir (`<work_root>/<job_id>/`) 與精確 argv builder。Path prerequisite 必須分辨 file/dir/executable/writable，錯誤只顯示設定 key，不顯示環境內容。

- [ ] **Step 6: 執行並確認 GREEN**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing/backend
python -m pytest tests/test_config_paths.py tests/test_fixed_video_workflows.py tests/test_argus_mlx_i2v.py -k 'argus or minimax_h3 or animegen or wan' -vv
```

Expected: PASS；既有 AnimeGen/Wan tests 仍通過。

- [ ] **Step 7: 範圍檢查與 commit**

```bash
cd /Users/USER/Desktop/ai-drawing
git diff --check
git add backend/app/services/argus_mlx_i2v.py backend/tests/test_argus_mlx_i2v.py
git add -p -- backend/app/config.py backend/app/core/fixed_video_workflows.py backend/tests/test_config_paths.py backend/tests/test_fixed_video_workflows.py
git diff --cached --check && git diff --cached
git commit -m "feat(backend): define Argus MLX H3 runner contract"
```

Expected: staged diff 不含舊 H3 workflow JSON、FILM、AnimeGen/Wan 或 `scripts/tmux-services.sh` 的無關 hunks。

---

### Task 2: Runner subprocess、終止、bounded diagnostics 與 MP4 驗證

**Files:**
- Modify: `backend/app/services/argus_mlx_i2v.py`
- Modify: `backend/tests/test_argus_mlx_i2v.py`

**Interfaces:**
- `ArgusMlxI2VRunner.run(request: ArgusMlxI2VRequest) -> ArgusMlxI2VResult`。
- `ArgusMlxI2VRunner.shutdown() -> None`：終止並 reap 目前 child；可重入。
- module-private `_probe_muxed_mp4(...) -> dict[str, int | float | str]` 與 `_terminate_process_group(process) -> None`。
- diagnostics 上限：stdout/stderr 各只保留最後 16 KiB，合併 user-facing `log_tail` 最多 24 KiB；控制字元與疑似 `TOKEN/KEY/SECRET/PASSWORD=...` 值遮蔽。

- [ ] **Step 1: 寫 RED tests 覆蓋 subprocess lifecycle**

以 executable fake Python script 模擬 success/nonzero/sleep/大量輸出；patch `Popen` 同時斷言 `cwd=runtime_root`、`start_new_session=True`、argv list、`shell=False`、HF cache env。驗證 random seed 由 request 傳入、nonzero 保存 exit code、timeout 先 `SIGTERM` process group 再 bounded wait/`SIGKILL`、`shutdown()` 終止 running child 並 `wait()` reap、第二次 shutdown 無害。大量輸出測試確認 Backend memory 不靠 `communicate()` 無界累積：stdout/stderr 由 reader threads 寫外接碟 log 並以 bounded deque/tail 回報。

- [ ] **Step 2: 寫 RED tests 覆蓋 cleanup 與 media validation**

用 tiny fixture MP4 或 mock ffprobe JSON 驗證：必須完整執行 ffmpeg decode；video codec=`h264`、audio codec=`aac`、24 FPS、width/height、`nb_frames=native_frames`、duration 約 `native_frames/24`（容許 1/24 秒及 container rounding）才成功。缺 MP4、零 bytes、decode fail、缺 audio、錯 codec/FPS/尺寸/幀數/duration 都回各自 stable code。任何失敗刪除 partial MP4/profile，但保留 bounded `runner.log`；成功 result 指向 job work dir，尚未碰 Gallery/DB。

- [ ] **Step 3: 執行並確認 RED**

Run: `cd /Users/USER/Desktop/ai-drawing/backend && python -m pytest tests/test_argus_mlx_i2v.py -k 'run or timeout or shutdown or probe or cleanup or sanit' -vv`

Expected: FAIL，因 `run/shutdown/probe` 尚未實作。

- [ ] **Step 4: 最小 GREEN 實作**

用 `Popen` + 兩個 drain threads 將 stdout/stderr append 至外接碟 log，同時只維護 bounded tail；timeout/shutdown 對 child process group 發 signal 並 reap。所有 ffprobe/ffmpeg 也是 list argv、`shell=False`、有限 timeout。先 prerequisites，再建立 work dir/profile/output/log；只有 child exit 0 且 MP4 全驗證通過才回 result。runner 不下載、不搬 Gallery、不寫 DB。

- [ ] **Step 5: 執行並確認 GREEN**

Run: `cd /Users/USER/Desktop/ai-drawing/backend && python -m pytest tests/test_argus_mlx_i2v.py -vv`

Expected: PASS，且測試結束沒有存活 fake child。

- [ ] **Step 6: commit**

```bash
cd /Users/USER/Desktop/ai-drawing
git add backend/app/services/argus_mlx_i2v.py backend/tests/test_argus_mlx_i2v.py
git diff --cached --check && git diff --cached
git commit -m "feat(backend): execute and validate Argus MLX video"
```

---

### Task 3: Queue engine 分支、artifact recording 與 application shutdown

**Files:**
- Modify: `backend/app/core/queue.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_argus_mlx_queue.py`
- Modify: `backend/tests/test_queue.py`
- Modify: `backend/tests/test_queue_failure.py`
- Modify: `backend/tests/test_generate_api.py`

**Interfaces:**
- `GenerateParams` 新增 `execution_engine: str`、`argus_mlx_i2v: dict[str, Any]`；H3 固定值為 `argus_mlx_i2v`。
- module singleton `get_argus_mlx_i2v_runner()`，供 worker 與 shutdown 使用；測試可 monkeypatch factory。
- `_process_argus_mlx_job(job: _Job) -> None`：同步 terminalize；不設定 `prompt_id`。
- `_record_argus_mlx_artifact(job, result) -> GeneratedArtifact`：atomic Gallery copy/move + DB record；失敗時刪除 Gallery destination。
- `stop_worker()` 先 set stop event，再 `runner.shutdown()`，最後 join worker thread。

- [ ] **Step 1: 寫 RED queue-routing tests**

`test_argus_mlx_queue.py` submit 一個 H3 job，fake runner 回 valid result；執行 `_process_pending(comfy=MagicMock())` 後斷言 runner 恰一次、Comfy 的 upload/submit/get_queue/get_history 全未呼叫、running 已釋放、`prompt_id is None`、seed 在 queue 進 runner 前以 `secrets.randbelow(2**63)` 配置並寫回 params。另排兩個 Argus job，阻塞第一個，證明第二個仍 queued、runner active count 最大 1；再排一般 Comfy job，證明其 engine 省略時仍走既有 submit/history 分支而不呼叫 Argus。

- [ ] **Step 2: 寫 RED artifact/failure/status tests**

使用 in-memory SQLite 與 tmp Gallery 驗證 success 只建立一筆：`artifact_type=video`、`mime_type=video/mp4`、`source_node_id="argus_mlx_i2v"`、`source_node_type="SaveVideo"`，欄位 fps/frame_count/duration/width/height 完整。`metadata_json` 明確含 engine、seed、requested_seconds、native_frames、timeline_span_seconds、container_duration_seconds、steps=9、NFE=8、profile=quality、low_memory/stream_blocks/no_block_cache/memory_pressure_guard、runtime/model path basename，不含完整 log、env 或 secret；`workflow_json` 為 `None`，negative prompt 為 `None`。

用 runner nonzero/timeout/prerequisite/invalid MP4、Gallery write fail、`recording_save_artifact` fail 分別驗證 job=`failed`、bounded error/recording_error、staged input與 partial/gallery destination 清理、DB artifact count=0，且下一個 pending job 可執行。`GET /api/generate/job/{id}` 對成功 artifact 在模擬 Backend restart（queue reset）後仍回 completed；Discord 所需 `SaveVideo` 欄位不變。

- [ ] **Step 3: 寫 RED shutdown tests**

patch runner `shutdown` 與 worker thread，驗證 `stop_worker()` 順序可解除 blocked `run()` 並在 5 秒 join；`app.main.lifespan` shutdown 沿用 `stop_queue_worker`，不重啟/停止 ComfyUI。明確測試 queued/running Argus state 不宣稱 restart recovery：沒有 artifact 且 queue reset 後 job 404。

- [ ] **Step 4: 執行並確認 RED**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing/backend
python -m pytest tests/test_argus_mlx_queue.py tests/test_queue.py tests/test_queue_failure.py tests/test_generate_api.py -k 'argus or completed_video or stop_worker' -vv
```

Expected: FAIL，engine 尚未分支且不會建立 Argus artifact。

- [ ] **Step 5: 最小 GREEN 實作**

在 `_process_pending` 取得 generation client 之前判斷 engine；Argus 分支建立 request、配置 backend seed、呼叫 runner、驗證 job-specific result path 仍在 work root，atomic move 至 `gallery/<UTC-date>/<job-id>_argus_mlx_i2v.mp4`，再呼叫 `recording_save_artifact`。DB save 失敗即移除 destination 並 `_record_failure`；任何 terminal path 都清 staging、partial profile/output，保留 runner.log 診斷。既有 `_check_running_complete` 只處理有 Comfy `prompt_id` 的 job，Argus 不進該分支。

- [ ] **Step 6: 執行並確認 GREEN**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing/backend
python -m pytest tests/test_argus_mlx_queue.py tests/test_queue.py tests/test_queue_failure.py tests/test_queue_completion.py tests/test_fixed_video_queue.py tests/test_generate_api.py -vv
```

Expected: PASS；existing Comfy/FILM/independent batch tests 不退化。

- [ ] **Step 7: commit**

```bash
cd /Users/USER/Desktop/ai-drawing
git add backend/tests/test_argus_mlx_queue.py
git add -p -- backend/app/core/queue.py backend/app/main.py backend/tests/test_queue.py backend/tests/test_queue_failure.py backend/tests/test_generate_api.py
git diff --cached --check && git diff --cached
git commit -m "feat(backend): route Argus jobs and record video artifacts"
```

---

### Task 4: FastAPI multipart 新契約與 fail-closed validation

**Files:**
- Modify: `backend/app/api/generate.py`
- Modify: `backend/tests/test_fixed_video_api.py`
- Modify: `backend/tests/test_generate_api.py`

**API contract:**

`POST /api/generate/video/minimax-h3-i2v` 唯一有執行語意的 multipart fields 為 `image`, `prompt`, `width`, `height`, `total_seconds`；成功 HTTP 201 `GenerateResponse` message 包含 native frames、timeline span、container duration 與「固定 Mac MLX」。舊 `negative_prompt`/`film_target_frames`/`execution_target` 不再被 endpoint function 宣告，也不進 queue params。

- [ ] **Step 1: 寫 RED success contract test**

以 PNG/JPEG/WebP 各一筆合法檔頭測試 201；patch `submit` 後精確斷言 params 只有 H3 engine payload、staged input、trimmed prompt/timing/dimensions，且 `execution_engine == "argus_mlx_i2v"`，沒有 `workflow/server_owned_verbatim/fixed_video_template/fixed_video_input_bindings/film_postprocess/negative_prompt/execution_target`。驗證 response message 對 5 秒為 124 frames、span 5.125 秒、container 5.167 秒且固定 Mac MLX。

- [ ] **Step 2: 寫 RED validation/cleanup matrix**

Parameterize：缺 field、prompt empty/whitespace/>4000、秒數 `0/6/1.5/true/nan`、width/height `<256/>1024`、非 32 倍數、pixel cap 超標，全部 HTTP 422 且 `submit` 未呼叫、staging 空。沿用現有 MIME/副檔名/檔頭/actual bytes/20 MiB validation，覆蓋 spoof、size mismatch、oversize、empty。QueueFull 回 503 並刪 staged；submit unexpected exception 刪 staged後向上拋。送舊欄位時測試它們不出現在 params，確保 FastAPI ignored multipart field 無執行語意。

- [ ] **Step 3: 寫 RED non-goal regression tests**

保留 AnimeGen/Wan success params 與 execution target tests；證明兩 endpoint 的 workflow/FILM 行為逐字不變。測試舊 H3 workflow builder 不再被 endpoint 呼叫；不要刪除目前 dirty untracked workflow JSON。

- [ ] **Step 4: 執行並確認 RED**

Run: `cd /Users/USER/Desktop/ai-drawing/backend && python -m pytest tests/test_fixed_video_api.py -k 'minimax or animegen or wan' -vv`

Expected: 新契約 tests FAIL，現 endpoint 仍要求/傳送舊欄位。

- [ ] **Step 5: 最小 GREEN 實作**

修改 endpoint signature/validation，先驗 prompt/dimensions/timing，再 `stage_upload`，最後組成 engine payload submit。不要呼叫 `build_minimax_h3_i2v_workflow`，不要使用 `ExecutionTarget`。保留共用 attachment helpers與 AnimeGen/Wan imports/endpoint 不變；只移除 generate.py 已無用途的 H3 workflow imports。

- [ ] **Step 6: 執行並確認 GREEN**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing/backend
python -m pytest tests/test_fixed_video_api.py tests/test_fixed_video_workflows.py tests/test_argus_mlx_queue.py tests/test_generate_api.py -vv
```

Expected: PASS。

- [ ] **Step 7: commit**

```bash
cd /Users/USER/Desktop/ai-drawing
git add -p -- backend/app/api/generate.py backend/tests/test_fixed_video_api.py backend/tests/test_generate_api.py
git diff --cached --check && git diff --cached
git commit -m "feat(api): replace MiniMax H3 multipart with MLX contract"
```

---

### Task 5: Discord validation 與 ApiClient wire contract

**Files:**
- Modify: `discord-bot/bot/validation.py`
- Modify: `discord-bot/bot/api_client.py`
- Modify: `discord-bot/tests/test_validation.py`
- Modify: `discord-bot/tests/test_api_client.py`

**Interfaces:**
- `parse_minimax_h3_dimensions(width, height) -> tuple[int, int]`：256–1024、32 倍數、pixel cap。
- `parse_minimax_h3_contract(total_seconds) -> tuple[int, int, float, float]`：`requested_seconds, native_frames, timeline_span, container_duration`；只收整數 1–5。
- `ApiClient.submit_minimax_h3_i2v(*, image, prompt, width, height, total_seconds) -> str`；multipart 僅新五欄。

- [ ] **Step 1: 寫 RED validation tests**

table-test 合法尺寸邊界與 768×1024=786432；拒絕 1024×1024 pixel cap、252/1056、非 32 倍數與 bool。秒數 1–5 全驗 native/span/container；拒絕空白、float string `1.0/1.5`、0、6、bool。AnimeGen/Wan `parse_video_contract` 保持既有 1–20/FILM 行為。

- [ ] **Step 2: 寫 RED client multipart test**

用 `httpx.MockTransport` parse multipart body，精確集合只能為 `image,prompt,width,height,total_seconds`；舊欄位字串不得出現在 body。驗 201 job ID、422 映射 `BackendError`、timeout 仍 explicit 120 秒。

- [ ] **Step 3: 執行並確認 RED**

Run: `cd /Users/USER/Desktop/ai-drawing/discord-bot && python -m pytest tests/test_validation.py tests/test_api_client.py -k minimax -vv`

Expected: FAIL，舊 parser/client 仍有 FILM、negative、execution target。

- [ ] **Step 4: 最小 GREEN 實作**

只改 H3 helper/method signature；不要改共用 `submit_fixed_video`，因 AnimeGen/Wan 仍用舊 fields。ApiClient 回 job ID，timing 顯示由 Bot純函式計算，不信任 response message。

- [ ] **Step 5: 執行並確認 GREEN**

Run: `cd /Users/USER/Desktop/ai-drawing/discord-bot && python -m pytest tests/test_validation.py tests/test_api_client.py -vv`

Expected: PASS，AnimeGen/Wan client tests 不變。

- [ ] **Step 6: commit**

```bash
cd /Users/USER/Desktop/ai-drawing
git add -p -- discord-bot/bot/validation.py discord-bot/bot/api_client.py discord-bot/tests/test_validation.py discord-bot/tests/test_api_client.py
git diff --cached --check && git diff --cached
git commit -m "feat(discord): send MiniMax H3 MLX API contract"
```

---

### Task 6: Discord slash schema、H3 modal 文案與 `/result` 相容

**Files:**
- Modify: `discord-bot/bot/main.py`
- Modify: `discord-bot/bot/views.py`
- Modify: `discord-bot/tests/test_main.py`
- Modify: `discord-bot/tests/test_views.py`
- Modify: `discord-bot/tests/test_api_client.py`（只補 `/result` contract regression，如 Task 5 未涵蓋）

**UI contract:**
- `/minimax_h3_i2v(image, width: Range[256,1024], height: Range[256,1024])`，沒有 execution target。
- `MiniMaxH3I2VModal(api,image,width,height)` 只有兩個 children：prompt（required/max 4000）與 total seconds（default 5，1–5）。
- queued 回覆含 job ID、native frames、timeline span、container duration、固定 Mac MLX 與 `/result id:<job-id>`。

- [ ] **Step 1: 寫 RED command schema tests**

command set 精確仍為 `draw,animegen_i2v,minimax_h3_i2v,wan22_animate,result`。只對 H3 斷言 parameters 不含 `execution_target`、width/height min/max 為 256/1024；`draw/animegen/wan` 仍有 Mac/Worker choices。H3 command 在 attachment/dimension/pixel validation 後開 modal、尚未下載附件；非法時 ephemeral error。

- [ ] **Step 2: 寫 RED modal tests**

斷言 H3 modal children labels/數量只有 prompt/秒數，沒有 negative/FILM/execution；blank prompt與非法秒數在讀附件前 fail；合法 submit 精確呼叫新 ApiClient signature。queued message 對 1 秒顯示 39 frames/span 1.583/container 1.625，含「固定 Mac MLX」與完整 result command；BackendError與附件讀取失敗保持 ephemeral sanitized 文案。

- [ ] **Step 3: 寫 RED `/result` SaveVideo regression**

`collect_job_result` 對 completed `SaveVideo` + `video/mp4` 建 Gallery URL並下載/交付；queued/running/failed 不下載；非 SaveVideo/unsupported MIME 排除。這確保 Argus artifact 不需 Discord 特判。

- [ ] **Step 4: 執行並確認 RED**

Run: `cd /Users/USER/Desktop/ai-drawing/discord-bot && python -m pytest tests/test_main.py tests/test_views.py tests/test_api_client.py -k 'minimax or result or generation_commands' -vv`

Expected: FAIL，H3 command/modal 尚有舊 controls。

- [ ] **Step 5: 最小 GREEN 實作**

移除 H3 command decorator choice/argument與 modal state；更新 descriptions 明示 Mac MLX、尺寸/pixel cap；使用新 timing helper及 client signature。不得修改 `FixedVideoModal` 的 AnimeGen/Wan fields，也不得移除全域 execution choices（其他 commands 仍用）。

- [ ] **Step 6: 執行並確認 GREEN**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing/discord-bot
python -m pytest tests/test_main.py tests/test_views.py tests/test_validation.py tests/test_api_client.py tests/test_delivery.py -vv
```

Expected: PASS；`/result` 可交付 SaveVideo。

- [ ] **Step 7: commit**

```bash
cd /Users/USER/Desktop/ai-drawing
git add -p -- discord-bot/bot/main.py discord-bot/bot/views.py discord-bot/tests/test_main.py discord-bot/tests/test_views.py discord-bot/tests/test_api_client.py
git diff --cached --check && git diff --cached
git commit -m "feat(discord): expose fixed-Mac MiniMax H3 MLX UI"
```

---

### Task 7: 操作文件、環境設定範本與已知生命週期限制

**Files:**
- Modify: `.env.example`
- Modify: `discord-bot/README.md`
- Modify: `docs/setup-guide.md`
- Modify: `docs/PROGRESS.md`
- Test: `backend/tests/test_argus_mlx_i2v.py`（設定範本 key inventory）

**Documentation contract:** 不修改目前 untracked `scripts/tmux-services.sh`；部署章節可引用它，但不得把它混入本功能 commit。文件必須說明固定 Mac MLX、外接碟、無 fallback/自動下載/FILM/negative、1–5 秒時序、restart 不恢復 queued/running、completed artifact durable、timeout 與 troubleshooting。

- [ ] **Step 1: 寫 RED env inventory test**

在 `test_argus_mlx_i2v.py` 讀 root `.env.example`，驗證上述 12 個 `ARGUS_MLX_*` keys 各出現一次、值沒有 token/secret、所有 storage/model/cache/work defaults 位於 `/Volumes/AI-Drawing-16T/ai-drawing`；timeout=3600/concurrency=1。測試同時禁止舊 `MINIMAX_H3_EXECUTION_TARGET` 類設定。

- [ ] **Step 2: 執行並確認 RED**

Run: `cd /Users/USER/Desktop/ai-drawing/backend && python -m pytest tests/test_argus_mlx_i2v.py -k env_example -vv`

Expected: FAIL，範本尚無 Argus keys。

- [ ] **Step 3: 更新文件與範本**

`.env.example` 加完整可覆寫值及外接碟註解。Discord README 新增 H3 command 表格與 modal fields，改寫「三個生成指令皆有 execution target」為只有 draw/AnimeGen/Wan；寫出 native frames/span/container 公式。setup guide 加 runtime prerequisite check（mount、可執行 Python/script、model dirs、HF cache/work writable、ffmpeg/ffprobe）、不自動下載及 timeout guidance。PROGRESS 新增本功能小節，但測試數字只在實際執行後填入真實輸出；此階段先記「focused implementation pending final gate」而不是虛構 PASS。

- [ ] **Step 4: 執行並確認 GREEN**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing/backend
python -m pytest tests/test_argus_mlx_i2v.py -k 'env_example or prerequisite' -vv
cd /Users/USER/Desktop/ai-drawing
python - <<'PY'
from pathlib import Path
for name in ('.env.example', 'discord-bot/README.md', 'docs/setup-guide.md', 'docs/PROGRESS.md'):
    text = Path(name).read_text(encoding='utf-8')
    assert 'Argus' in text or name == '.env.example'
print('documentation smoke: ok')
PY
```

Expected: tests PASS，script 印 `documentation smoke: ok`。

- [ ] **Step 5: commit**

```bash
cd /Users/USER/Desktop/ai-drawing
git add .env.example discord-bot/README.md docs/setup-guide.md docs/PROGRESS.md
git add -p -- backend/tests/test_argus_mlx_i2v.py
git diff --cached --check && git diff --cached
git commit -m "docs: document MiniMax H3 Argus MLX operation"
```

---

### Task 8: Focused、full regression 與靜態驗證

**Files:**
- Modify only if a real in-scope failure requires a fix: files already listed in Tasks 1–7 plus the directly corresponding test.
- Modify after truthful results: `docs/PROGRESS.md`

- [ ] **Step 1: 再確認 dirty baseline 與 queue idle（不啟服務）**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing
git status --short
git diff --check
git diff --name-only
```

Expected: 逐項比對開工時 dirty inventory；無 whitespace error。不得處理無關 dirty changes。

- [ ] **Step 2: Backend focused gate**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing/backend
python -m pytest \
  tests/test_argus_mlx_i2v.py \
  tests/test_argus_mlx_queue.py \
  tests/test_fixed_video_api.py \
  tests/test_fixed_video_workflows.py \
  tests/test_fixed_video_queue.py \
  tests/test_generate_api.py \
  tests/test_queue.py \
  tests/test_queue_failure.py \
  tests/test_queue_completion.py -vv
```

Expected: PASS；0 failed。若失敗，先確認是否本功能造成；in-scope 依 RED→最小修正→重跑，out-of-scope 記錄 baseline evidence，不修改它。

- [ ] **Step 3: Discord full gate**

Run: `cd /Users/USER/Desktop/ai-drawing/discord-bot && python -m pytest -vv`

Expected: PASS；command set、AnimeGen/Wan、delivery/operator tests 全綠。

- [ ] **Step 4: Backend full gate**

Run: `cd /Users/USER/Desktop/ai-drawing && python -m pytest backend/tests -q`

Expected: PASS；若 repository 有事先存在的 unrelated failures，保存完整 node ID 與 pristine/baseline 證據，不以修改無關 production code消紅。

- [ ] **Step 5: compile、contract scans 與 diff gate**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing
python -m compileall -q backend/app backend/tests discord-bot/bot discord-bot/tests
python - <<'PY'
from pathlib import Path
api = Path('backend/app/api/generate.py').read_text()
bot = Path('discord-bot/bot/main.py').read_text()
client = Path('discord-bot/bot/api_client.py').read_text()
assert 'execution_engine' in api and 'argus_mlx_i2v' in api
h3 = bot[bot.index('@tree.command(name="minimax_h3_i2v"'):bot.index('@tree.command(name="wan22_animate"')]
assert 'execution_target' not in h3
method = client[client.index('async def submit_minimax_h3_i2v'):client.index('async def submit_wan22_animate')]
for retired in ('negative_prompt', 'film_target_frames', 'execution_target'):
    assert retired not in method
print('contract scan: ok')
PY
git diff --check
```

Expected: compile exit 0、`contract scan: ok`、diff check exit 0。

- [ ] **Step 6: 更新真實驗證證據，RED→GREEN 重跑後 commit**

把實際 pass/fail/skip counts、命令、既有 baseline failures、未跑 live 的事實寫入 `docs/PROGRESS.md`，不得預填數字。若本 Task 有修正，先新增/收斂 reproducer test 取得 RED，再修正並重跑該 focused command與 full gate。

```bash
cd /Users/USER/Desktop/ai-drawing
git add -p -- docs/PROGRESS.md backend/app backend/tests discord-bot/bot discord-bot/tests
git diff --cached --check && git diff --cached
git commit -m "test: verify MiniMax H3 Argus MLX integration"
```

Expected: commit 只含真實驗證證據與必要 in-scope fixes；若沒有任何 diff，明確記錄「no commit needed」，不製造空 commit。

---

### Task 9: Live runner smoke、public API E2E 與受控部署驗證

**Files:**
- Modify after actual evidence only: `docs/PROGRESS.md`
- No production/test file changes unless live smoke 發現可重現 bug；若發現，回到對應 Task 先做 automated RED→GREEN。

**Safety gate:** 真實 MLX 會長時間占用 Mac/外接碟。執行前必須取得當次使用者對 live generation 與 Backend/Bot restart 的明確批准；未批准即將本 Task 記為 blocked/not run，不可偷跑。ComfyUI 不重啟、不 free memory、不改路由。

- [ ] **Step 1: 部署前 inventory、storage、runtime 與 idle 檢查**

Run:

```bash
cd /Users/USER/Desktop/ai-drawing
git status --short
python - <<'PY'
from pathlib import Path
paths = {
 'python': Path('/Volumes/AI-Drawing-16T/ai-drawing/runtimes/minimax-h3-mac-pr4/.venv/bin/python'),
 'script': Path('/Volumes/AI-Drawing-16T/ai-drawing/runtimes/minimax-h3-mac-pr4/scripts/generate.py'),
 'checkpoint': Path('/Volumes/AI-Drawing-16T/ai-drawing/models/minimax_h3_mlx/MiniMax-H3/FL2VA'),
 'transformer': Path('/Volumes/AI-Drawing-16T/ai-drawing/models/minimax_h3_mlx/MiniMax-H3-MLX-Argus-Calibrated-INT8'),
 'turbo': Path('/Volumes/AI-Drawing-16T/ai-drawing/models/minimax_h3_mlx/MiniMax-H3-Turbo-v4-step600-EMA-MLX'),
 'work': Path('/Volumes/AI-Drawing-16T/ai-drawing/staging/argus-minimax-h3'),
 'cache': Path('/Volumes/AI-Drawing-16T/ai-drawing/cache/huggingface'),
}
for key, path in paths.items():
    if key in {'work', 'cache'}:
        path.mkdir(parents=True, exist_ok=True)
    assert path.exists(), (key, path)
assert paths['python'].is_file() and paths['script'].is_file()
print('Argus prerequisites: ok')
PY
curl -fsS --max-time 5 http://127.0.0.1:8001/health
curl -fsS --max-time 5 http://127.0.0.1:8001/api/generate/queue
curl -fsS --max-time 5 http://127.0.0.1:8188/system_stats
```

Expected: prerequisites/health OK；Backend queue `queue_running=[]`、`queue_pending=[]`，並另外確認 LoRA training queue idle。若非 idle，停止，不取消他人工作。

- [ ] **Step 2: 64×64 runner integration smoke（不經 public API）**

以 gallery/staging 中一張合法 image 呼叫一個 checked-in 介面的一次性 Python snippet：建立 `ArgusMlxI2VRequest(job_id="live-smoke-<timestamp>", width=64, height=64, total_seconds=1, native_frames=39, backend random seed)` 並直接 `runner.run()`。此 smoke 只證明 Argus runtime/模型/ffmpeg integration；不寫 DB、不冒充 public E2E，結束後刪 output/profile，保留 bounded log與實際耗時證據。

Expected: 約 11 分鐘的估計僅供排程，不能當 timeout/pass 條件；實際 result 必須為完整可解碼 H.264+AAC、64×64、24 FPS、39 frames、container 約 1.625 秒。

- [ ] **Step 3: Public API 256×256、1 秒 E2E**

用合法 PNG multipart 呼叫：

```bash
curl -fsS --max-time 30 -X POST http://127.0.0.1:8001/api/generate/video/minimax-h3-i2v \
  -F image=@/absolute/path/to/smoke.png \
  -F prompt='Subtle natural motion, stable camera, coherent details' \
  -F width=256 -F height=256 -F total_seconds=1
```

保存真實 `job_id`，每 15 秒 `GET /api/generate/job/<job_id>`，最多 3600 秒；必須觀察 `queued -> running -> completed`（快速轉換可由 log佐證，不捏造漏觀察狀態）。Expected completed artifact：`SaveVideo`/`video/mp4`、H.264+AAC、256×256、24 FPS、39 frames、duration 約 1.625、metadata 含 seed/requested/native/span/container。再用 artifact gallery URL完整下載、ffmpeg decode，最後在 Discord 執行 `/result id:<job-id>`，確認影片可交付。此 gate 只驗 integration，不作視覺品質 PASS。

- [ ] **Step 4: Failure live smoke（不啟動模型）**

暫時以測試 process/isolated Settings 指向不存在 runtime 或 unmounted temp path（不可改 production `.env`），提交 runner prerequisite check，證明回 `runtime_missing/storage_unavailable`、不建立 artifact、不自動下載、不 fallback ComfyUI/Worker。完成後確認 production Settings 未變。

- [ ] **Step 5: 受控部署 Backend + Bot，ComfyUI 不動**

重新確認 queue/LoRA/Argus idle後，只 restart Backend 與 Discord Bot；若使用現有 `scripts/tmux-services.sh`，它是開工前 untracked dirty file，僅執行、不 stage、不修改。記錄「部署來自 dirty working tree」及 `git status --short`。不得 commit/push/PR/release。

Expected: Backend child shutdown test先前已證明可回收；live restart 不留 Argus child。ComfyUI PID、uptime及 `/system_stats` 在前後保持可用且未被 restart。

- [ ] **Step 6: 部署後 health、queue、TLS、command sync/schema**

Run:

```bash
curl -fsS --max-time 5 http://127.0.0.1:8001/health
curl -fsS --max-time 5 http://127.0.0.1:8001/api/generate/queue
curl -fsS --max-time 5 http://127.0.0.1:8188/system_stats
```

再確認 Bot process存活、到 Discord `:443` TLS established、log 出現 guild command sync success；Discord guild 實際 schema 仍含 `/minimax_h3_i2v`，其 options 精確為 image/width/height，沒有 execution target，Modal 精確為 prompt/total seconds。另抽查 `/animegen_i2v`、`/wan22_animate` 仍存在且 execution target 不變。

- [ ] **Step 7: 記錄 live 真實證據與最終 commit gate**

將 job ID、artifact ID/path、probe metadata、狀態轉換、實際耗時、deployment source dirty 說明、Backend/Bot/ComfyUI health結果寫入 `docs/PROGRESS.md`；不得寫 prompt secret或完整環境。若當次禁止 commit，只保留文件 diff並回報；若獲准 commit：

```bash
cd /Users/USER/Desktop/ai-drawing
git add -p -- docs/PROGRESS.md
git diff --cached --check && git diff --cached
git commit -m "docs: record live Argus MLX H3 acceptance"
```

Expected: 唯一 staged file 是 `docs/PROGRESS.md`；無 production code、舊 dirty workflow、tmux script或 output artifact。

---

## 最終完成定義

- [ ] H3 Backend/API/Bot focused tests 全綠，Backend full 與 Discord full gate有真實結果。
- [ ] Argus argv 精確、`shell=False`、外接碟 cache/work/log/profile/output、有限 timeout與 bounded sanitized diagnostics均有 automated tests。
- [ ] Queue engine branch 完全不碰 ComfyUI client，Argus 最大並行 1，shutdown reap child，失敗不 fallback。
- [ ] 只有完整驗證 MP4 才移 Gallery/寫 `GeneratedArtifact(SaveVideo)`；recording failure 不留下 completed/raw artifact。
- [ ] API 只使用新五欄，Bot H3 無 execution target/negative/FILM，其他 commands 不變。
- [ ] `/result` 交付 Argus SaveVideo，completed artifact 在 Backend restart 後仍可查；queued/running restart limitation有文件。
- [ ] `compileall`、contract scan、`git diff --check` 通過，dirty baseline未被 stash/revert/覆寫/誤 stage。
- [ ] Live 未獲批准時明確標 `not run`；獲批准時 runner 64×64 integration smoke、public 256×256 API E2E、部署後 health/TLS/sync/schema均有真實證據。
- [ ] 未 commit/push/PR/release任何未獲當次授權內容，ComfyUI 未重啟。
