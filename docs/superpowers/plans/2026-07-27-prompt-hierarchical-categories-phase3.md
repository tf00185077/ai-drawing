# Prompt Library 分類樹 Phase 3（工作台瀏覽器樹狀）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓工作台左側「加入 Prompt」改成鑽入式＋麵包屑的樹狀瀏覽（子分類資料夾＋該分類詞條），並支援跨整棵樹的搜尋。

**Architecture:** 純前端。`PromptEntryBrowser` 由「扁平分類 chip 列 + 開啟單一分類」改為「目前節點的子分類資料夾 chip＋麵包屑＋該分類詞條 chip」；搜尋時攤平顯示全樹命中詞條並標分類路徑。`PromptWorkbench` 把它初始化時本就抓到的各分類詞條彙整成 `allEntries` 供跨樹搜尋，並改 `onAddEntry` 帶上該詞所屬分類（讓搜尋結果能從任一分類加入）。後端不動（沿用 Phase 1 的 `parent_id`）。

**Tech Stack:** React 18 + TS + Vite + Tailwind；vitest + @testing-library（無 `user-event`，用 `fireEvent`）。

## Global Constraints

- **純前端**：不改後端/API/schema。
- **輸出不變**：加入詞條的 fragment 語意不變（source ref = 該詞所屬分類）；排序沿用 Phase 1 祖先路徑。
- **可靠性**：某分類若載入失敗（例如既有損壞的 body-appearance），其詞條不出現在跨樹搜尋中，但不得使瀏覽器崩潰或阻擋其他分類。
- **樹資料來源**：分類的 `parent_id`／`order` 來自 catalog（Phase 1 已回傳）。
- 驗證：`cd frontend && npx vitest run <file>`、`npx tsc --noEmit`、`npm run build`。

---

## File Structure

| 檔案 | 責任 | 動作 |
|---|---|---|
| `frontend/src/components/prompt-library/categoryTree.ts` | 新增 `childCategories` | Modify（Task 1） |
| `frontend/src/components/prompt-library/categoryTree.test.ts` | `childCategories` 測試 | Modify（Task 1） |
| `frontend/src/components/prompt-library/PromptEntryBrowser.tsx` | 鑽入式樹狀 + 麵包屑 + 跨樹搜尋 | Rewrite（Task 2） |
| `frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx` | 對應測試 | Modify（Task 2） |
| `frontend/src/components/prompt-library/PromptWorkbench.tsx` | 寬化 BrowserCategory、`addEntry(category, entry)`、彙整並傳 `allEntries` | Modify（Task 2） |
| `frontend/src/components/prompt-library/PromptWorkbench.test.tsx` | 對應調整 | Modify（Task 2） |
| `docs/PROGRESS.md` | 進度 | Modify（Task 3） |

---

## Task 1: `categoryTree.childCategories` 純函式（TDD）

**Files:**
- Modify: `frontend/src/components/prompt-library/categoryTree.ts`
- Test: `frontend/src/components/prompt-library/categoryTree.test.ts`

**Interfaces:**
- Consumes: 既有 `CategoryNodeLike`、內部 `childrenByParent`。
- Produces: `childCategories<T extends CategoryNodeLike>(categories: readonly T[], parentId: string | null): T[]`——回傳 `parentId` 的直接子分類（`null` 表示頂層 roots），依 `order` 再 `id` 排序；`parent_id` 懸空者視為 root（即 `childCategories(cats, null)` 會包含它）。

- [ ] **Step 1: 寫失敗測試**（追加到 `categoryTree.test.ts`）

```ts
import { childCategories } from "./categoryTree";

describe("childCategories", () => {
  const cats = [
    { id: "clothing", parent_id: null, order: 70 },
    { id: "clothing-top", parent_id: "clothing", order: 10 },
    { id: "clothing-bottom", parent_id: "clothing", order: 20 },
    { id: "quality", parent_id: null, order: 10 },
    { id: "dangling", parent_id: "ghost", order: 5 },
  ];
  it("returns roots for null parent sorted by order then id, incl dangling-as-root", () => {
    // roots by order: dangling(5), quality(10), clothing(70)
    expect(childCategories(cats, null).map((c) => c.id)).toEqual(["dangling", "quality", "clothing"]);
  });
  it("returns direct children of a parent ordered by order then id", () => {
    expect(childCategories(cats, "clothing").map((c) => c.id)).toEqual(["clothing-top", "clothing-bottom"]);
  });
  it("returns [] for a leaf", () => {
    expect(childCategories(cats, "quality")).toEqual([]);
  });
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd frontend && npx vitest run src/components/prompt-library/categoryTree.test.ts`
Expected: FAIL（`childCategories` 未匯出）。

