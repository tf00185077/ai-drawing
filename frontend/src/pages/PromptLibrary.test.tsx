import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import PromptLibrary from "./PromptLibrary";

vi.mock("../components/prompt-library/PromptWorkbench", () => ({
  default: () => <section>Prompt Workbench</section>,
}));

const emptyCatalog = {
  manifest: { schema_version: 1, library_id: "default", name: "Prompt Library", description_zh: "提示詞庫" },
  categories: [],
  combinations: [],
  diagnostics: [],
};

const createdCategory = {
  id: "street-scenes",
  polarity: "positive" as const,
  name_zh: "街景",
  description_zh: "都市、商店街與道路場景提示詞",
  aliases: ["urban scene", "street scene"],
  keywords: ["街道", "城市"],
  order: 10,
  revision: 1,
  archived: false,
  entry_count: 0,
  etag: "etag-1",
};

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response;
}

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText(/分類 ID/), { target: { value: "street-scenes" } });
  fireEvent.change(screen.getByLabelText(/中文名稱/), { target: { value: "街景" } });
  fireEvent.change(screen.getByLabelText(/分類說明/), {
    target: { value: "都市、商店街與道路場景提示詞" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("PromptLibrary", () => {
  it("creates a category and refreshes the catalog", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(emptyCatalog))
      .mockResolvedValueOnce(
        response({ category: { category: createdCategory, etag: createdCategory.etag } }),
      )
      .mockResolvedValueOnce(response({ ...emptyCatalog, categories: [createdCategory] }));
    vi.stubGlobal("fetch", fetchMock);

    render(<PromptLibrary />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fillRequiredFields();
    fireEvent.change(screen.getByLabelText(/別名/), {
      target: { value: "urban scene, street scene" },
    });
    fireEvent.change(screen.getByLabelText(/搜尋關鍵字/), {
      target: { value: "街道, 城市" },
    });
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));

    expect((await screen.findByRole("status")).textContent).toContain(
      "已建立正向分類「街景」（street-scenes）",
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("/api/prompt-library/categories/positive/street-scenes");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual({
      name_zh: "街景",
      description_zh: "都市、商店街與道路場景提示詞",
      aliases: ["urban scene", "street scene"],
      keywords: ["街道", "城市"],
      order: 10,
      expected_revision: 0,
    });
    expect(screen.getByText("街景")).toBeTruthy();
  });

  it("rejects an invalid category id before calling the write API", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(emptyCatalog));
    vi.stubGlobal("fetch", fetchMock);

    render(<PromptLibrary />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fillRequiredFields();
    fireEvent.change(screen.getByLabelText(/分類 ID/), { target: { value: "Street Scene" } });
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "分類 ID 只能使用小寫英文字母、數字與單一連字號",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows the actionable backend conflict message", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(emptyCatalog))
      .mockResolvedValueOnce(
        response(
          {
            detail: {
              code: "revision_conflict",
              message: "分類已存在",
              hint: "重新載入後使用最新revision",
            },
          },
          409,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<PromptLibrary />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: "建立分類" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "分類已存在（重新載入後使用最新revision）",
    );
  });
});
