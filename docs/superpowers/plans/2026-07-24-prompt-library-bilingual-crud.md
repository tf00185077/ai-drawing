# Prompt Library 雙語軟性偵測 + Entry 增刪改查 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 agent 透過 MCP 寫入雙語詞庫時，用軟性 warning 提醒補上有意義中文對照，並在操作台補齊 entry 的增刪改查，讓使用者能兜底修正。

**Architecture:** 三層、共用一條「可疑中文」啟發式，backend 端點與 schema 完全不動。(1) MCP `prompt_library_save` 加契約 docstring＋成功後附 `warnings`（永不擋）。(2) 前端共用啟發式模組標 ⚠️。(3) 操作台詞條區開放既有 `PUT .../entries/{id}` 與 `POST /archive` 端點，做完整 entry CRUD。

**Tech Stack:** Python 3.11（MCP，FastMCP tool，pytest）；React 18 + TypeScript + Vite + Tailwind（前端，vitest + @testing-library/react）。

## Global Constraints

- backend 端點與 Prompt Library JSON schema **完全不動**；本計畫只改 MCP 工具層與前端。
- 不引入任何 i18n 框架 / locale 檔；不新增 `name_en` 欄位。
- **Entry 的樂觀鎖單位是「分類檔案」**：新增／修改／封存 entry 一律帶 `expected_revision = 分類目前 revision`、`expected_etag = 分類目前 etag`（見 `backend/app/core/prompt_library_writes.py` 的 `save_entry` / `_archive_entry`，兩者都對 `current.model.revision`＝分類 revision 做 precondition）。不得改用 entry 自己的 revision，也不得繞過此契約。
- MCP 軟性偵測**永不擋**：`prompt_library_save` 回傳的 `ok` 恆為 True，problem 只透過 `warnings` 表達，格式為 `code + message + hint (+ details)`（對齊 AGENTS.md §3.5「錯誤是修復指南」與 backend `PromptWarning`）。
- 前端沿用既有慣例：函數元件、`.tsx`、Tailwind；樂觀鎖衝突把後端 `detail.message` 顯示給使用者，不繞過。
- 「可疑中文」啟發式只抓兩種鐵定失敗，不判斷翻譯品質、不檢查 `description_zh`：
  1. `name_zh` 不含 CJK 表意文字（regex `[㐀-䶿一-鿿]`）。
  2. （僅 entry，因只有 entry 有 `prompt`）`name_zh` 正規化（trim＋收斂空白＋小寫）後等於 `prompt`。
  偵測順序：先判 echoes（較具體），再判 missing-chinese。
- 每個 Task 完成即 commit。

---

### Task 1: MCP 契約 docstring + 軟性雙語 warning

**Files:**
- Modify: `mcp-server/mcp_server/tools/prompt_library.py`
- Test: `mcp-server/tests/test_prompt_library_tools.py`（新建）

**Interfaces:**
- Produces:
  - `_has_cjk(text: str) -> bool`
  - `_bilingual_warnings(resource_type: str, payload: dict) -> list[dict]`（每筆 warning：`{"code", "message", "hint", "details"}`）
  - `prompt_library_save(...)` 成功回傳新增選用鍵 `warnings: list[dict]`（僅在有 warning 時出現；`ok` 恆 True）。
- Consumes: 既有 `mcp_server.tools.prompt_library._get_client`（回傳的 client `.put(path, json=body)` → dict）。

- [ ] **Step 1: 寫失敗測試**

新建 `mcp-server/tests/test_prompt_library_tools.py`：

```python
"""Prompt Library MCP 工具：雙語軟性 warning 測試"""
from unittest.mock import MagicMock, patch

from mcp_server.tools.prompt_library import prompt_library_save


def _save(resource_type, payload, **kwargs):
    client = MagicMock()
    client.put.return_value = {"entry": {"id": kwargs.get("resource_id", "x")}, "entry_revision": 2}
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_save(resource_type=resource_type, payload=payload, **kwargs)
    return result, client


def test_entry_without_chinese_warns_but_saves():
    payload = {"name_zh": "masterpiece detail", "description_zh": "quality", "prompt": "masterpiece"}
    result, client = _save("entry", payload, resource_id="masterpiece", polarity="positive", category_id="quality-details")
    assert result["ok"] is True
    assert client.put.called
    assert result["warnings"][0]["code"] == "name_zh_missing_chinese"


def test_entry_echoing_prompt_warns_echoes():
    payload = {"name_zh": "Masterpiece", "description_zh": "quality", "prompt": "masterpiece"}
    result, _ = _save("entry", payload, resource_id="masterpiece", polarity="positive", category_id="quality-details")
    assert result["ok"] is True
    assert result["warnings"][0]["code"] == "name_zh_echoes_prompt"


def test_entry_with_meaningful_chinese_has_no_warnings():
    payload = {"name_zh": "傑作", "description_zh": "品質詞", "prompt": "masterpiece"}
    result, _ = _save("entry", payload, resource_id="masterpiece", polarity="positive", category_id="quality-details")
    assert result["ok"] is True
    assert "warnings" not in result


def test_category_without_chinese_warns_missing():
    payload = {"name_zh": "quality details", "description_zh": "quality"}
    result, _ = _save("category", payload, resource_id="quality-details", polarity="positive")
    assert result["ok"] is True
    assert result["warnings"][0]["code"] == "name_zh_missing_chinese"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd mcp-server && python -m pytest tests/test_prompt_library_tools.py -v`
