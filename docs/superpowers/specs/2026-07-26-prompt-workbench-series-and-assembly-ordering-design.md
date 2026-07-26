# Prompt Workbench：品質詞系列標註 · 推薦組裝排序 · 分類分區檢視

> 設計日期：2026-07-26
> 狀態：待實作（brainstorming 已核准）

## 背景與問題

Prompt Workbench（`frontend/src/components/prompt-library/`）目前有兩個痛點：

1. **品質詞分不出系列**。[quality-ratings.json](../../../prompt_library/positive/quality-ratings.json) 裡「傑作」出現 4 次（Illustrious / NoobAI / Anima / SD1.5），`name_zh` 完全相同，在台上無從分辨要用哪個系列。系列資訊目前只藏在 `aliases[0]`、`id` 前綴與 `keywords`，畫面不顯示。

2. **組裝順序全靠手動、最終文字要逐段看**。台上每個 polarity 是一串扁平片段，順序＝加入順序，只能用「上移／下移」手動調（[PromptComposerPanel.tsx](../../../frontend/src/components/prompt-library/PromptComposerPanel.tsx)）。後端 [`PromptComposer`](../../../backend/app/core/prompt_composer.py) 完全照前端送來的 `order` 排、再 `_renumber`，不套用任何推薦排序。最終文字是單一 textarea，沒有分類分區，要一段一段看才知道各類選了什麼。

Prompt 組裝有經驗法則（品質詞在前、主體/外觀早段、場景/背景後段……，詳見排序依據），使用者希望「組裝好的 prompt 本身就照推薦規則排好，除非手動調整」，並希望能一眼看到每個分類各選了哪些。

## 設計原則

- **輕量、資料驅動、不改輸出**：送 ComfyUI 的最終逗號字串在本次所有變更後**逐字不變**。
- **後端零改動**：`PromptComposer` 本來就照前端 `order` 排序，排序邏輯全放前端；系列標註與排序值是純 JSON 資料編輯。
- **comma-atomic 不變式維持**：最終文字 textarea 仍是唯一 raw 逗號字串，分類分區只是其上的檢視層。

---

## 範圍一：Task 1 — 品質詞補家族後綴（純資料）

### 做什麼

只改 [`prompt_library/positive/quality-ratings.json`](../../../prompt_library/positive/quality-ratings.json) 裡的**品質詞** `name_zh`，加上全形括號家族後綴。家族取自各詞條既有的 `aliases[0]`。

| 詞條 id 前綴 | 現在 name_zh | 改成 |
|---|---|---|
| `pony-quality-*` | 評分九 / 評分八以上 / 評分七以上 / 動漫來源 | 評分九（Pony）… |
| `illustrious-quality-*` | 傑作 / 最佳品質 / 驚艷品質 / 超高解析度 | 傑作（Illustrious）… |
| `noobai-quality-*` | 傑作 / 最佳品質 / 最新風格 / 超高解析度 / 高解析度 | 傑作（NoobAI）… |
| `anima-quality-*` | 傑作 / 最佳品質 / 高度美感 | 傑作（Anima）… |
| `sd1-5-quality-*` | 傑作 / 最佳品質 | 傑作（SD1.5）… |

### 不做什麼

- **分級詞（`*-rating-*`）不動**：它們的 `name_zh` 本來就有系列（如「Illustrious 分級：普遍」）。
- **不另造「SDXL」通用標**：站上實際家族是 Pony / Illustrious / NoobAI（皆 SDXL 系），照真實家族名標較精確。
- **其他分類不碰**：本次只做 `quality-ratings`。

### 安全性

- `name_zh` **不是** prompt snapshot 的一部分（fragment snapshot 只存 `prompt`）。改 `name_zh` 不影響任何已存組合的生圖結果，也不會觸發 `_resolve` 的 snapshot repair（該檢查只比對 `prompt` 與 `revision`）。
- 修改後將 category `revision`（現為 22）遞增，維持與 API 樂觀鎖語意一致。
- 每個 `PromptEntry` 仍須通過既有嚴格驗證（`name_zh` min_length ≥ 1；`prompt` 不含逗號）。本次只動 `name_zh`，不受逗號原子化規則影響。

---

## 範圍二：Task 2a — 推薦組裝排序 + 手動優先

### 排序依據（資料驅動）

片段排序鍵，由前到後：

1. **分類 `order`**（entry 片段用 `source.categoryId` 對到分類；literal 無分類 → 視為最大，排最後）
2. **分類內 entry `order`**
3. **加入順序**（穩定 tie-break；literal 之間亦依此保序）

分類 `order` 與 entry `order` 皆為既有欄位，可在「分類管理」UI 調整，不需改程式。

