# Prompt Workbench 系列標註 · 推薦排序 · 分類分區 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 Prompt Workbench 的品質詞可辨識系列、組裝時自動照推薦順序排列（可手動覆蓋）、並把已選片段依分類分組檢視，且送 ComfyUI 的字串逐字不變。

**Architecture:** 純前端邏輯 + 純 JSON 資料編輯，後端 `PromptComposer` 與所有 API/schema 不動。排序在前端 `compositionState.ts` 以純函式完成，`serializeFragments` 依陣列位置寫 `order`，後端照收。分類分區是卡片區的檢視層，最終文字 textarea 維持單一 raw 逗號字串。

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind（前端，vitest 測試）；Python 3.11 + Pydantic（後端資料驗證）。

## Global Constraints

- **輸出不變**：本 plan 所有變更後，送 ComfyUI 的 positive/negative 最終字串逐字不變；`GenerationPanel` 讀 `positive.text` / `negative.text` 不受影響。
- **後端零程式改動**：只改 `prompt_library/` 下 JSON 資料；不改 `backend/app/**`、不改 MCP、不改 API/schema。
- **comma-atomic 不變式**：最終文字 textarea 仍是唯一 raw 逗號字串；每個 ASCII 逗號＝一個 prompt。
- **系列標法**：照資料裡 `aliases[0]` 的實際家族名（Pony / Illustrious / NoobAI / Anima / SD1.5），全形括號後綴 `（家族）`，不另造「SDXL」通用標。
- **驗證指令**（前端）：`cd frontend && npx vitest run <file>`、`npx tsc --noEmit`、`npm run build`。

---

## File Structure

| 檔案 | 責任 | 動作 |
|---|---|---|
| `prompt_library/positive/quality-ratings.json` | 品質詞 `name_zh` 補家族後綴、bump revision | Modify（Task 1） |
| `prompt_library/positive/*.json`（10 檔） | 分類 `order` 調成推薦順序、bump revision | Modify（Task 2） |
| `frontend/src/components/prompt-library/compositionState.ts` | 新增 `sortFragmentsByRecommendation`、`groupFragmentsByCategory`、`FragmentGroup` | Modify（Task 3） |
| `frontend/src/components/prompt-library/compositionState.test.ts` | 上述純函式測試 | Modify（Task 3） |
| `frontend/src/components/prompt-library/PromptComposerPanel.tsx` | 分類分組渲染、重新套用排序按鈕；移除全域分頁 | Rewrite（Task 4） |
| `frontend/src/components/prompt-library/PromptComposerPanel.test.tsx` | 分組/按鈕/最終文字不變 測試 | Modify（Task 4） |
| `frontend/src/components/prompt-library/PromptOverview.tsx` | 透傳新 props | Modify（Task 5） |
| `frontend/src/components/prompt-library/PromptWorkbench.tsx` | 建 category rank/name 映射、auto/manual 狀態、加入時自動排序、onReapplySort | Modify（Task 5） |
| `frontend/src/components/prompt-library/PromptWorkbench.test.tsx` | 自動排序 + 手動優先 整合測試 | Modify（Task 5） |

---

## Task 1: 品質詞 `name_zh` 補家族後綴（資料）

**Files:**
- Modify: `prompt_library/positive/quality-ratings.json`

**Interfaces:**
- Consumes: 無。
- Produces: 18 個品質詞 entry 的 `name_zh` 帶家族後綴；category `revision` 22 → 23。前端 Task 4/5 靠 `name_zh` 顯示可辨識名稱。

目標對照（其餘 rating 詞不動）：

| entry id | 新 name_zh |
|---|---|
| pony-quality-score-9-88364ce6 | 評分九（Pony） |
| pony-quality-score-8-up-00f075e5 | 評分八以上（Pony） |
| pony-quality-score-7-up-64eefb3e | 評分七以上（Pony） |
| pony-quality-source-anime-7e53856d | 動漫來源（Pony） |
| illustrious-quality-masterpiece-905adc41 | 傑作（Illustrious） |
| illustrious-quality-best-quality-94d0f8f7 | 最佳品質（Illustrious） |
| illustrious-quality-amazing-quality-bd0b636a | 驚艷品質（Illustrious） |
| illustrious-quality-absurdres-d8cdf00b | 超高解析度（Illustrious） |
| noobai-quality-masterpiece-6812d6c3 | 傑作（NoobAI） |
| noobai-quality-best-quality-f5173132 | 最佳品質（NoobAI） |
| noobai-quality-newest-3e8f4562 | 最新風格（NoobAI） |
| noobai-quality-absurdres-8a4ddaf1 | 超高解析度（NoobAI） |
| noobai-quality-highres-b2fe9ee7 | 高解析度（NoobAI） |
| anima-quality-masterpiece-5d3c18a5 | 傑作（Anima） |
| anima-quality-best-quality-b870f8e8 | 最佳品質（Anima） |
| anima-quality-very-aesthetic-caea0057 | 高度美感（Anima） |
| sd1-5-quality-masterpiece-934c50a1 | 傑作（SD1.5） |
| sd1-5-quality-best-quality-7064319a | 最佳品質（SD1.5） |

- [ ] **Step 1: 寫套用腳本並執行**

以 id → 後綴映射改 `name_zh`、bump revision，保留其餘欄位。存成 `scratch_task1.py` 並執行：

