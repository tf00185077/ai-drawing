import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PromptCatalogCategorySummary, PromptLibraryCatalogResponse } from "../types/api";
import PromptCategoryManagement from "./PromptCategoryManagement";
import { getPromptCatalog, putPromptCategory } from "../components/prompt-library/promptLibraryApi";

vi.mock("../components/prompt-library/promptLibraryApi", () => ({
  getPromptCatalog: vi.fn(),
  putPromptCategory: vi.fn(),
}));

const positive: PromptCatalogCategorySummary = {
  id: "quality-ratings", polarity: "positive", name_zh: "品質", description_zh: "品質提示詞",
  aliases: [], keywords: [], order: 1, revision: 3, archived: false, entry_count: 2, etag: "p-etag",
};
const negative: PromptCatalogCategorySummary = {
  id: "bad-anatomy", polarity: "negative", name_zh: "不良結構", description_zh: "負向提示詞",
  aliases: [], keywords: [], order: 2, revision: 2, archived: false, entry_count: 1, etag: "n-etag",
};
const archived: PromptCatalogCategorySummary = {
  id: "legacy-quality", polarity: "positive", name_zh: "舊品質", description_zh: "已封存品質",
  aliases: [], keywords: [], order: 3, revision: 4, archived: true, entry_count: 0, etag: "a-etag",
};
const catalog: PromptLibraryCatalogResponse = {
  manifest: { schema_version: 1, library_id: "default", name: "Prompt Library", description_zh: "提示詞庫" },
  categories: [positive, negative, archived], combinations: [], diagnostics: [],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/prompt-library/categories"]}>
      <Routes>
        <Route path="/prompt-library/categories" element={<PromptCategoryManagement />} />
        <Route path="/prompt-library/categories/:polarity/:categoryId" element={<p>Category detail destination</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function fillRequiredFields(id = "street-scenes") {
  fireEvent.change(screen.getByLabelText(/分類 ID/), { target: { value: id } });
  fireEvent.change(screen.getByLabelText(/中文名稱/), { target: { value: "街景" } });
  fireEvent.change(screen.getByLabelText(/分類說明/), { target: { value: "都市道路場景" } });
}

afterEach(() => vi.clearAllMocks());

describe("PromptCategoryManagement", () => {
  it("creates with expected_revision zero and refreshes the catalog", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValueOnce({ ...catalog, categories: [] }).mockResolvedValueOnce(catalog);
    vi.mocked(putPromptCategory).mockResolvedValue({
      category: { category: { schema_version: 1, ...positive, entries: [] }, etag: "p-etag" },
      combination: null, entry: null, entry_revision: null, affected_combinations: [],
    });
    renderPage();
    await waitFor(() => expect(getPromptCatalog).toHaveBeenCalledTimes(1));
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));
    await screen.findByRole("status");
    expect(putPromptCategory).toHaveBeenCalledWith("positive", "street-scenes", expect.objectContaining({
      name_zh: "街景", description_zh: "都市道路場景", expected_revision: 0,
    }));
    expect(getPromptCatalog).toHaveBeenCalledTimes(2);
  });

  it("rejects an invalid slug without a PUT", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue(catalog);
    renderPage();
    await screen.findByText("品質");
    fillRequiredFields("Street Scene");
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("分類 ID 只能使用小寫英文字母");
    expect(putPromptCategory).not.toHaveBeenCalled();
  });

  it("keeps a structured conflict actionable", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue(catalog);
    vi.mocked(putPromptCategory).mockRejectedValue(new Error("分類已存在（重新載入後使用最新revision）"));
    renderPage();
    await screen.findByText("品質");
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("分類已存在（重新載入後使用最新revision）");
  });

  it("filters cards by positive and negative polarity", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue(catalog);
    renderPage();
    expect(await screen.findByText("品質")).toBeVisible();
    expect(screen.queryByText("不良結構")).not.toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("region", { name: "現有分類" })).getByRole("button", { name: "負向" }));
    expect(screen.getByText("不良結構")).toBeVisible();
    expect(screen.queryByText("品質")).not.toBeInTheDocument();
  });

  it("filters cards by active and archived state and labels archived cards", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue(catalog);
    renderPage();
    await screen.findByText("品質");
    fireEvent.click(screen.getByRole("button", { name: "已封存" }));
    expect(screen.getByText("舊品質")).toBeVisible();
    expect(screen.queryByText("品質")).not.toBeInTheDocument();
    expect(screen.getByText("已封存", { selector: "span" })).toBeVisible();
  });

  it("navigates to the encoded category detail when a card is clicked", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue(catalog);
    renderPage();
    fireEvent.click(await screen.findByRole("link", { name: /品質/ }));
    expect(screen.getByText("Category detail destination")).toBeVisible();
  });

  it("preserves rendered cards and offers retry when refresh fails", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValueOnce(catalog).mockRejectedValueOnce(new Error("目錄暫時無法使用"));
    renderPage();
    await screen.findByText("品質");
    fireEvent.click(screen.getByRole("button", { name: "重新整理分類" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("目錄暫時無法使用");
    expect(screen.getByText("品質")).toBeVisible();
    expect(screen.getByRole("button", { name: "重新載入" })).toBeVisible();
  });
});
