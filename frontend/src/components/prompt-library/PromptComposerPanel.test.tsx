import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appendFragment, emptyComposition, materializeRawText, type CompositionState } from "./compositionState";
import PromptComposerPanel from "./PromptComposerPanel";
import PromptWorkbench from "./PromptWorkbench";

afterEach(() => vi.unstubAllGlobals());

function fragments(count = 6): CompositionState {
  let state = emptyComposition();
  for (let index = 1; index <= count; index += 1) {
    state = appendFragment(state, {
      id: `fragment-${index}`,
      kind: "literal",
      displayName: "自訂文字",
      sourceSnapshotRaw: `prompt ${index}`,
      snapshotRaw: `prompt ${index}`,
      weight: "",
    });
  }
  return state;
}

function panelProps(state: CompositionState = fragments(1)) {
  return {
    title: "Positive Prompt" as const,
    state,
    arrangement: "auto" as const,
    categoryInfoOf: () => null,
    onReapplySort: vi.fn(),
    onTextChange: vi.fn(),
    onWeightChange: vi.fn(),
    onMove: vi.fn(),
    onRemove: vi.fn(),
    onFinalTextChange: vi.fn(),
  };
}

describe("PromptComposerPanel", () => {
  it("renders all fragments in a responsive two-column grid without pagination", () => {
    const state = fragments(7);
    render(<PromptComposerPanel {...panelProps(state)} />);

    expect(screen.getByTestId("prompt-option-grid")).toBeInTheDocument();
    expect(screen.getAllByLabelText(/內容$/)).toHaveLength(7);
    expect(screen.queryByRole("button", { name: "上一頁" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "下一頁" })).not.toBeInTheDocument();
  });

  it("uses fixed labels, true positions, and exposes exact literal content", () => {
    let state = emptyComposition();
    state = appendFragment(state, {
      id: "entry-human",
      kind: "entry",
      displayName: "精緻光影",
      source: { polarity: "positive", categoryId: "quality", entryId: "masterpiece" },
      sourceSnapshotRaw: "masterpiece",
      snapshotRaw: "masterpiece",
      weight: "",
    });
    state = appendFragment(state, {
      id: "literal",
      kind: "literal",
      displayName: "自訂文字",
      sourceSnapshotRaw: "soft light",
      snapshotRaw: "soft light",
      weight: "",
    });
    render(<PromptComposerPanel {...panelProps(state)} />);

    expect(screen.getByLabelText("精緻光影 內容")).toHaveValue("masterpiece");
    expect(screen.getByLabelText("自訂文字 內容")).toHaveValue("soft light");
    expect(screen.getByText("第 1 段")).toBeVisible();
    expect(screen.getByText("第 2 段")).toBeVisible();
  });

  it("rerenders the controlled final text on every exact keystroke", () => {
    let sequence = 0;
    function Harness() {
      const [state, setState] = useState(() => fragments(1));
      return <PromptComposerPanel {...panelProps(state)} onFinalTextChange={(text) => {
        setState((current) => materializeRawText(current, text, () => `direct-literal-${++sequence}`));
      }} />;
    }
    render(<Harness />);

    const editor = screen.getByLabelText("Positive Prompt 最終文字");
    expect(editor).not.toHaveAttribute("readonly");
    for (const text of ["masterpiece,", "masterpiece, ", "masterpiece,  (unfinished"]) {
      fireEvent.change(editor, { target: { value: text } });
      expect(editor).toHaveValue(text);
    }
    expect(screen.queryByRole("button", { name: /^(自由文字模式|套用|取消)$/ })).not.toBeInTheDocument();
  });

  it("preserves caret selection through comma-driven controlled rerenders", () => {
    let sequence = 0;
    function Harness() {
      const [state, setState] = useState(() => fragments(1));
      return <PromptComposerPanel {...panelProps(state)} onFinalTextChange={(text) => {
        setState((current) => materializeRawText(current, text, () => `caret-${++sequence}`));
      }} />;
    }
    render(<Harness />);

    const editor = screen.getByLabelText("Positive Prompt 最終文字") as HTMLTextAreaElement;
    editor.focus();
    fireEvent.change(editor, {
      target: {
        value: "prompt, 1",
        selectionStart: 7,
        selectionEnd: 7,
        selectionDirection: "none",
      },
    });

    expect(editor).toHaveFocus();
    expect(editor).toHaveValue("prompt, 1");
    expect(editor.selectionStart).toBe(7);
    expect(editor.selectionEnd).toBe(7);
  });

  it("assigns live browser entries trimmed names with prompt and ID fallbacks", async () => {
    const entries = [
      { id: "arbitrary-human-id", name_zh: "  細緻光影  ", prompt: "detailed light", description_zh: "", revision: 1, archived: false },
      { id: "arbitrary-prompt-id", name_zh: " ", prompt: "  cinematic glow  ", description_zh: "", revision: 1, archived: false },
      { id: "arbitrary-id-only", name_zh: undefined, prompt: undefined, description_zh: "", revision: 1, archived: false },
    ];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/prompt-library/migration-status") return { ok: true, status: 200, json: async () => ({ state: "finalized", marker_present: false, comma_atomic_ready: true, atomic_enforcement_active: true, run_id: null, data_validated: true }) };
      if (url === "/api/prompt-library/catalog") return { ok: true, status: 200, json: async () => ({ categories: [{ id: "lighting", polarity: "positive", name_zh: "光影", revision: 1, etag: "e1", archived: false }], combinations: [] }) };
      if (url === "/api/workflow-catalog/generation-forms") return { ok: true, status: 200, json: async () => ({ items: [] }) };
      return { ok: true, status: 200, json: async () => ({ category: { id: "lighting", polarity: "positive", name_zh: "光影", revision: 1, etag: "e1", archived: false, entries }, etag: "e1" }) };
    }));
    render(<PromptWorkbench />);

    fireEvent.click(await screen.findByRole("button", { name: "光影" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 細緻光影" }));
    fireEvent.click(screen.getByRole("button", { name: "加入 cinematic glow" }));
    fireEvent.click(screen.getByRole("button", { name: "加入 arbitrary-id-only" }));

    await waitFor(() => expect(screen.getByLabelText("細緻光影 內容")).toHaveValue("detailed light"));
    expect(screen.getByLabelText("cinematic glow 內容")).toHaveValue("  cinematic glow  ");
    expect(screen.getByLabelText("arbitrary-id-only 內容")).toHaveValue("arbitrary-id-only");
    expect(screen.getByLabelText("cinematic glow 中文對照可能未填好")).toBeVisible();
    expect(screen.getByLabelText("arbitrary-id-only 中文對照可能未填好")).toBeVisible();
    expect(screen.queryByText(/片段\s*\d+/)).not.toBeInTheDocument();
  });

  it("shows each fragment's category label on its card and keeps final text unchanged", () => {
    let state = emptyComposition();
    state = appendFragment(state, {
      id: "entry-quality",
      kind: "entry",
      displayName: "傑作",
      source: { polarity: "positive", categoryId: "quality-ratings", entryId: "masterpiece" },
      sourceSnapshotRaw: "masterpiece",
      snapshotRaw: "masterpiece",
      weight: "",
    });
    state = appendFragment(state, {
      id: "entry-environment",
      kind: "entry",
      displayName: "屋頂",
      source: { polarity: "positive", categoryId: "environment", entryId: "rooftop" },
      sourceSnapshotRaw: "rooftop",
      snapshotRaw: "rooftop",
      weight: "",
    });
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
    // each label appears twice: once as a filter chip, once as the per-card category badge.
    expect(screen.getAllByText("品質與分級")).toHaveLength(2);
    expect(screen.getAllByText("場景與氛圍")).toHaveLength(2);
    expect((screen.getByLabelText("Positive Prompt 最終文字") as HTMLTextAreaElement).value).toBe(
      "masterpiece,rooftop",
    );
  });

  it("shows a category filter that narrows the visible cards and keeps final text unchanged", () => {
    let state = emptyComposition();
    state = appendFragment(state, {
      id: "entry-quality",
      kind: "entry",
      displayName: "傑作",
      source: { polarity: "positive", categoryId: "quality-ratings", entryId: "masterpiece" },
      sourceSnapshotRaw: "masterpiece",
      snapshotRaw: "masterpiece",
      weight: "",
    });
    state = appendFragment(state, {
      id: "entry-environment",
      kind: "entry",
      displayName: "rooftop",
      source: { polarity: "positive", categoryId: "environment", entryId: "rooftop" },
      sourceSnapshotRaw: "rooftop",
      snapshotRaw: "rooftop",
      weight: "",
    });
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
    expect((screen.getByLabelText("Positive Prompt 最終文字") as HTMLTextAreaElement).value).toBe(
      "masterpiece,rooftop",
    );
  });

  it("paginates selected cards at 9 per page", () => {
    const state = fragments(10);
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

  it("fires onReapplySort when the button is clicked", () => {
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
    fireEvent.click(screen.getByLabelText("Positive Prompt 重新套用推薦排序"));
    expect(onReapplySort).toHaveBeenCalledTimes(1);
  });
});
