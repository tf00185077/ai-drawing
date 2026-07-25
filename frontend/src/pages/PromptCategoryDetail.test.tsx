import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getPromptCategory } from "../components/prompt-library/promptLibraryApi";
import PromptCategoryDetail from "./PromptCategoryDetail";

vi.mock("../components/prompt-library/promptLibraryApi", () => ({ getPromptCategory: vi.fn() }));

const versionedCategory = {
  category: {
    schema_version: 1 as const,
    id: "quality-ratings",
    polarity: "positive" as const,
    name_zh: "品質評分",
    description_zh: "品質與評分提示詞",
    aliases: ["quality"],
    keywords: ["品質"],
    order: 10,
    revision: 7,
    archived: true,
    entries: [],
  },
  etag: "etag-7",
};

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/prompt-library/categories/:polarity/:categoryId" element={<PromptCategoryDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("PromptCategoryDetail", () => {
  it("fetches valid params and displays complete category metadata", async () => {
    vi.mocked(getPromptCategory).mockResolvedValue(versionedCategory);
    renderAt("/prompt-library/categories/positive/quality-ratings");
    expect(await screen.findByRole("heading", { name: "品質評分" })).toBeVisible();
    expect(getPromptCategory).toHaveBeenCalledWith("positive", "quality-ratings");
    expect(screen.getByText("Revision 7")).toBeVisible();
    expect(screen.getByText("已封存")).toBeVisible();
    expect(screen.getByText("etag-7")).toBeVisible();
    expect(screen.getByText("品質與評分提示詞")).toBeVisible();
  });

  it("renders category ID as readonly and non-editable", async () => {
    vi.mocked(getPromptCategory).mockResolvedValue(versionedCategory);
    renderAt("/prompt-library/categories/positive/quality-ratings");
    const id = await screen.findByLabelText("分類 ID");
    expect(id).toHaveValue("quality-ratings");
    expect(id).toHaveAttribute("readonly");
  });

  it("links back to category management", async () => {
    vi.mocked(getPromptCategory).mockResolvedValue(versionedCategory);
    renderAt("/prompt-library/categories/positive/quality-ratings");
    expect(await screen.findByRole("link", { name: "返回分類管理" })).toHaveAttribute("href", "/prompt-library/categories");
  });

  it("rejects invalid polarity without fetching", async () => {
    renderAt("/prompt-library/categories/neutral/quality-ratings");
    expect(await screen.findByRole("alert")).toHaveTextContent("分類類型無效");
    expect(screen.getByRole("link", { name: "返回分類管理" })).toBeVisible();
    expect(getPromptCategory).not.toHaveBeenCalled();
  });

  it("provides accessible loading and actionable fetch-error states", async () => {
    let rejectRequest!: (error: Error) => void;
    vi.mocked(getPromptCategory).mockImplementation(() => new Promise((_resolve, reject) => { rejectRequest = reject; }));
    renderAt("/prompt-library/categories/positive/quality-ratings");
    expect(screen.getByRole("status")).toHaveTextContent("載入分類中");
    rejectRequest(new Error("分類讀取失敗"));
    expect(await screen.findByRole("alert")).toHaveTextContent("分類讀取失敗");
    expect(screen.getByRole("button", { name: "重新載入" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "重新載入" }));
    await waitFor(() => expect(getPromptCategory).toHaveBeenCalledTimes(2));
  });
});
