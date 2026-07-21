# Prompt Workbench UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Prompt Library into routed category/workbench screens and deliver an immediately composed, dual-polarity Prompt Workbench with editable fragments, optional ComfyUI weights, range-mapped final-text editing, and current-text workflow generation.

**Architecture:** Use a nested React Router layout for Prompt Library. Move category management into its own page, decompose the workbench into browser/overview/generation components, and keep prompt reconciliation in pure TypeScript utilities so it can be tested without React. The browser owns only the active add polarity; positive and negative composer state remain simultaneously visible and generation reads their current rendered strings.

**Tech Stack:** React 18, React Router 6, TypeScript 5, Tailwind CSS, Vitest, Testing Library, Vite.

---

## File structure

- Create `frontend/src/pages/PromptLibraryLayout.tsx`: sidebar and nested route outlet.
- Create `frontend/src/pages/PromptCategoryManagement.tsx`: category catalog/create UI extracted from the current combined page.
- Modify `frontend/src/pages/PromptLibrary.tsx`: compatibility redirect component only.
- Create `frontend/src/components/prompt-library/compositionState.ts`: workbench fragment model, rendering, range calculation, reordering, and final-text reconciliation.
- Create `frontend/src/components/prompt-library/compositionState.test.ts`: pure state behavior.
- Create `frontend/src/components/prompt-library/PromptEntryBrowser.tsx`: polarity navigation, categories, search, entry creation, and add actions.
- Create `frontend/src/components/prompt-library/PromptComposerPanel.tsx`: one polarity's fragment rows and final textarea.
- Create `frontend/src/components/prompt-library/PromptOverview.tsx`: positive and negative panels stacked vertically.
- Create `frontend/src/components/prompt-library/GenerationPanel.tsx`: workflow selection and current-text generation.
- Modify `frontend/src/components/prompt-library/PromptWorkbench.tsx`: API loading and coordination only.
- Create `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`: workbench integration tests.
- Modify `frontend/src/pages/PromptLibrary.test.tsx`: nested navigation and redirect tests.
- Modify `frontend/src/App.tsx`: nested Prompt Library routes.
- Modify `frontend/src/App.test.tsx`: route-level assertions.
- Modify `frontend/src/types/api.ts`: shared detailed Prompt Library and workflow-form response types.
- Modify `docs/PROGRESS.md`: completed behavior and verification evidence.

### Task 1: Add nested Prompt Library routing

**Files:**
- Create: `frontend/src/pages/PromptLibraryLayout.tsx`
- Create: `frontend/src/pages/PromptCategoryManagement.tsx`
- Modify: `frontend/src/pages/PromptLibrary.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/PromptLibrary.test.tsx`
- Modify: `frontend/src/App.test.tsx`

- [ ] **Step 1: Write failing route and sidebar tests**

Add MemoryRouter tests asserting that `/prompt-library` redirects to `/prompt-library/workbench`, both sidebar links exist, the active link has `aria-current="page"`, category management does not render the workbench, and the workbench route does not render category creation.

```tsx
render(
  <MemoryRouter initialEntries={["/prompt-library/categories"]}>
    <Routes>
      <Route path="/prompt-library" element={<PromptLibraryLayout />}>
        <Route index element={<Navigate replace to="workbench" />} />
        <Route path="workbench" element={<div>Prompt Workbench Screen</div>} />
        <Route path="categories" element={<PromptCategoryManagement />} />
      </Route>
    </Routes>
  </MemoryRouter>,
);
expect(screen.getByRole("link", { name: "分類管理" })).toHaveAttribute("aria-current", "page");
expect(screen.queryByText("Prompt Workbench Screen")).not.toBeInTheDocument();
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `cd frontend; npm test -- src/pages/PromptLibrary.test.tsx src/App.test.tsx`

Expected: FAIL because `PromptLibraryLayout`, nested routes, and separated pages do not exist.

- [ ] **Step 3: Extract category management and implement nested layout**

Move the catalog/create state and markup from `PromptLibrary.tsx` into `PromptCategoryManagement.tsx`. Implement the layout with `NavLink` and `Outlet`:

```tsx
export default function PromptLibraryLayout() {
  return (
    <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
      <aside aria-label="Prompt Library" className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
        <nav className="space-y-1">
          <LibraryLink to="workbench">Prompt Workbench</LibraryLink>
          <LibraryLink to="categories">分類管理</LibraryLink>
        </nav>
      </aside>
      <main className="min-w-0"><Outlet /></main>
    </div>
  );
}
```

Make `PromptLibrary.tsx` return `<Navigate replace to="/prompt-library/workbench" />`. In `App.tsx`, nest the index redirect, workbench, and categories routes under `/prompt-library` and change the global link target to `/prompt-library/workbench`.

- [ ] **Step 4: Run the route tests and verify success**

Run: `cd frontend; npm test -- src/pages/PromptLibrary.test.tsx src/App.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit routing separation**

```powershell
git add frontend/src/pages/PromptLibraryLayout.tsx frontend/src/pages/PromptCategoryManagement.tsx frontend/src/pages/PromptLibrary.tsx frontend/src/pages/PromptLibrary.test.tsx frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat: split prompt library routes"
```

