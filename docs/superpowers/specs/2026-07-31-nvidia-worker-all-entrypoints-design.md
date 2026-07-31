# NVIDIA Worker 全入口設計

## 目標

Mac 繼續擔任 ai-drawing 協調器、資料庫、Gallery與權威資源庫；所有產品級 ComfyUI 生成入口都能明確選擇 `local` 或已配對的 Windows NVIDIA `worker`。選定 Worker 後任何配對、資源、節點、輸入或執行錯誤都必須終止該工作，不得改送 Mac。

## 產品入口

支援範圍包含：一般圖片、圖片 custom workflow、影片 custom workflow、AnimeGen I2V、Wan Animate、Wan keyframes、Civitai generate-like／recipe／variant／variation-set、Gallery rerun、Style Preset saved-workflow test、LoRA smoke test，以及對應 MCP、Discord Bot與Web UI。一次性 experiments/tmp scripts不屬產品入口。

所有入口使用同一 `ExecutionTarget = Literal["local", "worker"]` 契約，省略時維持 `local`。重跑與測試入口由本次呼叫明確選擇，不依歷史工作猜測目標。

## 執行與資料流

Backend只將目標寫入 queue params；Queue是唯一選擇 ComfyUI client的地方。同一 client負責能力預檢、輸入上傳、模型同步、prompt提交、queue/history查詢與artifact抓取。

Gallery相對輸入、multipart staged image/video、keyframes、mask與pose在工作開始後才上傳至選定client。Workflow內只寫入目標ComfyUI回傳的server-side相對名稱；不把Mac絕對路徑傳到Windows。

## 資源與節點

Worker同步workflow實際引用的checkpoint、diffusion model、text encoder、VAE、LoRA、ControlNet、upscaler、CLIP vision、GGUF與audio/model資源。傳輸沿用SHA-256、8MiB可續傳partial與atomic promotion。

Windows installer使用version manifest安裝目前正式workflow所需custom-node repositories與固定revision。Worker在prompt前以`/object_info`能力資料驗證全部class_type；缺節點時回結構化錯誤。普通生成請求不得安裝任意Git URL或重啟ComfyUI。

## 使用介面

MCP tool schema、Discord slash command/modal state與Web Generate/Prompt Library/Gallery操作都公開一致的Local/Windows選擇。MCP仍以`local`為相容預設；Discord/Web顯示人類可讀標籤，wire value固定為`local|worker`。

## 容量

Worker cache以`cache_gb`和`minimum_free_gb`控制，不預先建立100GB檔案。安裝包預設模型cache調整為100GB，仍保留至少20GB可用空間；文件明確要求Windows至少準備足夠runtime、cache與暫存的總空間。

## 錯誤與安全

Worker未配對、無法連線、驗證失敗、cache不足、缺資源、digest不符、缺節點或ComfyUI拒絕時，工作以可查詢的結構化failure終止。Worker只對Private network／授權Token開放；ComfyUI持續只監聽loopback。

## 驗收

本輪完成所有offline unit/integration tests、MCP catalog/schema、Discord tests、Frontend tests/build、OpenSpec strict validation、Windows package內容一致性與live Mac服務schema部署。Windows安裝後再完成真機配對、第一次缺模型同步、圖片與影片各一個Gallery artifact，以及fail-closed驗證。
