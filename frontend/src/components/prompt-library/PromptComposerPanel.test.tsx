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
      originalSnapshot: `prompt ${index}`,
      text: `prompt ${index}`,
      weight: "",
    });
  }
  return state;
}

function panelProps(state: CompositionState = fragments(1)) {
  return {
    title: "Positive Prompt" as const,
    state,
    onTextChange: vi.fn(),
    onWeightChange: vi.fn(),
    onMove: vi.fn(),
    onRemove: vi.fn(),
    onFinalTextChange: vi.fn(),
  };
}

describe("PromptComposerPanel", () => {
  it("shows six options per page in a responsive two-column grid", () => {
    const state = fragments(7);
    render(<PromptComposerPanel {...panelProps(state)} />);

    expect(screen.getByTestId("prompt-option-grid")).toHaveClass("grid", "grid-cols-1", "md:grid-cols-2");
    expect(screen.getAllByLabelText(/內容$/)).toHaveLength(6);
    expect(screen.getByText("1 / 2")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "下一頁" }));
    expect(screen.getAllByLabelText(/內容$/)).toHaveLength(1);
    expect(screen.getByText("2 / 2")).toBeVisible();
  });

  it("uses human fragment labels, marks edited entry copies, and exposes literal content", () => {
    let state = emptyComposition();
    state = appendFragment(state, {
      id: "entry-human",
      kind: "entry",
      displayName: "精緻光影",
      source: { polarity: "positive", categoryId: "quality", entryId: "masterpiece" },
      originalSnapshot: "masterpiece",
      text: "masterwork",
      weight: "",
    });
    state = appendFragment(state, {
      id: "literal",
      kind: "literal",
      displayName: "自訂文字",
      originalSnapshot: "soft light",
      text: "soft light",
      weight: "",
    });
    render(<PromptComposerPanel {...panelProps(state)} />);

    expect(screen.getByLabelText("精緻光影 內容")).toHaveValue("masterwork");
    expect(screen.getByText("自訂副本")).toBeVisible();
    expect(screen.getByLabelText("自訂文字 內容")).toHaveValue("soft light");
    expect(screen.queryByText(/片段\s*\d+/)).not.toBeInTheDocument();
  });

  it("rerenders the controlled final text on every exact keystroke", () => {
    function Harness() {
      const [state, setState] = useState(() => fragments(1));
      return <PromptComposerPanel {...panelProps(state)} onFinalTextChange={(text) => {
        setState((current) => materializeRawText(current, text, () => "direct-literal"));
      }} />;
    }
    render(<Harness />);

    const editor = screen.getByLabelText("Positive Prompt 最終文字");
    expect(editor).not.toHaveAttribute("readonly");
    for (const text of ["masterpiece,", "masterpiece, ", "masterpiece,  (unfinished"]) {
      fireEvent.change(editor, { target: { value: text } });
      expect(editor).toHaveValue(text);
    }
    expect(screen.queryByRole("button", { name: /自由文字模式|套用|取消/ })).not.toBeInTheDocument();
  });

  it("assigns live browser entries trimmed names with prompt and ID fallbacks", async () => {
    const entries = [
      { id: "arbitrary-human-id", name_zh: "  細緻光影  ", prompt: "detailed light", description_zh: "", revision: 1, archived: false },
      { id: "arbitrary-prompt-id", name_zh: " ", prompt: "  cinematic glow  ", description_zh: "", revision: 1, archived: false },
      { id: "arbitrary-id-only", name_zh: undefined, prompt: undefined, description_zh: "", revision: 1, archived: false },
    ];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
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
});
