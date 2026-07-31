# NVIDIA Worker All Entry Points Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓所有產品級ai-drawing ComfyUI生成入口、MCP、Discord與Web UI都能明確選擇Mac local或Windows worker，並完成跨機輸入、資源與節點能力準備。

**Architecture:** Queue是唯一目標client選擇邊界；所有上層入口只傳遞`execution_target`。Queue使用同一client完成輸入上傳、資源同步、submit、poll與artifact fetch；Windows Worker提供authenticated proxy、content-addressed cache與node capability preflight。

**Tech Stack:** FastAPI/Pydantic/Python, FastMCP, discord.py, React/TypeScript/Vite, PowerShell, ComfyUI HTTP API, pytest/Vitest.

## Global Constraints

- `execution_target`只接受`local|worker`且預設`local`。
- Worker失敗不得自動回退Mac。
- ComfyUI在Windows只監聽loopback。
- 普通生成請求不得安裝任意custom-node Git URL或重啟ComfyUI。
- Windows未安裝前只宣稱offline readiness，不宣稱真機E2E完成。

---

### Task 1: Backend契約與全入口傳遞

**Files:** Backend schemas/APIs for generate, gallery, style presets, Civitai, LoRA smoke and corresponding tests.

- [ ] 在每個request/API test先加入`worker`預期並執行focused pytest，確認因欄位缺失或params未傳而RED。
- [ ] 新增共用ExecutionTarget型別並讓所有產品級生成／rerun／test入口傳入queue params。
- [ ] 重跑focused tests確認GREEN，並驗證省略欄位仍為local。

### Task 2: 跨機輸入與資源能力

**Files:** `backend/app/core/queue.py`, `backend/app/services/nvidia_worker.py`, Worker runtime and focused tests.

- [ ] 先寫RED tests，證明custom gallery inputs、fixed-video staged files與keyframes使用選定client上傳，而非Mac input direct copy。
- [ ] 先寫RED tests覆蓋DualCLIP、CLIPVision、GGUF及已知loader資源解析與unknown/missing node preflight。
- [ ] 實作統一remote input upload/resource manifest/capability check並維持fail-closed。
- [ ] 重跑worker/queue/video tests確認GREEN。

### Task 3: MCP完整schema

**Files:** MCP generation/Civitai/gallery/style/LoRA tools、catalog tests與README。

- [ ] 先讓FastMCP schema/forwarding tests要求每個生成意圖工具具有`execution_target`並跑RED。
- [ ] 加入參數、精確forwarding與submitted回讀；更新audited docs/catalog。
- [ ] 跑MCP focused/full tests並直接列FastMCP schema確認enum。

### Task 4: Discord Bot完整選擇

**Files:** Discord command/view/client/validation與tests。

- [ ] 先寫slash command、modal state、multipart/JSON forwarding RED tests。
- [ ] 在圖片及影片命令加入Local/Windows選項，傳入Backend；預設local。
- [ ] 跑Discord完整tests確認GREEN。

### Task 5: Web UI選擇

**Files:** Generate、Prompt Library GenerationPanel、Gallery rerun API/types/components與tests。

- [ ] 先寫request payload/component RED tests，要求target selector與exact wire value。
- [ ] 實作共用ExecutionTarget控制元件並接到三個入口。
- [ ] 跑frontend tests、typecheck與production build。

### Task 6: Windows安裝包與能力鎖定

**Files:** `worker/windows/*`, build script, `dist/AI-Drawing-NVIDIA-Worker/*`, tests/docs.

- [ ] 先寫manifest/package tests，要求100GB cache、20GB reserve、pinned custom-node entries及dist/source一致。
- [ ] 實作custom-node fixed revision安裝與Worker `/object_info` proxy/preflight。
- [ ] 重建dist並執行PowerShell parser/static checks和pytest。

### Task 7: 驗證與部署

- [ ] 跑Backend/MCP/Discord/Frontend完整門檻與`git diff --check`。
- [ ] 執行`openspec validate add-nvidia-worker --strict`與authoritative validation。
- [ ] 確認queue無進行中工作後，只重啟受影響Backend、MCP/Gateway、Discord Bot；不重啟ComfyUI。
- [ ] 讀回live Backend OpenAPI、`/api/workers/status`與active MCP schema；Windows未配對應顯示not_paired。
- [ ] 將真機圖片/影片/Gallery/fail-closed驗收保留為明確未完成gate。
