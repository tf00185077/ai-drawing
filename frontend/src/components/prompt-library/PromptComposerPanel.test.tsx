import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { appendFragment, emptyComposition } from "./compositionState";
import PromptComposerPanel from "./PromptComposerPanel";

function sixFragments() {
  let state = emptyComposition();
  for (let index = 1; index <= 6; index += 1) {
    state = appendFragment(state, {
      id: `fragment-${index}`,
      kind: "literal",
      originalSnapshot: `prompt ${index}`,
      text: `prompt ${index}`,
      weight: "",
    });
  }
  return state;
}

describe("PromptComposerPanel", () => {
  it("shows five options per page in a three-column grid", () => {
    render(
      <PromptComposerPanel
        title="Positive Prompt"
        state={sixFragments()}
        onTextChange={vi.fn()}
        onWeightChange={vi.fn()}
        onMove={vi.fn()}
        onRemove={vi.fn()}
        onComposedTextChange={vi.fn()}
      />,
    );

    expect(screen.getByTestId("prompt-option-grid")).toHaveClass("grid", "grid-cols-3");
    expect(screen.getAllByLabelText(/內容$/)).toHaveLength(5);
    expect(screen.getByText("1 / 2")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "下一頁" }));
    expect(screen.getAllByLabelText(/內容$/)).toHaveLength(1);
    expect(screen.getByText("2 / 2")).toBeVisible();
  });
});
