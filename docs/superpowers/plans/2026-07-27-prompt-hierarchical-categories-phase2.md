# Prompt Library 分類樹 Phase 2（管理 UX）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓使用者在分類管理與詳情頁能設定/搬移父分類，並以縮排樹與麵包屑呈現階層——建立在 Phase 1 已完成的後端 `parent_id` 之上。

**Architecture:** 純前端。先把 `parent_id` 接進前端的分類寫入路徑（目前 `categoryWriteBody` 會把它丟掉）；新增純函式 `categoryTree.ts`（樹列/祖先鏈/子孫集）；再改「新增分類」表單（父分類選擇器）、分類清單（縮排樹）與詳情頁（麵包屑＋搬移父分類，且編輯時保留既有 parent）。後端已於 Phase 1 支援並驗證，無需改動。

**Tech Stack:** React 18 + TS + Vite + Tailwind；vitest + @testing-library（無 `user-event`，用 `fireEvent`）。

## Global Constraints

- **純前端**：不改後端/API schema（Phase 1 已提供 `parent_id` 寫入與驗證、catalog 帶出 `parent_id`）。
- **編輯不可誤清 parent**：詳情頁儲存分類時必須送出目前的 `parent_id`（後端在缺欄位時會視為 None＝清除父分類）。
- **清除父分類**：以送出 `parent_id: null` 表示「作為頂層」。
- **成環由後端把關**：前端 UX 排除自我與子孫以減少誤操作，但最終防環仍由 Phase 1 後端負責；後端錯誤以既有 `message（hint）` 呈現。
- 驗證：`cd frontend && npx vitest run <file>`、`npx tsc --noEmit`、`npm run build`。

---

## File Structure

| 檔案 | 責任 | 動作 |
|---|---|---|
| `frontend/src/types/api.ts` | `PromptCategoryWriteRequest` 加 `parent_id` | Modify（Task 1） |
| `frontend/src/components/prompt-library/promptLibraryApi.ts` | `putPromptCategory` 送出 `parent_id` | Modify（Task 1） |
| `frontend/src/components/prompt-library/categoryTree.ts` | 純函式：樹列 / 祖先鏈 / 子孫集 | Create（Task 1） |
| `frontend/src/components/prompt-library/categoryTree.test.ts` | 純函式測試 | Create（Task 1） |
| `frontend/src/pages/PromptCategoryManagement.tsx` | 新增表單父分類選擇器 + 縮排樹清單 | Modify（Task 2） |
| `frontend/src/pages/PromptCategoryManagement.test.tsx` | 對應測試 | Modify（Task 2） |
| `frontend/src/pages/PromptCategoryDetail.tsx` | 麵包屑 + 搬移父分類 + 編輯保留 parent | Modify（Task 3） |
| `frontend/src/pages/PromptCategoryDetail.test.tsx` | 對應測試 | Modify（Task 3） |
| `docs/PROGRESS.md` | 進度 | Modify（Task 4） |

---

## Task 1: 前端 `parent_id` 寫入串接 + `categoryTree` 純函式（TDD）

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/components/prompt-library/promptLibraryApi.ts`
- Create: `frontend/src/components/prompt-library/categoryTree.ts`
- Test: `frontend/src/components/prompt-library/categoryTree.test.ts`（新建）
- Test: `frontend/src/components/prompt-library/promptLibraryApi.test.ts`（追加）

**Interfaces:**
- Produces:
  - `PromptCategoryWriteRequest.parent_id?: string | null`
  - `putPromptCategory` 在 `input.parent_id !== undefined` 時把 `parent_id` 放入送出 body（可為 `null` 以清除父分類）。**不動** `putPromptEntry`（entry 寫入不帶 parent_id）。
  - `categoryTree.ts`：
    - `interface CategoryNodeLike { id: string; parent_id?: string | null; order: number }`
    - `orderedCategoryRows<T extends CategoryNodeLike>(categories: readonly T[]): { category: T; depth: number }[]`（前序：先父後子；同層依 `order` 再 `id`；`parent_id` 為空或指向集合外者視為 root）
    - `descendantIds(categories: readonly CategoryNodeLike[], rootId: string): Set<string>`（不含 rootId 自身）
    - `ancestorChain<T extends CategoryNodeLike>(categories: readonly T[], id: string): T[]`（回傳 `[root, …, self]`；含 cycle 防護）

- [ ] **Step 1: 寫失敗測試**

新建 `categoryTree.test.ts`：

```ts
import { describe, expect, it } from "vitest";
import { ancestorChain, descendantIds, orderedCategoryRows } from "./categoryTree";