### 推薦分類順序（調整 `order` 值）

依 Pony / Illustrious / Animagine 官方與主流社群指南（見文末參考），把 positive 分類 `order` 調成下列順序（實作時給定明確整數，間距 10 以利日後插入）。三系列一致：主體/外觀最前段（品質之後）、場景/背景放後段、光影效果殿後。

| 順位 | 分類 | id | 現在 order | 新 order | 依據 |
|---|---|---|---|---|---|
| 1 | 品質與分級 | quality-ratings | 10 | 10 | Pony 必須前置＋社群多數前置；純 Animagine 想放最後可手動下移 |
| 2 | 人物與身形 | body-appearance | 200 | 20 | 主體/外觀最前段（三系列一致） |
| 3 | 服裝 | clothing | 210 | 30 | 外觀後接服裝 |
| 4 | 內衣褲 | underwear | 220 | 40 | 同上 |
| 5 | 配件 | accessories | 230 | 50 | 同上 |
| 6 | 表情 | expressions | 280 | 60 | 角色狀態中段 |
| 7 | 姿勢與體位 | poses | 260 | 70 | 中段 |
| 8 | 動作與互動 | actions-interactions | 270 | 80 | 中段 |
| 9 | 場景與氛圍 | environment | 240 | 90 | 場景/背景放後段（研究一致，非靠前） |
| 10 | 鏡頭與構圖 | camera-composition | 250 | 100 | Illustrious 構圖與背景同段偏後 |
| 11 | 身體效果 | physical-effects | 290 | 110 | 光影/效果殿後 |

「特定主題靠前」不設預設，交由使用者手動調整（見手動優先）。

（negative 只有 `base-negative`，順序無意義，不動。）

改 category `order` 同樣遞增各檔 `revision`。此為顯示與組裝排序用途，不影響已存組合的既存 fragment 順序（見下）。

### 手動優先（auto / manual 狀態機）

每個 polarity 面板持有一個排列模式狀態：

- **新建空白 → `auto`**：每次 `addEntry` / `addLiteral` 後，整段依排序鍵重排。
- **首次手動移動（上移／下移）→ 切 `manual`**：之後加入的片段只接在尾端，不再自動重排。
- **「重新套用推薦排序」按鈕**：按下 → 依排序鍵重排並切回 `auto`。
- **載入已存組合 → `manual`**：尊重存檔時的既定 fragment 順序，不偷偷重排（存檔的 `order` 是刻意的）。

狀態存於 `PromptWorkbench` 的 React state，隨 polarity 各自獨立；不持久化到後端。

### 排序在哪裡執行

純前端。`compositionState.ts` 新增純函式：

```
sortFragmentsByRecommendation(
  state: CompositionState,
  rankOf: (fragment: WorkbenchFragment) => number,   // 由 categoryId → 分類 order 映射；literal → +∞
): CompositionState
```

- 用穩定排序，保留同 rank 的相對加入序。
- 產生新 fragments 陣列後走既有 `rebuild()`，確保 `text` / `range` / `renderedRaw` 一致。
- `serializeFragments` 已依陣列位置寫 `order = (index+1)*10`，後端照收；因此重排後送出的 `order` 即為新順序，`PromptComposer._renumber` 照樣運作。**後端不需改。**

分類 rank 映射：`PromptWorkbench` 已載入所有分類（catalog + 逐一 GET），新增 `categoryRankByRef: Map<"polarity/categoryId", order>`，傳入面板。

---

## 範圍三：Task 2b — 最終文字分類分區（純檢視）

### 做什麼

在每個 polarity 面板，把**已選片段卡片依分類分組**，各組一個標題列。分組鍵：entry 片段用 `source.categoryId` → 分類 `name_zh`；literal / 手動編輯過的片段 → 「自訂文字」組。

版面示意：

```
Positive Prompt                                   （N 個片段）
 ── 品質與分級 ─────────────────────────
    [傑作（Illustrious）]  [score_9]
 ── 場景與氛圍 ─────────────────────────
    [rooftop]  [sunset]
 ── 動作與互動 ─────────────────────────
    [hugging]  [running]
 ── 自訂文字 ───────────────────────────
    [my custom tag]

 最終文字（textarea，維持單一 raw 逗號字串，不變）
```

- 每張卡片保留既有的內容編輯／權重／上移下移／刪除功能。
- 組的顯示順序 = 分類 `order`（與 2a 排序一致）；「自訂文字」組排最後。
- 底下「最終文字」textarea **完全維持原狀**（controlled raw text、comma-atomic 不變式），送 ComfyUI 的字串逐字不變。分組只是卡片區的檢視。

### 分頁調整

現行卡片區是整段 6/頁分頁。改為分類分組後：

