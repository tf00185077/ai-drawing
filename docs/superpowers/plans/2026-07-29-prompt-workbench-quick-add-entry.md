# Prompt Workbench 快速新增自訂詞條 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在工作台「加入 Prompt」面板加一個「新增詞條」小表單：選任一層分類＋中文＋英文，即把自訂詞條存進詞庫（不自動加入組合）。

**Architecture:** 純前端。新增純函式 `slugifyEntryId`（英文自動產生 slug、同分類去重）；`PromptEntryBrowser` 加表單並透過新 prop `onCreateEntry` 回呼；`PromptWorkbench` 實作 `onCreateEntry`（先 `getPromptCategory` 取現況與既有 id → `putPromptEntry` → 刷新搜尋資料/重載開啟中的分類）。後端/API 不動。

**Tech Stack:** React 18 + TS + Vite + Tailwind；vitest + @testing-library（無 `user-event`，用 `fireEvent`）。

## Global Constraints

- **純前端**：不改後端/API/schema/MCP；沿用既有 `getPromptCategory`、`putPromptEntry`。
- **不覆蓋既有詞條**：自動 slug 撞名時加後綴 `-2`、`-3`…。
- **comma-atomic**：英文 prompt 不得含逗號（表單擋＋`onCreateEntry` 防禦性再查）。
- **只存入詞庫**：建立後不加入目前組合；但要讓新詞條立即可被瀏覽/搜尋。
- **自動欄位**：`description_zh = name_zh`、`order = 10`、`aliases/keywords = []`。
- 驗證：`cd frontend && npx vitest run <file>`、`npx tsc --noEmit`、`npm run build`。

---

## File Structure

| 檔案 | 責任 | 動作 |
|---|---|---|
| `frontend/src/components/prompt-library/entrySlug.ts` | 純函式 `slugifyEntryId` | Create（Task 1） |
| `frontend/src/components/prompt-library/entrySlug.test.ts` | 測試 | Create（Task 1） |
| `frontend/src/components/prompt-library/PromptEntryBrowser.tsx` | 「新增詞條」表單 + `onCreateEntry` prop | Modify（Task 2） |
| `frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx` | 表單測試 | Modify（Task 2） |
| `frontend/src/components/prompt-library/PromptWorkbench.tsx` | 實作 `onCreateEntry` + wiring + 刷新 | Modify（Task 2） |
| `frontend/src/components/prompt-library/PromptWorkbench.test.tsx` | 對應測試 | Modify（Task 2） |
| `docs/PROGRESS.md` | 進度 | Modify（Task 3） |

---

## Task 1: `slugifyEntryId` 純函式（TDD）

**Files:**
- Create: `frontend/src/components/prompt-library/entrySlug.ts`
- Test: `frontend/src/components/prompt-library/entrySlug.test.ts`

**Interfaces:**
- Produces: `slugifyEntryId(prompt: string, existingIds: readonly string[]): string`——英文小寫、非 `a-z0-9` 轉 `-`、收斂連續與首尾 `-`；與 `existingIds` 撞名時回 `${base}-2`（再撞 `-3`…）；base 為空丟 `Error("無法從英文產生 ID，請確認英文內容")`。

- [ ] **Step 1: 寫失敗測試**

新建 `entrySlug.test.ts`：

```ts
import { describe, expect, it } from "vitest";
import { slugifyEntryId } from "./entrySlug";

describe("slugifyEntryId", () => {
  it("slugifies English into lowercase-hyphen id", () => {
    expect(slugifyEntryId("Detailed Eyes", [])).toBe("detailed-eyes");
    expect(slugifyEntryId("  best   quality!! ", [])).toBe("best-quality");
    expect(slugifyEntryId("score_9", [])).toBe("score-9");
  });
  it("appends a numeric suffix on collision within the category", () => {
    expect(slugifyEntryId("dress", ["dress"])).toBe("dress-2");
    expect(slugifyEntryId("dress", ["dress", "dress-2"])).toBe("dress-3");
  });
  it("returns the base when there is no collision", () => {
    expect(slugifyEntryId("dress", ["skirt"])).toBe("dress");
  });
  it("throws when the slug is empty (no ascii alphanumerics)", () => {
    expect(() => slugifyEntryId("　！？", [])).toThrowError(/無法從英文產生 ID/);
    expect(() => slugifyEntryId("", [])).toThrowError(/無法從英文產生 ID/);
  });
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd frontend && npx vitest run src/components/prompt-library/entrySlug.test.ts`
Expected: FAIL（`entrySlug` 不存在）。

