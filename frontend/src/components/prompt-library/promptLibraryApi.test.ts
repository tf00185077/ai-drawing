import { afterEach, describe, expect, it, vi } from "vitest";
import {
  archivePromptResource,
  composeAndSaveCombination,
  getPromptCatalog,
  getPromptCategory,
  getPromptCombination,
  moveEntry,
  promptLibraryErrorMessage,
  putPromptCategory,
  putPromptEntry,
  restorePromptResource,
} from "./promptLibraryApi";

const jsonResponse = (data: unknown = {}, ok = true, status = 200): Response =>
  ({ ok, status, json: vi.fn().mockResolvedValue(data) }) as unknown as Response;

const fetchMock = (response: Response = jsonResponse()): ReturnType<typeof vi.fn> => {
  const mock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", mock);
  return mock;
};

const bodyOf = (mock: ReturnType<typeof vi.fn>): unknown =>
  JSON.parse((mock.mock.calls[0][1] as RequestInit).body as string);

afterEach(() => vi.unstubAllGlobals());

describe("Prompt Library GET requests", () => {
  it("uses the exact catalog URL", async () => {
    const fetch = fetchMock(jsonResponse({ categories: [] }));
    await getPromptCatalog();
    expect(fetch).toHaveBeenCalledWith("/api/prompt-library/catalog", undefined);
  });

  it("encodes polarity and category path segments", async () => {
    const fetch = fetchMock();
    await getPromptCategory("positive/value" as "positive", "人物 分類");
    expect(fetch).toHaveBeenCalledWith(
      "/api/prompt-library/categories/positive%2Fvalue/%E4%BA%BA%E7%89%A9%20%E5%88%86%E9%A1%9E",
      undefined,
    );
  });

  it("encodes the combination path segment", async () => {
    const fetch = fetchMock();
    await getPromptCombination("角色/草稿 一");
    expect(fetch).toHaveBeenCalledWith(
      "/api/prompt-library/combinations/%E8%A7%92%E8%89%B2%2F%E8%8D%89%E7%A8%BF%20%E4%B8%80",
      undefined,
    );
  });
});

