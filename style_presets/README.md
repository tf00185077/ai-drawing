# Style Presets

創作者／風格「食譜」目錄。以 **agent（機器）** 與 **human（人類）** 兩個子資料夾分開，
但同屬一個 `style_presets/` 目錄：

```
style_presets/
├── agent/                  # 機器可讀來源（後端與 MCP 實際讀取），分兩層：
│   ├── index.json          #   輕量索引：[{id, name, profiles, 資源摘要}] ← list 只讀這個
│   └── presets/
│       └── <preset-id>.json #  單一 preset 完整食譜 ← get/compose 只讀對應單檔
└── human/                  # 人類筆記（不被程式解析）
    ├── _template.md        #   撰寫範本
    └── <preset-id>.md
```

> **分層**：`list` 只讀 `index.json`（不全掃所有食譜）；`get`/`compose` 只讀對應的
> `presets/<id>.json`。編輯／新增 preset 後執行 **reindex**（MCP `reindex_style_presets`
> 或 `POST /api/style-presets/reindex`）重建索引；`index.json` 不存在時讀取路徑會自動重建。
> `validate_style_presets` 會回報 index 與 detail 檔的漂移。

> **多 LoRA**：preset 可用 `loras: [{name, strength_model, strength_clip?}]`（取代單一 `lora`，
> 優先生效）；compose 會帶成 `generation.loras`，生圖時依模板內 `LoraLoader` 節點的出現順序逐一
>對應（第 i 個 lora → 第 i 個 loader），`strength_clip` 省略時沿用 `strength_model`。模板需含足夠
> 的 LoraLoader 節點（能力標 `multi_lora`）。

> **建立 preset**：agent 可用 MCP `create_style_preset(id, name, …)`（或 `POST /api/style-presets/`）
> 依描述一次建立**機器食譜 + 人類 note**（note frontmatter `preset_id` 自動對齊）並 reindex；
> id 重複預設不覆寫（需 `overwrite=true`），缺資源會回報但不阻擋建立。

## 規則

- **同一個穩定的 kebab-case `preset_id`** 必須在三處一致：`agent/catalog.json` 的 `id`、
  human note 的檔名、note frontmatter 的 `preset_id`。
- `agent/catalog.json` 只放機器要的結構化資料（資源檔名、生成預設、profiles），保持精簡、可自動解析。
- 創作者來源、授權、試驗心得、範例 prompt 等散文放 `human/<preset-id>.md`。
- preset 的 `note_path` 以 **專案根目錄相對路徑** 指向 human note（例：`style_presets/human/creator-a.md`）；
  `validate_style_presets` 會檢查該檔存在且 frontmatter `preset_id` 與 catalog `id` 一致。

## 程式進入點

- 後端讀取路徑：`backend/app/core/style_presets.py` 的 `DEFAULT_CATALOG_PATH`
  （= `style_presets/agent/catalog.json`）。
- API：`GET/POST /api/style-presets`（list / `{id}` / validate / `{id}/compose`）。
- MCP tool：`list_style_presets` / `get_style_preset` / `validate_style_presets` / `compose_style_preset`。
- 行為規格：`openspec/specs/style-preset-catalog/spec.md`。
