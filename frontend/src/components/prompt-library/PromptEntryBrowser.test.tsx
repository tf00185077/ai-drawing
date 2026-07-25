import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PromptEntryBrowser, { type BrowserCategory, type BrowserEntry } from "./PromptEntryBrowser";

const category: BrowserCategory = { id: "quality", polarity: "positive", name_zh: "品質", revision: 1, etag: "p1", archived: false };
const entries: BrowserEntry[] = [
  { id: "masterpiece", name_zh: "傑作", prompt: "masterpiece", description_zh: "大師級品質", aliases: ["傑作"], keywords: ["quality"], order: 10, revision: 1, archived: false },
  { id: "best-quality", name_zh: "best quality", prompt: "best quality", description_zh: "最佳品質", aliases: [], keywords: [], order: 20, revision: 1, archived: false },
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
    ...overrides,
  };
  render(<PromptEntryBrowser {...props} />);
  return props;
}

describe("PromptEntryBrowser read-only source catalog", () => {
  it("renders no source create, edit, archive, or restore controls", () => {
    renderBrowser();

    expect(screen.queryByRole("button", { name: "新增詞條" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /編輯/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /封存/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /恢復/ })).not.toBeInTheDocument();
  });

  it("filters source entries by Chinese name or prompt", () => {
    renderBrowser();

    fireEvent.change(screen.getByLabelText("搜尋提示詞"), { target: { value: "masterpiece" } });

    expect(screen.getByRole("button", { name: "加入 傑作" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "加入 best quality" })).not.toBeInTheDocument();
  });

  it("forwards polarity and category switching", () => {
    const negativeCategory: BrowserCategory = { id: "artifacts", polarity: "negative", name_zh: "瑕疵", revision: 1, etag: "n1", archived: false };
    const props = renderBrowser({ categories: [category, negativeCategory], selectedCategory: null });

    fireEvent.click(screen.getByRole("button", { name: "負向" }));
    expect(props.onPolarityChange).toHaveBeenCalledWith("negative");

    fireEvent.click(screen.getByRole("button", { name: "品質" }));
    expect(props.onOpenCategory).toHaveBeenCalledWith(category);
  });

  it("adds the exact source entry reference", () => {
    const props = renderBrowser();

    fireEvent.click(screen.getByRole("button", { name: "加入 傑作" }));

    expect(props.onAddEntry).toHaveBeenCalledWith(entries[0]);
  });

  it("adds literal text without trimming the entered value", () => {
    const props = renderBrowser();

    fireEvent.change(screen.getByLabelText("自由文字"), { target: { value: "  soft light  " } });
    fireEvent.click(screen.getByRole("button", { name: "加入目前正向" }));

    expect(props.onAddLiteral).toHaveBeenCalledWith("  soft light  ");
  });

  it("flags entries whose name_zh has no meaningful Chinese", () => {
    renderBrowser();
    expect(screen.getByLabelText("best quality 中文對照可能未填好")).toBeInTheDocument();
    expect(screen.queryByLabelText("傑作 中文對照可能未填好")).not.toBeInTheDocument();
  });
});
