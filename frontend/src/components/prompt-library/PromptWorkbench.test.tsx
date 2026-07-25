import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PromptWorkbench from "./PromptWorkbench";

const catalog = {
  categories: [
    { id: "quality", polarity: "positive", name_zh: "品質", revision: 1, etag: "p1", archived: false },
    { id: "artifacts", polarity: "negative", name_zh: "瑕疵", revision: 1, etag: "n1", archived: false },
  ],
  combinations: [
    { id: "my-quality", revision: 1, etag: "combo-1" },
  ],
};
const forms = { items: [{ id: "basic-txt2img", display_name: "Basic", fields: [] }] };
const positiveCategory = {
  category: {
    ...catalog.categories[0],
    entries: [
      { id: "masterpiece", name_zh: "高品質", description_zh: "", prompt: "masterpiece", revision: 1, archived: false },
      { id: "prompt-only", name_zh: " ", description_zh: "", prompt: "  sharp focus  ", revision: 1, archived: false },
      { id: "id-only", name_zh: "", description_zh: "", prompt: "", revision: 1, archived: false },
    ],
  },
  etag: "p1",
};
const negativeCategory = {
  category: {
    ...catalog.categories[1],
    entries: [{ id: "blurry", name_zh: "模糊", description_zh: "", prompt: "blurry", revision: 1, archived: false }],
  },
  etag: "n1",
};

function response(data: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => data } as Response;
}