```python
# scratch_task1.py
import json, io

PATH = "prompt_library/positive/quality-ratings.json"
FAMILY = {
    "pony-quality-score-9-88364ce6": "Pony",
    "pony-quality-score-8-up-00f075e5": "Pony",
    "pony-quality-score-7-up-64eefb3e": "Pony",
    "pony-quality-source-anime-7e53856d": "Pony",
    "illustrious-quality-masterpiece-905adc41": "Illustrious",
    "illustrious-quality-best-quality-94d0f8f7": "Illustrious",
    "illustrious-quality-amazing-quality-bd0b636a": "Illustrious",
    "illustrious-quality-absurdres-d8cdf00b": "Illustrious",
    "noobai-quality-masterpiece-6812d6c3": "NoobAI",
    "noobai-quality-best-quality-f5173132": "NoobAI",
    "noobai-quality-newest-3e8f4562": "NoobAI",
    "noobai-quality-absurdres-8a4ddaf1": "NoobAI",
    "noobai-quality-highres-b2fe9ee7": "NoobAI",
    "anima-quality-masterpiece-5d3c18a5": "Anima",
    "anima-quality-best-quality-b870f8e8": "Anima",
    "anima-quality-very-aesthetic-caea0057": "Anima",
    "sd1-5-quality-masterpiece-934c50a1": "SD1.5",
    "sd1-5-quality-best-quality-7064319a": "SD1.5",
}

with io.open(PATH, encoding="utf-8") as handle:
    data = json.load(handle)

changed = 0
for entry in data["entries"]:
    family = FAMILY.get(entry["id"])
    if not family:
        continue
    suffix = f"（{family}）"
    if not entry["name_zh"].endswith(suffix):
        entry["name_zh"] = f"{entry['name_zh']}{suffix}"
        changed += 1

assert changed == 18, f"expected 18 changes, got {changed}"
data["revision"] = 23

with io.open(PATH, "w", encoding="utf-8", newline="\n") as handle:
    json.dump(data, handle, ensure_ascii=False, indent=2)
    handle.write("\n")

print("updated", changed, "entries; revision ->", data["revision"])
```

Run:
```bash
export PYTHONUTF8=1 && python scratch_task1.py
```
Expected: `updated 18 entries; revision -> 23`

- [ ] **Step 2: 驗證檔案仍通過嚴格 schema 且後綴正確**

Run:
```bash
export PYTHONUTF8=1 PYTHONPATH=backend && python -c "
import json
from app.core.prompt_library_models import PromptCategory
d = json.load(open('prompt_library/positive/quality-ratings.json', encoding='utf-8'))
cat = PromptCategory.model_validate(d)
names = {e.id: e.name_zh for e in cat.entries}
assert names['illustrious-quality-masterpiece-905adc41'] == '傑作（Illustrious）', names['illustrious-quality-masterpiece-905adc41']
assert names['anima-quality-masterpiece-5d3c18a5'] == '傑作（Anima）'
assert names['sd1-5-quality-best-quality-7064319a'] == '最佳品質（SD1.5）'
assert names['pony-quality-score-9-88364ce6'] == '評分九（Pony）'
assert names['pony-rating-safe'] == 'Pony 分級：普遍'  # rating 未變
assert cat.revision == 23
print('OK', cat.revision)
"
```
Expected: `OK 23`

- [ ] **Step 3: 檢查 diff 只動 name_zh 與 revision**

Run:
```bash
git diff --stat prompt_library/positive/quality-ratings.json && git diff prompt_library/positive/quality-ratings.json | grep '^[+-]' | grep -v '^[+-][+-]' | grep -viE 'name_zh|"revision"' | head
```
Expected：第二段（列出非 name_zh/revision 的增刪行）**沒有輸出**。若有輸出代表 json 重排了格式，檢視是否可接受（值不變即可）。

- [ ] **Step 4: 清理腳本並 commit**

```bash
rm scratch_task1.py
git add prompt_library/positive/quality-ratings.json
git commit -m "data(prompt-library): suffix model family onto quality-word name_zh"
```

---

## Task 2: 分類 `order` 調成推薦順序（資料）

**Files:**
- Modify: `prompt_library/positive/environment.json`, `body-appearance.json`, `expressions.json`, `poses.json`, `actions-interactions.json`, `clothing.json`, `underwear.json`, `accessories.json`, `camera-composition.json`, `physical-effects.json`

**Interfaces:**
- Consumes: 無。
- Produces: 各 positive 分類 top-level `order` 為推薦值；改動的檔 `revision` +1。前端 Task 5 的 `rankOf` 靠這些 `order` 排序。

推薦值（`quality-ratings` 維持 10，不改）：

| id | 新 order |
|---|---|
| environment | 20 |
| body-appearance | 30 |
| expressions | 40 |
| poses | 50 |
| actions-interactions | 60 |
| clothing | 70 |
| underwear | 80 |
| accessories | 90 |
| camera-composition | 100 |
| physical-effects | 110 |

- [ ] **Step 1: 寫套用腳本並執行**

```python
# scratch_task2.py
import json, io

ORDERS = {
    "environment": 20,
    "body-appearance": 30,
    "expressions": 40,
    "poses": 50,
    "actions-interactions": 60,
    "clothing": 70,
    "underwear": 80,
    "accessories": 90,
    "camera-composition": 100,
    "physical-effects": 110,
}

for cid, new_order in ORDERS.items():
    path = f"prompt_library/positive/{cid}.json"
    with io.open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["id"] == cid, (data["id"], cid)
    if data["order"] != new_order:
        data["order"] = new_order
        data["revision"] = data["revision"] + 1
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"{cid}: order={data['order']} revision={data['revision']}")
```

Run:
```bash
export PYTHONUTF8=1 && python scratch_task2.py
```
Expected: 十行，每行顯示對應 order（如 `environment: order=20 ...`）。

- [ ] **Step 2: 驗證全部 positive 分類仍通過 schema 且 order 為推薦序**