- [ ] **Step 3: 實作**

新建 `entrySlug.ts`：

```ts
export function slugifyEntryId(prompt: string, existingIds: readonly string[]): string {
  const base = prompt
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (base === "") {
    throw new Error("無法從英文產生 ID，請確認英文內容");
  }
  const taken = new Set(existingIds);
  if (!taken.has(base)) return base;
  let suffix = 2;
  while (taken.has(`${base}-${suffix}`)) suffix += 1;
  return `${base}-${suffix}`;
}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/entrySlug.test.ts`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/entrySlug.ts frontend/src/components/prompt-library/entrySlug.test.ts
git commit -m "feat(prompt-library): slugifyEntryId helper (auto id + collision suffix)"
```

---

## Task 2: 表單（`PromptEntryBrowser`）＋ `onCreateEntry`（`PromptWorkbench`）

**Files:**
- Modify: `frontend/src/components/prompt-library/PromptEntryBrowser.tsx`
- Modify: `frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`

**Interfaces:**
- Consumes: Task 1 的 `slugifyEntryId`；既有 `getPromptCategory`、`putPromptEntry`、`orderedCategoryRows`。
- Produces:
  - `PromptEntryBrowser` 新增必填 prop `onCreateEntry: (category: BrowserCategory, input: { name_zh: string; prompt: string }) => Promise<void>`。
  - `PromptWorkbench` 新增 `createEntry(targetCategory, input)` 並傳入。

- [ ] **Step 1: `PromptWorkbench` 實作 `createEntry` + 傳入**

在 `PromptWorkbench.tsx`：
1. import 補：`getPromptCategory` 已 import；加 `putPromptEntry`（自 `./promptLibraryApi`）與 `import { slugifyEntryId } from "./entrySlug";`。若 `BrowserEntry` 型別未 import，於 `PromptEntryBrowser` import 補上 `type BrowserEntry`。
2. 新增函式（放在 `addEntry` 附近；注意：workbench 內開啟中的分類 state 變數名為 `category`，故參數改名 `targetCategory` 以免混淆）：
```tsx
  async function createEntry(
    targetCategory: BrowserCategory,
    input: { name_zh: string; prompt: string },
  ): Promise<void> {
    if (input.prompt.includes(",")) {
      throw new Error("英文 prompt 不能含逗號（一個詞條是一個 tag）");
    }
    const detail = await getPromptCategory(targetCategory.polarity, targetCategory.id);
    const existingIds = detail.category.entries.map((item) => item.id);
    const id = slugifyEntryId(input.prompt, existingIds);
    const response = await putPromptEntry(targetCategory.polarity, targetCategory.id, id, {
      name_zh: input.name_zh,
      description_zh: input.name_zh,
      prompt: input.prompt,
      aliases: [],
      keywords: [],
      order: 10,
      expected_revision: detail.category.revision,
      expected_etag: detail.etag,
    });
    const savedEntry = response.entry;
    if (savedEntry) {
      setAllEntries((current) => [...current, { category: targetCategory, entry: savedEntry }]);
    }
    // 若目前正停在該分類，重載其詞條清單讓新詞條立即出現
    if (category && category.id === targetCategory.id && category.polarity === targetCategory.polarity) {
      openCategory(category);
    }
  }
```
> 註：`putPromptEntry` 回傳的 `response.entry` 型別為 `PromptEntry | null`，結構相容 `BrowserEntry`（id/name_zh/prompt/description_zh/aliases/keywords/order/revision/archived）。若 tsc 對型別有意見，`response.entry as BrowserEntry`。
3. render 傳入：把 `<PromptEntryBrowser ... />` 加上 `onCreateEntry={createEntry}`（其餘 props 不變）。

- [ ] **Step 2: `PromptEntryBrowser` 加「新增詞條」表單**

在 `PromptEntryBrowser.tsx`：
1. import 補：`import { ancestorChain, childCategories, orderedCategoryRows } from "./categoryTree";`（`orderedCategoryRows` 新增）。
2. Props 介面加：
```tsx
  onCreateEntry: (category: BrowserCategory, input: { name_zh: string; prompt: string }) => Promise<void>;
