# Style Presets

創作者／風格「食譜」目錄。以 **agent（機器）** 與 **human（人類）** 兩個子資料夾分開，
但同屬一個 `style_presets/` 目錄：

```
style_presets/
├── agent/            # 機器可讀來源（後端與 MCP 實際讀取）
│   └── catalog.json  # 執行期唯一真相：每個 preset 的 id / 資源 / prompt / params / profiles
└── human/            # 人類筆記（不被程式解析）
    ├── _template.md  # 撰寫範本
    └── <preset-id>.md
```

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