Run:
```bash
export PYTHONUTF8=1 PYTHONPATH=backend && python -c "
import json, glob
from app.core.prompt_library_models import PromptCategory
expected = {'quality-ratings':10,'environment':20,'body-appearance':30,'expressions':40,'poses':50,
            'actions-interactions':60,'clothing':70,'underwear':80,'accessories':90,
            'camera-composition':100,'physical-effects':110}
got = {}
for path in glob.glob('prompt_library/positive/*.json'):
    cat = PromptCategory.model_validate(json.load(open(path, encoding='utf-8')))
    got[cat.id] = cat.order
for cid, order in expected.items():
    assert got[cid] == order, (cid, got.get(cid), order)
print('OK', sorted(got.items(), key=lambda kv: kv[1]))
"
```
Expected: `OK [('quality-ratings', 10), ('environment', 20), ...]` 依序遞增。

- [ ] **Step 3: 清理腳本並 commit**

```bash
rm scratch_task2.py
git add prompt_library/positive/*.json
git commit -m "data(prompt-library): recommended category order (scene-forward)"
```

---

## Task 3: `compositionState` 排序與分組純函式（TDD）

**Files:**
- Modify: `frontend/src/components/prompt-library/compositionState.ts`
- Test: `frontend/src/components/prompt-library/compositionState.test.ts`

**Interfaces:**
- Consumes: 既有 `CompositionState`、`WorkbenchFragment`、module 內私有 `rebuild`。
- Produces:
  - `sortFragmentsByRecommendation(state: CompositionState, rankOf: (fragment: WorkbenchFragment) => number): CompositionState`
  - `interface FragmentGroup { key: string; displayName: string; order: number; fragments: WorkbenchFragment[] }`
  - `groupFragmentsByCategory(fragments: readonly WorkbenchFragment[], categoryInfoOf: (fragment: WorkbenchFragment) => { key: string; displayName: string; order: number } | null, literalLabel?: string): FragmentGroup[]`

- [ ] **Step 1: 寫失敗測試**

在 `compositionState.test.ts` 末尾（最後一個 `});` 之前的檔案結尾處）新增。先在頂部 import 補上三個新符號：把現有 import 區塊的 `serializeFragments,` 之後加入

```ts
  serializeFragments,
  sortFragmentsByRecommendation,
  groupFragmentsByCategory,
```

檔案末尾新增測試：

```ts
describe("sortFragmentsByRecommendation", () => {
  const ids = sequentialIds("s");
  const entryFrag = (categoryId: string, entryId: string) => ({
    id: ids(),
    kind: "entry" as const,
    displayName: entryId,
    source: { polarity: "positive" as const, categoryId, entryId, revision: 1 },
    sourceSnapshotRaw: entryId,
    snapshotRaw: entryId,
    weight: "",
  });

  // 分類 rank：environment=20, quality=10；entry order 忽略時同 rank
  const rankOf = (fragment: { kind: string; source?: { categoryId: string } }): number => {
    if (fragment.kind !== "entry" || !fragment.source) return Number.POSITIVE_INFINITY;
    return { "quality-ratings": 10, environment: 20, actions: 60 }[fragment.source.categoryId] ?? Infinity;
  };

  it("sorts entries by category rank and pushes literals last, stably", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("actions", "hug"));
    state = appendLiteralText(state, "custom tag", ids);
    state = appendFragment(state, entryFrag("quality-ratings", "masterpiece"));
    state = appendFragment(state, entryFrag("environment", "rooftop"));

    const sorted = sortFragmentsByRecommendation(state, rankOf);

    expect(sorted.fragments.map((fragment) => fragment.snapshotRaw)).toEqual([
      "masterpiece",
      "rooftop",
      "hug",
      "custom tag",
    ]);
    // 輸出字串仍是逗號串接、與片段順序一致
    expect(sorted.text).toBe("masterpiece,rooftop,hug,custom tag");
  });

  it("keeps original order among same-rank fragments (stable)", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("actions", "first"));
    state = appendFragment(state, entryFrag("actions", "second"));
    const sorted = sortFragmentsByRecommendation(state, rankOf);
    expect(sorted.fragments.map((fragment) => fragment.snapshotRaw)).toEqual(["first", "second"]);
  });
});

describe("groupFragmentsByCategory", () => {
  const ids = sequentialIds("g");
  const entryFrag = (categoryId: string, entryId: string) => ({
    id: ids(),
    kind: "entry" as const,
    displayName: entryId,
    source: { polarity: "positive" as const, categoryId, entryId, revision: 1 },
    sourceSnapshotRaw: entryId,
    snapshotRaw: entryId,
    weight: "",
  });
  const info = (fragment: { kind: string; source?: { categoryId: string } }) => {
    if (fragment.kind !== "entry" || !fragment.source) return null;
    const meta: Record<string, { displayName: string; order: number }> = {
      "quality-ratings": { displayName: "品質與分級", order: 10 },
      environment: { displayName: "場景與氛圍", order: 20 },
    };
    const found = meta[fragment.source.categoryId];
    return found ? { key: fragment.source.categoryId, ...found } : null;
  };

  it("groups by category ordered by rank, literals into 自訂文字 last", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("environment", "rooftop"));
    state = appendLiteralText(state, "custom", ids);
    state = appendFragment(state, entryFrag("quality-ratings", "masterpiece"));
    state = appendFragment(state, entryFrag("environment", "sunset"));

    const groups = groupFragmentsByCategory(state.fragments, info);

    expect(groups.map((group) => group.displayName)).toEqual([
      "品質與分級",
      "場景與氛圍",
      "自訂文字",
    ]);
    expect(groups[1].fragments.map((fragment) => fragment.snapshotRaw)).toEqual(["rooftop", "sunset"]);
    expect(groups[2].key).toBe("__literal__");
  });
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd frontend && npx vitest run src/components/prompt-library/compositionState.test.ts`
Expected: FAIL —「sortFragmentsByRecommendation is not a function / not exported」等。

- [ ] **Step 3: 實作純函式**

在 `compositionState.ts` 末尾新增（`rebuild` 為同檔私有函式，可直接用）：

