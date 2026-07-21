import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    entries: [{ id: "masterpiece", name_zh: "高品質", description_zh: "", prompt: "masterpiece", revision: 1, archived: false }],
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

function installFetch() {
  let savedRevision = 1;
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/prompt-library/catalog") return response(catalog);
    if (url === "/api/workflow-catalog/generation-forms") return response(forms);
    if (url.endsWith("/positive/quality")) return response(positiveCategory);
    if (url.endsWith("/negative/artifacts")) return response(negativeCategory);
    if (url === "/api/generate/") return response({ job_id: "job-1" });
    if (url === "/api/prompt-library/compose" && init?.method === "POST") {
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
    fireEvent.change(screen.getByLabelText("Positive Prompt 最終文字"), { target: { value: "(masterwork:1.2)" } });
    expect(screen.getByLabelText("高品質 內容")).toHaveValue("masterwork");
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

    fireEvent.change(screen.getByLabelText("Positive Prompt 最終文字"), { target: { value: "edited positive" } });
    fireEvent.change(screen.getByLabelText("Negative Prompt 最終文字"), { target: { value: "edited negative" } });
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
});
