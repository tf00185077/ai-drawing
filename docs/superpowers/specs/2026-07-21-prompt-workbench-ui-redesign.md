# Prompt Workbench UI Redesign

**Date:** 2026-07-21

## Goal

Separate Prompt Library category management from Prompt Workbench, make positive and negative prompt collection immediate, and keep both composed prompts visible and editable while preserving the existing workflow-generation capability.

## Scope

This change is limited to the frontend UI, routing, and workbench client state. It reuses the existing Prompt Library, compose/save, workflow catalog, and generation APIs. It does not change the backend data format or write workbench edits back to Prompt Library JSON files.

## Routes and navigation

- `/prompt-library/categories` contains category management only.
- `/prompt-library/workbench` contains Prompt Workbench only.
- `/prompt-library` redirects to `/prompt-library/workbench`.
- A Prompt Library sidebar links to Prompt Workbench and category management and indicates the active child route.
- The global navigation retains one Prompt Library entry.

## Workbench layout

The desktop workbench has two vertical sections:

1. The upper section uses two columns. The left column is the prompt-entry browser and add area. The right column is the composed-prompt overview.
2. The lower section is a full-width, independent workflow-generation panel.

On small screens the content stacks in this order: entry browser, composed-prompt overview, workflow generation.

The entry browser has positive and negative navigation tabs. The active tab controls which categories and entries are shown and where newly selected entries are added. It does not control overview visibility.

The overview always shows Positive Prompt and Negative Prompt as two vertically stacked panels. Both remain visible and editable regardless of the active entry-browser tab.

## Composition behavior

Selecting an entry immediately adds a workbench copy to the active polarity. There is no separate compose action.

Each workbench fragment stores:

- its source reference when it came from the library;
- its original snapshot;
- its current workbench-only text;
- an optional weight;
- its order;
- its current character range in the composed text.

Editing this state never updates category or entry JSON. Saving a combination remains available and sends the current workbench state through the existing API without requiring a preliminary compose action.

### Weight formatting

Weight is optional and blank by default:

- blank weight: `masterpiece`
- weight `1.2`: `(masterpiece:1.2)`

The UI must not serialize blank weight as `1.0`.

### Editing fragments and final text

Each polarity panel supports:

- editing individual fragment text;
- setting or clearing individual weight;
- deleting and reordering fragments;
- editing the complete composed prompt directly.

Fragment edits, weight changes, deletion, and reordering immediately rebuild the complete prompt.

Direct edits to the complete prompt use a range-mapped text-diff strategy:

- an edit inside a known fragment updates that workbench fragment;
- text inserted between known fragments becomes a new literal fragment;
- range metadata is recomputed after every successful synchronization;
- no synchronized edit is written back to the source library entry.

This is intentionally best-effort. If a user breaks delimiters, parentheses, or weight syntax, the editor remains usable and generation is not blocked. The UI may show a lightweight synchronization warning. Malformed hand-edited syntax is treated as user-owned input and is not required to round-trip perfectly into structured fragments.

## Generation behavior

The workflow-generation panel stays below the browser and overview. It reads the current positive and negative composed text directly at submission time. It must not depend on a stale result produced by an earlier compose request.

Existing workflow selection, workflow defaults, seed behavior, and job feedback remain available.

## Component boundaries

- `PromptLibraryLayout`: sidebar and nested-route outlet.
- `CategoryManagement`: existing category-management behavior separated from the workbench.
- `PromptWorkbench`: data loading and coordination of polarity state and generation input.
- `PromptEntryBrowser`: polarity navigation, category selection, search, entry creation where retained, and add actions.
- `PromptOverview`: vertically stacks the positive and negative panels.
- `PromptComposerPanel`: fragment editing, optional weights, ordering, deletion, final-text editing, and sync feedback.
- `GenerationPanel`: workflow-driven generation below the main workbench.
- Pure composition-state utilities: ComfyUI weight serialization, range calculation, and text-diff reconciliation independent of React.

Components should use the existing API types where available and avoid duplicating category, entry, or workflow response shapes locally.

## Error handling

- Catalog, category, workflow, save, and generation request failures remain visible in their owning panel.
- Final-text synchronization failures do not crash the workbench or mutate Prompt Library JSON.
- A sync warning is informational and does not disable prompt editing, saving, or generation.
- Empty prompt collections remain valid for editing; generation retains its existing eligibility requirements.

## Verification

Tests must cover:

- nested routes, redirect behavior, sidebar links, and active state;
- category management and workbench rendering on separate routes;
- polarity navigation filtering the browser and selecting the add destination;
- both positive and negative overview panels remaining visible;
- immediate composition after adding, editing, deleting, and reordering fragments;
- blank weight producing raw text and a supplied weight producing ComfyUI syntax;
- final-text edits updating only workbench fragment copies;
- inserted text becoming a literal fragment where the range mapping is unambiguous;
- malformed user edits remaining non-fatal;
- generation using the current positive and negative text;
- responsive stacking through stable layout classes or component-level assertions.

Completion requires focused frontend tests, the full frontend test suite, TypeScript checking, and a production build. After implementation and verification, `docs/PROGRESS.md` must record the completed UI redesign and verification results.

## Out of scope

- Backend schema or API redesign.
- OpenSpec artifacts or workflow.
- Persisting unsaved workbench state across browser reloads.
- Guaranteeing structured round-trip behavior after arbitrary malformed final-text edits.
- Unrelated visual redesign of the global application navigation.
