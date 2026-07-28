import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PromptEntryBrowser, { type BrowserCategory, type BrowserEntry } from "./PromptEntryBrowser";

const category: BrowserCategory = { id: "quality", polarity: "positive", name_zh: "品質", revision: 1, etag: "p1", archived: false, parent_id: null, order: 10 };
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
    allEntries: entries.map((entry) => ({ category, entry })),
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

  it("filters source entries by Chinese name or prompt across the whole tree", () => {
    renderBrowser();

    fireEvent.change(screen.getByLabelText("搜尋提示詞"), { target: { value: "masterpiece" } });

    expect(screen.getByRole("button", { name: "加入 傑作" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "加入 best quality" })).not.toBeInTheDocument();
  });

  it("forwards polarity switching and drill-in category opening", () => {
    const negativeCategory: BrowserCategory = { id: "artifacts", polarity: "negative", name_zh: "瑕疵", revision: 1, etag: "n1", archived: false, parent_id: null, order: 10 };
    const props = renderBrowser({ categories: [category, negativeCategory], selectedCategory: null });

    fireEvent.click(screen.getByRole("button", { name: "負向" }));
    expect(props.onPolarityChange).toHaveBeenCalledWith("negative");

    fireEvent.click(screen.getByRole("button", { name: "📁 品質" }));
    expect(props.onOpenCategory).toHaveBeenCalledWith(category);
  });

  it("adds the exact source entry reference once drilled into its category", () => {
    const props = renderBrowser();

    fireEvent.click(screen.getByRole("button", { name: "📁 品質" }));
    fireEvent.click(screen.getByRole("button", { name: "加入 傑作" }));

    expect(props.onAddEntry).toHaveBeenCalledWith(category, entries[0]);
  });

  it("adds literal text without trimming the entered value", () => {
    const props = renderBrowser();

    fireEvent.change(screen.getByLabelText("自由文字"), { target: { value: "  soft light  " } });
    fireEvent.click(screen.getByRole("button", { name: "加入目前正向" }));

    expect(props.onAddLiteral).toHaveBeenCalledWith("  soft light  ");
  });

  it("flags entries whose name_zh has no meaningful Chinese", () => {
    renderBrowser();
    fireEvent.click(screen.getByRole("button", { name: "📁 品質" }));

    const suspectWarningTitle = "name_zh 可能沒有有意義的中文對照，建議編輯修正";
    const suspectChip = screen.getByRole("button", { name: "加入 best quality" });
    expect(suspectChip.querySelector(`[title="${suspectWarningTitle}"]`)).toBeInTheDocument();
    const okChip = screen.getByRole("button", { name: "加入 傑作" });
    expect(okChip.querySelector(`[title="${suspectWarningTitle}"]`)).not.toBeInTheDocument();
  });

  it("renders entries as content-width chips with prompt in the title and fires onAddEntry", () => {
    const onAddEntry = vi.fn();
    const entry: BrowserEntry = { id: "e1", name_zh: "傑作", prompt: "masterpiece", description_zh: "d", aliases: [], keywords: [], order: 10, revision: 1, archived: false };
    render(
      <PromptEntryBrowser
        categories={[category]}
        activePolarity="positive"
        onPolarityChange={() => {}}
        selectedCategory={null}
        entries={[entry]}
        allEntries={[]}
        onOpenCategory={() => {}}
        onAddEntry={onAddEntry}
        onAddLiteral={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "📁 品質" }));
    const chip = screen.getByRole("button", { name: "加入 傑作" });
    expect(chip).toHaveAttribute("title", "masterpiece");
    fireEvent.click(chip);
    expect(onAddEntry).toHaveBeenCalledTimes(1);
    expect(onAddEntry).toHaveBeenCalledWith(category, entry);
  });

  it("paginates at 30 entries per page", () => {
    const entries = Array.from({ length: 31 }, (_, index) => ({
      id: `e${index}`, name_zh: `詞${index}`, prompt: `p${index}`, description_zh: "d",
      aliases: [], keywords: [], order: 10, revision: 1, archived: false,
    }));
    render(
      <PromptEntryBrowser
        categories={[category]}
        activePolarity="positive"
        onPolarityChange={() => {}}
        selectedCategory={null}
        entries={entries}
        allEntries={[]}
        onOpenCategory={() => {}}
        onAddEntry={() => {}}
        onAddLiteral={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "📁 品質" }));
    // 30 chips on page 1, pagination present
    expect(screen.getAllByRole("button", { name: /^加入 / })).toHaveLength(30);
    fireEvent.click(screen.getByLabelText("下一頁"));
    expect(screen.getAllByRole("button", { name: /^加入 / })).toHaveLength(1);
  });

  it("resets to the first page when switching from category browsing to a search", () => {
    // 62 entries -> 3 pages while browsing the category; the first 32 carry a
    // "keep" marker so that searching for "keep" still yields 2 pages, keeping
    // the pagination nav visible (a query that narrowed results to <=30 matches
    // would hide the nav entirely).
    const entries = Array.from({ length: 62 }, (_, index) => ({
      id: `e${index}`,
      name_zh: index < 32 ? `詞${index}keep` : `詞${index}`,
      prompt: `p${index}`,
      description_zh: "d",
      aliases: [], keywords: [], order: 10, revision: 1, archived: false,
    }));
    render(
      <PromptEntryBrowser
        categories={[category]}
        activePolarity="positive"
        onPolarityChange={() => {}}
        selectedCategory={null}
        entries={entries}
        allEntries={entries.map((entry) => ({ category, entry }))}
        onOpenCategory={() => {}}
        onAddEntry={() => {}}
        onAddLiteral={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "📁 品質" }));
    fireEvent.click(screen.getByLabelText("下一頁"));
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("搜尋提示詞"), { target: { value: "keep" } });
    // query narrows results to 32 matches (2 pages) and page snaps back to page 1
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
  });

  it("drills into a category, revealing its child folders and the breadcrumb path", () => {
    const childCategory: BrowserCategory = { id: "quality-sub", polarity: "positive", name_zh: "細節", revision: 1, etag: "p2", archived: false, parent_id: "quality", order: 10 };
    const onOpenCategory = vi.fn();
    render(
      <PromptEntryBrowser
        categories={[category, childCategory]}
        activePolarity="positive"
        onPolarityChange={() => {}}
        selectedCategory={null}
        entries={[]}
        allEntries={[]}
        onOpenCategory={onOpenCategory}
        onAddEntry={() => {}}
        onAddLiteral={() => {}}
      />,
    );

    // Top level only shows the root folder; the nested child stays hidden.
    expect(screen.getByRole("button", { name: "📁 品質" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "📁 細節" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "📁 品質" }));

    expect(onOpenCategory).toHaveBeenCalledWith(category);
    expect(screen.getByRole("button", { name: "📁 細節" })).toBeInTheDocument();
    const breadcrumb = screen.getByRole("navigation", { name: "分類路徑" });
    expect(within(breadcrumb).getByRole("button", { name: "頂層" })).toBeInTheDocument();
    expect(within(breadcrumb).getByRole("button", { name: "品質" })).toBeInTheDocument();
  });

  it("reloads the ancestor category's entries when its breadcrumb button is clicked", () => {
    const childCategory: BrowserCategory = { id: "quality-sub", polarity: "positive", name_zh: "細節", revision: 1, etag: "p2", archived: false, parent_id: "quality", order: 10 };
    const onOpenCategory = vi.fn();
    render(
      <PromptEntryBrowser
        categories={[category, childCategory]}
        activePolarity="positive"
        onPolarityChange={() => {}}
        selectedCategory={null}
        entries={[]}
        allEntries={[]}
        onOpenCategory={onOpenCategory}
        onAddEntry={() => {}}
        onAddLiteral={() => {}}
      />,
    );

    // Drill root -> child.
    fireEvent.click(screen.getByRole("button", { name: "📁 品質" }));
    fireEvent.click(screen.getByRole("button", { name: "📁 細節" }));
    expect(onOpenCategory).toHaveBeenLastCalledWith(childCategory);

    // Jump back to the root via its breadcrumb button; this must re-fire
    // onOpenCategory for the root so the workbench reloads its entries
    // (currentId alone would leave the entries prop pointing at the child).
    const breadcrumb = screen.getByRole("navigation", { name: "分類路徑" });
    fireEvent.click(within(breadcrumb).getByRole("button", { name: "品質" }));

    expect(onOpenCategory).toHaveBeenLastCalledWith(category);
  });

  it("searches across the whole tree and labels each hit with its category path", () => {
    const otherCategory: BrowserCategory = { id: "style", polarity: "positive", name_zh: "風格", revision: 1, etag: "p3", archived: false, parent_id: null, order: 20 };
    const hit: BrowserEntry = { id: "soft", name_zh: "柔焦光", prompt: "soft masterpiece light", description_zh: "d", aliases: [], keywords: [], order: 10, revision: 1, archived: false };
    render(
      <PromptEntryBrowser
        categories={[category, otherCategory]}
        activePolarity="positive"
        onPolarityChange={() => {}}
        selectedCategory={null}
        entries={[]}
        allEntries={[...entries.map((entry) => ({ category, entry })), { category: otherCategory, entry: hit }]}
        onOpenCategory={() => {}}
        onAddEntry={() => {}}
        onAddLiteral={() => {}}
      />,
    );

    fireEvent.change(screen.getByLabelText("搜尋提示詞"), { target: { value: "masterpiece" } });

    const hitFromQuality = screen.getByRole("button", { name: "加入 傑作" });
    const hitFromStyle = screen.getByRole("button", { name: "加入 柔焦光" });
    expect(hitFromQuality).toHaveTextContent("品質");
    expect(hitFromStyle).toHaveTextContent("風格");
  });

  it("adds a search hit using its own category, not the currently drilled-in one", () => {
    const otherCategory: BrowserCategory = { id: "style", polarity: "positive", name_zh: "風格", revision: 1, etag: "p3", archived: false, parent_id: null, order: 20 };
    const hit: BrowserEntry = { id: "soft", name_zh: "柔焦光", prompt: "soft masterpiece light", description_zh: "d", aliases: [], keywords: [], order: 10, revision: 1, archived: false };
    const onAddEntry = vi.fn();
    render(
      <PromptEntryBrowser
        categories={[category, otherCategory]}
        activePolarity="positive"
        onPolarityChange={() => {}}
        selectedCategory={null}
        entries={entries}
        allEntries={[...entries.map((entry) => ({ category, entry })), { category: otherCategory, entry: hit }]}
        onOpenCategory={() => {}}
        onAddEntry={onAddEntry}
        onAddLiteral={() => {}}
      />,
    );

    // Drill into "quality" (品質), not "style" (風格) where the search hit lives.
    fireEvent.click(screen.getByRole("button", { name: "📁 品質" }));
    fireEvent.change(screen.getByLabelText("搜尋提示詞"), { target: { value: "masterpiece" } });
    fireEvent.click(screen.getByRole("button", { name: "加入 柔焦光" }));

    expect(onAddEntry).toHaveBeenCalledWith(otherCategory, hit);
  });
});