### Task 2: Build pure prompt composition state

**Files:**
- Create: `frontend/src/components/prompt-library/compositionState.ts`
- Create: `frontend/src/components/prompt-library/compositionState.test.ts`

- [ ] **Step 1: Write failing serialization and reconciliation tests**

Cover blank weight, weighted rendering, stable ranges, editing inside one range, inserting between ranges as a literal, deleting/reordering, and malformed input returning a warning without throwing.

```ts
const state = appendFragment(emptyComposition(), {
  id: "f-1", kind: "entry", source: positiveRef, originalSnapshot: "masterpiece",
  text: "masterpiece", weight: "",
});
expect(state.text).toBe("masterpiece");
expect(setFragmentWeight(state, "f-1", "1.2").text).toBe("(masterpiece:1.2)");

const edited = reconcileComposedText(twoFragmentState, "masterwork, dramatic light");
expect(edited.fragments[0].text).toBe("masterwork");
expect(edited.warning).toBeNull();
```

- [ ] **Step 2: Run the utility test and verify failure**

Run: `cd frontend; npm test -- src/components/prompt-library/compositionState.test.ts`

Expected: FAIL because the module is missing.

- [ ] **Step 3: Implement the workbench-only model and renderer**

Define the state explicitly:

```ts
export type EditableWeight = "" | `${number}`;
export interface WorkbenchFragment {
  id: string;
  kind: "entry" | "literal";
  source?: { polarity: PromptPolarity; categoryId: string; entryId: string; revision: number };
  originalSnapshot: string;
  text: string;
  weight: EditableWeight;
  range: { start: number; end: number };
}
export interface CompositionState {
  fragments: WorkbenchFragment[];
  text: string;
  warning: string | null;
}
```

Render fragments with `, ` separators. A blank weight renders raw trimmed text; a finite supplied weight in `(0, 2]` renders `(${text}:${weight})`. Recompute ranges over the exact rendered output. Implement append, update text, update weight, delete, and move operations as immutable functions.

- [ ] **Step 4: Implement range-mapped final-text reconciliation**

Use longest common prefix/suffix to locate one contiguous edit. If it overlaps one known rendered range, update that fragment's text after best-effort removal of its known weight wrapper. If it falls in a separator, insert a literal fragment at that boundary. If it spans ambiguous ranges or malformed wrapper syntax, preserve the supplied final text, keep the prior structured fragments, and set a non-blocking warning.

When serializing for `/compose`, send an edited library fragment as `kind: "literal"` if `text !== originalSnapshot`; otherwise preserve its entry ref. Always translate blank UI weight to backend weight `1`.

- [ ] **Step 5: Run utility tests and verify success**

Run: `cd frontend; npm test -- src/components/prompt-library/compositionState.test.ts`

Expected: PASS.

- [ ] **Step 6: Commit composition state**

```powershell
git add frontend/src/components/prompt-library/compositionState.ts frontend/src/components/prompt-library/compositionState.test.ts
git commit -m "feat: add editable prompt composition state"
```

### Task 3: Build the browser and always-visible overview

**Files:**
- Modify: `frontend/src/types/api.ts`
- Create: `frontend/src/components/prompt-library/PromptEntryBrowser.tsx`
- Create: `frontend/src/components/prompt-library/PromptComposerPanel.tsx`
- Create: `frontend/src/components/prompt-library/PromptOverview.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`
- Create: `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`

- [ ] **Step 1: Write failing interaction tests**

Mock the catalog, category details, and workflow forms. Assert both overview headings remain visible, the active polarity filters category buttons, adding an entry immediately changes only the matching final textarea, blank weight stays raw, a supplied weight adds ComfyUI syntax, and editing the final textarea updates the fragment input without issuing a write request.

```tsx
expect(screen.getByRole("heading", { name: "Positive Prompt" })).toBeVisible();
expect(screen.getByRole("heading", { name: "Negative Prompt" })).toBeVisible();
fireEvent.click(await screen.findByRole("button", { name: "加入 masterpiece" }));
expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("masterpiece");
fireEvent.change(screen.getByLabelText("masterpiece 權重"), { target: { value: "1.2" } });
expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("(masterpiece:1.2)");
```

- [ ] **Step 2: Run the workbench test and verify failure**

Run: `cd frontend; npm test -- src/components/prompt-library/PromptWorkbench.test.tsx`

Expected: FAIL because the decomposed UI and immediate composition are missing.

- [ ] **Step 3: Add shared API response types**

Extend `types/api.ts` with `PromptLibraryEntry`, `PromptLibraryCategoryDetail`, `PromptLibraryCategoryResponse`, and `GenerationFormDescriptor`. Replace local `Category`, `Entry`, and `Form` definitions in the workbench with these shared types.

- [ ] **Step 4: Implement the entry browser**

Render positive/negative tab buttons with `aria-pressed`. Filter categories by the active polarity before rendering. Category selection loads only that category's entries. Entry add callbacks include the active category reference and create a workbench copy with blank weight. Retain search and entry creation, but keep entry creation scoped to the currently opened category.

