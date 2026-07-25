import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  archivePromptResource,
  getPromptCategory,
  putPromptCategory,
  putPromptEntry,
  restorePromptResource,
} from "../components/prompt-library/promptLibraryApi";
import PromptCategoryDetail from "./PromptCategoryDetail";

vi.mock("../components/prompt-library/promptLibraryApi", () => ({
  archivePromptResource: vi.fn(),
  getPromptCategory: vi.fn(),
  putPromptCategory: vi.fn(),
  putPromptEntry: vi.fn(),
  restorePromptResource: vi.fn(),
}));

const activeEntry = {
  id: "masterpiece",
  name_zh: "傑作",
  description_zh: "高品質",
  prompt: "masterpiece",
  aliases: ["best"],
  keywords: ["品質"],
  order: 10,
  revision: 3,
  archived: false,
};
const archivedEntry = { ...activeEntry, id: "old-style", name_zh: "舊風格", archived: true };
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
    archived: false,
    entries: [activeEntry, archivedEntry],
  },
  etag: "etag-7",
};
const archivedCategory = { ...versionedCategory, category: { ...versionedCategory.category, archived: true } };
const reloadedCategory = {
  ...versionedCategory,
  category: { ...versionedCategory.category, name_zh: "新版品質", revision: 8 },
  etag: "etag-8",
};
function versionAt(revision: number, overrides: Partial<typeof versionedCategory.category> = {}) {
  return {
    category: { ...versionedCategory.category, revision, ...overrides },
    etag: `etag-${revision}`,
  };
}
const writeResponse = { category: null, combination: null, entry: null, entry_revision: null, affected_combinations: [] };

function renderAt(path = "/prompt-library/categories/positive/quality-ratings") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/prompt-library/categories/:polarity/:categoryId" element={<PromptCategoryDetail />} /></Routes>
    </MemoryRouter>,
  );
}
function NavigationHarness() {
  const navigate = useNavigate();
  return <><button type="button" onClick={() => navigate("/prompt-library/categories/negative/bad-anatomy")}>前往不良結構</button><Routes><Route path="/prompt-library/categories/:polarity/:categoryId" element={<PromptCategoryDetail />} /></Routes></>;
}
function renderNavigable(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><NavigationHarness /></MemoryRouter>);
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => { resolve = resolvePromise; reject = rejectPromise; });
  return { promise, resolve, reject };
}
function categoryFor(id: string, polarity: "positive" | "negative", name: string) {
  return { ...versionedCategory, category: { ...versionedCategory.category, id, polarity, name_zh: name } };
}

const confirmSpy = vi.spyOn(window, "confirm");
beforeEach(() => {
  vi.resetAllMocks();
  confirmSpy.mockReturnValue(true);
});
afterEach(() => vi.clearAllMocks());

