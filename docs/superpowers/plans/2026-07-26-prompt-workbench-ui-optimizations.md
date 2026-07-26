# Prompt Workbench UI 優化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓詞條選項改成內容寬度 chips＋分頁；已選區改成「分類 filter＋每頁 3×3」；「載入組合」改成 append（去重、清身分、套自動排序）。

**Architecture:** 純前端。新增兩個 `compositionState` 純函式（`distinctCategoriesOf`、`appendFragmentsDeduped`）並移除不再使用的 `groupFragmentsByCategory`；`PromptEntryBrowser`、`PromptComposerPanel` 改版；`PromptWorkbench` 新增 append 流程；`CombinationToolbar` 按鈕改名。後端零改動、輸出不變。

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind；vitest + @testing-library（無 `user-event`，用 `fireEvent`）。

## Global Constraints

- **輸出不變**：送 ComfyUI 的最終字串仍是單一逗號串接；append 只多加片段、排序只動順序、filter/分頁只影響顯示。
- **後端零改動**：只改 `frontend/`；不動 API/schema/MCP/資料。
- **comma-atomic 不變式**：最終文字 textarea 仍是唯一 raw 逗號字串。
- 沿用既有排序狀態機（auto/manual）、`rankOf`、`categoryInfoOf`、`sortFragmentsByRecommendation`。
- 驗證：`cd frontend && npx vitest run <file>`、`npx tsc --noEmit`、`npm run build`。

---

## File Structure

| 檔案 | 責任 | 動作 |
|---|---|---|
| `frontend/src/components/prompt-library/compositionState.ts` | 新增 `distinctCategoriesOf`、`appendFragmentsDeduped`、export `LITERAL_GROUP_KEY`；（Task 5）移除 `groupFragmentsByCategory`/`FragmentGroup` | Modify（Task 1、Task 5） |
| `frontend/src/components/prompt-library/compositionState.test.ts` | 新函式測試；（Task 5）移除舊 grouping 測試 | Modify（Task 1、Task 5） |
| `frontend/src/components/prompt-library/PromptEntryBrowser.tsx` | 詞條 chips＋30/頁分頁 | Rewrite（Task 2） |
| `frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx` | chips/分頁/tooltip/⚠️/click 測試 | Modify（Task 2） |
| `frontend/src/components/prompt-library/PromptComposerPanel.tsx` | filter＋3×3 分頁，移除 grouping 渲染，每卡分類標籤 | Rewrite（Task 3） |
| `frontend/src/components/prompt-library/PromptComposerPanel.test.tsx` | filter/分頁/分類標籤/最終文字不變 | Modify（Task 3） |
| `frontend/src/components/prompt-library/PromptWorkbench.tsx` | `appendCombination`（取代 loadCombination 取代語意）；wire onLoad | Modify（Task 4） |
| `frontend/src/components/prompt-library/PromptWorkbench.test.tsx` | append/去重/清身分/auto 重排 | Modify（Task 4） |
| `frontend/src/components/prompt-library/CombinationToolbar.tsx` | 按鈕文案「載入組合」→「加入組合」 | Modify（Task 4） |
| `docs/PROGRESS.md` | 進度 | Modify（Task 6） |

---

## Task 1: `compositionState` 新增 append/filter helper（TDD）

**Files:**
- Modify: `frontend/src/components/prompt-library/compositionState.ts`
- Test: `frontend/src/components/prompt-library/compositionState.test.ts`

**Interfaces:**
- Consumes: 既有 `CompositionState`、`WorkbenchFragment`、私有 `rebuild`、現有私有 `const LITERAL_GROUP_KEY = "__literal__"`。
- Produces:
  - `export const LITERAL_GROUP_KEY`（把現有私有 const 改為 export）。
  - `distinctCategoriesOf(fragments, categoryInfoOf, literalLabel?): { key: string; displayName: string; order: number }[]`（依 order 去重排序；若有 literal 片段，於尾端附一筆 `{ key: LITERAL_GROUP_KEY, displayName: literalLabel, order: +Infinity }`）。
  - `appendFragmentsDeduped(target: CompositionState, incoming: readonly WorkbenchFragment[]): CompositionState`（跳過與 target 內既有、或本次已加入的同來源 entry ref；literal 一律加入；走 `rebuild`；無新增則回傳原 target）。
- 保留 `groupFragmentsByCategory`（Task 5 才移除），確保本 task 後 repo 仍 green。

- [ ] **Step 1: 寫失敗測試**

在 `compositionState.test.ts` 匯入區加入 `appendFragmentsDeduped, distinctCategoriesOf, LITERAL_GROUP_KEY`（與既有 `sortFragmentsByRecommendation` 等並列）。檔尾新增：

