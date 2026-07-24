import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
      { id: "masterpiece", fields: { name_zh: "大師傑作", description_zh: "大師級品質", prompt: "masterpiece", aliases: ["傑作"], keywords: ["quality"], order: 10 } },
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
    expect(vi.mocked(props.onSaveEntry).mock.calls[0][1]).toBe("create");
    expect(vi.mocked(props.onSaveEntry).mock.calls[0][0].id).toBe("sharp-focus");
  });
});