describe("Prompt Library writes", () => {
  it("PUTs a category with an explicit creation token", async () => {
    const fetch = fetchMock();
    await putPromptCategory("positive", "人物/主角", {
      name_zh: "人物",
      description_zh: "人物描述",
      aliases: ["角色"],
      keywords: ["person"],
      order: 20,
      expected_revision: 0,
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/prompt-library/categories/positive/%E4%BA%BA%E7%89%A9%2F%E4%B8%BB%E8%A7%92",
      expect.objectContaining({ method: "PUT", headers: { "Content-Type": "application/json" } }),
    );
    expect(bodyOf(fetch)).toEqual({
      name_zh: "人物",
      description_zh: "人物描述",
      aliases: ["角色"],
      keywords: ["person"],
      order: 20,
      expected_revision: 0,
    });
  });

  it("putPromptCategory sends parent_id when provided (including null to clear)", async () => {
    const calls: RequestInit[] = [];
    const mockFetch = vi.fn(async (_url: string, init?: RequestInit) => {
      calls.push(init as RequestInit);
      return jsonResponse();
    });
    vi.stubGlobal("fetch", mockFetch);

    await putPromptCategory("positive", "clothing-top", {
      name_zh: "上衣", description_zh: "d", aliases: [], keywords: [], order: 10,
      expected_revision: 0, parent_id: "clothing",
    });
    expect(JSON.parse(calls[0].body as string).parent_id).toBe("clothing");

    await putPromptCategory("positive", "clothing", {
      name_zh: "服裝", description_zh: "d", aliases: [], keywords: [], order: 70,
      expected_revision: 1, parent_id: null,
    });
    expect(JSON.parse(calls[1].body as string).parent_id).toBeNull();
  });

  it("PUTs an entry with its parent category concurrency token", async () => {
    const fetch = fetchMock();
    await putPromptEntry("negative", "bad anatomy", "extra/limbs", {
      name_zh: "多餘肢體",
      description_zh: "排除多餘肢體",
      prompt: "extra limbs",
      aliases: [],
      keywords: ["anatomy"],
      order: 10,
      expected_revision: 7,
      expected_etag: "category-etag",
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/prompt-library/categories/negative/bad%20anatomy/entries/extra%2Flimbs",
      expect.objectContaining({ method: "PUT", headers: { "Content-Type": "application/json" } }),
    );
    expect(bodyOf(fetch)).toEqual({
      name_zh: "多餘肢體",
      description_zh: "排除多餘肢體",
      prompt: "extra limbs",
      aliases: [],
      keywords: ["anatomy"],
      order: 10,
      expected_revision: 7,
      expected_etag: "category-etag",
    });
  });

  it("POSTs the exact archive locator and omits absent optional fields", async () => {
    const fetch = fetchMock();
    await archivePromptResource({
      resource_type: "combination",
      resource_id: "電影感",
      expected_revision: 3,
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/prompt-library/archive",
      expect.objectContaining({ method: "POST", headers: { "Content-Type": "application/json" } }),
    );
    expect(bodyOf(fetch)).toEqual({
      resource_type: "combination",
      resource_id: "電影感",
      expected_revision: 3,
    });
  });

  it("POSTs the exact restore locator and omits absent optional etag/category", async () => {
    const fetch = fetchMock();
    await restorePromptResource({
      resource_type: "category",
      resource_id: "quality",
      polarity: "positive",
      expected_revision: 4,
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/prompt-library/restore",
      expect.objectContaining({ method: "POST", headers: { "Content-Type": "application/json" } }),
    );
    expect(bodyOf(fetch)).toEqual({
      resource_type: "category",
      resource_id: "quality",
      polarity: "positive",
      expected_revision: 4,
    });
  });

  it("POSTs exact compose fragments, optional combination id, and save intent", async () => {
    const fetch = fetchMock();
    const positive = [{
      kind: "entry" as const,
      ref: { polarity: "positive" as const, category_id: "quality", entry_id: "masterpiece" },
      snapshot: "masterpiece",
      source_revision: 2,
      weight: 1.2,
      order: 10,
    }];
    const negative = [{ kind: "literal" as const, snapshot: "blurry", weight: 1, order: 10 }];
    const save_as = {
      id: "電影感",
      name_zh: "電影感",
      description_zh: "電影風格",
      aliases: ["cinematic"],
      keywords: ["film"],
      order: 10,
      expected_revision: 0,
      legacy_template: false,
      positive,
      negative,
    };

    await composeAndSaveCombination({ combination_id: "舊/組合", positive, negative, save_as });

    expect(fetch).toHaveBeenCalledWith(
      "/api/prompt-library/compose",
      expect.objectContaining({ method: "POST", headers: { "Content-Type": "application/json" } }),
    );
    expect(bodyOf(fetch)).toEqual({ combination_id: "舊/組合", positive, negative, save_as });
  });
});

describe("promptLibraryErrorMessage", () => {
  it("formats a structured Backend message and hint", () => {
    expect(promptLibraryErrorMessage({
      detail: { code: "revision_conflict", message: "版本衝突", hint: "重新載入", details: {} },
    }, 409)).toBe("版本衝突（重新載入）");
  });

  it("formats FastAPI validation paths without a leading body segment", () => {
    expect(promptLibraryErrorMessage({
      detail: [{ loc: ["body", "resource_id"], msg: "Field required", type: "missing" }],
    }, 422)).toBe("resource_id：Field required");
  });

  it("returns an actionable status fallback for non-JSON errors", async () => {
    const response = {
      ok: false,
      status: 503,
      json: vi.fn().mockRejectedValue(new SyntaxError("not JSON")),
    } as unknown as Response;
    fetchMock(response);

    await expect(getPromptCatalog()).rejects.toThrow("Prompt Library 請求失敗（HTTP 503），請稍後重試");
    expect(promptLibraryErrorMessage({}, 500)).toBe("Prompt Library 請求失敗（HTTP 500），請稍後重試");
  });
});

describe("moveEntry", () => {
  it("POSTs to the move route with to_category_id + entry fields", async () => {
    const fetch = fetchMock(jsonResponse({}));
    await moveEntry("positive", "src", "dress", {
      to_category_id: "dst",
      name_zh: "洋裝",
      description_zh: "d",
      prompt: "dress",
      aliases: [],
      keywords: [],
      order: 10,
      expected_revision: 1,
    });
    expect(fetch.mock.calls[0][0]).toBe("/api/prompt-library/categories/positive/src/entries/dress/move");
    expect((fetch.mock.calls[0][1] as RequestInit).method).toBe("POST");
    const body = bodyOf(fetch) as { to_category_id: string; prompt: string };
    expect(body.to_category_id).toBe("dst");
    expect(body.prompt).toBe("dress");
  });
});