Expected: FAIL — `KeyError: 'warnings'`（目前 save 不產 warnings）。

- [ ] **Step 3: 實作 helper 與 warning 合併**

在 `mcp-server/mcp_server/tools/prompt_library.py` 頂部 import 區加入 `import re`，並在 `_error` 之前新增：

```python
_CJK = re.compile(r"[㐀-䶿一-鿿]")


def _has_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))


def _norm(text: str) -> str:
    return " ".join((text or "").split()).casefold()


def _bilingual_warnings(resource_type: str, payload: dict) -> list[dict[str, Any]]:
    """偵測 name_zh 是否缺少有意義中文對照；只回 warning，永不擋。"""
    name_zh = str(payload.get("name_zh", ""))
    prompt = str(payload.get("prompt", ""))
    if resource_type == "entry" and prompt and _norm(name_zh) == _norm(prompt):
        return [{"code": "name_zh_echoes_prompt", "message": "name_zh 只是照抄英文 prompt", "hint": "建議填實際中文意思，方便日後用中文檢索", "details": {"name_zh": name_zh}}]
    if not _has_cjk(name_zh):
        return [{"code": "name_zh_missing_chinese", "message": "name_zh 看起來沒有中文對照", "hint": "建議補上中文翻譯，方便日後用中文檢索", "details": {"name_zh": name_zh}}]
    return []
```

把 `prompt_library_save` 改為（加 docstring、成功後附 warnings）：

```python
@mcp.tool()
def prompt_library_save(resource_type: str, resource_id: str, payload: dict, expected_revision: int = 0, expected_etag: str | None = None, polarity: str | None = None, category_id: str | None = None) -> dict[str, Any]:
    """建立或更新 Prompt Library 的 entry／category／combination。

    payload 內的 name_zh 必須是英文 prompt 的「有意義中文對照」（翻譯或說明），
    不是照抄英文、也不是機械拼接——這是給中文使用者日後用中文檢索、回想此詞
    用途的依據。若 name_zh 沒填好，本工具仍會照常儲存，但回傳 warnings 提示補件。
    """
    tool = "prompt_library_save"; path, problem = _locator(resource_type, resource_id, polarity, category_id)
    if problem: return {"tool": tool, **problem}
    body = dict(payload); body.pop("expected_revision", None); body.pop("expected_etag", None); body["expected_revision"] = expected_revision
    if expected_etag is not None: body["expected_etag"] = expected_etag
    try:
        result = {"ok": True, "tool": tool, **_get_client().put(path, json=body), "next": "reload the resource and use its new revision and etag"}
        warnings = _bilingual_warnings(resource_type, payload)
        if warnings: result["warnings"] = warnings
        return result
    except Exception as exc: return _error(tool, exc)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd mcp-server && python -m pytest tests/test_prompt_library_tools.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 5: 跑 MCP 全套回歸**

Run: `cd mcp-server && python -m pytest -q`
Expected: 既有測試全過（77 passed 之類）＋新增 4 條。

- [ ] **Step 6: Commit**

```bash
git add mcp-server/mcp_server/tools/prompt_library.py mcp-server/tests/test_prompt_library_tools.py
git commit -m "feat(mcp): prompt_library_save soft bilingual warnings + contract docstring"
```

---

### Task 2: 前端共用「可疑中文」啟發式

**Files:**
- Create: `frontend/src/components/prompt-library/suspectChinese.ts`
- Test: `frontend/src/components/prompt-library/suspectChinese.test.ts`

**Interfaces:**
- Produces:
  - `hasCjk(text: string): boolean`
  - `type SuspectReason = "missing_chinese" | "echoes_prompt"`
  - `suspectReason(nameZh: string, prompt?: string): SuspectReason | null`（與 Task 1 Python 版行為對齊：先 echoes 後 missing）

- [ ] **Step 1: 寫失敗測試**

新建 `frontend/src/components/prompt-library/suspectChinese.test.ts`：

```ts
import { describe, expect, it } from "vitest";
import { hasCjk, suspectReason } from "./suspectChinese";