- [ ] **Step 3: 實作**

在 `categoryTree.ts` 末尾新增（複用既有 `childrenByParent`）：
```ts
export function childCategories<T extends CategoryNodeLike>(
  categories: readonly T[],
  parentId: string | null,
): T[] {
  const { roots, children } = childrenByParent(categories);
  return parentId === null ? roots : children.get(parentId) ?? [];
}
```
（`childrenByParent` 已對 roots 與 children 各自依 `order` 再 `id` 排序，並把懸空 parent 視為 root。）

- [ ] **Step 4: 執行測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/categoryTree.test.ts`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/categoryTree.ts frontend/src/components/prompt-library/categoryTree.test.ts
git commit -m "feat(prompt-library): childCategories tree helper"
```

---

## Task 2: `PromptEntryBrowser` 鑽入式樹狀 + 麵包屑 + 跨樹搜尋

**Files:**
- Rewrite: `frontend/src/components/prompt-library/PromptEntryBrowser.tsx`
- Modify: `frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`

**Interfaces:**
- Consumes: Task 1 的 `childCategories`；既有 `ancestorChain`。
- Produces:
  - `BrowserCategory` 加 `parent_id?: string | null; order: number`。
  - `PromptEntryBrowser` props 改為：`categories`、`activePolarity`、`onPolarityChange`、`selectedCategory`、`entries`、`onOpenCategory`、`onAddEntry: (category: BrowserCategory, entry: BrowserEntry) => void`、`onAddLiteral`、新增 `allEntries: { category: BrowserCategory; entry: BrowserEntry }[]`。
  - `PromptWorkbench.addEntry(category: BrowserCategory, entry: BrowserEntry)`；初始化時彙整 `allEntries` 並傳入。

- [ ] **Step 1: 寬化 BrowserCategory + workbench `addEntry(category, entry)` + `allEntries`**

在 `PromptEntryBrowser.tsx` 把 `BrowserCategory` 介面改為：
```ts
export interface BrowserCategory { id: string; polarity: PromptPolarity; name_zh: string; revision: number; etag: string; archived: boolean; parent_id?: string | null; order: number }
```
在 `PromptWorkbench.tsx`：
1. 頂部 import 加 `import { childCategories } from "./compositionState"`？**否**——`childCategories` 在 `categoryTree`。改為 `import { ancestorChain, childCategories } from "./categoryTree";`（browser 用，不一定 workbench 用；若 workbench 未用可不 import）。
2. 新增 state：`const [allEntries, setAllEntries] = useState<{ category: BrowserCategory; entry: BrowserEntry }[]>([]);`
3. 在載入 catalog 的 effect 內、既有 `categoryResults` 處理區（建 labelMap/entryOrderByRef 之處），彙整 allEntries：
```tsx
          const collectedEntries: { category: BrowserCategory; entry: BrowserEntry }[] = [];
          categoryResults.forEach((result) => {
            if (result.status !== "fulfilled") return;
            const cat = result.value.category;
            const browserCategory: BrowserCategory = {
              id: cat.id, polarity: cat.polarity, name_zh: cat.name_zh,
              revision: cat.revision, etag: result.value.etag, archived: cat.archived,
              parent_id: cat.parent_id ?? null, order: cat.order,
            };
            cat.entries.forEach((entry) => {
              if (!entry.archived) collectedEntries.push({ category: browserCategory, entry });
            });
          });
          setAllEntries(collectedEntries);
```
4. 改 `addEntry` 由 `(entry)` 為 `(category, entry)`，用傳入的 category（不再依賴 `category` state）：
```tsx
  function addEntry(sourceCategory: BrowserCategory, entry: BrowserEntry) {
    const promptText = promptEntryContent(entry);
    const displayName = promptEntryLabel(entry);
    const item = {
      id: nextId(`${sourceCategory.polarity}-${sourceCategory.id}-${entry.id}`),
      kind: "entry" as const,
      displayName,
      source: { polarity: sourceCategory.polarity, categoryId: sourceCategory.id, entryId: entry.id, revision: entry.revision },
      sourceSnapshotRaw: promptText,
      snapshotRaw: promptText,
      weight: "",
      userAddedSource: true,
    };
    const setter = sourceCategory.polarity === "positive" ? setPositive : setNegative;
    mutate(setter, (state) => {
      const appended = appendFragment(state, item);
      return arrangement[sourceCategory.polarity] === "auto"
        ? sortFragmentsByRecommendation(appended, rankOf)
        : appended;
    });
  }
```
> 注意：原本用 `activePolarity` 決定 setter；改用 `sourceCategory.polarity`（一致，因為分類本身帶 polarity，且瀏覽器只顯示 activePolarity 的分類）。
5. render 傳新 props：把 `<PromptEntryBrowser ... onAddEntry={addEntry} .../>` 改為傳 `allEntries={allEntries}`，`onAddEntry={addEntry}`（簽名已改）。移除對 `selectedCategory`/`entries`/`onOpenCategory` 的變動——這些沿用（drill-down 仍用 onOpenCategory 載入詞條）。