```ts
describe("appendFragmentsDeduped", () => {
  const ids = sequentialIds("ap");
  const entryFrag = (categoryId: string, entryId: string) => ({
    id: ids(),
    kind: "entry" as const,
    displayName: entryId,
    source: { polarity: "positive" as const, categoryId, entryId, revision: 1 },
    sourceSnapshotRaw: entryId,
    snapshotRaw: entryId,
    weight: "",
  });

  it("appends only non-duplicate entry refs and keeps the single comma-joined text", () => {
    let target = emptyComposition();
    target = appendFragment(target, entryFrag("quality-ratings", "masterpiece"));
    const incoming = [
      entryFrag("quality-ratings", "masterpiece"), // duplicate ref → skipped
      entryFrag("environment", "rooftop"), // new → kept
    ];
    const result = appendFragmentsDeduped(target, incoming as never);
    expect(result.fragments.map((f) => f.snapshotRaw)).toEqual(["masterpiece", "rooftop"]);
    expect(result.text).toBe("masterpiece,rooftop");
  });

  it("always appends literals and dedupes duplicates within the incoming batch", () => {
    let target = emptyComposition();
    target = appendLiteralText(target, "solo", ids);
    const incoming = [
      { id: ids(), kind: "literal" as const, displayName: "自訂文字", snapshotRaw: "solo", sourceSnapshotRaw: "solo", weight: "" },
      entryFrag("environment", "rooftop"),
      entryFrag("environment", "rooftop"), // duplicate within batch → skipped
    ];
    const result = appendFragmentsDeduped(target, incoming as never);
    // literal "solo" appended again (literals are not deduped); rooftop appears once
    expect(result.fragments.map((f) => f.snapshotRaw)).toEqual(["solo", "solo", "rooftop"]);
  });

  it("returns the same target when nothing new is added", () => {
    let target = emptyComposition();
    target = appendFragment(target, entryFrag("quality-ratings", "a"));
    const result = appendFragmentsDeduped(target, [entryFrag("quality-ratings", "a")] as never);
    expect(result).toBe(target);
  });
});

describe("distinctCategoriesOf", () => {
  const ids = sequentialIds("dc");
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

  it("returns distinct categories ordered by order, literals last", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("environment", "rooftop"));
    state = appendLiteralText(state, "custom", ids);
    state = appendFragment(state, entryFrag("quality-ratings", "masterpiece"));
    state = appendFragment(state, entryFrag("environment", "sunset"));

    const categories = distinctCategoriesOf(state.fragments, info);
    expect(categories.map((c) => c.key)).toEqual(["quality-ratings", "environment", LITERAL_GROUP_KEY]);
    expect(categories[2].displayName).toBe("自訂文字");
  });

  it("omits the literal entry when there are no literals", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("quality-ratings", "a"));
    const categories = distinctCategoriesOf(state.fragments, info);
    expect(categories.map((c) => c.key)).toEqual(["quality-ratings"]);
  });
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd frontend && npx vitest run src/components/prompt-library/compositionState.test.ts`
Expected: FAIL —「appendFragmentsDeduped / distinctCategoriesOf / LITERAL_GROUP_KEY is not exported」。

- [ ] **Step 3: 實作**

在 `compositionState.ts`：把 `const LITERAL_GROUP_KEY = "__literal__";` 改為 `export const LITERAL_GROUP_KEY = "__literal__";`。在檔尾新增：

```ts
export function appendFragmentsDeduped(
  target: CompositionState,
  incoming: readonly WorkbenchFragment[],
): CompositionState {
  const seen = new Set<string>();
  const refKey = (fragment: WorkbenchFragment) =>
    fragment.kind === "entry" && fragment.source
      ? `${fragment.source.polarity}/${fragment.source.categoryId}/${fragment.source.entryId}`
      : null;
  for (const fragment of target.fragments) {
    const key = refKey(fragment);
    if (key) seen.add(key);
  }
  const additions: WorkbenchFragment[] = [];
  for (const fragment of incoming) {
    const key = refKey(fragment);
    if (key) {
      if (seen.has(key)) continue;
      seen.add(key);
    }
    additions.push(fragment);
  }
  if (additions.length === 0) return target;
  return rebuild([...target.fragments, ...additions]);
}

export function distinctCategoriesOf(
  fragments: readonly WorkbenchFragment[],
  categoryInfoOf: (
    fragment: WorkbenchFragment,
  ) => { key: string; displayName: string; order: number } | null,
  literalLabel = "自訂文字",
): { key: string; displayName: string; order: number }[] {
  const byKey = new Map<string, { key: string; displayName: string; order: number }>();
  let hasLiteral = false;
  fragments.forEach((fragment) => {
    const info = categoryInfoOf(fragment);
    if (!info) {
      hasLiteral = true;
      return;
    }
    if (!byKey.has(info.key)) byKey.set(info.key, info);
  });
  const result = [...byKey.values()].sort((left, right) => left.order - right.order);
  if (hasLiteral) {
    result.push({ key: LITERAL_GROUP_KEY, displayName: literalLabel, order: Number.POSITIVE_INFINITY });
  }
  return result;
}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/compositionState.test.ts`
Expected: PASS（含既有測試）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/compositionState.ts frontend/src/components/prompt-library/compositionState.test.ts
git commit -m "feat(prompt-workbench): append-dedup + distinct-categories helpers"
```

---

## Task 2: `PromptEntryBrowser` 內容寬度 chips + 30/頁分頁

**Files:**
- Rewrite: `frontend/src/components/prompt-library/PromptEntryBrowser.tsx`
- Modify: `frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx`

**Interfaces:**
- Consumes: 既有 props（`categories`、`activePolarity`、`onPolarityChange`、`selectedCategory`、`entries`、`onOpenCategory`、`onAddEntry`、`onAddLiteral`）與匯出 `promptEntryLabel`、`promptEntryContent`、型別 `BrowserCategory`、`BrowserEntry`、`suspectReason`。契約不變。
- Produces: 詞條區改為 flex-wrap chips，每頁 30，超過分頁。

- [ ] **Step 1: 全檔改寫**

用以下內容整檔取代 `PromptEntryBrowser.tsx`（保留頂部 export、type、`promptEntryLabel`、`promptEntryContent` 不變；只改詞條清單為 chips＋分頁）：

```tsx
import { useEffect, useMemo, useState } from "react";
import type { PromptPolarity } from "../../types/api";
import { suspectReason } from "./suspectChinese";