const cats = [
  { id: "clothing", parent_id: null, order: 70 },
  { id: "clothing-top", parent_id: "clothing", order: 10 },
  { id: "clothing-bottom", parent_id: "clothing", order: 20 },
  { id: "quality", parent_id: null, order: 10 },
];

describe("orderedCategoryRows", () => {
  it("returns pre-order rows with depth, roots by order then children by order", () => {
    expect(orderedCategoryRows(cats).map((r) => [r.category.id, r.depth])).toEqual([
      ["quality", 0],
      ["clothing", 0],
      ["clothing-top", 1],
      ["clothing-bottom", 1],
    ]);
  });
  it("treats a dangling parent as a root", () => {
    const rows = orderedCategoryRows([{ id: "x", parent_id: "ghost", order: 5 }]);
    expect(rows).toEqual([{ category: { id: "x", parent_id: "ghost", order: 5 }, depth: 0 }]);
  });
});

describe("descendantIds", () => {
  it("collects all descendants excluding the root itself", () => {
    expect([...descendantIds(cats, "clothing")].sort()).toEqual(["clothing-bottom", "clothing-top"]);
    expect([...descendantIds(cats, "quality")]).toEqual([]);
  });
});

describe("ancestorChain", () => {
  it("returns root..self", () => {
    expect(ancestorChain(cats, "clothing-top").map((c) => c.id)).toEqual(["clothing", "clothing-top"]);
    expect(ancestorChain(cats, "quality").map((c) => c.id)).toEqual(["quality"]);
  });
  it("stops on a cycle without hanging", () => {
    const cyclic = [
      { id: "a", parent_id: "b", order: 1 },
      { id: "b", parent_id: "a", order: 1 },
    ];
    const chain = ancestorChain(cyclic, "a").map((c) => c.id);
    expect(chain[chain.length - 1]).toBe("a");
    expect(chain.length).toBeLessThanOrEqual(2);
  });
});
```

在 `promptLibraryApi.test.ts` 追加（沿用該檔既有 fetch mock 慣例；若檔案以 `vi.stubGlobal("fetch", ...)` 或攔截 `fetch` 驗證 body，照其模式）：

```ts
it("putPromptCategory sends parent_id when provided (including null to clear)", async () => {
  const calls: RequestInit[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    calls.push(init as RequestInit);
    return { ok: true, json: async () => ({}) } as Response;
  }));
  const { putPromptCategory } = await import("./promptLibraryApi");
  await putPromptCategory("positive", "clothing-top", {
    name_zh: "上衣", description_zh: "d", aliases: [], keywords: [], order: 10,
    expected_revision: 0, parent_id: "clothing",
  });
  expect(JSON.parse(calls[0].body as string).parent_id).toBe("clothing");
  await putPromptCategory("positive", "clothing", {
    name_zh: "服裝", description_zh: "d", aliases: [], keywords: [], order: 70,
    expected_revision: 1, parent_id: null,
  });
  expect(JSON.parse(calls[1].body as string).parent_id).toBeNull();
});
```
> 若既有 `promptLibraryApi.test.ts` 已有共用 fetch mock/helper，改用它，勿重複 stub。

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd frontend && npx vitest run src/components/prompt-library/categoryTree.test.ts src/components/prompt-library/promptLibraryApi.test.ts`
Expected: FAIL（`categoryTree` 不存在；`putPromptCategory` 未送 parent_id）。

- [ ] **Step 3: 實作**