- [ ] **Step 2: 全檔改寫 `PromptEntryBrowser.tsx`**

用以下內容整檔取代（保留頂部 export/type/`promptEntryLabel`/`promptEntryContent`；`BrowserCategory` 用 Step 1 的寬化版）：

```tsx
import { useEffect, useMemo, useState } from "react";
import type { PromptPolarity } from "../../types/api";
import { ancestorChain, childCategories } from "./categoryTree";
import { suspectReason } from "./suspectChinese";

export interface BrowserCategory { id: string; polarity: PromptPolarity; name_zh: string; revision: number; etag: string; archived: boolean; parent_id?: string | null; order: number }
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
  allEntries: { category: BrowserCategory; entry: BrowserEntry }[];
  onOpenCategory: (category: BrowserCategory) => void;
  onAddEntry: (category: BrowserCategory, entry: BrowserEntry) => void;
  onAddLiteral: (text: string) => void;
}

function EntryChip({ category, entry, pathLabel, onAdd }: { category: BrowserCategory; entry: BrowserEntry; pathLabel?: string; onAdd: (category: BrowserCategory, entry: BrowserEntry) => void }) {
  const reason = suspectReason(entry.name_zh, entry.prompt);
  const displayName = promptEntryLabel(entry);
  return (
    <button
      type="button"
      title={entry.prompt}
      aria-label={`加入 ${displayName}`}
      onClick={() => onAdd(category, entry)}
      className="inline-flex max-w-[16rem] items-center gap-1 rounded-full border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:border-emerald-500 hover:bg-slate-700"
    >
      {reason && <span title="name_zh 可能沒有有意義的中文對照，建議編輯修正" aria-label={`${displayName} 中文對照可能未填好`} className="text-amber-400">⚠️</span>}
      {pathLabel && <span className="text-xs text-slate-500">{pathLabel}·</span>}
      <span className="truncate">{displayName}</span>
    </button>
  );
}

export default function PromptEntryBrowser({ categories, activePolarity, onPolarityChange, selectedCategory, entries, allEntries, onOpenCategory, onAddEntry, onAddLiteral }: Props) {
  const [query, setQuery] = useState("");
  const [literal, setLiteral] = useState("");
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const polarityCategories = useMemo(
    () => categories.filter((category) => !category.archived && category.polarity === activePolarity),
    [categories, activePolarity],
  );

  const trimmedQuery = query.trim().toLowerCase();
  const searching = trimmedQuery !== "";

  // Cross-tree search results (whole polarity), else the current category's entries.
  const searchResults = useMemo(() => {
    if (!searching) return [];
    return allEntries.filter(
      ({ category, entry }) =>
        category.polarity === activePolarity &&
        !entry.archived &&
        `${entry.name_zh} ${entry.prompt}`.toLowerCase().includes(trimmedQuery),
    );
  }, [allEntries, activePolarity, searching, trimmedQuery]);

  const currentCategory = useMemo(
    () => polarityCategories.find((category) => category.id === currentId) ?? null,
    [polarityCategories, currentId],
  );
  const folders = useMemo(() => childCategories(polarityCategories, currentId), [polarityCategories, currentId]);
  const breadcrumb = useMemo(
    () => (currentId ? ancestorChain(polarityCategories, currentId) : []),
    [polarityCategories, currentId],
  );
  const currentEntries = useMemo(
    () => (currentCategory ? entries.filter((entry) => !entry.archived) : []),
    [entries, currentCategory],
  );

  const listForPaging = searching ? searchResults : currentEntries;
  useEffect(() => { setPage(0); }, [trimmedQuery, currentId, activePolarity]);
  const pageCount = Math.max(1, Math.ceil(listForPaging.length / PAGE_SIZE));
  useEffect(() => { if (page >= pageCount) setPage(pageCount - 1); }, [page, pageCount]);
  const pageStart = page * PAGE_SIZE;

  const enterCategory = (category: BrowserCategory) => {
    setCurrentId(category.id);
    onOpenCategory(category);
  };
  const pathLabelOf = (category: BrowserCategory) =>
    ancestorChain(polarityCategories, category.id).map((node) => node.name_zh).join(" › ");

  const changePolarity = (polarity: PromptPolarity) => {
    setCurrentId(null);
    onPolarityChange(polarity);
  };

  return (
    <section className="h-fit rounded-xl border border-slate-700 bg-slate-900/70 p-5">
      <h2 className="text-lg font-semibold text-white">加入 Prompt</h2>
      <div className="mt-4 grid grid-cols-2 rounded-lg bg-slate-800 p-1" aria-label="Prompt 類型">
        {(["positive", "negative"] as const).map((polarity) => <button key={polarity} type="button" aria-pressed={activePolarity === polarity} onClick={() => changePolarity(polarity)} className={`rounded-md px-3 py-2 text-sm ${activePolarity === polarity ? "bg-emerald-600 text-white" : "text-slate-400"}`}>{polarity === "positive" ? "正向" : "負向"}</button>)}
      </div>
      <input aria-label="搜尋提示詞" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜尋整棵樹（中文或英文）" className="mt-4 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" />

      {!searching && (
        <nav aria-label="分類路徑" className="mt-3 flex flex-wrap items-center gap-1 text-sm">
          <button type="button" onClick={() => setCurrentId(null)} className={`rounded px-2 py-1 ${currentId === null ? "text-white" : "text-emerald-400 hover:underline"}`}>頂層</button>
          {breadcrumb.map((node) => (
            <span key={node.id} className="flex items-center gap-1">
              <span className="text-slate-600">›</span>
              <button type="button" onClick={() => setCurrentId(node.id)} className={`rounded px-2 py-1 ${node.id === currentId ? "text-white" : "text-emerald-400 hover:underline"}`}>{node.name_zh}</button>
            </span>
          ))}
        </nav>
      )}

      {!searching && folders.length > 0 && (
        <div data-testid="prompt-folder-chips" className="mt-3 flex flex-wrap gap-2">
          {folders.map((folder) => (
            <button key={folder.id} type="button" onClick={() => enterCategory(folder)} className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-300 hover:bg-slate-700">
              📁 {folder.name_zh}
            </button>
          ))}
        </div>
      )}

      <div data-testid="prompt-entry-chips" className="mt-4 flex flex-wrap gap-2">
        {searching && searchResults.length === 0 && <p className="text-sm text-slate-500">沒有符合的詞條</p>}
        {!searching && currentCategory === null && folders.length === 0 && <p className="text-sm text-slate-500">尚無分類</p>}
        {!searching && currentCategory !== null && currentEntries.length === 0 && <p className="text-sm text-slate-500">此分類尚無詞條</p>}
        {searching
          ? searchResults.slice(pageStart, pageStart + PAGE_SIZE).map(({ category, entry }) => (
              <EntryChip key={`${category.id}/${entry.id}`} category={category} entry={entry} pathLabel={pathLabelOf(category)} onAdd={onAddEntry} />
            ))
          : currentCategory !== null
            ? currentEntries.slice(pageStart, pageStart + PAGE_SIZE).map((entry) => (
                <EntryChip key={entry.id} category={currentCategory} entry={entry} onAdd={onAddEntry} />
              ))
            : null}
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
> `selectedCategory` prop 仍保留於 Props（workbench 傳入，維持相容），本檔目前未用於高亮但不移除，避免 workbench 端型別改動；若 lint 對未使用 prop 有意見，於解構保留即可（已解構但未用不影響）。

- [ ] **Step 3: 更新測試（browser + workbench）**

Run: `cd frontend && cat src/components/prompt-library/PromptEntryBrowser.test.tsx`
Run: `cd frontend && cat src/components/prompt-library/PromptWorkbench.test.tsx`

Browser 測試調整：
1. 既有測試 render `<PromptEntryBrowser .../>` 需補新必填 props `allEntries={[]}`，且 `onAddEntry` 現為 `(category, entry) => void`（既有 spy 斷言改為檢查第二參數 entry，或第一參數 category）。
2. 既有「chips + 30/頁分頁」測試改為在「已鑽入某分類」狀態下驗證：先點該分類的資料夾 chip（`📁 <name>`）進入，再驗證詞條 chips／分頁。或直接以 search 模式驗證分頁（輸入 query 讓 allEntries 命中 ≥31 筆）。
3. 新增測試：
   - **鑽入**：給 root 分類 + 一個子分類，頂層顯示 root 資料夾；點 root → 顯示其子分類資料夾 + 觸發 `onOpenCategory(root)`；麵包屑顯示「頂層 › root」。
   - **跨樹搜尋**：`allEntries` 含兩個不同分類的詞；輸入 query → 兩者都出現且各帶分類路徑標籤；點一個 → `onAddEntry` 收到「該詞所屬分類」與該 entry。
   - **加入帶正確分類**：搜尋結果點擊時，`onAddEntry` 第一參數為該 hit 的 category（不是目前鑽入的分類）。

Workbench 測試調整：
1. `addEntry` 呼叫點改為 `(category, entry)`；既有「加入詞條」互動測試若透過 UI 觸發則不受影響（UI 會傳 category）。
2. 既有 auto-sort/nested 整合測試：加入詞條的路徑改經新的 browser（點資料夾→點詞條）或直接呼叫 `addEntry(category, entry)`；確保仍斷言排序結果。
3. `getPromptCatalog`/`getPromptCategory` mock 需讓 `categoryResults` 可彙整 `allEntries`（既有 mock 通常已回 entries）。

> 依既有 mock/操作 helper 補齊；核心新斷言：鑽入顯示子分類與麵包屑、跨樹搜尋帶路徑、加入用 hit 的分類。

- [ ] **Step 4: 全前端測試 + typecheck + build**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 全 PASS、typecheck 乾淨、build 成功、輸出 pristine。**務必跑整套**（此改動牽動 workbench 與跨檔整合測試）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/PromptEntryBrowser.tsx frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx frontend/src/components/prompt-library/PromptWorkbench.tsx frontend/src/components/prompt-library/PromptWorkbench.test.tsx
git commit -m "feat(prompt-workbench): drill-down tree browser with breadcrumb + cross-tree search"
```