- 分頁改為**在組內**分頁，或（較簡單）移除分頁改為各組自然展開。決策：**移除全域分頁，各組自然展開**（片段總數通常不致過多；若某組過長，卡片區本就可捲動）。實作時保留 `data-testid="prompt-option-grid"` 等測試掛鉤所需選擇器語意，必要時更新對應測試。

### 動作衝突警告

**不做**。分類分區本身已讓使用者一眼看到動作類選了哪些，衝突與否由使用者自行判斷（甚至可能刻意要衝突效果）。系統不加任何警告或限制。

---

## 資料流與元件邊界

```
PromptWorkbench (state: positive/negative CompositionState,
                 positiveArrangement/negativeArrangement: "auto"|"manual",
                 categoryRankByRef, categoryNameByRef)
  │  addEntry/addLiteral → 若該 lane 為 auto，append 後呼叫 sortFragmentsByRecommendation
  │  onMove → 切該 lane 為 manual（既有 moveFragment）
  │  onReapplySort → sortFragmentsByRecommendation + 切 auto
  ▼
PromptOverview (透傳)
  ▼
PromptComposerPanel (依 categoryNameByRef 把 fragments 分組渲染；
                     顯示「重新套用推薦排序」按鈕；最終文字 textarea 不變)
```

- `compositionState.ts`：新增 `sortFragmentsByRecommendation`（純函式、可獨立測）與一個把 fragments 依 categoryId 分組的 `groupFragmentsByCategory` helper（供面板使用，回傳 `{ categoryId | null, displayName, fragments }[]`，順序依 rank）。
- 元件邊界不變：面板仍只透過既有 `PanelActions` 回呼與 `CompositionState` 溝通，新增 `onReapplySort` 一個回呼與 `categoryNameByRef` / `categoryRankByRef` 兩個唯讀 prop。

## 測試

- **前端 vitest**
  - `sortFragmentsByRecommendation`：多分類混合、literal 排尾、同分類保加入序、穩定性。
  - auto/manual 狀態機：新增觸發重排；手動移動後新增只接尾端；重新套用按鈕重排並回 auto；載入組合維持 manual。
  - `groupFragmentsByCategory`：分組正確、組序依 rank、literal 歸「自訂文字」、空狀態。
  - 面板渲染：分組標題出現、最終文字 textarea 值不因分組改變。
  - 既有 `PromptComposerPanel.test.tsx` / `PromptWorkbench.test.tsx` 因版面調整需更新斷言。
- **資料驗證**（後端既有）：改完 `quality-ratings.json` 與各分類 `order` 後，跑 backend prompt-library 測試確認全部檔案通過 `PromptCategory` / `PromptEntry` 嚴格驗證。
- **回歸**：`tsc --noEmit`、Vite production build、`git diff --check`。

## 明確不做（YAGNI）

- 不動後端 `PromptComposer` 或任何 API／schema。
- 不新增 `model_series` 結構化欄位（改採 `name_zh` 後綴）。
- 不做動作衝突警告或任何選詞限制。
- 不把推薦排序模板搬到後端／config（先前端常數＋既有 `order` 欄位即可）。
- 不改 MCP 工具。

## 未決／待實作時確認

- 各分類新 `order` 整數值以上表為準；若使用者另有「特定主題靠前」清單，於實作前併入。

## 排序參考來源

推薦順序綜合下列各系列官方與主流指南（2026-07 查證）：

- Pony Diffusion：[Stable Diffusion Art — Pony prompt tags](https://stable-diffusion-art.com/pony-diffusion-prompt-tags/)、[anakin.ai Pony prompt guide](http://anakin.ai/blog/pony-diffusion-prompt-guide/)（score/rating 前置；場景/背景靠後）。
- Illustrious / Animagine：[kazumu 順序專文](https://note.com/kazumu/n/n6390a899bdce?hl=en)、[Animagine XL 4.0 官方優化指南](https://cagliostrolab.net/posts/optimizing-animagine-xl-40-in-depth-guideline-and-update)（主體→角色→rating→容姿→服裝/構圖/背景→品質；品質可置後）。
- NoobAI / Illustrious 社群：[SeaArt Illustrious 指南](https://www.seaart.ai/articleDetail/d182mq5e878c73cnnbo0)、[SeaArt NoobAI 指南](https://docs.seaart.ai/guide-1/6-permanent-events/high-quality-models-recommendation/noobai-xl)（主體/外觀早段、品質詞多前置）。

分歧點：品質詞前置（Pony／社群）vs 置後（Illustrious／Animagine 官方最新）。本設計預設前置（最不易因 77 token 截斷被切、且 Pony 硬性要求），需置後時由使用者手動下移「品質與分級」整組。