export interface BrowserCategory { id: string; polarity: PromptPolarity; name_zh: string; revision: number; etag: string; archived: boolean }
export interface BrowserEntry { id: string; name_zh: string; prompt: string; description_zh: string; aliases: string[]; keywords: string[]; order: number; revision: number; archived: boolean }

export function promptEntryLabel(entry: Pick<BrowserEntry, "id" | "name_zh" | "prompt">): string {
  return entry.name_zh?.trim() || entry.prompt?.trim() || entry.id;
}

export function promptEntryContent(entry: Pick<BrowserEntry, "id" | "prompt">): string {
  return entry.prompt?.trim() ? entry.prompt : entry.id;
}

const PAGE_SIZE = 30;

interface Props {
  categories: BrowserCategory[];
  activePolarity: PromptPolarity;
  onPolarityChange: (polarity: PromptPolarity) => void;
  selectedCategory: BrowserCategory | null;
  entries: BrowserEntry[];
  onOpenCategory: (category: BrowserCategory) => void;
  onAddEntry: (entry: BrowserEntry) => void;
  onAddLiteral: (text: string) => void;
}

export default function PromptEntryBrowser({ categories, activePolarity, onPolarityChange, selectedCategory, entries, onOpenCategory, onAddEntry, onAddLiteral }: Props) {
  const [query, setQuery] = useState("");
  const [literal, setLiteral] = useState("");
  const [page, setPage] = useState(0);
  const visibleEntries = useMemo(() => entries.filter((entry) => !entry.archived && `${entry.name_zh} ${entry.prompt}`.toLowerCase().includes(query.toLowerCase())), [entries, query]);

  // Reset to first page whenever the search or the opened category changes.
  useEffect(() => { setPage(0); }, [query, selectedCategory?.id]);

  const pageCount = Math.max(1, Math.ceil(visibleEntries.length / PAGE_SIZE));
  useEffect(() => { if (page >= pageCount) setPage(pageCount - 1); }, [page, pageCount]);
  const pageEntries = visibleEntries.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  return (
    <section className="h-fit rounded-xl border border-slate-700 bg-slate-900/70 p-5">
      <h2 className="text-lg font-semibold text-white">加入 Prompt</h2>
      <div className="mt-4 grid grid-cols-2 rounded-lg bg-slate-800 p-1" aria-label="Prompt 類型">
        {(["positive", "negative"] as const).map((polarity) => <button key={polarity} type="button" aria-pressed={activePolarity === polarity} onClick={() => onPolarityChange(polarity)} className={`rounded-md px-3 py-2 text-sm ${activePolarity === polarity ? "bg-emerald-600 text-white" : "text-slate-400"}`}>{polarity === "positive" ? "正向" : "負向"}</button>)}
      </div>
      <input aria-label="搜尋提示詞" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜尋中文或英文" className="mt-4 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" />
      <div className="mt-3 flex flex-wrap gap-2">{categories.filter((category) => !category.archived && category.polarity === activePolarity).map((category) => <button key={category.id} type="button" onClick={() => onOpenCategory(category)} className={`rounded-lg px-3 py-2 text-sm ${selectedCategory?.id === category.id ? "bg-emerald-700 text-white" : "bg-slate-800 text-slate-300"}`}>{category.name_zh}</button>)}</div>

      <div data-testid="prompt-entry-chips" className="mt-4 flex flex-wrap gap-2">
        {visibleEntries.length === 0 && <p className="text-sm text-slate-500">沒有符合的詞條</p>}
        {pageEntries.map((entry) => {
          const reason = suspectReason(entry.name_zh, entry.prompt);
          const displayName = promptEntryLabel(entry);
          return (
            <button
              key={entry.id}
              type="button"
              title={entry.prompt}
              aria-label={`加入 ${displayName}`}
              onClick={() => onAddEntry(entry)}
              className="inline-flex max-w-[16rem] items-center gap-1 rounded-full border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:border-emerald-500 hover:bg-slate-700"
            >
              {reason && <span title="name_zh 可能沒有有意義的中文對照，建議編輯修正" className="text-amber-400">⚠️</span>}
              <span className="truncate">{displayName}</span>
            </button>
          );
        })}
      </div>
      {pageCount > 1 && (
        <nav aria-label="詞條分頁" className="mt-3 flex items-center justify-center gap-3">
          <button type="button" aria-label="上一頁" disabled={page === 0} onClick={() => setPage((value) => value - 1)} className="rounded-md bg-slate-700 px-3 py-1.5 text-xs disabled:opacity-40">上一頁</button>
          <span className="text-xs text-slate-400">{page + 1} / {pageCount}</span>
          <button type="button" aria-label="下一頁" disabled={page === pageCount - 1} onClick={() => setPage((value) => value + 1)} className="rounded-md bg-slate-700 px-3 py-1.5 text-xs disabled:opacity-40">下一頁</button>
        </nav>
      )}

      <div className="mt-5 border-t border-slate-700 pt-4">
        <label className="text-sm text-slate-400">自由文字<input aria-label="自由文字" value={literal} onChange={(event) => setLiteral(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" /></label>
        <button type="button" disabled={!literal.trim()} onClick={() => { onAddLiteral(literal); setLiteral(""); }} className="mt-2 w-full rounded-lg bg-slate-700 px-3 py-2 text-sm disabled:opacity-40">加入目前{activePolarity === "positive" ? "正向" : "負向"}</button>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 讀現有測試並更新**

Run: `cd frontend && cat src/components/prompt-library/PromptEntryBrowser.test.tsx`

調整重點：
1. 若既有測試靠「加入 <label>」的 `aria-label` 找加入按鈕，仍可用（chip 的 `aria-label` 保持 `加入 ${displayName}`）。
2. 若既有測試斷言 entry 卡內同時顯示 `entry.prompt` 文字，改為斷言 chip 的 `title` 屬性等於 `entry.prompt`（prompt 移到 tooltip）。
3. 移除任何假設「每筆佔一列 `<li>`」的結構斷言。

- [ ] **Step 3: 新增 chips/分頁測試**

在 `PromptEntryBrowser.test.tsx` 末尾新增（沿用該檔既有 render/mock 慣例；若缺 import 補 `render`、`screen`、`fireEvent`）：

```tsx
it("renders entries as content-width chips with prompt in the title and fires onAddEntry", () => {
  const onAddEntry = vi.fn();
  render(
    <PromptEntryBrowser
      categories={[]}
      activePolarity="positive"
      onPolarityChange={() => {}}
      selectedCategory={null}
      entries={[{ id: "e1", name_zh: "傑作", prompt: "masterpiece", description_zh: "d", aliases: [], keywords: [], order: 10, revision: 1, archived: false }]}
      onOpenCategory={() => {}}
      onAddEntry={onAddEntry}
      onAddLiteral={() => {}}
    />,
  );
  const chip = screen.getByRole("button", { name: "加入 傑作" });
  expect(chip).toHaveAttribute("title", "masterpiece");
  fireEvent.click(chip);
  expect(onAddEntry).toHaveBeenCalledTimes(1);
});

it("paginates at 30 entries per page", () => {
  const entries = Array.from({ length: 31 }, (_, index) => ({
    id: `e${index}`, name_zh: `詞${index}`, prompt: `p${index}`, description_zh: "d",
    aliases: [], keywords: [], order: 10, revision: 1, archived: false,
  }));
  render(
    <PromptEntryBrowser
      categories={[]}
      activePolarity="positive"
      onPolarityChange={() => {}}
      selectedCategory={null}
      entries={entries}
      onOpenCategory={() => {}}
      onAddEntry={() => {}}
      onAddLiteral={() => {}}
    />,
  );
  // 30 chips on page 1, pagination present
  expect(screen.getAllByRole("button", { name: /^加入 / })).toHaveLength(30);
  fireEvent.click(screen.getByLabelText("下一頁"));
  expect(screen.getAllByRole("button", { name: /^加入 / })).toHaveLength(1);
});
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/PromptEntryBrowser.test.tsx`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/PromptEntryBrowser.tsx frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx
git commit -m "feat(prompt-workbench): entry browser content-width chips with 30/page paging"
```

---

## Task 3: `PromptComposerPanel` filter + 3×3 分頁（移除 grouping 渲染）

**Files:**
- Rewrite: `frontend/src/components/prompt-library/PromptComposerPanel.tsx`
- Modify: `frontend/src/components/prompt-library/PromptComposerPanel.test.tsx`

**Interfaces:**
- Consumes: Task 1 的 `distinctCategoriesOf`、`LITERAL_GROUP_KEY`；既有 `WorkbenchFragment`、`CompositionState`、`categoryInfoOf` prop。
- Produces: `PromptComposerPanel` props 不變；改為 filter chip 列 + 每頁 9（3×3）分頁；每卡顯示分類標籤。不再匯入 `groupFragmentsByCategory`。

- [ ] **Step 1: 全檔改寫**

用以下內容整檔取代 `PromptComposerPanel.tsx`：

```tsx
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CompositionState, WorkbenchFragment } from "./compositionState";
import { distinctCategoriesOf, LITERAL_GROUP_KEY } from "./compositionState";

const PAGE_SIZE = 9;
const ALL_KEY = "__all__";

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
  const [filterKey, setFilterKey] = useState<string>(ALL_KEY);
  const [page, setPage] = useState(0);
  const [pendingCardFocus, setPendingCardFocus] = useState<number | null>(null);
  const finalTextarea = useRef<HTMLTextAreaElement>(null);
  const pendingSelection = useRef<{
    start: number;
    end: number;
    direction: "forward" | "backward" | "none";
  } | null>(null);

  const matchesFilter = (fragment: WorkbenchFragment) => {
    if (filterKey === ALL_KEY) return true;
    const info = categoryInfoOf(fragment);
    if (filterKey === LITERAL_GROUP_KEY) return info === null;
    return info?.key === filterKey;
  };

  const filterOptions = distinctCategoriesOf(state.fragments, categoryInfoOf);
  const filtered = state.fragments.filter(matchesFilter);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageFragments = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  // Reset to page 1 when the filter changes; clamp when the page count shrinks.
  useEffect(() => { setPage(0); }, [filterKey]);
  useEffect(() => { if (page >= pageCount) setPage(pageCount - 1); }, [page, pageCount]);
  // If the active filter no longer exists (its last fragment removed), fall back to 全部.
  useEffect(() => {
    if (filterKey === ALL_KEY) return;
    const stillPresent = filterKey === LITERAL_GROUP_KEY
      ? state.fragments.some((fragment) => categoryInfoOf(fragment) === null)
      : filterOptions.some((option) => option.key === filterKey);
    if (!stillPresent) setFilterKey(ALL_KEY);
  }, [filterKey, filterOptions, state.fragments, categoryInfoOf]);

  useEffect(() => {
    const focusInvalid = (event: Event) => {
      const detail = (event as CustomEvent<{ polarity: string; position: number }>).detail;
      if (detail.polarity !== polarity) return;
      setFilterKey(ALL_KEY);
      setPage(Math.floor((detail.position - 1) / PAGE_SIZE));
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
  }, [pendingCardFocus, polarity, state.fragments, page]);

  useLayoutEffect(() => {
    const selection = pendingSelection.current;
    const textarea = finalTextarea.current;
    if (!selection || !textarea || document.activeElement !== textarea) return;
    const clamp = (value: number) => Math.min(value, textarea.value.length);
    textarea.setSelectionRange(clamp(selection.start), clamp(selection.end), selection.direction);
    pendingSelection.current = null;
  }, [state.text, state.fragments]);

  const filterButtonClass = (active: boolean) =>
    `rounded-full px-3 py-1 text-xs ${active ? "bg-emerald-700 text-white" : "bg-slate-800 text-slate-300"}`;

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="mt-1 text-xs text-slate-500">篩選檢視 · 最終文字</p>
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

      <div role="group" aria-label={`${title} 分類篩選`} className="mt-3 flex flex-wrap gap-2">
        <button type="button" aria-pressed={filterKey === ALL_KEY} onClick={() => setFilterKey(ALL_KEY)} className={filterButtonClass(filterKey === ALL_KEY)}>全部</button>
        {filterOptions.map((option) => (
          <button key={option.key} type="button" aria-pressed={filterKey === option.key} onClick={() => setFilterKey(option.key)} className={filterButtonClass(filterKey === option.key)}>
            {option.displayName}
          </button>
        ))}
      </div>

      <div data-testid="prompt-option-grid" className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
        {state.fragments.length === 0 && (
          <p className="col-span-full rounded-lg border border-dashed border-slate-700 p-3 text-sm text-slate-500">尚未加入 Prompt</p>
        )}
        {pageFragments.map((fragment) => {
          const index = state.fragments.indexOf(fragment);
          const label = fragment.displayName;
          const categoryLabel = categoryInfoOf(fragment)?.displayName ?? "自訂文字";
          const invalid = fragment.snapshotRaw.trim() === "" || fragment.renderedRaw.trim() === "";
          return (
            <div
              key={fragment.id}
              className={`rounded-lg border bg-slate-800/70 p-3 ${invalid ? "border-red-500" : "border-slate-700"}`}
            >
              <div className="mb-2 flex flex-wrap items-center gap-2 text-sm font-medium text-slate-200">
                <span className="rounded-full bg-slate-900 px-2 py-0.5 text-xs text-slate-400">{categoryLabel}</span>
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
                    <button type="button" disabled={index === 0} onClick={() => onMove(fragment.id, -1)} className="rounded-md bg-slate-700 px-2 py-1.5 text-xs disabled:opacity-40">上移</button>
                    <button type="button" disabled={index === state.fragments.length - 1} onClick={() => onMove(fragment.id, 1)} className="rounded-md bg-slate-700 px-2 py-1.5 text-xs disabled:opacity-40">下移</button>
                  </div>
                  <button type="button" onClick={() => onRemove(fragment.id)} className="rounded-md bg-red-950 px-2 py-1.5 text-xs text-red-300">刪除</button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {pageCount > 1 && (
        <nav aria-label={`${title} 分頁`} className="mt-3 flex items-center justify-center gap-3">
          <button type="button" aria-label="上一頁" disabled={page === 0} onClick={() => setPage((value) => value - 1)} className="rounded-md bg-slate-700 px-3 py-1.5 text-xs disabled:opacity-40">上一頁</button>
          <span className="text-xs text-slate-400">{page + 1} / {pageCount}</span>
          <button type="button" aria-label="下一頁" disabled={page === pageCount - 1} onClick={() => setPage((value) => value + 1)} className="rounded-md bg-slate-700 px-3 py-1.5 text-xs disabled:opacity-40">下一頁</button>
        </nav>
      )}

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

- [ ] **Step 2: 讀現有測試並更新**

Run: `cd frontend && cat src/components/prompt-library/PromptComposerPanel.test.tsx`

調整重點：
1. 移除／改寫任何斷言「分類區塊標題（`prompt-group-*` testid 或 group heading 文字如『品質與分級』作為 section 標題）」的測試——分類現在以 filter chip 與每卡標籤呈現。
2. 保留「最終文字」`aria-label` 與其值斷言、reapply 按鈕斷言、空狀態斷言。
3. 提供三個新必填 props 的 render helper 已存在（`arrangement`、`categoryInfoOf`、`onReapplySort`）；不變。

- [ ] **Step 3: 新增 filter/分頁/分類標籤測試**

在 `PromptComposerPanel.test.tsx` 新增（`state` 用檔案內既有 helper 或 `emptyComposition`/`appendFragment` 建；`info` 對映 quality-ratings→品質與分級(10)、environment→場景與氛圍(20)）：

```tsx
it("shows a category filter that narrows the visible cards and keeps final text unchanged", () => {
  // build a state with one quality entry and one environment entry (both real source refs)
  const state = /* 依既有 helper：兩個 entry 片段，text 例如 "masterpiece,rooftop" */;
  const info = (fragment: { source?: { categoryId: string } }) => {
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
      categoryInfoOf={info as never}
      onReapplySort={() => {}}
      onFinalTextChange={() => {}}
      onTextChange={() => {}}
      onWeightChange={() => {}}
      onMove={() => {}}
      onRemove={() => {}}
    />,
  );
  // filter chips present; category labels shown on cards
  expect(screen.getByRole("button", { name: "全部" })).toBeInTheDocument();
  const envFilter = screen.getByRole("button", { name: "場景與氛圍" });
  // clicking a filter shows only that category's card content
  fireEvent.click(envFilter);
  expect(screen.getByLabelText("rooftop 內容")).toBeInTheDocument();
  expect(screen.queryByLabelText("傑作 內容")).not.toBeInTheDocument();
  // final text is untouched by filtering
  expect((screen.getByLabelText("Positive Prompt 最終文字") as HTMLTextAreaElement).value).toBe("masterpiece,rooftop");
});

it("paginates selected cards at 9 per page", () => {
  const state = /* 依既有 helper 建 10 個 literal/entry 片段的 CompositionState */;
  render(
    <PromptComposerPanel
      title="Positive Prompt"
      state={state}
      arrangement="manual"
      categoryInfoOf={() => null}
      onReapplySort={() => {}}
      onFinalTextChange={() => {}}
      onTextChange={() => {}}
      onWeightChange={() => {}}
      onMove={() => {}}
      onRemove={() => {}}
    />,
  );
  // 9 content textareas on page 1
  expect(screen.getAllByLabelText(/ 內容$/)).toHaveLength(9);
  fireEvent.click(screen.getByLabelText("Positive Prompt 分頁").querySelector('[aria-label="下一頁"]')!);
  expect(screen.getAllByLabelText(/ 內容$/)).toHaveLength(1);
});
```

> 註：`state` 依該測試檔既有慣例建（多半用 `emptyComposition()` + `appendFragment(...)` from `compositionState`，或直接組物件）。實作者補齊註解處，確保 `state.text` 與片段一致。

- [ ] **Step 4: 執行測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/PromptComposerPanel.test.tsx`
Expected: PASS。

- [ ] **Step 5: typecheck（部分檔案暫時未更新可容忍）**

Run: `cd frontend && npx tsc --noEmit`
Expected: 面板自身無錯。`compositionState.ts` 仍匯出 `groupFragmentsByCategory`（Task 5 才移除），故不會有 unused-export 錯誤。若有錯誤只出現在尚未於本 task 範圍的檔案，記錄並續行。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/prompt-library/PromptComposerPanel.tsx frontend/src/components/prompt-library/PromptComposerPanel.test.tsx
git commit -m "feat(prompt-workbench): selected view category filter + 3x3 paging"
```

---

## Task 4: `PromptWorkbench` 加入組合（append）+ Toolbar 改名

**Files:**
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`
- Modify: `frontend/src/components/prompt-library/CombinationToolbar.tsx`
- Test: `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`

**Interfaces:**
- Consumes: Task 1 的 `appendFragmentsDeduped`；既有 `deserializeWithReferenceLabels`、`resolveEntryNames`、`warningMessages`、`sortFragmentsByRecommendation`、`rankOf`、`arrangement`、`blankDocument`。
- Produces: `appendCombination()` 取代 `loadCombination()` 的取代語意並綁到 Toolbar「加入組合」按鈕。

- [ ] **Step 1: import `appendFragmentsDeduped`**

在 `PromptWorkbench.tsx` 頂部 `compositionState` 的 import 清單加入 `appendFragmentsDeduped`（與 `sortFragmentsByRecommendation` 並列）。

- [ ] **Step 2: 以 `appendCombination` 取代 `loadCombination`**

把整個 `loadCombination` 函式（`async function loadCombination() { ... }`）取代為：

```tsx
  async function appendCombination() {
    if (!selectedId) return;
    const id = beginOperation();
    setSuccess("");
    try {
      const detail = await getPromptCombination(selectedId);
      const names = await resolveEntryNames(
        detail.combination.positive,
        detail.combination.negative,
        labelMap.current,
      );
      if (operationId.current !== id) return;
      const literalLabel = (snapshot: string) => resolveLiteralDisplayLabel(snapshot, literalLabelIndex.current);
      const loadedPositive = deserializeWithReferenceLabels(detail.combination.positive, "positive", () => nextId("loaded"), names.labels, literalLabel);
      const loadedNegative = deserializeWithReferenceLabels(detail.combination.negative, "negative", () => nextId("loaded"), names.labels, literalLabel);
      labelMap.current = names.labels;
      setPositive((current) => {
        const merged = appendFragmentsDeduped(current, loadedPositive.fragments);
        return arrangement.positive === "auto" ? sortFragmentsByRecommendation(merged, rankOf) : merged;
      });
      setNegative((current) => {
        const merged = appendFragmentsDeduped(current, loadedNegative.fragments);
        return arrangement.negative === "auto" ? sortFragmentsByRecommendation(merged, rankOf) : merged;
      });
      setDocument({ ...blankDocument(), dirty: true, warnings: [...warningMessages(detail.warnings), ...names.warnings] });
      setSuccess("已加入組合到目前工作區（未儲存草稿）");
    } catch (reason) {
      if (operationId.current === id) setError(reason instanceof Error ? reason.message : String(reason));
    } finally { finishOperation(id); }
  }
```

Notes:
- 不呼叫 `canReplace()`（append 非破壞性）。
- 不呼叫 `installCombination`（那是取代語意；`saveCombination` 仍用它，保留不動）。
- `setDocument({ ...blankDocument(), dirty: true, warnings })` 清掉身分並標為草稿。

- [ ] **Step 3: 綁定 Toolbar 的 onLoad 到 appendCombination**

在 render 內找到 `<CombinationToolbar ... onLoad={loadCombination} ... />`，改為 `onLoad={appendCombination}`。（其餘 props 不變。）

- [ ] **Step 4: Toolbar 按鈕改名**

在 `CombinationToolbar.tsx`，把「載入組合」按鈕文字改為「加入組合」：

```tsx
        <button type="button" disabled={busy || !selectedId} onClick={onLoad} className="rounded-lg bg-sky-700 px-4 py-2.5 font-medium text-white disabled:bg-slate-700">加入組合</button>
```

- [ ] **Step 5: 更新／新增 Workbench 測試**

Run: `cd frontend && cat src/components/prompt-library/PromptWorkbench.test.tsx`

1. 若有測試點「載入組合」按鈕（依文字或角色），改成「加入組合」。
2. 若有測試斷言載入後**取代**現有內容或斷言 document 綁定 id，改成 append 語意（保留現有 + 加入新的、document 身分清空）。
3. 新增一個 append 測試（沿用既有 mock 慣例）：先加入一個詞條到 positive，再「加入組合」一個含不同詞條的組合，斷言 positive 最終文字同時包含兩者、且（auto lane）已依 category order 重排；再斷言「更新目前組合」為 disabled（document.id 清空）。骨架：

```tsx
it("appends a saved combination into the current work area and clears the document identity", async () => {
  // mock getPromptCatalog → includes a combination summary with a known id
  // mock getPromptCombination(id) → returns a combination whose positive has one entry
  //   in a category different from the one added interactively
  render(<PromptWorkbench />);
  await screen.findByText("Prompt Workbench");
  // interactively add one entry (existing helper), then select the combination and click 加入組合
  // ... existing add-entry helper ...
  fireEvent.change(screen.getByLabelText("已儲存組合"), { target: { value: "<combo-id>" } });
  fireEvent.click(screen.getByRole("button", { name: "加入組合" }));
  const finalText = await screen.findByLabelText("Positive Prompt 最終文字");
  // both the interactively-added atom and the combination's atom are present
  expect((finalText as HTMLTextAreaElement).value).toContain("<interactive-atom>");
  expect((finalText as HTMLTextAreaElement).value).toContain("<combination-atom>");
  // document identity cleared → 更新目前組合 disabled
  expect(screen.getByRole("button", { name: "更新目前組合" })).toBeDisabled();
});
```

> 實作者依既有 mock/操作 helper 補齊 `<combo-id>`、`<interactive-atom>`、`<combination-atom>`。核心斷言：**append 不清空現有**、**document 身分清空**。若既有測試已有「載入組合」流程可直接改寫為 append 斷言。

- [ ] **Step 6: 全前端測試 + typecheck**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: 全 PASS、typecheck 乾淨（`groupFragmentsByCategory` 仍存在但未被引用——尚不移除；unused export 不會使 tsc 失敗）。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/prompt-library/PromptWorkbench.tsx frontend/src/components/prompt-library/CombinationToolbar.tsx frontend/src/components/prompt-library/PromptWorkbench.test.tsx
git commit -m "feat(prompt-workbench): load-combination becomes append (dedup, clears identity)"
```

---

## Task 5: 移除不再使用的 `groupFragmentsByCategory` / `FragmentGroup`

**Files:**
- Modify: `frontend/src/components/prompt-library/compositionState.ts`
- Modify: `frontend/src/components/prompt-library/compositionState.test.ts`

**Interfaces:**
- Consumes: 無新增。
- Produces: 移除 `groupFragmentsByCategory`、`FragmentGroup`；`LITERAL_GROUP_KEY` 保留（`distinctCategoriesOf` 與面板仍用）。

- [ ] **Step 1: 確認無其他引用**

Run: `cd frontend && grep -rn "groupFragmentsByCategory\|FragmentGroup" src/`
Expected: 只出現在 `compositionState.ts`（定義）與 `compositionState.test.ts`（測試）。若出現在其他檔，停止並回報（代表某處仍依賴，需先處理）。

- [ ] **Step 2: 移除實作與測試**

- 在 `compositionState.ts` 刪除 `export interface FragmentGroup { ... }` 與 `export function groupFragmentsByCategory(...) { ... }`（保留 `export const LITERAL_GROUP_KEY`）。
- 在 `compositionState.test.ts` 刪除 `describe("groupFragmentsByCategory", ...)` 整段，並從 import 清單移除 `groupFragmentsByCategory`（保留 `distinctCategoriesOf`、`appendFragmentsDeduped`、`LITERAL_GROUP_KEY` 等）。

- [ ] **Step 3: 全前端測試 + typecheck + build**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 全 PASS、typecheck 乾淨、build 成功。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/prompt-library/compositionState.ts frontend/src/components/prompt-library/compositionState.test.ts
git commit -m "refactor(prompt-workbench): drop unused groupFragmentsByCategory helper"
```

---

## Task 6: 收尾驗證與進度更新

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: 全前端驗證**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 測試全綠、typecheck 無錯、build 成功（記錄測試數）。

- [ ] **Step 2: `git diff --check`**

Run: `git diff --check`
Expected: 無輸出。

- [ ] **Step 3: 更新 `docs/PROGRESS.md`**

在檔案最上方新增（依既有格式）：

```markdown
## 2026-07-26 Prompt Workbench UI 優化：詞條 chips · 已選 filter+分頁 · 加入組合

- 左側「加入 Prompt」詞條由全寬列表改為內容寬度 chips（prompt 移到 tooltip、保留 ⚠️ 可疑中文標記），每頁最多 30 個、超過分頁；搜尋或切換分類回第 1 頁。
- 已選片段檢視由常駐分類區塊改為「分類 filter + 每頁 3×3（9 張）分頁」：預設「全部」、可只看某分類，每卡加分類標籤；卡片保留內容/權重/上移下移/刪除，最終文字 textarea 與輸出不變。移除前版 `groupFragmentsByCategory`，改用 `distinctCategoriesOf` 建 filter。
- 「載入組合」改名「加入組合」，行為由取代改為 append：把選中組合片段接進目前工作區、自動去重同來源 entry ref（literal 不去重）、清掉目前組合身分變未儲存草稿、並套既有自動排序狀態機（auto 重排／manual 接尾）。
- 純前端；後端/API/schema 零改動，送 ComfyUI 的最終字串邏輯不變。驗證：前端 vitest 全綠、`tsc --noEmit` 與 Vite build 通過。
```

- [ ] **Step 4: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): prompt workbench UI optimizations (chips, filter+paging, append)"
```

---

## Self-Review 對照

- **範圍一（詞條 chips + 30/頁）** → Task 2。✅
- **範圍二（filter + 3×3 分頁，取代 grouping）** → Task 1（`distinctCategoriesOf`）＋ Task 3（面板）＋ Task 5（移除舊 grouping）。✅
- **範圍三（載入→加入 append、去重、清身分、套排序）** → Task 1（`appendFragmentsDeduped`）＋ Task 4（workbench＋toolbar）。✅
- **輸出不變 / 後端零改動** → Global Constraints；各 task 測試含最終文字值斷言。✅
- **型別一致性**：`distinctCategoriesOf`/`appendFragmentsDeduped`/`LITERAL_GROUP_KEY` 在 Task 1 定義，Task 3/4 使用一致；`categoryInfoOf` 回傳 `{ key, displayName, order }` 與面板 filter/label 一致。✅
- **repo 每 task 後保持 green**：新 helper（1）→ 瀏覽器（2）→ 面板改用新 helper（3）→ workbench（4）→ 最後才移除舊 grouping（5）。✅