```
並在解構參數加入 `onCreateEntry`。
3. 元件內新增 local state（在既有 `useState` 附近）：
```tsx
  const [newCategoryId, setNewCategoryId] = useState("");
  const [newNameZh, setNewNameZh] = useState("");
  const [newPrompt, setNewPrompt] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
```
4. 於 `changePolarity` 內清掉新增表單的分類選擇與訊息：
```tsx
  const changePolarity = (polarity: PromptPolarity) => {
    setCurrentId(null);
    setNewCategoryId("");
    setCreateError(null);
    setCreateSuccess(null);
    onPolarityChange(polarity);
  };
```
5. 新增提交函式：
```tsx
  const submitNewEntry = async () => {
    setCreateError(null);
    setCreateSuccess(null);
    const category = polarityCategories.find((item) => item.id === newCategoryId);
    if (!category) { setCreateError("請選擇分類"); return; }
    const nameZh = newNameZh.trim();
    const prompt = newPrompt.trim();
    if (!nameZh || !prompt) { setCreateError("請填寫中文名稱與英文 prompt"); return; }
    if (prompt.includes(",")) { setCreateError("英文 prompt 不能含逗號（一個詞條是一個 tag）"); return; }
    setCreating(true);
    try {
      await onCreateEntry(category, { name_zh: nameZh, prompt });
      setNewNameZh("");
      setNewPrompt("");
      setCreateSuccess(`已新增到「${category.name_zh}」`);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : String(error));
    } finally {
      setCreating(false);
    }
  };