在 `types/api.ts` 的 `PromptCategoryWriteRequest` 介面加：
```ts
  parent_id?: string | null;
```
在 `promptLibraryApi.ts` 的 `putPromptCategory` 把 body 改為帶 parent_id（不動 `categoryWriteBody`，以免影響 `putPromptEntry`）：
```ts
export function putPromptCategory(
  polarity: PromptPolarity,
  categoryId: string,
  input: PromptCategoryWriteRequest,
): Promise<PromptLibraryWriteResponse> {
  const body: PromptCategoryWriteRequest = {
    ...categoryWriteBody(input),
    ...(input.parent_id !== undefined ? { parent_id: input.parent_id } : {}),
  };
  return requestJson<PromptLibraryWriteResponse>(
    `${API_ROOT}/categories/${segment(polarity)}/${segment(categoryId)}`,
    jsonWrite("PUT", body),
  );
}
```
新建 `categoryTree.ts`：
```ts
export interface CategoryNodeLike {
  id: string;
  parent_id?: string | null;
  order: number;
}

function childrenByParent<T extends CategoryNodeLike>(
  categories: readonly T[],
): { roots: T[]; children: Map<string, T[]> } {
  const ids = new Set(categories.map((category) => category.id));
  const children = new Map<string, T[]>();
  const roots: T[] = [];
  for (const category of categories) {
    const parentId = category.parent_id ?? null;
    if (parentId && ids.has(parentId)) {
      const bucket = children.get(parentId) ?? [];
      bucket.push(category);
      children.set(parentId, bucket);
    } else {
      roots.push(category);
    }
  }
  const bySiblingOrder = (a: T, b: T) => a.order - b.order || a.id.localeCompare(b.id);
  roots.sort(bySiblingOrder);
  for (const bucket of children.values()) bucket.sort(bySiblingOrder);
  return { roots, children };
}

export function orderedCategoryRows<T extends CategoryNodeLike>(
  categories: readonly T[],
): { category: T; depth: number }[] {
  const { roots, children } = childrenByParent(categories);
  const rows: { category: T; depth: number }[] = [];
  const visit = (category: T, depth: number, guard: Set<string>) => {
    if (guard.has(category.id)) return;
    guard.add(category.id);
    rows.push({ category, depth });
    for (const child of children.get(category.id) ?? []) visit(child, depth + 1, guard);
  };
  const guard = new Set<string>();
  for (const root of roots) visit(root, 0, guard);
  return rows;
}

export function descendantIds(
  categories: readonly CategoryNodeLike[],
  rootId: string,
): Set<string> {
  const { children } = childrenByParent(categories);
  const result = new Set<string>();
  const stack = [...(children.get(rootId) ?? [])];
  while (stack.length > 0) {
    const node = stack.pop()!;
    if (result.has(node.id)) continue;
    result.add(node.id);
    stack.push(...(children.get(node.id) ?? []));
  }
  return result;
}

export function ancestorChain<T extends CategoryNodeLike>(
  categories: readonly T[],
  id: string,
): T[] {
  const byId = new Map(categories.map((category) => [category.id, category]));
  const chain: T[] = [];
  const guard = new Set<string>();
  let cursor: string | null = id;
  while (cursor) {
    const node = byId.get(cursor);
    if (!node || guard.has(cursor)) break;
    guard.add(cursor);
    chain.push(node);
    cursor = node.parent_id ?? null;
  }
  return chain.reverse();
}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/categoryTree.test.ts src/components/prompt-library/promptLibraryApi.test.ts`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/components/prompt-library/promptLibraryApi.ts frontend/src/components/prompt-library/categoryTree.ts frontend/src/components/prompt-library/categoryTree.test.ts frontend/src/components/prompt-library/promptLibraryApi.test.ts
git commit -m "feat(prompt-library): thread category parent_id through write API + tree helpers"
```

---

## Task 2: 分類管理 — 新增表單父分類選擇器 + 縮排樹清單

**Files:**
- Modify: `frontend/src/pages/PromptCategoryManagement.tsx`
- Modify: `frontend/src/pages/PromptCategoryManagement.test.tsx`

**Interfaces:**
- Consumes: Task 1 的 `orderedCategoryRows`、`putPromptCategory` 帶 parent_id。
- Produces: 新增分類可選父分類（送出 `parent_id`）；「現有分類」清單改縮排樹。

- [ ] **Step 1: 實作父分類選擇器 + 送出 parent_id**

在 `PromptCategoryManagement.tsx`：
1. 頂部 import 加：
```tsx
import { orderedCategoryRows } from "../components/prompt-library/categoryTree";
```
2. 於 state 區新增：
```tsx
  const [parentId, setParentId] = useState("");