describe("PromptCategoryDetail", () => {
  it("edits category metadata with the current token and reloads the latest category", async () => {
    vi.mocked(getPromptCategory).mockResolvedValueOnce(versionedCategory).mockResolvedValueOnce(reloadedCategory);
    vi.mocked(putPromptCategory).mockResolvedValue(writeResponse);
    renderAt();
    expect(await screen.findByRole("heading", { name: "品質評分" })).toBeVisible();
    expect(screen.getByLabelText("分類 ID")).toHaveAttribute("readonly");
    fireEvent.change(screen.getByLabelText("分類中文名稱"), { target: { value: "新版品質" } });
    fireEvent.change(screen.getByLabelText("分類說明"), { target: { value: "新版說明" } });
    fireEvent.change(screen.getByLabelText("分類別名"), { target: { value: "quality, rating" } });
    fireEvent.change(screen.getByLabelText("分類關鍵字"), { target: { value: "品質, 評分" } });
    fireEvent.change(screen.getByLabelText("分類排序"), { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存分類" }));
    await waitFor(() => expect(putPromptCategory).toHaveBeenCalledWith("positive", "quality-ratings", {
      name_zh: "新版品質", description_zh: "新版說明", aliases: ["quality", "rating"], keywords: ["品質", "評分"], order: 12,
      expected_revision: 7, expected_etag: "etag-7",
    }));
    expect(await screen.findByRole("heading", { name: "新版品質" })).toBeVisible();
    expect(screen.getByText("Revision 8")).toBeVisible();
    expect(screen.getByText("etag-8")).toBeVisible();
  });

  it("rejects a blank category order without writing", async () => {
    vi.mocked(getPromptCategory).mockResolvedValue(versionedCategory);
    renderAt();
    fireEvent.change(await screen.findByLabelText("分類排序"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存分類" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("分類排序必須是大於或等於 0 的整數");
    expect(screen.getByLabelText("分類排序")).toHaveValue(null);
    expect(putPromptCategory).not.toHaveBeenCalled();
  });

  it("reloads category archive/restore state, preserves archived entries, and uses each new token", async () => {
    const afterArchive = versionAt(8, { archived: true });
    const afterRestore = versionAt(9, { archived: false });
    const afterSave = versionAt(10, { name_zh: "恢復後品質" });
    vi.mocked(getPromptCategory)
      .mockResolvedValueOnce(versionedCategory)
      .mockResolvedValueOnce(afterArchive)
      .mockResolvedValueOnce(afterRestore)
      .mockResolvedValueOnce(afterSave);
    vi.mocked(archivePromptResource).mockResolvedValue(writeResponse);
    vi.mocked(restorePromptResource).mockResolvedValue(writeResponse);
    vi.mocked(putPromptCategory).mockResolvedValue(writeResponse);
    confirmSpy.mockReturnValueOnce(false).mockReturnValueOnce(true);
    renderAt();
    await screen.findByRole("heading", { name: "品質評分" });
    fireEvent.click(screen.getByRole("button", { name: "封存分類" }));
    expect(archivePromptResource).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "封存分類" }));
    await waitFor(() => expect(archivePromptResource).toHaveBeenCalledWith({
      resource_type: "category", resource_id: "quality-ratings", polarity: "positive", expected_revision: 7, expected_etag: "etag-7",
    }));
    expect(await screen.findByText("Revision 8")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "恢復分類" }));
    await waitFor(() => expect(restorePromptResource).toHaveBeenCalledWith({
      resource_type: "category", resource_id: "quality-ratings", polarity: "positive", expected_revision: 8, expected_etag: "etag-8",
    }));
    expect(await screen.findByText("Revision 9")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "已封存詞條" }));
    expect(screen.getByText("舊風格")).toBeVisible();

    fireEvent.change(screen.getByLabelText("分類中文名稱"), { target: { value: "恢復後品質" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存分類" }));
    await waitFor(() => expect(putPromptCategory).toHaveBeenCalledWith("positive", "quality-ratings", expect.objectContaining({
      expected_revision: 9, expected_etag: "etag-9",
    })));
    expect(getPromptCategory).toHaveBeenCalledTimes(4);
  });

  it("preserves category draft and displays an actionable mutation error", async () => {
    vi.mocked(getPromptCategory).mockResolvedValue(versionedCategory);
    vi.mocked(putPromptCategory).mockRejectedValue(new Error("版本衝突，請重新載入後再試"));
    renderAt();
    fireEvent.change(await screen.findByLabelText("分類中文名稱"), { target: { value: "尚未儲存名稱" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存分類" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("版本衝突");
    expect(screen.getByLabelText("分類中文名稱")).toHaveValue("尚未儲存名稱");
    expect(getPromptCategory).toHaveBeenCalledTimes(1);
  });

  it("filters active and archived entries", async () => {
    vi.mocked(getPromptCategory).mockResolvedValue(versionedCategory);
    renderAt();
    await screen.findByText("傑作");
    expect(screen.queryByText("舊風格")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "已封存詞條" }));
    expect(screen.getByText("舊風格")).toBeVisible();
    expect(screen.queryByText("傑作")).not.toBeInTheDocument();
  });

  it("creates an entry with the current parent token and reloads", async () => {
    vi.mocked(getPromptCategory).mockResolvedValueOnce(versionedCategory).mockResolvedValueOnce(reloadedCategory);
    vi.mocked(putPromptEntry).mockResolvedValue(writeResponse);
    renderAt();
    fireEvent.click(await screen.findByRole("button", { name: "新增詞條" }));
    fireEvent.change(screen.getByLabelText("詞條 ID"), { target: { value: "detailed-eyes" } });
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "細緻眼睛" } });
    fireEvent.change(screen.getByLabelText("詞條說明"), { target: { value: "眼睛細節" } });
    fireEvent.change(screen.getByLabelText("詞條英文 prompt"), { target: { value: "detailed eyes" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    await waitFor(() => expect(putPromptEntry).toHaveBeenCalledWith("positive", "quality-ratings", "detailed-eyes", expect.objectContaining({
      name_zh: "細緻眼睛", prompt: "detailed eyes", expected_revision: 7, expected_etag: "etag-7",
    })));
    await waitFor(() => expect(getPromptCategory).toHaveBeenCalledTimes(2));
  });

  it("edits an immutable entry ID and reports affected combinations", async () => {
    vi.mocked(getPromptCategory).mockResolvedValueOnce(versionedCategory).mockResolvedValueOnce(reloadedCategory);
    vi.mocked(putPromptEntry).mockResolvedValue({ ...writeResponse, affected_combinations: ["combo-a", "combo-b"] });
    renderAt();
    fireEvent.click(await screen.findByRole("button", { name: "編輯 masterpiece" }));
    expect(screen.getByLabelText("詞條 ID")).toBeDisabled();
    expect(screen.getByLabelText("詞條 ID")).toHaveValue("masterpiece");
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "超級傑作" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    await waitFor(() => expect(putPromptEntry).toHaveBeenCalledWith("positive", "quality-ratings", "masterpiece", expect.objectContaining({ expected_revision: 7, expected_etag: "etag-7" })));
    expect(await screen.findByText("已同步更新 2 個組合：combo-a、combo-b")).toBeVisible();
  });

  it("clears an affected-combination notice on the next mutation and empty response", async () => {
    vi.mocked(getPromptCategory)
      .mockResolvedValueOnce(versionedCategory)
      .mockResolvedValueOnce(versionAt(8))
      .mockResolvedValueOnce(versionAt(9));
    vi.mocked(putPromptEntry)
      .mockResolvedValueOnce({ ...writeResponse, affected_combinations: ["combo-a"] })
      .mockResolvedValueOnce(writeResponse);
    renderAt();
    fireEvent.click(await screen.findByRole("button", { name: "編輯 masterpiece" }));
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(await screen.findByText("已同步更新 1 個組合：combo-a")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "編輯 masterpiece" }));
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(screen.queryByText("已同步更新 1 個組合：combo-a")).not.toBeInTheDocument();
    await waitFor(() => expect(getPromptCategory).toHaveBeenCalledTimes(3));
    expect(screen.queryByText("已同步更新 1 個組合：combo-a")).not.toBeInTheDocument();
  });

  it("reloads entry archive/restore state and uses reloaded tokens for later writes", async () => {
    const afterArchive = versionAt(8, { entries: [{ ...activeEntry, archived: true }, archivedEntry] });
    const restoredOldEntry = { ...archivedEntry, archived: false };
    const afterRestore = versionAt(9, { entries: [{ ...activeEntry, archived: true }, restoredOldEntry] });
    const afterEdit = versionAt(10, { entries: [{ ...activeEntry, archived: true }, restoredOldEntry] });
    vi.mocked(getPromptCategory)
      .mockResolvedValueOnce(versionedCategory)
      .mockResolvedValueOnce(afterArchive)
      .mockResolvedValueOnce(afterRestore)
      .mockResolvedValueOnce(afterEdit);
    vi.mocked(archivePromptResource).mockResolvedValue(writeResponse);
    vi.mocked(restorePromptResource).mockResolvedValue(writeResponse);
    vi.mocked(putPromptEntry).mockResolvedValue(writeResponse);
    confirmSpy.mockReturnValueOnce(false).mockReturnValueOnce(true);
    renderAt();
    const activeCard = (await screen.findByText("傑作")).closest("article")!;
    fireEvent.click(within(activeCard).getByRole("button", { name: "封存" }));
    expect(archivePromptResource).not.toHaveBeenCalled();
    fireEvent.click(within(activeCard).getByRole("button", { name: "封存" }));
    await waitFor(() => expect(archivePromptResource).toHaveBeenCalledWith({
      resource_type: "entry", resource_id: "masterpiece", category_id: "quality-ratings", polarity: "positive", expected_revision: 7, expected_etag: "etag-7",
    }));
    expect(await screen.findByText("Revision 8")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "已封存詞條" }));
    fireEvent.click(within(screen.getByText("舊風格").closest("article")!).getByRole("button", { name: "恢復" }));
    await waitFor(() => expect(restorePromptResource).toHaveBeenCalledWith({
      resource_type: "entry", resource_id: "old-style", category_id: "quality-ratings", polarity: "positive", expected_revision: 8, expected_etag: "etag-8",
    }));
    expect(await screen.findByText("Revision 9")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "使用中詞條" }));
    fireEvent.click(screen.getByRole("button", { name: "編輯 old-style" }));
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    await waitFor(() => expect(putPromptEntry).toHaveBeenCalledWith("positive", "quality-ratings", "old-style", expect.objectContaining({
      expected_revision: 9, expected_etag: "etag-9",
    })));
    expect(getPromptCategory).toHaveBeenCalledTimes(4);
  });

  it("keeps a rejected entry editor and draft mounted", async () => {
    vi.mocked(getPromptCategory).mockResolvedValue(versionedCategory);
    vi.mocked(putPromptEntry).mockRejectedValue(new Error("版本衝突"));
    renderAt();
    fireEvent.click(await screen.findByRole("button", { name: "編輯 masterpiece" }));
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "草稿傑作" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("版本衝突");
    expect(screen.getByLabelText("詞條中文名稱")).toHaveValue("草稿傑作");
  });

  it("disables mutation controls while submitting", async () => {
    const mutation = deferred<typeof writeResponse>();
    vi.mocked(getPromptCategory).mockResolvedValue(versionedCategory);
    vi.mocked(putPromptEntry).mockReturnValue(mutation.promise);
    renderAt();
    fireEvent.click(await screen.findByRole("button", { name: "編輯 masterpiece" }));
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(screen.getByRole("button", { name: "儲存中…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "取消" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "封存分類" })).toBeDisabled();
    await act(async () => mutation.resolve(writeResponse));
  });

  it("disables entry restore under an archived parent and explains why", async () => {
    vi.mocked(getPromptCategory).mockResolvedValue(archivedCategory);
    renderAt();
    fireEvent.click(await screen.findByRole("button", { name: "已封存詞條" }));
    expect(screen.getByRole("button", { name: "恢復" })).toBeDisabled();
    expect(screen.getByText("請先恢復分類")).toBeVisible();
  });

  it("rejects invalid polarity without fetching", async () => {
    renderAt("/prompt-library/categories/neutral/quality-ratings");
    expect(await screen.findByRole("alert")).toHaveTextContent("分類類型無效");
    expect(getPromptCategory).not.toHaveBeenCalled();
  });

  it("shows loading and fetch errors and retries the category request", async () => {
    const initialRequest = deferred<typeof versionedCategory>();
    vi.mocked(getPromptCategory)
      .mockReturnValueOnce(initialRequest.promise)
      .mockResolvedValueOnce(versionedCategory);
    renderAt();
    expect(screen.getByRole("status")).toHaveTextContent("載入分類中");
    await act(async () => initialRequest.reject(new Error("暫時無法讀取")));
    expect(await screen.findByRole("alert")).toHaveTextContent("暫時無法讀取");
    fireEvent.click(screen.getByRole("button", { name: "重新載入" }));
    expect(screen.getByRole("status")).toHaveTextContent("載入分類中");
    expect(await screen.findByRole("heading", { name: "品質評分" })).toBeVisible();
    expect(getPromptCategory).toHaveBeenCalledTimes(2);
  });

  it("clears the previous category as soon as route params change", async () => {
    const nextRequest = deferred<ReturnType<typeof categoryFor>>();
    vi.mocked(getPromptCategory).mockResolvedValueOnce(categoryFor("quality-ratings", "positive", "品質評分")).mockReturnValueOnce(nextRequest.promise);
    renderNavigable("/prompt-library/categories/positive/quality-ratings");
    expect(await screen.findByRole("heading", { name: "品質評分" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "前往不良結構" }));
    expect(screen.getByRole("status")).toHaveTextContent("載入分類中");
    expect(screen.queryByRole("heading", { name: "品質評分" })).not.toBeInTheDocument();
    nextRequest.resolve(categoryFor("bad-anatomy", "negative", "不良結構"));
    expect(await screen.findByRole("heading", { name: "不良結構" })).toBeVisible();
  });

  it("does not let an old-route mutation reload overwrite the current route", async () => {
    const oldMutation = deferred<typeof writeResponse>();
    vi.mocked(getPromptCategory)
      .mockResolvedValueOnce(categoryFor("quality-ratings", "positive", "品質評分"))
      .mockResolvedValueOnce(categoryFor("bad-anatomy", "negative", "不良結構"))
      .mockResolvedValue(categoryFor("quality-ratings", "positive", "品質評分"));
    vi.mocked(putPromptCategory).mockReturnValue(oldMutation.promise);
    renderNavigable("/prompt-library/categories/positive/quality-ratings");
    fireEvent.change(await screen.findByLabelText("分類中文名稱"), { target: { value: "舊路由草稿" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存分類" }));
    fireEvent.click(screen.getByRole("button", { name: "前往不良結構" }));
    expect(await screen.findByRole("heading", { name: "不良結構" })).toBeVisible();
    expect(screen.getByRole("button", { name: "儲存分類" })).toBeEnabled();
    await act(async () => { oldMutation.resolve(writeResponse); await oldMutation.promise; });
    await waitFor(() => expect(getPromptCategory).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("heading", { name: "不良結構" })).toBeVisible();
  });

  it("rejects an old-route write without changing route B error, loading, or controls", async () => {
    const oldMutation = deferred<typeof writeResponse>();
    vi.mocked(getPromptCategory)
      .mockResolvedValueOnce(categoryFor("quality-ratings", "positive", "品質評分"))
      .mockResolvedValueOnce(categoryFor("bad-anatomy", "negative", "不良結構"));
    vi.mocked(putPromptCategory).mockReturnValue(oldMutation.promise);
    renderNavigable("/prompt-library/categories/positive/quality-ratings");
    fireEvent.click(await screen.findByRole("button", { name: "儲存分類" }));
    fireEvent.click(screen.getByRole("button", { name: "前往不良結構" }));
    expect(await screen.findByRole("heading", { name: "不良結構" })).toBeVisible();
    expect(screen.getByRole("button", { name: "儲存分類" })).toBeEnabled();
    await act(async () => oldMutation.reject(new Error("A 寫入失敗")));
    expect(screen.queryByText("A 寫入失敗")).not.toBeInTheDocument();
    expect(screen.queryByText("載入分類中…")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "儲存分類" })).toBeEnabled();
  });

  it("ignores an old post-write reload that resolves after route B", async () => {
    const oldReload = deferred<ReturnType<typeof categoryFor>>();
    vi.mocked(getPromptCategory)
      .mockResolvedValueOnce(categoryFor("quality-ratings", "positive", "品質評分"))
      .mockReturnValueOnce(oldReload.promise)
      .mockResolvedValueOnce(categoryFor("bad-anatomy", "negative", "不良結構"));
    vi.mocked(putPromptCategory).mockResolvedValue(writeResponse);
    renderNavigable("/prompt-library/categories/positive/quality-ratings");
    fireEvent.click(await screen.findByRole("button", { name: "儲存分類" }));
    await waitFor(() => expect(getPromptCategory).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "前往不良結構" }));
    expect(await screen.findByRole("heading", { name: "不良結構" })).toBeVisible();
    await act(async () => oldReload.resolve(categoryFor("quality-ratings", "positive", "舊分類重載")));
    expect(screen.getByRole("heading", { name: "不良結構" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "舊分類重載" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "儲存分類" })).toBeEnabled();
  });

  it("rejects an old post-write reload without changing route B", async () => {
    const oldReload = deferred<ReturnType<typeof categoryFor>>();
    vi.mocked(getPromptCategory)
      .mockResolvedValueOnce(categoryFor("quality-ratings", "positive", "品質評分"))
      .mockReturnValueOnce(oldReload.promise)
      .mockResolvedValueOnce(categoryFor("bad-anatomy", "negative", "不良結構"));
    vi.mocked(putPromptCategory).mockResolvedValue(writeResponse);
    renderNavigable("/prompt-library/categories/positive/quality-ratings");
    fireEvent.click(await screen.findByRole("button", { name: "儲存分類" }));
    await waitFor(() => expect(getPromptCategory).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "前往不良結構" }));
    expect(await screen.findByRole("heading", { name: "不良結構" })).toBeVisible();
    expect(screen.getByRole("button", { name: "儲存分類" })).toBeEnabled();
    await act(async () => oldReload.reject(new Error("A reload 失敗")));
    expect(screen.queryByText("A reload 失敗")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "不良結構" })).toBeVisible();
    expect(screen.getByRole("button", { name: "儲存分類" })).toBeEnabled();
  });

  it("does not let an old operation finally clear route B's newer busy state", async () => {
    const oldMutation = deferred<typeof writeResponse>();
    const currentMutation = deferred<typeof writeResponse>();
    vi.mocked(getPromptCategory)
      .mockResolvedValueOnce(categoryFor("quality-ratings", "positive", "品質評分"))
      .mockResolvedValueOnce(categoryFor("bad-anatomy", "negative", "不良結構"))
      .mockResolvedValueOnce(categoryFor("bad-anatomy", "negative", "不良結構"));
    vi.mocked(putPromptCategory)
      .mockReturnValueOnce(oldMutation.promise)
      .mockReturnValueOnce(currentMutation.promise);
    renderNavigable("/prompt-library/categories/positive/quality-ratings");
    fireEvent.click(await screen.findByRole("button", { name: "儲存分類" }));
    fireEvent.click(screen.getByRole("button", { name: "前往不良結構" }));
    expect(await screen.findByRole("heading", { name: "不良結構" })).toBeVisible();
    expect(screen.getByRole("button", { name: "儲存分類" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "儲存分類" }));
    expect(screen.getByRole("button", { name: "處理中…" })).toBeDisabled();
    await act(async () => oldMutation.reject(new Error("舊操作失敗")));
    expect(screen.getByRole("button", { name: "處理中…" })).toBeDisabled();
    await act(async () => currentMutation.resolve(writeResponse));
    await waitFor(() => expect(screen.getByRole("button", { name: "儲存分類" })).toBeEnabled());
  });

  it("clears affected-combination notices when navigating to another category", async () => {
    vi.mocked(getPromptCategory)
      .mockResolvedValueOnce(categoryFor("quality-ratings", "positive", "品質評分"))
      .mockResolvedValueOnce(versionAt(8))
      .mockResolvedValueOnce(categoryFor("bad-anatomy", "negative", "不良結構"));
    vi.mocked(putPromptEntry).mockResolvedValue({ ...writeResponse, affected_combinations: ["combo-a"] });
    renderNavigable("/prompt-library/categories/positive/quality-ratings");
    fireEvent.click(await screen.findByRole("button", { name: "編輯 masterpiece" }));
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(await screen.findByText("已同步更新 1 個組合：combo-a")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "前往不良結構" }));
    expect(await screen.findByRole("heading", { name: "不良結構" })).toBeVisible();
    expect(screen.queryByText("已同步更新 1 個組合：combo-a")).not.toBeInTheDocument();
  });

  it("ignores an older request that resolves after the current route", async () => {
    const oldRequest = deferred<ReturnType<typeof categoryFor>>();
    const currentRequest = deferred<ReturnType<typeof categoryFor>>();
    vi.mocked(getPromptCategory).mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(currentRequest.promise);
    renderNavigable("/prompt-library/categories/positive/quality-ratings");
    fireEvent.click(screen.getByRole("button", { name: "前往不良結構" }));
    await waitFor(() => expect(getPromptCategory).toHaveBeenLastCalledWith("negative", "bad-anatomy"));
    currentRequest.resolve(categoryFor("bad-anatomy", "negative", "不良結構"));
    expect(await screen.findByRole("heading", { name: "不良結構" })).toBeVisible();
    await act(async () => { oldRequest.resolve(categoryFor("quality-ratings", "positive", "品質評分")); await oldRequest.promise; });
    expect(screen.queryByRole("heading", { name: "品質評分" })).not.toBeInTheDocument();
  });
});
