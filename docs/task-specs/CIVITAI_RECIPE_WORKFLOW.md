# Civitai Recipe Import 工作流程

1. **CIV-A Recipe foundation**：schema、raw metadata、reproduction report。
2. **CIV-B Civitai acquisition**：URL resolver、Images/Versions API、embedded metadata。
3. **CIV-C Resource identity**：AIR/ID/hash ledger、strict resolution、安全下載。
4. **CIV-D Workflow compiler**：SDXL/Illustrious、clip skip、多 LoRA、hires/upscale/detailer/control。
5. **CIV-E Gallery provenance**：完整 recipe/input/resource/runtime snapshot、export/rerun。
6. **CIV-F MCP integration**：inspect/resolve/build/run/export tools 與 API contracts。
7. **CIV-G Live reproduction**：公開 Civitai recipe smoke、逐圖交付、文件與回歸。

每個 stage 由 Terra 實作、Sol review；dispatcher 驗證及 commit。任何 runtime 圖片不得由 Agent自行視覺裁定。