- [ ] **Step 5: Implement composer panels and overview**

`PromptComposerPanel` receives one `CompositionState` plus callbacks. Render editable fragment text, optional numeric weight, move up/down, delete, and a labeled final textarea. `PromptOverview` renders positive first and negative second in `space-y-5`; neither is conditional on active browser polarity.

- [ ] **Step 6: Rebuild PromptWorkbench coordination and layout**

Keep `positive` and `negative` as independent composition states and `activePolarity` for the browser only. Use this layout:

```tsx
<div className="space-y-6">
  <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(380px,0.9fr)]">
    <PromptEntryBrowser activePolarity={activePolarity} onPolarityChange={setActivePolarity} onAdd={addToActive} />
    <PromptOverview positive={positive} negative={negative} />
  </div>
  <GenerationPanel positivePrompt={positive.text} negativePrompt={negative.text} />
</div>
```

Save-combination submits serialized current fragments to `/api/prompt-library/compose`; there is no ordinary compose button and the response must not replace current workbench text.

- [ ] **Step 7: Run workbench and utility tests**

Run: `cd frontend; npm test -- src/components/prompt-library/PromptWorkbench.test.tsx src/components/prompt-library/compositionState.test.ts`

Expected: PASS.

- [ ] **Step 8: Commit the workbench UI**

```powershell
git add frontend/src/types/api.ts frontend/src/components/prompt-library/PromptEntryBrowser.tsx frontend/src/components/prompt-library/PromptComposerPanel.tsx frontend/src/components/prompt-library/PromptOverview.tsx frontend/src/components/prompt-library/PromptWorkbench.tsx frontend/src/components/prompt-library/PromptWorkbench.test.tsx
git commit -m "feat: redesign prompt workbench composition UI"
```

### Task 4: Extract generation and use current prompt text

**Files:**
- Create: `frontend/src/components/prompt-library/GenerationPanel.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.tsx`
- Modify: `frontend/src/components/prompt-library/PromptWorkbench.test.tsx`

- [ ] **Step 1: Write a failing current-text generation test**

Select a workflow, add and edit positive and negative fragments, click generate, and assert the `/api/generate/` request uses the current textarea values without a preceding compose request.

```ts
expect(JSON.parse(String(generateCall[1].body))).toMatchObject({
  template: "basic-txt2img",
  prompt: "edited positive",
  negative_prompt: "edited negative",
  use_workflow_defaults: true,
  seed_mode: "random",
});
expect(fetchMock.mock.calls.filter(([url]) => url === "/api/prompt-library/compose")).toHaveLength(0);
```

- [ ] **Step 2: Run the generation test and verify failure**

Run: `cd frontend; npm test -- src/components/prompt-library/PromptWorkbench.test.tsx`

Expected: FAIL because generation still depends on the old compose result.

- [ ] **Step 3: Implement GenerationPanel**

Move workflow selection, seed mode, generate request, error, and job feedback into `GenerationPanel`. Accept `forms`, `positivePrompt`, and `negativePrompt` as props. Build the request from those props inside the click handler. Keep generation disabled when workflow or positive text is empty.

- [ ] **Step 4: Run focused frontend tests**

Run: `cd frontend; npm test -- src/components/prompt-library/PromptWorkbench.test.tsx src/components/prompt-library/compositionState.test.ts src/pages/PromptLibrary.test.tsx src/App.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit generation extraction**

```powershell
git add frontend/src/components/prompt-library/GenerationPanel.tsx frontend/src/components/prompt-library/PromptWorkbench.tsx frontend/src/components/prompt-library/PromptWorkbench.test.tsx
git commit -m "feat: generate from current workbench prompts"
```

### Task 5: Verify, document, and finish

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Run all frontend tests**

Run: `cd frontend; npm test`

Expected: all tests pass.

- [ ] **Step 2: Run TypeScript checking**

Run: `cd frontend; npx tsc --noEmit`

Expected: exit code 0 with no diagnostics.

- [ ] **Step 3: Build production assets**

Run: `cd frontend; npm run build`

Expected: Vite exits successfully and writes `frontend/dist`.

- [ ] **Step 4: Record completion in progress documentation**

Add a dated `2026-07-21 Prompt Workbench UI redesign` entry to `docs/PROGRESS.md` listing the nested sidebar routes, immediate positive/negative composition, optional ComfyUI weights, range-mapped editing, current-text generation, and the exact test/typecheck/build results.

- [ ] **Step 5: Review the final diff and status**

Run: `git diff --check; git status --short; git diff --stat HEAD~4..HEAD`

Expected: no whitespace errors; only intended source, tests, plan/spec, and progress files are changed. Preserve the pre-existing untracked root `package-lock.json`.

- [ ] **Step 6: Commit documentation**

```powershell
git add docs/PROGRESS.md docs/superpowers/plans/2026-07-21-prompt-workbench-ui-redesign.md
git commit -m "docs: record prompt workbench UI redesign"
```