```
6. 在「自由文字」區塊**之後**（`</div>` 收尾前）新增表單區：
```tsx
      <div className="mt-5 border-t border-slate-700 pt-4">
        <h3 className="text-sm font-medium text-slate-300">新增詞條到詞庫</h3>
        <label className="mt-2 block text-xs text-slate-400">分類
          <select aria-label="新增詞條分類" value={newCategoryId} disabled={creating} onChange={(event) => setNewCategoryId(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-sm text-white">
            <option value="">（請選擇分類）</option>
            {orderedCategoryRows(polarityCategories).map(({ category, depth }) => (
              <option key={category.id} value={category.id}>{`${"　".repeat(depth)}${category.name_zh}`}</option>
            ))}
          </select>
        </label>
        <label className="mt-2 block text-xs text-slate-400">中文名稱
          <input aria-label="新增詞條中文名稱" value={newNameZh} disabled={creating} onChange={(event) => setNewNameZh(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-sm text-white" />
        </label>
        <label className="mt-2 block text-xs text-slate-400">英文 prompt
          <input aria-label="新增詞條英文 prompt" value={newPrompt} disabled={creating} onChange={(event) => setNewPrompt(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-sm text-white" />
        </label>
        <button type="button" disabled={creating} onClick={submitNewEntry} className="mt-2 w-full rounded-lg bg-emerald-700 px-3 py-2 text-sm text-white disabled:opacity-40">{creating ? "新增中…" : "新增到詞庫"}</button>
        {createError && <p role="alert" className="mt-2 text-xs text-red-300">{createError}</p>}
        {createSuccess && <p role="status" className="mt-2 text-xs text-emerald-300">{createSuccess}</p>}
      </div>
```
（`polarityCategories` 已於檔內定義為目前 polarity 未封存分類。）

- [ ] **Step 3: 更新/新增測試**

Run: `cd frontend && cat src/components/prompt-library/PromptEntryBrowser.test.tsx`
Run: `cd frontend && cat src/components/prompt-library/PromptWorkbench.test.tsx`

Browser 測試：
1. 既有 render `<PromptEntryBrowser .../>` 補新必填 prop `onCreateEntry={vi.fn().mockResolvedValue(undefined)}`（或既有 helper 統一補）。
2. 新增測試：
   - **驗證擋下**：未選分類按「新增到詞庫」→ 顯示「請選擇分類」；選了分類但英文含逗號 → 顯示逗號提示；`onCreateEntry` 未被呼叫。
   - **成功流程**：選分類、填中文/英文、送出 → `onCreateEntry` 收到 `(該 category, { name_zh, prompt })`；resolve 後欄位清空並顯示成功訊息。
   - **失敗顯示**：`onCreateEntry` reject(Error("x")) → 顯示「x」。

Workbench 測試：
1. `createEntry` 整合：mock `getPromptCategory` 回一個含既有詞條 id 的分類、mock `putPromptEntry` 回 `{ entry: {...} }`；透過瀏覽器表單（或直接呼叫）建立 → 斷言 `putPromptEntry` 以**去重後的 slug**、`description_zh === name_zh`、`order === 10`、帶 `expected_revision/expected_etag` 呼叫；成功後新詞條可經跨樹搜尋找到（進入 allEntries）、且**未**加入 Positive/Negative 最終文字（不加入組合）。
2. 既有 mock 若缺 `putPromptEntry`，補上 `vi.mocked(putPromptEntry)`。

> 依既有 mock/操作 helper 補齊；核心斷言：去重 slug、自動欄位、只存不加入組合。

- [ ] **Step 4: 全前端測試 + typecheck + build**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 全 PASS、typecheck 乾淨、build 成功、pristine。**務必跑整套**（牽動 workbench 與跨檔測試）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/PromptEntryBrowser.tsx frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx frontend/src/components/prompt-library/PromptWorkbench.tsx frontend/src/components/prompt-library/PromptWorkbench.test.tsx
git commit -m "feat(prompt-workbench): quick-add custom entry form (pick layer + zh + en)"
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
## 2026-07-29 Prompt Workbench 快速新增自訂詞條

- 工作台「加入 Prompt」面板新增「新增詞條到詞庫」小表單：選任一層分類（縮排樹下拉）＋中文名稱＋英文 prompt，即把自訂詞條存入該分類。
- 自動處理其餘欄位：由英文自動產生 slug（同分類撞名加 `-2`/`-3` 後綴，不覆蓋既有詞條）、`description_zh` 帶中文名、`order` 預設、別名/關鍵字留空；英文含逗號會擋下（一個詞條＝一個 tag）。送出前先讀該分類目前 revision/etag 與既有 id 做去重與樂觀鎖。
- 依決策：建立後**只存入詞庫、不自動加入目前組合**；成功後把新詞條併入跨樹搜尋資料、若正停在該分類則重載，使其立即可瀏覽/搜尋/手動加入。
- 純前端；沿用既有 `getPromptCategory`／`putPromptEntry`，後端/API 不動。驗證：前端 vitest 全綠、`tsc` 與 Vite build 通過。
```

- [ ] **Step 4: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): workbench quick-add custom entry"
```

---

## Self-Review 對照

- **spec：面板內表單（分類樹選擇＋中文＋英文）** → Task 2（browser）。✅
- **spec：自動 slug + 同分類去重、不覆蓋** → Task 1（`slugifyEntryId`）＋ Task 2（`createEntry` 用既有 id 去重）。✅
- **spec：description_zh=name_zh、order 預設、別名/關鍵字空** → Task 2（`createEntry`）。✅
- **spec：擋逗號（comma-atomic）** → Task 2（表單 + `createEntry` 雙擋）。✅
- **spec：只存入詞庫、不加入組合、成功後可搜尋** → Task 2（append allEntries、重載開啟分類、無 addEntry）＋ workbench 測試。✅
- **spec：先取現況做去重/樂觀鎖** → Task 2（`getPromptCategory` → expected_revision/etag）。✅
- **後端不動** → Global Constraints；只用既有 API。✅
- **型別一致**：`slugifyEntryId(prompt, existingIds)`、`onCreateEntry(category, { name_zh, prompt })`、`createEntry(targetCategory, input)` 在 Task 1/2 一致。✅
- **每 task 後 repo green**：純函式（1）→ 表單＋workbench 一起改（2，避免 prop 簽名跨 task 破壞 tsc）→ 收尾（3）。✅