```ts
export function sortFragmentsByRecommendation(
  state: CompositionState,
  rankOf: (fragment: WorkbenchFragment) => number,
): CompositionState {
  const ranked = state.fragments.map((fragment, index) => ({
    fragment,
    index,
    rank: rankOf(fragment),
  }));
  ranked.sort((left, right) => left.rank - right.rank || left.index - right.index);
  return rebuild(ranked.map((item) => item.fragment));
}

export interface FragmentGroup {
  key: string;
  displayName: string;
  order: number;
  fragments: WorkbenchFragment[];
}

const LITERAL_GROUP_KEY = "__literal__";

export function groupFragmentsByCategory(
  fragments: readonly WorkbenchFragment[],
  categoryInfoOf: (
    fragment: WorkbenchFragment,
  ) => { key: string; displayName: string; order: number } | null,
  literalLabel = "自訂文字",
): FragmentGroup[] {
  const groups = new Map<string, FragmentGroup>();
  fragments.forEach((fragment) => {
    const info = categoryInfoOf(fragment);
    const key = info?.key ?? LITERAL_GROUP_KEY;
    const existing = groups.get(key);
    if (existing) {
      existing.fragments.push(fragment);
      return;
    }
    groups.set(key, {
      key,
      displayName: info?.displayName ?? literalLabel,
      order: info ? info.order : Number.POSITIVE_INFINITY,
      fragments: [fragment],
    });
  });
  return [...groups.values()].sort((left, right) => left.order - right.order);
}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/compositionState.test.ts`
Expected: PASS（含既有測試）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/compositionState.ts frontend/src/components/prompt-library/compositionState.test.ts
git commit -m "feat(prompt-workbench): recommendation sort + category grouping helpers"
```

---

## Task 4: `PromptComposerPanel` 分類分組渲染 + 重新套用排序按鈕

**Files:**
- Rewrite: `frontend/src/components/prompt-library/PromptComposerPanel.tsx`
- Modify: `frontend/src/components/prompt-library/PromptComposerPanel.test.tsx`

**Interfaces:**
- Consumes: `sortFragmentsByRecommendation` 不直接用；用 `groupFragmentsByCategory`、`WorkbenchFragment`、`CompositionState`。
- Produces: `PromptComposerPanel` 新增必填 props：
  - `arrangement: "auto" | "manual"`
  - `categoryInfoOf: (fragment: WorkbenchFragment) => { key: string; displayName: string; order: number } | null`
  - `onReapplySort: () => void`
  既有 props（`title`、`state`、`onFinalTextChange`、`onTextChange`、`onWeightChange`、`onMove`、`onRemove`）不變。

- [ ] **Step 1: 全檔改寫**

用以下內容整檔取代 `PromptComposerPanel.tsx`（移除全域分頁；卡片依分類分組；每張卡片以 `state.fragments.indexOf(fragment)` 取全域位置維持「第 N 段」與上/下移；最終文字 textarea 與 selection 保留邏輯不動）：

```tsx
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CompositionState, WorkbenchFragment } from "./compositionState";
import { groupFragmentsByCategory } from "./compositionState";

interface Props {
  title: "Positive Prompt" | "Negative Prompt";
  state: CompositionState;
  arrangement: "auto" | "manual";
  categoryInfoOf: (
    fragment: WorkbenchFragment,
  ) => { key: string; displayName: string; order: number } | null;
  onReapplySort: () => void;
  onFinalTextChange: (text: string) => void;
  onTextChange: (id: string, text: string) => void;
  onWeightChange: (id: string, weight: string) => void;
  onMove: (id: string, direction: -1 | 1) => void;
  onRemove: (id: string) => void;
}