function installFetch(
  { composeValidationError = false }: { composeValidationError?: boolean } = {},
) {
  let savedRevision = 1;
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/prompt-library/catalog") return response(catalog);
    if (url === "/api/workflow-catalog/generation-forms") return response(forms);
    if (url.endsWith("/positive/quality")) return response(positiveCategory);
    if (url.endsWith("/negative/artifacts")) return response(negativeCategory);
    if (url === "/api/generate/") return response({ job_id: "job-1" });
    if (url === "/api/prompt-library/compose" && init?.method === "POST") {
      if (composeValidationError) {
        return response({ detail: [{ loc: ["body", "save_as", "id"], msg: "String should match pattern", type: "string_pattern_mismatch" }] }, 422);
      }
      savedRevision += 1;
      return response({ saved_combination: { combination: { id: "my-quality", revision: savedRevision }, etag: `combo-${savedRevision}` } });
    }
    return response({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("PromptWorkbench", () => {
  it("adds to the active polarity while keeping both editable overviews visible", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);

    expect(screen.getByRole("heading", { name: "Positive Prompt" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Negative Prompt" })).toBeVisible();
    fireEvent.click(await screen.findByRole("button", { name: "品質" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 高品質" }));
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("masterpiece");
    expect(screen.getByLabelText("Negative Prompt 最終文字")).toHaveValue("");

    fireEvent.change(screen.getByLabelText("高品質 權重"), { target: { value: "1.2" } });
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("(masterpiece:1.2)");
    fireEvent.change(screen.getByLabelText("高品質 內容"), { target: { value: "masterwork" } });
    expect(screen.getByLabelText("高品質 內容")).toHaveValue("masterwork");
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("(masterwork:1.2)");
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).includes("/entries/") && init?.method === "PUT")).toBe(false);

    fireEvent.change(screen.getByLabelText("組合 ID"), { target: { value: "my-quality" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存組合" }));
    await waitFor(() => expect(screen.getByText("組合已儲存")).toBeVisible());
    const saveCall = fetchMock.mock.calls.find(([url]) => url === "/api/prompt-library/compose") as [string, RequestInit];
    const firstSaveBody = JSON.parse(String(saveCall[1].body));
    expect(firstSaveBody.positive).toEqual([
      { kind: "literal", snapshot: "masterwork", weight: 1.2, order: 10 },
    ]);
    expect(firstSaveBody.save_as).toMatchObject({ expected_revision: 1, expected_etag: "combo-1" });

    fireEvent.click(screen.getByRole("button", { name: "儲存組合" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === "/api/prompt-library/compose")).toHaveLength(2));
    const secondSaveCall = fetchMock.mock.calls.filter(([url]) => url === "/api/prompt-library/compose")[1] as [string, RequestInit];
    expect(JSON.parse(String(secondSaveCall[1].body)).save_as).toMatchObject({ expected_revision: 2, expected_etag: "combo-2" });
  });

  it("uses Prompt text and then entry ID when a Chinese entry name is unavailable", async () => {
    installFetch();
    render(<PromptWorkbench />);

    fireEvent.click(await screen.findByRole("button", { name: "品質" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 sharp focus" }));
    expect(screen.getByLabelText("sharp focus 內容")).toHaveValue("  sharp focus  ");

    fireEvent.click(screen.getByRole("button", { name: "加入 id-only" }));
    expect(screen.getByLabelText("id-only 內容")).toHaveValue("id-only");
    expect(screen.queryByText(/片段\s*\d/)).not.toBeInTheDocument();
  });

  it("accepts safe Unicode combination IDs", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);
    await screen.findByRole("button", { name: "品質" });

    fireEvent.change(screen.getByLabelText("組合 ID"), { target: { value: "niji基礎瑟瑟" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存組合" }));

    await waitFor(() => expect(screen.getByText("組合已儲存")).toBeVisible());
    const saveCall = fetchMock.mock.calls.find(([url]) => url === "/api/prompt-library/compose") as [string, RequestInit];
    expect(JSON.parse(String(saveCall[1].body)).save_as.id).toBe("niji基礎瑟瑟");
  });

  it("rejects path-unsafe combination IDs before sending compose", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);
    await screen.findByRole("button", { name: "品質" });

    fireEvent.change(screen.getByLabelText("組合 ID"), { target: { value: "../逃逸" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存組合" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Unicode 字母、數字與連字號");
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/prompt-library/compose")).toHaveLength(0);
  });

  it("shows FastAPI validation details instead of a bare HTTP 422", async () => {
    installFetch({ composeValidationError: true });
    render(<PromptWorkbench />);
    await screen.findByRole("button", { name: "品質" });

    fireEvent.change(screen.getByLabelText("組合 ID"), { target: { value: "valid-id" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存組合" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("save_as.id：String should match pattern");
  });

  it("keeps the overview visible when switching polarity and generates from current text", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);

    fireEvent.click(await screen.findByRole("button", { name: "品質" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 高品質" }));
    fireEvent.click(screen.getByRole("button", { name: "負向" }));
    expect(screen.queryByRole("button", { name: "品質" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Positive Prompt" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "瑕疵" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 模糊" }));

    const positivePanel = screen.getByRole("heading", { name: "Positive Prompt" }).closest("section")!;
    fireEvent.click(within(positivePanel).getByRole("button", { name: "自由文字模式" }));
    fireEvent.change(within(positivePanel).getByLabelText("Positive Prompt 自由文字草稿"), { target: { value: "edited positive" } });
    fireEvent.click(within(positivePanel).getByRole("button", { name: "套用" }));

    const negativePanel = screen.getByRole("heading", { name: "Negative Prompt" }).closest("section")!;
    fireEvent.click(within(negativePanel).getByRole("button", { name: "自由文字模式" }));
    fireEvent.change(within(negativePanel).getByLabelText("Negative Prompt 自由文字草稿"), { target: { value: "edited negative" } });
    fireEvent.click(within(negativePanel).getByRole("button", { name: "套用" }));
    fireEvent.change(screen.getByLabelText("Workflow"), { target: { value: "basic-txt2img" } });
    fireEvent.click(screen.getByRole("button", { name: "開始生圖" }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("job-1"));
    const call = fetchMock.mock.calls.find(([url]) => url === "/api/generate/") as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toMatchObject({
      template: "basic-txt2img",
      prompt: "edited positive",
      negative_prompt: "edited negative",
      use_workflow_defaults: true,
      seed_mode: "random",
    });
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/prompt-library/compose")).toHaveLength(0);
  });

  it("keeps every source interaction on the read-only network boundary", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);

    expect(screen.queryByRole("button", { name: "新增詞條" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /編輯/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /封存/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /恢復/ })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("搜尋提示詞"), { target: { value: "高品質" } });
    fireEvent.click(await screen.findByRole("button", { name: "品質" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 高品質" }));
    fireEvent.change(screen.getByLabelText("自由文字"), { target: { value: " local detail " } });
    fireEvent.click(screen.getByRole("button", { name: "加入目前正向" }));
    fireEvent.click(screen.getByRole("button", { name: "負向" }));
    fireEvent.change(screen.getByLabelText("搜尋提示詞"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "瑕疵" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 模糊" }));

    const sourceWrites = fetchMock.mock.calls.filter(([url, init]) =>
      init?.method === "PUT" || String(url).includes("/archive") || String(url).includes("/restore"),
    );
    expect(sourceWrites).toHaveLength(0);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/positive/quality"))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/negative/artifacts"))).toBe(true);
  });

  it("adds, reorders, removes, and composes local fragments", async () => {
    installFetch();
    render(<PromptWorkbench />);

    fireEvent.click(await screen.findByRole("button", { name: "品質" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 高品質" }));
    fireEvent.change(screen.getByLabelText("自由文字"), { target: { value: "soft light" } });
    fireEvent.click(screen.getByRole("button", { name: "加入目前正向" }));
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("masterpiece, soft light");

    fireEvent.click(screen.getAllByRole("button", { name: "下移" })[0]);
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("soft light, masterpiece");

    fireEvent.click(screen.getAllByRole("button", { name: "刪除" })[0]);
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("masterpiece");
  });
});