describe("suspectChinese", () => {
  it("detects CJK ideographs", () => {
    expect(hasCjk("傑作")).toBe(true);
    expect(hasCjk("masterpiece")).toBe(false);
    expect(hasCjk("")).toBe(false);
  });

  it("flags name_zh with no Chinese as missing_chinese", () => {
    expect(suspectReason("masterpiece detail", "masterpiece")).toBe("missing_chinese");
  });

  it("flags name_zh echoing the prompt as echoes_prompt", () => {
    expect(suspectReason("Masterpiece", "masterpiece")).toBe("echoes_prompt");
    expect(suspectReason("  best  quality ", "best quality")).toBe("echoes_prompt");
  });

  it("passes meaningful Chinese", () => {
    expect(suspectReason("傑作", "masterpiece")).toBeNull();
    expect(suspectReason("最佳品質")).toBeNull();
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd frontend && npx vitest run src/components/prompt-library/suspectChinese.test.ts`
Expected: FAIL — 找不到模組 `./suspectChinese`。

- [ ] **Step 3: 實作**

新建 `frontend/src/components/prompt-library/suspectChinese.ts`：

```ts
const CJK = /[㐀-䶿一-鿿]/;

export function hasCjk(text: string): boolean {
  return CJK.test(text ?? "");
}

function normalize(text: string): string {
  return (text ?? "").trim().replace(/\s+/g, " ").toLowerCase();
}

export type SuspectReason = "missing_chinese" | "echoes_prompt";

export function suspectReason(nameZh: string, prompt?: string): SuspectReason | null {
  if (prompt && normalize(nameZh) === normalize(prompt)) return "echoes_prompt";
  if (!hasCjk(nameZh)) return "missing_chinese";
  return null;
}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/suspectChinese.test.ts`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/suspectChinese.ts frontend/src/components/prompt-library/suspectChinese.test.ts
git commit -m "feat(frontend): shared suspect-Chinese heuristic for prompt entries"
```

---

### Task 3: PromptEntryEditor 元件（新增／編輯表單）

**Files:**
- Create: `frontend/src/components/prompt-library/PromptEntryEditor.tsx`
- Test: `frontend/src/components/prompt-library/PromptEntryEditor.test.tsx`

**Interfaces:**
- Produces:
  - `interface EntryEditorValue { id: string; fields: { name_zh: string; description_zh: string; prompt: string; aliases: string[]; keywords: string[]; order: number } }`
  - `default export PromptEntryEditor`，Props：`{ mode: "create" | "edit"; initial?: {...}; submitting?: boolean; onSubmit: (value: EntryEditorValue) => void; onCancel: () => void }`
  - 驗證：create 模式 id 需符合 slug；name_zh/description_zh/prompt 皆必填；order 為 ≥0 整數；失敗顯示 `role="alert"`，不呼叫 onSubmit。

- [ ] **Step 1: 寫失敗測試**

新建 `frontend/src/components/prompt-library/PromptEntryEditor.test.tsx`：

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PromptEntryEditor from "./PromptEntryEditor";

describe("PromptEntryEditor", () => {
  it("submits parsed values in create mode", () => {
    const onSubmit = vi.fn();
    render(<PromptEntryEditor mode="create" onSubmit={onSubmit} onCancel={() => {}} />);

    fireEvent.change(screen.getByLabelText("詞條 ID"), { target: { value: "detailed-eyes" } });
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "細緻眼睛" } });
    fireEvent.change(screen.getByLabelText("詞條說明"), { target: { value: "眼睛細節" } });
    fireEvent.change(screen.getByLabelText("詞條英文 prompt"), { target: { value: "detailed eyes" } });
    fireEvent.change(screen.getByLabelText("詞條別名"), { target: { value: "眼睛, eyes" } });
    fireEvent.change(screen.getByLabelText("詞條排序"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));

    expect(onSubmit).toHaveBeenCalledWith({
      id: "detailed-eyes",
      fields: { name_zh: "細緻眼睛", description_zh: "眼睛細節", prompt: "detailed eyes", aliases: ["眼睛", "eyes"], keywords: [], order: 20 },
    });
  });

  it("rejects an invalid slug without calling onSubmit", () => {
    const onSubmit = vi.fn();
    render(<PromptEntryEditor mode="create" onSubmit={onSubmit} onCancel={() => {}} />);
    fireEvent.change(screen.getByLabelText("詞條 ID"), { target: { value: "Bad ID" } });
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "壞" } });
    fireEvent.change(screen.getByLabelText("詞條說明"), { target: { value: "壞" } });
    fireEvent.change(screen.getByLabelText("詞條英文 prompt"), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeVisible();
  });

  it("hides the id field and prefills values in edit mode", () => {
    const onSubmit = vi.fn();
    render(<PromptEntryEditor mode="edit" initial={{ id: "masterpiece", name_zh: "傑作", description_zh: "品質", prompt: "masterpiece", aliases: ["a"], keywords: ["k"], order: 10 }} onSubmit={onSubmit} onCancel={() => {}} />);
    expect(screen.queryByLabelText("詞條 ID")).not.toBeInTheDocument();
    expect(screen.getByLabelText("詞條中文名稱")).toHaveValue("傑作");
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "大師傑作" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(onSubmit).toHaveBeenCalledWith({
      id: "masterpiece",
      fields: { name_zh: "大師傑作", description_zh: "品質", prompt: "masterpiece", aliases: ["a"], keywords: ["k"], order: 10 },
    });
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd frontend && npx vitest run src/components/prompt-library/PromptEntryEditor.test.tsx`
Expected: FAIL — 找不到模組 `./PromptEntryEditor`。

- [ ] **Step 3: 實作**

新建 `frontend/src/components/prompt-library/PromptEntryEditor.tsx`：

```tsx
import { useState } from "react";

export interface EntryEditorValue {
  id: string;
  fields: {
    name_zh: string;
    description_zh: string;
    prompt: string;
    aliases: string[];
    keywords: string[];
    order: number;
  };
}

interface Props {
  mode: "create" | "edit";
  initial?: {
    id?: string;
    name_zh?: string;
    description_zh?: string;
    prompt?: string;
    aliases?: string[];
    keywords?: string[];
    order?: number;
  };
  submitting?: boolean;
  onSubmit: (value: EntryEditorValue) => void;
  onCancel: () => void;
}

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function commaSeparated(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

const inputClass = "mt-1 w-full rounded border border-slate-600 bg-slate-900 p-2 text-sm text-white";

export default function PromptEntryEditor({ mode, initial, submitting, onSubmit, onCancel }: Props) {
  const [id, setId] = useState(initial?.id ?? "");
  const [nameZh, setNameZh] = useState(initial?.name_zh ?? "");
  const [descriptionZh, setDescriptionZh] = useState(initial?.description_zh ?? "");
  const [prompt, setPrompt] = useState(initial?.prompt ?? "");
  const [aliases, setAliases] = useState((initial?.aliases ?? []).join(", "));
  const [keywords, setKeywords] = useState((initial?.keywords ?? []).join(", "));
  const [order, setOrder] = useState(String(initial?.order ?? 10));
  const [error, setError] = useState<string | null>(null);

  function submit() {
    const trimmedId = (mode === "create" ? id : initial?.id ?? "").trim();
    if (mode === "create" && !SLUG_PATTERN.test(trimmedId)) {
      setError("詞條 ID 只能使用小寫英文字母、數字與單一連字號，例如 detailed-eyes");
      return;
    }
    if (!nameZh.trim() || !descriptionZh.trim() || !prompt.trim()) {
      setError("請填寫中文名稱、說明與英文 prompt");
      return;
    }
    const orderNumber = Number(order);
    if (!Number.isInteger(orderNumber) || orderNumber < 0) {
      setError("排序必須是大於或等於 0 的整數");
      return;
    }
    setError(null);
    onSubmit({
      id: trimmedId,
      fields: {
        name_zh: nameZh.trim(),
        description_zh: descriptionZh.trim(),
        prompt: prompt.trim(),
        aliases: commaSeparated(aliases),
        keywords: commaSeparated(keywords),
        order: orderNumber,
      },
    });
  }

  return (
    <form className="mt-3 space-y-2 rounded-lg border border-slate-600 bg-slate-800/60 p-3" onSubmit={(event) => { event.preventDefault(); submit(); }} noValidate>
      {mode === "create" && (
        <label className="block text-xs text-slate-400">詞條 ID
          <input aria-label="詞條 ID" value={id} onChange={(e) => setId(e.target.value)} className={inputClass} />
        </label>
      )}
      <label className="block text-xs text-slate-400">中文名稱
        <input aria-label="詞條中文名稱" value={nameZh} onChange={(e) => setNameZh(e.target.value)} className={inputClass} />
      </label>
      <label className="block text-xs text-slate-400">說明
        <input aria-label="詞條說明" value={descriptionZh} onChange={(e) => setDescriptionZh(e.target.value)} className={inputClass} />
      </label>
      <label className="block text-xs text-slate-400">英文 prompt
        <input aria-label="詞條英文 prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} className={inputClass} />
      </label>
      <label className="block text-xs text-slate-400">別名（逗號分隔）
        <input aria-label="詞條別名" value={aliases} onChange={(e) => setAliases(e.target.value)} className={inputClass} />
      </label>
      <label className="block text-xs text-slate-400">關鍵字（逗號分隔）
        <input aria-label="詞條關鍵字" value={keywords} onChange={(e) => setKeywords(e.target.value)} className={inputClass} />
      </label>
      <label className="block text-xs text-slate-400">排序
        <input aria-label="詞條排序" type="number" min={0} value={order} onChange={(e) => setOrder(e.target.value)} className={inputClass} />
      </label>
      {error && <p role="alert" className="text-xs text-red-300">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={submitting} className="rounded bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-40">{submitting ? "儲存中…" : "儲存"}</button>
        <button type="button" onClick={onCancel} className="rounded bg-slate-700 px-3 py-1.5 text-sm text-slate-200">取消</button>
      </div>
    </form>
  );
}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/PromptEntryEditor.test.tsx`
Expected: PASS（3 passed）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/PromptEntryEditor.tsx frontend/src/components/prompt-library/PromptEntryEditor.test.tsx
git commit -m "feat(frontend): PromptEntryEditor create/edit form"
```

---

### Task 4: PromptEntryBrowser 補 CRUD 動作 + ⚠️ 標記

**Files:**
- Modify: `frontend/src/components/prompt-library/PromptEntryBrowser.tsx`（全檔替換為下方內容）
- Test: `frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx`（新建）

**Interfaces:**
- Consumes: Task 2 `suspectReason`；Task 3 `PromptEntryEditor` 與 `EntryEditorValue`。
- Produces: `PromptEntryBrowser` Props 新增
  - `onSaveEntry: (value: EntryEditorValue, mode: "create" | "edit") => Promise<void>`
  - `onArchiveEntry: (entry: BrowserEntry) => Promise<void>`
  既有 `onAddEntry` / `onAddLiteral` / `onOpenCategory` 等維持不變（含 aria-label `加入 {name_zh}`）。

- [ ] **Step 1: 寫失敗測試**

新建 `frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx`：

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PromptEntryBrowser, { type BrowserCategory, type BrowserEntry } from "./PromptEntryBrowser";

const category: BrowserCategory = { id: "quality", polarity: "positive", name_zh: "品質", revision: 1, etag: "p1", archived: false };
const entries: BrowserEntry[] = [
  { id: "masterpiece", name_zh: "傑作", prompt: "masterpiece", revision: 1, archived: false },
  { id: "best-quality", name_zh: "best quality", prompt: "best quality", revision: 1, archived: false },
];

function renderBrowser(overrides: Partial<React.ComponentProps<typeof PromptEntryBrowser>> = {}) {
  const props = {
    categories: [category],
    activePolarity: "positive" as const,
    onPolarityChange: vi.fn(),
    selectedCategory: category,
    entries,
    onOpenCategory: vi.fn(),
    onAddEntry: vi.fn(),
    onAddLiteral: vi.fn(),
    onSaveEntry: vi.fn().mockResolvedValue(undefined),
    onArchiveEntry: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  render(<PromptEntryBrowser {...props} />);
  return props;
}

describe("PromptEntryBrowser CRUD", () => {
  it("flags entries whose name_zh has no meaningful Chinese", () => {
    renderBrowser();
    expect(screen.getByLabelText("best quality 中文對照可能未填好")).toBeInTheDocument();
    expect(screen.queryByLabelText("傑作 中文對照可能未填好")).not.toBeInTheDocument();
  });

  it("edits an entry and forwards the parsed value", async () => {
    const props = renderBrowser();
    fireEvent.click(screen.getByRole("button", { name: "編輯 傑作" }));
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "大師傑作" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    await waitFor(() => expect(props.onSaveEntry).toHaveBeenCalledTimes(1));
    expect(props.onSaveEntry).toHaveBeenCalledWith(
      { id: "masterpiece", fields: { name_zh: "大師傑作", description_zh: expect.any(String), prompt: "masterpiece", aliases: [], keywords: [], order: 10 } },
      "edit",
    );
  });

  it("archives an entry", async () => {
    const props = renderBrowser();
    fireEvent.click(screen.getByRole("button", { name: "封存 傑作" }));
    await waitFor(() => expect(props.onArchiveEntry).toHaveBeenCalledWith(entries[0]));
  });

  it("creates a new entry", async () => {
    const props = renderBrowser();
    fireEvent.click(screen.getByRole("button", { name: "新增詞條" }));
    fireEvent.change(screen.getByLabelText("詞條 ID"), { target: { value: "sharp-focus" } });
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "銳利對焦" } });
    fireEvent.change(screen.getByLabelText("詞條說明"), { target: { value: "對焦銳利" } });
    fireEvent.change(screen.getByLabelText("詞條英文 prompt"), { target: { value: "sharp focus" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    await waitFor(() => expect(props.onSaveEntry).toHaveBeenCalledTimes(1));
    expect(props.onSaveEntry.mock.calls[0][1]).toBe("create");
    expect(props.onSaveEntry.mock.calls[0][0].id).toBe("sharp-focus");
  });
});
```

> 註：edit 測試中 `description_zh` 用 `expect.any(String)`，因為 `BrowserEntry` 目前不帶 `description_zh`（見下方 Step 3，編輯器 initial 的 description 以空字串代入）。

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd frontend && npx vitest run src/components/prompt-library/PromptEntryBrowser.test.tsx`
Expected: FAIL — 目前元件無 `onSaveEntry` 等 props 與對應按鈕。

- [ ] **Step 3: 實作（全檔替換）**

把 `frontend/src/components/prompt-library/PromptEntryBrowser.tsx` 全檔換成：

```tsx
import { useMemo, useState } from "react";
import type { PromptPolarity } from "../../types/api";
import PromptEntryEditor, { type EntryEditorValue } from "./PromptEntryEditor";
import { suspectReason } from "./suspectChinese";

export interface BrowserCategory { id: string; polarity: PromptPolarity; name_zh: string; revision: number; etag: string; archived: boolean }
export interface BrowserEntry { id: string; name_zh: string; prompt: string; revision: number; archived: boolean }

interface Props {
  categories: BrowserCategory[];
  activePolarity: PromptPolarity;
  onPolarityChange: (polarity: PromptPolarity) => void;
  selectedCategory: BrowserCategory | null;
  entries: BrowserEntry[];
  onOpenCategory: (category: BrowserCategory) => void;
  onAddEntry: (entry: BrowserEntry) => void;
  onAddLiteral: (text: string) => void;
  onSaveEntry: (value: EntryEditorValue, mode: "create" | "edit") => Promise<void>;
  onArchiveEntry: (entry: BrowserEntry) => Promise<void>;
}

export default function PromptEntryBrowser({ categories, activePolarity, onPolarityChange, selectedCategory, entries, onOpenCategory, onAddEntry, onAddLiteral, onSaveEntry, onArchiveEntry }: Props) {
  const [query, setQuery] = useState("");
  const [literal, setLiteral] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const visibleEntries = useMemo(() => entries.filter((entry) => !entry.archived && `${entry.name_zh} ${entry.prompt}`.toLowerCase().includes(query.toLowerCase())), [entries, query]);

  async function handleSave(value: EntryEditorValue, mode: "create" | "edit") {
    setBusy(true);
    try {
      await onSaveEntry(value, mode);
      setEditingId(null);
      setCreating(false);
    } finally {
      setBusy(false);
    }
  }

  async function handleArchive(entry: BrowserEntry) {
    setBusy(true);
    try { await onArchiveEntry(entry); } finally { setBusy(false); }
  }

  return (
    <section className="h-fit rounded-xl border border-slate-700 bg-slate-900/70 p-5">
      <h2 className="text-lg font-semibold text-white">加入 Prompt</h2>
      <div className="mt-4 grid grid-cols-2 rounded-lg bg-slate-800 p-1" aria-label="Prompt 類型">
        {(["positive", "negative"] as const).map((polarity) => <button key={polarity} type="button" aria-pressed={activePolarity === polarity} onClick={() => onPolarityChange(polarity)} className={`rounded-md px-3 py-2 text-sm ${activePolarity === polarity ? "bg-emerald-600 text-white" : "text-slate-400"}`}>{polarity === "positive" ? "正向" : "負向"}</button>)}
      </div>
      <input aria-label="搜尋提示詞" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜尋中文或英文" className="mt-4 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" />
      <div className="mt-3 flex flex-wrap gap-2">{categories.filter((category) => !category.archived && category.polarity === activePolarity).map((category) => <button key={category.id} type="button" onClick={() => onOpenCategory(category)} className={`rounded-lg px-3 py-2 text-sm ${selectedCategory?.id === category.id ? "bg-emerald-700 text-white" : "bg-slate-800 text-slate-300"}`}>{category.name_zh}</button>)}</div>
      <ul className="mt-4 space-y-2">{visibleEntries.map((entry) => {
        const reason = suspectReason(entry.name_zh, entry.prompt);
        return (
          <li key={entry.id} className="rounded-lg bg-slate-800 p-3">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1 font-medium text-white">
                  {reason && <span title="name_zh 可能沒有有意義的中文對照，建議編輯修正" aria-label={`${entry.name_zh} 中文對照可能未填好`} className="text-amber-400">⚠️</span>}
                  <span className="truncate">{entry.name_zh}</span>
                </p>
                <p className="mt-1 break-words text-xs text-slate-400">{entry.prompt}</p>
              </div>
              <div className="flex shrink-0 gap-1">
                <button type="button" aria-label={`加入 ${entry.name_zh}`} onClick={() => onAddEntry(entry)} className="rounded-md bg-emerald-600 px-2.5 py-1.5 text-sm text-white">加入</button>
                <button type="button" aria-label={`編輯 ${entry.name_zh}`} onClick={() => { setCreating(false); setEditingId(entry.id); }} className="rounded-md bg-slate-600 px-2.5 py-1.5 text-sm text-white">編輯</button>
                <button type="button" aria-label={`封存 ${entry.name_zh}`} disabled={busy} onClick={() => handleArchive(entry)} className="rounded-md bg-slate-700 px-2.5 py-1.5 text-sm text-slate-200 disabled:opacity-40">封存</button>
              </div>
            </div>
            {editingId === entry.id && (
              <PromptEntryEditor
                mode="edit"
                initial={{ id: entry.id, name_zh: entry.name_zh, description_zh: "", prompt: entry.prompt, aliases: [], keywords: [], order: 10 }}
                submitting={busy}
                onSubmit={(value) => handleSave(value, "edit")}
                onCancel={() => setEditingId(null)}
              />
            )}
          </li>
        );
      })}</ul>
      {selectedCategory && (
        <div className="mt-4">
          {creating ? (
            <PromptEntryEditor mode="create" submitting={busy} onSubmit={(value) => handleSave(value, "create")} onCancel={() => setCreating(false)} />
          ) : (
            <button type="button" onClick={() => { setEditingId(null); setCreating(true); }} className="w-full rounded-lg border border-dashed border-slate-600 px-3 py-2 text-sm text-slate-300">＋ 新增詞條</button>
          )}
        </div>
      )}
      <div className="mt-5 border-t border-slate-700 pt-4">
        <label className="text-sm text-slate-400">自由文字<input aria-label="自由文字" value={literal} onChange={(event) => setLiteral(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" /></label>
        <button type="button" disabled={!literal.trim()} onClick={() => { onAddLiteral(literal.trim()); setLiteral(""); }} className="mt-2 w-full rounded-lg bg-slate-700 px-3 py-2 text-sm disabled:opacity-40">加入目前{activePolarity === "positive" ? "正向" : "負向"}</button>
      </div>
    </section>
  );
}
```

> 註：`新增詞條` 按鈕文字含全形「＋」，測試以 name `新增詞條`（`getByRole` 對 accessible name 做子字串比對）即可命中。

- [ ] **Step 4: 跑測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/PromptEntryBrowser.test.tsx`
Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/prompt-library/PromptEntryBrowser.tsx frontend/src/components/prompt-library/PromptEntryBrowser.test.tsx
git commit -m "feat(frontend): entry CRUD actions and suspect-Chinese flag in PromptEntryBrowser"
```

---

### Task 5: PromptWorkbench 串接 entry 儲存／封存（樂觀鎖 + 重載）

**Files:**
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`
- Test: `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`（擴充）

**Interfaces:**
- Consumes: Task 3 `EntryEditorValue`；Task 4 的 `onSaveEntry` / `onArchiveEntry` props。
- Produces: `saveEntry(value, mode)` PUT `/api/prompt-library/categories/{polarity}/{id}/entries/{entryId}`；`archiveEntry(entry)` POST `/api/prompt-library/archive`。兩者 body 皆帶 `expected_revision = category.revision`、`expected_etag = category.etag`，成功後 `openCategory(category)` 重載。

- [ ] **Step 1: 寫失敗測試（擴充既有檔）**

在 `frontend/src/components/prompt-library/PromptWorkbench.test.tsx` 的 `installFetch` 內，於 `return response({}, 404);` 之前插入三條路由：

```ts
    if (url.includes("/positive/quality/entries/") && init?.method === "PUT") {
      return response({ entry: { id: "masterpiece", revision: 2 }, entry_revision: 2 });
    }
    if (url === "/api/prompt-library/archive" && init?.method === "POST") {
      return response({ entry: { id: "masterpiece", revision: 2 } });
    }
```

在 `describe("PromptWorkbench", ...)` 內新增測試：

```ts
  it("edits an entry with the category revision and etag as the concurrency token", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);

    fireEvent.click(await screen.findByRole("button", { name: "品質" }));
    fireEvent.click(await screen.findByRole("button", { name: "編輯 高品質" }));
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "大師傑作" } });
    fireEvent.change(screen.getByLabelText("詞條說明"), { target: { value: "品質詞" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => String(url).includes("/positive/quality/entries/masterpiece") && init?.method === "PUT")).toBe(true));
    const call = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/entries/masterpiece") && init?.method === "PUT") as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toMatchObject({
      name_zh: "大師傑作",
      description_zh: "品質詞",
      prompt: "masterpiece",
      expected_revision: 1,
      expected_etag: "p1",
    });
  });

  it("archives an entry via the archive endpoint", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);

    fireEvent.click(await screen.findByRole("button", { name: "品質" }));
    fireEvent.click(await screen.findByRole("button", { name: "封存 高品質" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/prompt-library/archive" && init?.method === "POST")).toBe(true));
    const call = fetchMock.mock.calls.find(([url]) => url === "/api/prompt-library/archive") as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toMatchObject({
      resource_type: "entry",
      resource_id: "masterpiece",
      polarity: "positive",
      category_id: "quality",
      expected_revision: 1,
      expected_etag: "p1",
    });
  });
```

> `positiveCategory` 內的 entry `name_zh` 是「高品質」，故按鈕為「編輯 高品質」「封存 高品質」。

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd frontend && npx vitest run src/components/prompt-library/PromptWorkbench.test.tsx`
Expected: FAIL — Workbench 尚未把 `onSaveEntry` / `onArchiveEntry` 傳給 Browser，找不到「編輯 高品質」按鈕。

- [ ] **Step 3: 實作**

在 `frontend/src/components/prompt-library/PromptWorkbench.tsx`：

(a) import 區加入型別：

```ts
import PromptEntryBrowser, { type BrowserCategory, type BrowserEntry } from "./PromptEntryBrowser";
import type { EntryEditorValue } from "./PromptEntryEditor";
```

(b) 在 `saveCombination` 之後、`return (` 之前，新增兩個函式：

```ts
  async function saveEntry(value: EntryEditorValue, mode: "create" | "edit") {
    if (!category) return;
    setError("");
    const body = {
      ...value.fields,
      expected_revision: category.revision,
      ...(category.etag ? { expected_etag: category.etag } : {}),
    };
    const response = await fetch(`/api/prompt-library/categories/${category.polarity}/${category.id}/entries/${encodeURIComponent(value.id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = data?.detail?.message || `HTTP ${response.status}`;
      setError(String(message));
      throw new Error(String(message));
    }
    await openCategory(category);
  }

  async function archiveEntry(entry: BrowserEntry) {
    if (!category) return;
    setError("");
    const body = {
      resource_type: "entry",
      resource_id: entry.id,
      polarity: category.polarity,
      category_id: category.id,
      expected_revision: category.revision,
      ...(category.etag ? { expected_etag: category.etag } : {}),
    };
    const response = await fetch("/api/prompt-library/archive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = data?.detail?.message || `HTTP ${response.status}`;
      setError(String(message));
      throw new Error(String(message));
    }
    await openCategory(category);
  }
```

(c) 把 `<PromptEntryBrowser ... />` 這一行的 props 補上兩個 callback：

```tsx
        <PromptEntryBrowser categories={categories} activePolarity={activePolarity} onPolarityChange={changePolarity} selectedCategory={category} entries={entries} onOpenCategory={openCategory} onAddEntry={addEntry} onAddLiteral={addLiteral} onSaveEntry={saveEntry} onArchiveEntry={archiveEntry} />
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd frontend && npx vitest run src/components/prompt-library/PromptWorkbench.test.tsx`
Expected: PASS（既有 2 條 + 新增 2 條）。

- [ ] **Step 5: 前端全套 + 型別 + build**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: 全部通過；build 成功。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/prompt-library/PromptWorkbench.tsx frontend/src/components/prompt-library/PromptWorkbench.test.tsx
git commit -m "feat(frontend): wire entry save/archive with category-level optimistic concurrency"
```

---

### Task 6: 更新進度文件

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: 在 `docs/PROGRESS.md` 最上方（在 `## 2026-07-21 Prompt Library Git persistence` 之前）新增一段**

```markdown
## 2026-07-24 Prompt Library 雙語軟性偵測 + Entry 增刪改查

背景：詞庫改由 agent 經 MCP 寫入後，agent 不知道使用者需要「有意義的中文對照」，可能把 name_zh
照抄英文或機械拼接。經討論確認不適合用 i18n（i18n 是「切換語言」，需求是「中英同時對照」；另立 i18n
store 會與詞條 JSON 形成雙重來源）。改以「MCP 軟性提醒 + 操作台兜底編輯」解決。

1. MCP `prompt_library_save` 加契約 docstring 並在成功後附 `warnings`（name_zh 無 CJK 或照抄英文
   prompt），永不擋、ok 恆 True，符合「寬進嚴出、錯誤是修復指南」。
2. 前端新增共用啟發式 `suspectChinese.ts`，操作台詞條區對可疑 name_zh 標 ⚠️。
3. 操作台補齊 entry 增刪改查：新增 `PromptEntryEditor`，`PromptEntryBrowser` 加編輯／封存／新增，
   `PromptWorkbench` 串接 `PUT .../entries/{id}` 與 `POST /archive`。entry 樂觀鎖以「分類 revision + etag」
   為單位（後端契約），寫入後重載分類刷新 token。刪＝封存（可復原），未做實體刪檔。
4. backend 端點與 schema 未動；未引入 i18n。
5. 驗證：MCP `pytest` 新增 4 條；前端 vitest 新增啟發式／編輯器／Browser CRUD／Workbench 串接測試，
   `tsc --noEmit` 與 Vite build 通過。
```

- [ ] **Step 2: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs: record prompt-library bilingual soft-validation + entry CRUD"
```

---

## Self-Review

**Spec coverage：**
- Part 0 共用啟發式 → Task 1（Python）＋ Task 2（TS），兩處行為對齊（先 echoes 後 missing、CJK 範圍相同）。✓
- Part 1 MCP 契約 + 軟性 warning → Task 1（docstring + `_bilingual_warnings` + 永不擋）。✓
- Part 2 操作台 entry 增刪改查 → Task 3（編輯器）＋ Task 4（Browser 動作 + ⚠️）＋ Task 5（Workbench API 串接）。✓
- 「刪＝封存」→ Task 5 `archiveEntry` 走 `/archive`。✓
- 樂觀鎖以分類 revision+etag 為單位 → Global Constraints 明列，Task 5 body 帶 `category.revision` / `category.etag`，測試斷言 `expected_revision:1, expected_etag:"p1"`。✓
- 進度同步 → Task 6。✓

**與設計文件的兩處修正（實作以本計畫為準）：**
1. 設計文件說 entry 編輯帶「該 entry 目前 revision」，實際後端契約是「分類 revision + etag」——本計畫已更正。
2. 設計文件提到「category payload 逐條檢查 entries[]」，但 category 寫入 payload 不含 entries（見 `CategoryWriteRequest`），故 Task 1 對 category 只做 name_zh 的 no-CJK 檢查；echoes 檢查僅適用於有 `prompt` 的 entry。

**Placeholder scan：** 無 TODO/TBD；每個 code step 均含完整程式碼與可執行指令。✓

**Type consistency：** `EntryEditorValue`（`{id, fields:{name_zh, description_zh, prompt, aliases[], keywords[], order}}`）在 Task 3 定義，Task 4/5 一致使用；`onSaveEntry(value, mode)` / `onArchiveEntry(entry)` 簽名在 Task 4 定義、Task 5 實作一致；MCP warning 鍵 `code/message/hint/details` 在 Task 1 一致。✓