export default function PromptComposerPanel({
  title,
  state,
  arrangement,
  categoryInfoOf,
  onReapplySort,
  onFinalTextChange,
  onTextChange,
  onWeightChange,
  onMove,
  onRemove,
}: Props) {
  const polarity = title === "Positive Prompt" ? "positive" : "negative";
  const [pendingCardFocus, setPendingCardFocus] = useState<number | null>(null);
  const finalTextarea = useRef<HTMLTextAreaElement>(null);
  const pendingSelection = useRef<{
    start: number;
    end: number;
    direction: "forward" | "backward" | "none";
  } | null>(null);

  useEffect(() => {
    const focusInvalid = (event: Event) => {
      const detail = (event as CustomEvent<{ polarity: string; position: number }>).detail;
      if (detail.polarity !== polarity) return;
      setPendingCardFocus(detail.position);
    };
    window.addEventListener("prompt-workbench-focus", focusInvalid);
    return () => window.removeEventListener("prompt-workbench-focus", focusInvalid);
  }, [polarity]);

  useLayoutEffect(() => {
    if (pendingCardFocus === null) return;
    const selector = `textarea[data-polarity="${polarity}"][data-segment-position="${pendingCardFocus}"]`;
    document.querySelector<HTMLTextAreaElement>(selector)?.focus();
    setPendingCardFocus(null);
  }, [pendingCardFocus, polarity, state.fragments]);

  useLayoutEffect(() => {
    const selection = pendingSelection.current;
    const textarea = finalTextarea.current;
    if (!selection || !textarea || document.activeElement !== textarea) return;
    const clamp = (value: number) => Math.min(value, textarea.value.length);
    textarea.setSelectionRange(clamp(selection.start), clamp(selection.end), selection.direction);
    pendingSelection.current = null;
  }, [state.text, state.fragments]);

  const groups = groupFragmentsByCategory(state.fragments, categoryInfoOf);

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="mt-1 text-xs text-slate-500">依分類分區檢視 · 最終文字</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-slate-800 px-2 py-1 text-xs text-slate-400">
            {state.fragments.length} 個片段
          </span>
          <span
            className={`rounded-full px-2 py-1 text-xs ${
              arrangement === "auto" ? "bg-emerald-900/60 text-emerald-300" : "bg-slate-800 text-slate-400"
            }`}
          >
            {arrangement === "auto" ? "已自動排序" : "手動排序"}
          </span>
          <button
            type="button"
            aria-label={`${title} 重新套用推薦排序`}
            onClick={onReapplySort}
            className="rounded-md bg-sky-700 px-2 py-1 text-xs text-white"
          >
            重新套用推薦排序
          </button>
        </div>
      </div>

      <div data-testid="prompt-option-grid" className="mt-3 space-y-4">
        {state.fragments.length === 0 && (
          <p className="rounded-lg border border-dashed border-slate-700 p-3 text-sm text-slate-500">尚未加入 Prompt</p>
        )}
        {groups.map((group) => (
          <div key={group.key} data-testid={`prompt-group-${group.key}`}>
            <h4 className="mb-2 border-b border-slate-700 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
              {group.displayName}
              <span className="ml-2 text-slate-500">{group.fragments.length}</span>
            </h4>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {group.fragments.map((fragment) => {
                const index = state.fragments.indexOf(fragment);
                const label = fragment.displayName;
                const invalid = fragment.snapshotRaw.trim() === "" || fragment.renderedRaw.trim() === "";
                return (
                  <div
                    key={fragment.id}
                    className={`rounded-lg border bg-slate-800/70 p-3 ${invalid ? "border-red-500" : "border-slate-700"}`}
                  >
                    <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200">
                      <span>{label}</span>
                      <span className="text-xs text-slate-500">第 {index + 1} 段</span>
                      {invalid && (
                        <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-xs text-red-300">必須填寫</span>
                      )}
                    </div>
                    <label className="block text-xs text-slate-400">內容
                      <textarea
                        data-polarity={polarity}
                        data-segment-position={index + 1}
                        aria-invalid={invalid}
                        aria-label={`${label} 內容`}
                        value={fragment.snapshotRaw}
                        onChange={(event) => onTextChange(fragment.id, event.target.value)}
                        className="mt-1 min-h-16 w-full resize-y rounded-md border border-slate-600 bg-slate-950 p-2 text-sm text-white"
                      />
                    </label>
                    <div className="mt-2 flex flex-wrap items-end gap-2">
                      <label className="text-xs text-slate-400">權重
                        <input
                          aria-label={`${label} 權重`}
                          type="number"
                          min="0.01"
                          max="2"
                          step="0.1"
                          placeholder="未設定"
                          value={fragment.weight}
                          onChange={(event) => onWeightChange(fragment.id, event.target.value)}
                          className="mt-1 block w-24 rounded-md border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
                        />
                      </label>
                      <div className="flex w-full justify-between">
                        <div className="flex gap-2">
                          <button
                            type="button"
                            disabled={index === 0}
                            onClick={() => onMove(fragment.id, -1)}
                            className="rounded-md bg-slate-700 px-2 py-1.5 text-xs disabled:opacity-40"
                          >
                            上移
                          </button>
                          <button
                            type="button"
                            disabled={index === state.fragments.length - 1}
                            onClick={() => onMove(fragment.id, 1)}
                            className="rounded-md bg-slate-700 px-2 py-1.5 text-xs disabled:opacity-40"
                          >
                            下移
                          </button>
                        </div>
                        <button
                          type="button"
                          onClick={() => onRemove(fragment.id)}
                          className="rounded-md bg-red-950 px-2 py-1.5 text-xs text-red-300"
                        >
                          刪除
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <label className="mt-4 block text-sm font-medium text-slate-300">最終文字
        <textarea
          ref={finalTextarea}
          aria-label={`${title} 最終文字`}
          value={state.text}
          onChange={(event) => {
            pendingSelection.current = {
              start: event.currentTarget.selectionStart,
              end: event.currentTarget.selectionEnd,
              direction: event.currentTarget.selectionDirection,
            };
            onFinalTextChange(event.currentTarget.value);
          }}
          className="mt-2 min-h-28 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-sm text-slate-100 focus:border-emerald-600 focus:outline-none"
        />
      </label>
      {state.warning && <p className="mt-2 text-xs text-amber-300">{state.warning}</p>}
    </section>
  );
}
```

- [ ] **Step 2: 更新既有測試以符合新 props 與分組版面**

先讀現有測試看它建立 panel 的方式：
Run: `cd frontend && cat src/components/prompt-library/PromptComposerPanel.test.tsx`

修改重點（逐一套用）：
1. 每次 render `<PromptComposerPanel .../>` 補上三個新必填 props：
   ```tsx
   arrangement="auto"
   categoryInfoOf={() => null}
   onReapplySort={() => {}}
   ```
   （`categoryInfoOf={() => null}` 會讓所有片段落入「自訂文字」組，維持既有斷言仍能找到卡片。）
2. **移除任何針對「分頁 / 上一頁 / 下一頁 / 第 N 頁」的斷言**（該功能已移除）。若測試名稱含分頁，改測「所有片段都渲染在同一區、不分頁」。
3. 其餘（內容編輯、權重、上/下移、刪除、最終文字）斷言保留。

- [ ] **Step 3: 新增分組與按鈕測試**

在 `PromptComposerPanel.test.tsx` 末尾新增：

```tsx
it("groups cards by category heading and keeps final text unchanged", () => {
  const state = /* 用檔案內既有 helper 建含 environment+quality 片段的 CompositionState；
     若無 helper，直接組 { fragments:[...], text:"masterpiece,rooftop", warning:null } */;
  const infoOf = (fragment: { source?: { categoryId: string } }) => {
    const meta: Record<string, { displayName: string; order: number }> = {
      "quality-ratings": { displayName: "品質與分級", order: 10 },
      environment: { displayName: "場景與氛圍", order: 20 },
    };
    const found = fragment.source ? meta[fragment.source.categoryId] : undefined;
    return found ? { key: fragment.source!.categoryId, ...found } : null;
  };
  render(
    <PromptComposerPanel
      title="Positive Prompt"
      state={state}
      arrangement="auto"
      categoryInfoOf={infoOf as never}
      onReapplySort={() => {}}
      onFinalTextChange={() => {}}
      onTextChange={() => {}}
      onWeightChange={() => {}}
      onMove={() => {}}
      onRemove={() => {}}
    />,
  );
  expect(screen.getByText("品質與分級")).toBeInTheDocument();
  expect(screen.getByText("場景與氛圍")).toBeInTheDocument();
  expect((screen.getByLabelText("Positive Prompt 最終文字") as HTMLTextAreaElement).value).toBe("masterpiece,rooftop");
});

it("fires onReapplySort when the button is clicked", async () => {
  const onReapplySort = vi.fn();
  render(
    <PromptComposerPanel
      title="Positive Prompt"
      state={{ fragments: [], text: "", warning: null }}
      arrangement="manual"
      categoryInfoOf={() => null}
      onReapplySort={onReapplySort}
      onFinalTextChange={() => {}}
      onTextChange={() => {}}
      onWeightChange={() => {}}
      onMove={() => {}}
      onRemove={() => {}}
    />,
  );
  await userEvent.click(screen.getByLabelText("Positive Prompt 重新套用推薦排序"));
  expect(onReapplySort).toHaveBeenCalledTimes(1);
});
```

> 註：`state` 的建法沿用該測試檔既有慣例（多半直接組 `CompositionState` 物件，或 import compositionState 的 `appendFragment`/`emptyComposition`）。若檔案已 import `render`/`screen`/`userEvent`/`vi` 則沿用；缺哪個就補 import（`@testing-library/react`、`@testing-library/user-event`、`vitest`）。

- [ ] **Step 4: 執行測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/PromptComposerPanel.test.tsx`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/PromptComposerPanel.tsx frontend/src/components/prompt-library/PromptComposerPanel.test.tsx
git commit -m "feat(prompt-workbench): category-grouped card view + reapply-sort button"
```

---

## Task 5: `PromptWorkbench` 串接自動排序 + 手動優先

**Files:**
- Modify: `frontend/src/components/prompt-library/PromptOverview.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`
- Test: `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`

**Interfaces:**
- Consumes: Task 3 的 `sortFragmentsByRecommendation`；Task 4 的 `PromptComposerPanel` 新 props。
- Produces: 加入詞條/自由文字在 `auto` lane 自動排序；上/下移切 `manual`；「重新套用推薦排序」重排並切 `auto`；載入組合為 `manual`、新建空白為 `auto`。輸出字串不變。

- [ ] **Step 1: 更新 `PromptOverview.tsx` 透傳新 props**

整檔取代為：

```tsx
import type { CompositionState, WorkbenchFragment } from "./compositionState";
import PromptComposerPanel from "./PromptComposerPanel";

interface PanelActions {
  onTextChange: (id: string, text: string) => void;
  onWeightChange: (id: string, weight: string) => void;
  onMove: (id: string, direction: -1 | 1) => void;
  onRemove: (id: string) => void;
  onFinalTextChange: (text: string) => void;
  onReapplySort: () => void;
}

interface Props {
  positive: CompositionState;
  negative: CompositionState;
  positiveActions: PanelActions;
  negativeActions: PanelActions;
  positiveArrangement: "auto" | "manual";
  negativeArrangement: "auto" | "manual";
  categoryInfoOf: (
    fragment: WorkbenchFragment,
  ) => { key: string; displayName: string; order: number } | null;
}

export default function PromptOverview({
  positive,
  negative,
  positiveActions,
  negativeActions,
  positiveArrangement,
  negativeArrangement,
  categoryInfoOf,
}: Props) {
  const { onReapplySort: onPositiveReapply, ...positiveRest } = positiveActions;
  const { onReapplySort: onNegativeReapply, ...negativeRest } = negativeActions;
  return (
    <div className="space-y-5">
      <PromptComposerPanel
        title="Positive Prompt"
        state={positive}
        arrangement={positiveArrangement}
        categoryInfoOf={categoryInfoOf}
        onReapplySort={onPositiveReapply}
        {...positiveRest}
      />
      <PromptComposerPanel
        title="Negative Prompt"
        state={negative}
        arrangement={negativeArrangement}
        categoryInfoOf={categoryInfoOf}
        onReapplySort={onNegativeReapply}
        {...negativeRest}
      />
    </div>
  );
}
```

- [ ] **Step 2: `PromptWorkbench.tsx` — import 與新 state**

在頂部 import：把 `compositionState` 的 import 補上 `sortFragmentsByRecommendation`（加在 `serializeFragments,` 附近），並把 React import 改為含 `useCallback`：
```tsx
import { useCallback, useEffect, useRef, useState } from "react";
```
在 `compositionState` 的 import 清單加：
```tsx
  sortFragmentsByRecommendation,
```
在 `PromptWorkbench()` 內、`const [negative, setNegative] = useState<CompositionState>(emptyComposition);` 之後新增：
```tsx
  const [arrangement, setArrangement] = useState<{ positive: "auto" | "manual"; negative: "auto" | "manual" }>({
    positive: "auto",
    negative: "auto",
  });
  const [categoryMeta, setCategoryMeta] = useState<Map<string, { order: number; nameZh: string }>>(new Map());
  const entryOrderByRef = useRef<Map<string, number>>(new Map());
```

- [ ] **Step 3: 在載入 catalog 的 effect 內建立分類 meta 與 entry order 映射**

在既有初始化 effect 內，`setForms(descriptor.items || []);` 之後新增（`catalog.categories` 為 `PromptCategorySummary[]`，含 `order` 與 `name_zh`）：
```tsx
        const meta = new Map<string, { order: number; nameZh: string }>();
        (catalog.categories || []).forEach((item) =>
          meta.set(`${item.polarity}/${item.id}`, { order: item.order, nameZh: item.name_zh }),
        );
        setCategoryMeta(meta);
```
在同 effect 內、既有 `categoryResults.forEach((result) => { ... labelMap ... })` 區塊之後（`labelMap.current = labels;` 之後）新增建立 entry order 映射：
```tsx
          const orders = new Map<string, number>();
          categoryResults.forEach((result) => {
            if (result.status !== "fulfilled") return;
            const cat = result.value.category;
            cat.entries.forEach((entry) => orders.set(`${cat.polarity}/${cat.id}/${entry.id}`, entry.order));
          });
          entryOrderByRef.current = orders;
```

- [ ] **Step 4: 新增 `rankOf` / `categoryInfoOf` / 排序輔助**

在 `nextId` 函式之後新增：
```tsx
  const rankOf = useCallback(
    (fragment: import("./compositionState").WorkbenchFragment): number => {
      if (fragment.kind !== "entry" || !fragment.source) return Number.POSITIVE_INFINITY;
      const catKey = `${fragment.source.polarity}/${fragment.source.categoryId}`;
      const meta = categoryMeta.get(catKey);
      if (!meta) return Number.POSITIVE_INFINITY;
      const entryOrder = entryOrderByRef.current.get(`${catKey}/${fragment.source.entryId}`) ?? 10;
      return meta.order * 100000 + entryOrder;
    },
    [categoryMeta],
  );

  const categoryInfoOf = useCallback(
    (fragment: import("./compositionState").WorkbenchFragment) => {
      if (fragment.kind !== "entry" || !fragment.source) return null;
      const catKey = `${fragment.source.polarity}/${fragment.source.categoryId}`;
      const meta = categoryMeta.get(catKey);
      if (!meta) return null;
      return { key: fragment.source.categoryId, displayName: meta.nameZh, order: meta.order };
    },
    [categoryMeta],
  );
```
> 若偏好，把 `WorkbenchFragment` 加入頂部 `compositionState` 的 type import，改用 `WorkbenchFragment` 取代 inline `import(...)`。

- [ ] **Step 5: 加入時自動排序（改 `addEntry` / `addLiteral`）**

把 `addEntry` 內的：
```tsx
    if (activePolarity === "positive") {
      mutate(setPositive, (state) => appendFragment(state, item));
    } else {
      mutate(setNegative, (state) => appendFragment(state, item));
    }
```
改為：
```tsx
    const setter = activePolarity === "positive" ? setPositive : setNegative;
    mutate(setter, (state) => {
      const appended = appendFragment(state, item);
      return arrangement[activePolarity] === "auto"
        ? sortFragmentsByRecommendation(appended, rankOf)
        : appended;
    });
```
把 `addLiteral` 內的：
```tsx
    if (activePolarity === "positive") {
      mutate(setPositive, append);
    } else {
      mutate(setNegative, append);
    }
```
改為：
```tsx
    const setter = activePolarity === "positive" ? setPositive : setNegative;
    mutate(setter, (state) => {
      const appended = append(state);
      return arrangement[activePolarity] === "auto"
        ? sortFragmentsByRecommendation(appended, rankOf)
        : appended;
    });
```

- [ ] **Step 6: `actions()` 帶 polarity、onMove 切 manual、新增 onReapplySort**

把 `actions` 的簽章與 `onMove` 改成帶 polarity，並加 `onReapplySort`。將：
```tsx
  const actions = (
    setter: React.Dispatch<React.SetStateAction<CompositionState>>,
    state: CompositionState,
  ) => ({
```
改為：
```tsx
  const actions = (
    polarity: PromptPolarity,
    setter: React.Dispatch<React.SetStateAction<CompositionState>>,
  ) => ({
```
把該物件內 `onMove` 改為：
```tsx
    onMove: (id: string, direction: -1 | 1) => {
      mutate(setter, (current) => moveFragment(current, id, direction));
      setArrangement((current) => ({ ...current, [polarity]: "manual" }));
    },
```
在該回傳物件末尾（`onFinalTextChange` 之後）加：
```tsx
    onReapplySort: () => {
      mutate(setter, (current) => sortFragmentsByRecommendation(current, rankOf));
      setArrangement((current) => ({ ...current, [polarity]: "auto" }));
    },
```
（`state` 參數原本未被使用，移除不影響。）

- [ ] **Step 7: 載入 = manual、新建空白 = auto**

在 `installCombination` 內、`setNegative(nextNegative);` 之後新增：
```tsx
    setArrangement({ positive: "manual", negative: "manual" });
```
在 `createBlank` 內、`setNegative(emptyComposition());` 之後新增：
```tsx
    setArrangement({ positive: "auto", negative: "auto" });
```

- [ ] **Step 8: 更新 `PromptOverview` 使用點傳新 props**

把：
```tsx
        <PromptOverview positive={positive} negative={negative} positiveActions={actions(setPositive, positive)} negativeActions={actions(setNegative, negative)} />
```
改為：
```tsx
        <PromptOverview
          positive={positive}
          negative={negative}
          positiveActions={actions("positive", setPositive)}
          negativeActions={actions("negative", setNegative)}
          positiveArrangement={arrangement.positive}
          negativeArrangement={arrangement.negative}
          categoryInfoOf={categoryInfoOf}
        />
```

- [ ] **Step 9: typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: 無錯誤。若報 `WorkbenchFragment` 未 export，於 `compositionState.ts` 確認 `export interface WorkbenchFragment`（本就 export）並在 workbench 頂部 type import 補上。

- [ ] **Step 10: 寫整合測試**

先讀既有測試看其 mock 慣例（`getPromptCatalog`、`getPromptCategory` 通常被 mock）：
Run: `cd frontend && cat src/components/prompt-library/PromptWorkbench.test.tsx`

新增一個測試，驗證「auto lane 加入兩個不同分類詞條 → 最終文字依分類 order 排列」。沿用該檔既有 mock helper 建 catalog（含 `environment` order=20、`quality-ratings` order=10 兩分類，各一 entry）。骨架：

```tsx
it("auto-sorts newly added entries by category order", async () => {
  // 依既有 mock 慣例，讓 getPromptCatalog 回兩個分類，getPromptCategory 回其 entries：
  //   quality-ratings(order 10) -> entry masterpiece(prompt "masterpiece")
  //   environment(order 20)     -> entry rooftop(prompt "rooftop")
  render(<PromptWorkbench />);
  // 等 readiness=ready
  await screen.findByText("Prompt Workbench");
  // 先開 environment 分類、加入 rooftop；再開 quality-ratings、加入 masterpiece
  //   （用既有測試操作分類/加入詞條的方式）
  // 斷言：Positive 最終文字為 "masterpiece,rooftop"（quality 在前，雖後加入）
  const finalText = await screen.findByLabelText("Positive Prompt 最終文字");
  expect((finalText as HTMLTextAreaElement).value).toBe("masterpiece,rooftop");
});
```

> 實作者依該檔既有 mock/操作 helper 補齊註解處。關鍵斷言：**後加入的 quality 詞排在先加入的 environment 詞之前**，證明 auto-sort 生效。若既有測試已有「加入詞條」的 util，直接複用。

- [ ] **Step 11: 執行前端全套測試**

Run: `cd frontend && npx vitest run`
Expected: 全 PASS（含既有 130 條 + 新增）。若既有 `PromptWorkbench.test.tsx` 因 `actions()` 簽章或載入行為改變而失敗，依新行為調整斷言（載入組合後為 manual、加入為 auto）。

- [ ] **Step 12: build 驗證**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: typecheck 無錯、Vite build 成功。

- [ ] **Step 13: Commit**

```bash
git add frontend/src/components/prompt-library/PromptOverview.tsx frontend/src/components/prompt-library/PromptWorkbench.tsx frontend/src/components/prompt-library/PromptWorkbench.test.tsx
git commit -m "feat(prompt-workbench): auto-sort on add with manual-override state"
```

---

## Task 6: 收尾驗證與進度更新

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: 全前端測試 + typecheck + build（總驗證）**

Run:
```bash
cd frontend && npx vitest run && npx tsc --noEmit && npm run build
```
Expected: 測試全綠、typecheck 無錯、build 成功。

- [ ] **Step 2: 後端資料回歸（確認 JSON 改動未破壞 library 載入）**

Run:
```bash
cd backend && python -m pytest tests -k "prompt_library" -q
```
Expected: 全 PASS（若無此標記的測試集，改跑最接近的 prompt library 測試檔；資料若合法應不受影響）。

- [ ] **Step 3: `git diff --check`**

Run: `git diff --check`
Expected: 無輸出（無行尾空白/衝突標記）。

- [ ] **Step 4: 更新 `docs/PROGRESS.md`**

在檔案最上方新增一段（依既有格式，一項工作一段、講清楚做了什麼與為什麼）：

```markdown
## 2026-07-26 Prompt Workbench 系列標註 · 推薦排序 · 分類分區

- 品質與分級的品質詞 `name_zh` 補上家族後綴（Pony / Illustrious / NoobAI / Anima / SD1.5），台上可分辨同名品質詞屬哪個系列；分級詞本就有系列故不動。純資料變更，`name_zh` 非 snapshot，不影響任何已存組合的生圖。
- positive 分類 `order` 調成「場景靠前」的推薦順序（品質→場景→人物身形→表情→姿勢→動作→服裝→內衣褲→配件→鏡頭構圖→身體效果），作為組裝排序依據。
- Workbench 加入詞條/自由文字時，若該 polarity 為 `auto` 會依（分類 order → entry order → 加入序）自動排序；一旦手動上/下移即切 `manual` 不再自動重排，並提供「重新套用推薦排序」切回 auto。載入既有組合為 manual（尊重存檔順序），新建空白為 auto。
- 最終文字卡片區改為依分類分組檢視（品質/場景/動作…各一區，literal 歸「自訂文字」），方便一眼看到各分類選了哪些；最終文字 textarea 仍是單一 raw 逗號字串，送 ComfyUI 的輸出逐字不變。後端 `PromptComposer` 與 API/schema 零改動。
- 驗證：前端 vitest 全綠、`tsc --noEmit` 與 Vite build 通過；prompt library JSON 通過 Pydantic 嚴格 schema 驗證。
```

- [ ] **Step 5: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): prompt workbench series labels, ordering, category view"
```

---

## Self-Review 對照

- **Spec 範圍一（品質詞系列）** → Task 1。✅
- **Spec 範圍二（推薦排序 + 手動優先）** → Task 2（資料 order）+ Task 3（sort 函式）+ Task 5（auto/manual 狀態、加入自動排序、載入=manual、按鈕）。✅
- **Spec 範圍三（分類分區、只影響檢視）** → Task 3（group 函式）+ Task 4（分組渲染）。最終 textarea 不變由 Task 3/4 測試守。✅
- **動作衝突警告不做** → plan 未含任何警告邏輯。✅
- **後端零改動 / 輸出不變** → Global Constraints + 各 Task 測試（最終文字值斷言）。✅
- **型別一致性**：`sortFragmentsByRecommendation`、`groupFragmentsByCategory`、`FragmentGroup`、`categoryInfoOf` 回傳 `{ key, displayName, order }`、`arrangement: "auto"|"manual"` 在 Task 3/4/5 使用一致。✅
```
