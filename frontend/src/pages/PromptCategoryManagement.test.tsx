import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => { resolve = nextResolve; reject = nextReject; });
  return { promise, resolve, reject };
}

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

// 「現有分類」清單以外，新增表單的父分類 <select> 也會渲染分類名稱作為選項文字；
// 用 within 侷限查詢範圍，避免與 select 的 option 文字撞名。
function categoryList() {
  return within(screen.getByRole("region", { name: "現有分類" }));
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
    await categoryList().findByText("品質");
    fillRequiredFields("Street Scene");
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("分類 ID 只能使用小寫英文字母");
    expect(putPromptCategory).not.toHaveBeenCalled();
  });

  it("rejects blank category order without a PUT", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue(catalog);
    renderPage();
    await categoryList().findByText("品質");
    fillRequiredFields();
    fireEvent.change(screen.getByLabelText(/排序/), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("排序必須是大於或等於 0 的整數");
    expect(putPromptCategory).not.toHaveBeenCalled();
  });

  it("does not let a pre-create catalog response overwrite the create follow-up refresh", async () => {
    const initial = deferred<PromptLibraryCatalogResponse>();
    const followUp = deferred<PromptLibraryCatalogResponse>();
    vi.mocked(getPromptCatalog).mockReturnValueOnce(initial.promise).mockReturnValueOnce(followUp.promise);
    vi.mocked(putPromptCategory).mockResolvedValue({
      category: { category: { schema_version: 1, ...positive, id: "street-scenes", name_zh: "街景", entries: [] }, etag: "created-etag" },
      combination: null, entry: null, entry_revision: null, affected_combinations: [],
    });
    renderPage();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));
    await waitFor(() => expect(getPromptCatalog).toHaveBeenCalledTimes(2));

    const created = { ...positive, id: "street-scenes", name_zh: "街景", etag: "created-etag" };
    await act(async () => {
      followUp.resolve({ ...catalog, categories: [created] });
    });
    expect(categoryList().getByText("街景")).toBeVisible();
    await act(async () => {
      initial.resolve({ ...catalog, categories: [] });
    });
    expect(categoryList().getByText("街景")).toBeVisible();
  });

  it("keeps newest refresh loading and error ownership against an older rejection", async () => {
    const initial = deferred<PromptLibraryCatalogResponse>();
    const newest = deferred<PromptLibraryCatalogResponse>();
    vi.mocked(getPromptCatalog).mockReturnValueOnce(initial.promise).mockReturnValueOnce(newest.promise);
    renderPage();
    await waitFor(() => expect(getPromptCatalog).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "重新整理分類" }));
    await act(async () => {
      initial.reject(new Error("obsolete catalog error"));
    });

    expect(screen.getByRole("status")).toHaveTextContent("載入分類中");
    expect(screen.queryByText("obsolete catalog error")).not.toBeInTheDocument();
    await act(async () => {
      newest.resolve(catalog);
    });
    expect(categoryList().getByText("品質")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps a structured conflict actionable", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue(catalog);
    vi.mocked(putPromptCategory).mockRejectedValue(new Error("分類已存在（重新載入後使用最新revision）"));
    renderPage();
    await categoryList().findByText("品質");
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("分類已存在（重新載入後使用最新revision）");
  });

  it("filters cards by positive and negative polarity", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue(catalog);
    renderPage();
    expect(await categoryList().findByText("品質")).toBeVisible();
    expect(categoryList().queryByText("不良結構")).not.toBeInTheDocument();
    fireEvent.click(categoryList().getByRole("button", { name: "負向" }));
    expect(categoryList().getByText("不良結構")).toBeVisible();
    expect(categoryList().queryByText("品質")).not.toBeInTheDocument();
  });

  it("filters cards by active and archived state and labels archived cards", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue(catalog);
    renderPage();
    await categoryList().findByText("品質");
    fireEvent.click(screen.getByRole("button", { name: "已封存" }));
    expect(categoryList().getByText("舊品質")).toBeVisible();
    expect(categoryList().queryByText("品質")).not.toBeInTheDocument();
    expect(categoryList().getByText("已封存", { selector: "span" })).toBeVisible();
  });

  it("links quality-ratings to its exact category detail href", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue(catalog);
    renderPage();
    const link = await screen.findByRole("link", { name: /品質/ });
    expect(link).toHaveAttribute("href", "/prompt-library/categories/positive/quality-ratings");
    fireEvent.click(link);
    expect(screen.getByText("Category detail destination")).toBeVisible();
  });

  it("encodes arbitrary category IDs in the detail href", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValue({
      ...catalog,
      categories: [{ ...positive, id: "quality ratings/精選", name_zh: "需編碼品質" }],
    });
    renderPage();
    expect(await screen.findByRole("link", { name: /需編碼品質/ })).toHaveAttribute(
      "href",
      "/prompt-library/categories/positive/quality%20ratings%2F%E7%B2%BE%E9%81%B8",
    );
  });

  it("preserves rendered cards and offers retry when refresh fails", async () => {
    vi.mocked(getPromptCatalog).mockResolvedValueOnce(catalog).mockRejectedValueOnce(new Error("目錄暫時無法使用"));
    renderPage();
    await categoryList().findByText("品質");
    fireEvent.click(screen.getByRole("button", { name: "重新整理分類" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("目錄暫時無法使用");
    expect(categoryList().getByText("品質")).toBeVisible();
    expect(screen.getByRole("button", { name: "重新載入" })).toBeVisible();
  });

  it("creates a child category under the selected parent", async () => {
    const root: PromptCatalogCategorySummary = {
      id: "clothing", polarity: "positive", name_zh: "服裝", description_zh: "服裝提示詞",
      aliases: [], keywords: [], order: 70, parent_id: null, revision: 1, archived: false, entry_count: 0, etag: "e",
    };
    vi.mocked(getPromptCatalog).mockResolvedValueOnce({ ...catalog, categories: [root] }).mockResolvedValueOnce({
      ...catalog,
      categories: [root],
    });
    vi.mocked(putPromptCategory).mockResolvedValue({
      category: { category: { schema_version: 1, ...positive, id: "street-scenes", name_zh: "街景", parent_id: "clothing", entries: [] }, etag: "created-etag" },
      combination: null, entry: null, entry_revision: null, affected_combinations: [],
    });
    renderPage();
    await categoryList().findByText("服裝");
    fillRequiredFields();
    fireEvent.change(screen.getByLabelText("父分類"), { target: { value: "clothing" } });
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));
    await waitFor(() => expect(putPromptCategory).toHaveBeenCalled());
    const [, , body] = vi.mocked(putPromptCategory).mock.calls[0];
    expect(body.parent_id).toBe("clothing");
  });
});