---

## Task 3: 收尾驗證與進度更新

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: 全前端驗證**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 測試全綠、typecheck、build 成功、pristine（無新增 console 警告）。

- [ ] **Step 2: `git diff --check`**

Run: `git diff --check`
Expected: 無輸出。

- [ ] **Step 3: 更新 `docs/PROGRESS.md`**

於檔案最上方新增：

```markdown
## 2026-07-27 Prompt Library 分類樹 Phase 3（工作台瀏覽器樹狀）

- 工作台左側「加入 Prompt」由扁平分類 chip 列改為**鑽入式＋麵包屑**：頂層列出 root 分類資料夾，點入後顯示其子分類資料夾與該分類詞條 chip（30/頁沿用）；麵包屑可跳回任一層或頂層。
- **跨整棵樹搜尋**：輸入關鍵字即攤平該 polarity 全樹，列出命中詞條並標示其分類路徑，點擊即以「該詞所屬分類」加入（`onAddEntry(category, entry)`）；某分類若載入失敗其詞條不入搜尋，但不影響其他分類。
- 純前端；後端沿用 Phase 1 的 `parent_id`。分類樹三階段（資料/排序、管理 UX、瀏覽器）至此完成。驗證：前端 vitest 全綠、`tsc` 與 Vite build 通過。
```

- [ ] **Step 4: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): prompt library category tree phase 3 (drill-down browser)"
```

---

## Self-Review 對照

- **spec Phase 3：左側鑽入式＋麵包屑（子分類資料夾＋該分類詞）** → Task 2（browser）＋ Task 1（childCategories）。✅
- **spec Phase 3：搜尋跨整棵樹、標分類路徑** → Task 2（search 模式 + allEntries + pathLabel）。✅
- **加入用該詞所屬分類（可從搜尋結果加入任一分類）** → Task 2（`addEntry(category, entry)`）。✅
- **可靠性：失敗分類不崩潰、不入搜尋** → allEntries 只彙整 fulfilled 分類；Global Constraints。✅
- **輸出不變／後端不動** → Global Constraints；fragment source ref 語意不變。✅
- **型別一致**：`BrowserCategory.parent_id/order`、`childCategories`、`onAddEntry(category, entry)`、`allEntries` 在 Task 1/2 一致。✅
- **每 task 後 repo green**：helper（1）→ browser＋workbench 一起改（2，避免簽名跨 task 破壞 tsc）→ 收尾（3）。✅