```
3. 於 `createCategory` 內的 `putPromptCategory(polarity, id, { ... })` 物件加一行（在 `expected_revision: 0,` 之後）：
```tsx
          parent_id: parentId || null,
```
4. 成功後（`setCategoryId("");` 那組 reset 之後）加：
```tsx
        setParentId("");
```
5. 在表單「分類 ID」欄位**之前**插入父分類選擇器（用同 polarity 未封存分類建縮排 options）：
```tsx
            <div>
              <label htmlFor="category-parent" className="mb-1 block text-sm text-slate-400">父分類</label>
              <select
                id="category-parent"
                value={parentId}
                onChange={(event) => setParentId(event.target.value)}
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
              >
                <option value="">（無，作為頂層）</option>
                {orderedCategoryRows(
                  catalog.filter((category) => category.polarity === polarity && !category.archived),
                ).map(({ category, depth }) => (
                  <option key={category.id} value={category.id}>
                    {`${"　".repeat(depth)}${category.name_zh}`}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-500">留空表示頂層分類；巢狀深度不限。</p>
            </div>
```
6. 切換 polarity 時清掉已選父分類，避免跨 polarity 殘留：把 `PolarityTabs` 於**表單內**那顆的 `onChange` 由 `setPolarity` 改為：
```tsx
              <PolarityTabs value={polarity} onChange={(next) => { setPolarity(next); setParentId(""); }} />
```

- [ ] **Step 2: 清單改縮排樹**

把「現有分類」的 `<ul className="grid gap-2 sm:grid-cols-2">{visibleCategories.map(...)}</ul>` 改為單欄縮排樹（沿用 `CategoryCard`，外層加左內距表示深度）：
```tsx
              <ul className="space-y-2">
                {orderedCategoryRows(visibleCategories).map(({ category, depth }) => (
                  <li key={`${category.polarity}-${category.id}`} style={{ marginLeft: depth * 20 }}>
                    <CategoryCard category={category} />
                  </li>
                ))}
              </ul>
```
（`CategoryCard` 內部不變；`visibleCategories` 已是同 polarity + 同封存狀態的集合。）

- [ ] **Step 3: 更新/新增測試**

Run: `cd frontend && cat src/pages/PromptCategoryManagement.test.tsx`

依既有 mock（`getPromptCatalog`、`putPromptCategory` 多被 mock）新增/調整：
1. 若既有測試斷言清單為 grid，改為斷言分類名稱仍出現（縮排不影響文字）。
2. 新增測試：mock catalog 有一個 root 分類；填表單、選該 root 為父分類、送出 → 斷言 `putPromptCategory` 收到的第三參數含 `parent_id: "<root-id>"`。骨架：
```tsx
it("creates a child category under the selected parent", async () => {
  // getPromptCatalog → [{ polarity:"positive", id:"clothing", name_zh:"服裝", order:70, parent_id:null, archived:false, entry_count:0, etag:"e" }]
  // putPromptCategory → resolves { category: { category: {...}, etag:"e" } }
  render(/* the page, per existing test's render helper */);
  // fill 分類 ID / 中文名稱 / 說明 / 排序, then:
  fireEvent.change(screen.getByLabelText("父分類"), { target: { value: "clothing" } });
  fireEvent.click(screen.getByRole("button", { name: /建立分類/ }));
  await waitFor(() => expect(putPromptCategorySpy).toHaveBeenCalled());
  const [, , body] = putPromptCategorySpy.mock.calls[0];
  expect(body.parent_id).toBe("clothing");
});
```
> 依該檔既有 spy/mock 命名補齊。

- [ ] **Step 4: 執行測試 + typecheck**

Run: `cd frontend && npx vitest run src/pages/PromptCategoryManagement.test.tsx && npx tsc --noEmit`
Expected: PASS、typecheck 乾淨。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PromptCategoryManagement.tsx frontend/src/pages/PromptCategoryManagement.test.tsx
git commit -m "feat(prompt-library): parent picker + indented tree in category management"
```

---

## Task 3: 分類詳情 — 麵包屑 + 搬移父分類（編輯保留 parent）

**Files:**
- Modify: `frontend/src/pages/PromptCategoryDetail.tsx`
- Modify: `frontend/src/pages/PromptCategoryDetail.test.tsx`

**Interfaces:**
- Consumes: Task 1 的 `ancestorChain`、`descendantIds`、`orderedCategoryRows`、`getPromptCatalog`、`putPromptCategory` 帶 parent_id。
- Produces: 詳情頁載入 catalog 以顯示麵包屑與父分類選項；`CategoryDraft` 帶 `parentId`；儲存送出 `parent_id`（保留或變更）。

- [ ] **Step 1: 載入 catalog + draft 帶 parentId + 送出 parent_id**

在 `PromptCategoryDetail.tsx`：
1. import 加：
```tsx
import { getPromptCatalog, ... } from "../components/prompt-library/promptLibraryApi";
import { ancestorChain, descendantIds, orderedCategoryRows } from "../components/prompt-library/categoryTree";
import type { PromptCategorySummary } from "../types/api";
```
（`getPromptCatalog` 併入既有 promptLibraryApi import。）
2. `CategoryDraft` 型別加 `parentId: string`：
```tsx
type CategoryDraft = Pick<PromptCategory, "name_zh" | "description_zh"> & { aliases: string; keywords: string; order: string; parentId: string };
```
3. `draftFrom` 帶入 parent：
```tsx
function draftFrom(category: PromptCategory): CategoryDraft {
  return {
    name_zh: category.name_zh,
    description_zh: category.description_zh,
    aliases: category.aliases.join(", "),
    keywords: category.keywords.join(", "),
    order: String(category.order),
    parentId: category.parent_id ?? "",
  };
}
```
4. 新增 catalog state 與載入（於既有 `useEffect` 載入單一分類旁，新增一支載入 catalog 的 effect）：
```tsx
  const [categories, setCategories] = useState<PromptCategorySummary[]>([]);
  useEffect(() => {
    let active = true;
    void getPromptCatalog().then((data) => { if (active) setCategories(data.categories ?? []); }).catch(() => {});
    return () => { active = false; };
  }, [retryGeneration]);
```
5. `saveCategory` 送出 parent_id（於 `putPromptCategory(currentPolarity, currentCategoryId, { ... })` 內、`order,` 之後加）：
```tsx
      parent_id: categoryDraft!.parentId ? categoryDraft!.parentId : null,
```

- [ ] **Step 2: 麵包屑 + 父分類選擇器 UI**

在「分類資料編輯」section 內、`<div className="grid ...">` 的欄位群中，於「分類 ID」欄位後新增父分類選擇器（同 polarity、排除自己與所有子孫，避免明顯成環）：
```tsx
          <Field label="父分類">
            <select
              aria-label="父分類"
              disabled={busy}
              value={categoryDraft.parentId}
              onChange={(event) => setCategoryDraft({ ...categoryDraft, parentId: event.target.value })}
              className={fieldClass}
            >
              <option value="">（無，作為頂層）</option>
              {orderedCategoryRows(
                categories.filter(
                  (item) =>
                    item.polarity === currentPolarity &&
                    !item.archived &&
                    item.id !== currentCategoryId &&
                    !descendantIds(
                      categories.filter((c) => c.polarity === currentPolarity),
                      currentCategoryId,
                    ).has(item.id),
                ),
              ).map(({ category: option, depth }) => (
                <option key={option.id} value={option.id}>
                  {`${"　".repeat(depth)}${option.name_zh}`}
                </option>
              ))}
            </select>
          </Field>
```
在 `<header ...>` 內（分類標題附近）加麵包屑：
```tsx
        {categories.length > 0 && (
          <nav aria-label="分類路徑" className="mt-2 text-xs text-slate-400">
            {ancestorChain(categories.filter((c) => c.polarity === details.polarity), details.id)
              .map((node) => node.name_zh)
              .join(" › ")}
          </nav>
        )}
```

- [ ] **Step 3: 測試**

Run: `cd frontend && cat src/pages/PromptCategoryDetail.test.tsx`

依既有 mock（`getPromptCategory`、`putPromptCategory`、可能需新增 `getPromptCatalog` mock）新增/調整：
1. **編輯保留 parent**：載入一個已有 `parent_id` 的分類，只改中文名稱後儲存 → 斷言 `putPromptCategory` body 的 `parent_id` 等於原值（不被清成 null）。
2. **搬移**：改父分類選擇器後儲存 → body `parent_id` 為新值；選「（無）」→ `parent_id` 為 null。
3. **麵包屑**：mock catalog 有 root＋child，載入 child → 斷言麵包屑文字含 root › child。
4. 既有測試若因新增 `getPromptCatalog` 呼叫而需要 mock，補上回傳 `{ categories: [...] }`。

骨架（依既有慣例補齊 mock）：
```tsx
it("preserves parent_id when editing an unrelated field", async () => {
  // getPromptCategory → category with parent_id "clothing"
  // getPromptCatalog → categories incl clothing + this
  render(/* detail route per existing helper */);
  await screen.findByLabelText("分類中文名稱");
  fireEvent.change(screen.getByLabelText("分類中文名稱"), { target: { value: "新名稱" } });
  fireEvent.click(screen.getByRole("button", { name: /儲存分類/ }));
  await waitFor(() => expect(putPromptCategorySpy).toHaveBeenCalled());
  const [, , body] = putPromptCategorySpy.mock.calls[0];
  expect(body.parent_id).toBe("clothing");
});
```

- [ ] **Step 4: 全前端測試 + typecheck + build**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 全 PASS、typecheck 乾淨、build 成功。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PromptCategoryDetail.tsx frontend/src/pages/PromptCategoryDetail.test.tsx
git commit -m "feat(prompt-library): category detail breadcrumb + parent move (preserve on edit)"
```

---

## Task 4: 收尾驗證與進度更新

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: 全前端驗證**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 測試全綠、typecheck、build 成功（記錄測試數）。

- [ ] **Step 2: `git diff --check`**

Run: `git diff --check`
Expected: 無輸出。

- [ ] **Step 3: 更新 `docs/PROGRESS.md`**

於檔案最上方新增：

```markdown
## 2026-07-27 Prompt Library 分類樹 Phase 2（管理 UX）

- 前端分類寫入路徑接上 `parent_id`（先前 `categoryWriteBody` 會丟棄）；`putPromptCategory` 現會送出 `parent_id`（可為 null 以設為頂層）。新增純函式 `categoryTree`（樹列前序、祖先鏈、子孫集）。
- 分類管理頁：「新增分類」表單加「父分類」選擇器（同 polarity 縮排選項，留空＝頂層）；「現有分類」清單改縮排樹呈現。
- 分類詳情頁：顯示分類路徑麵包屑；可搬移父分類（選項排除自己與所有子孫，避免明顯成環，最終防環由後端把關）；**編輯任何欄位都會保留既有 parent**，不會誤清。
- 純前端；後端沿用 Phase 1 的 parent_id 寫入與驗證。畫面工作台瀏覽器樹狀（Phase 3）另行。驗證：前端 vitest 全綠、`tsc` 與 Vite build 通過。
```

- [ ] **Step 4: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): prompt library category tree phase 2 (management UX)"
```

---

## Self-Review 對照

- **spec Phase 2：新增分類選父分類** → Task 1（API/型別）+ Task 2（表單）。✅
- **spec Phase 2：分類清單縮排樹** → Task 2。✅
- **spec Phase 2：詳情頁麵包屑 + 搬移父分類** → Task 3。✅
- **spec Phase 2：詞條增刪改幾乎不變** → 未動 `PromptEntryEditor`／entry 寫入路徑。✅
- **編輯不可誤清 parent** → Global Constraints + Task 3 Step 1（draftFrom 帶 parentId）+ Task 3 測試 1。✅
- **成環由後端把關、前端排除自我/子孫** → Task 3 Step 2 + Global Constraints。✅
- **型別一致性**：`parent_id?: string | null`、`CategoryNodeLike`、`orderedCategoryRows`/`descendantIds`/`ancestorChain`、`CategoryDraft.parentId` 在 Task 1/2/3 使用一致。✅
- **每 task 後 repo green**：helper+API（1）→ 管理頁（2）→ 詳情頁（3）→ 收尾（4）。✅
- Phase 3（工作台瀏覽器樹狀）不在本 plan。
