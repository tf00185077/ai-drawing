import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PromptWorkbench from "./PromptWorkbench";

const summary = (id: string, revision = 1, archived = false) => ({
  id, name_zh: id, description_zh: "", aliases: [], keywords: [], order: 10,
  revision, archived, legacy_template: false, positive_prompt_snapshot: "", negative_prompt_snapshot: "", etag: `summary-${revision}`,
});
const catalog = {
  manifest: { schema_version: 1, library_id: "test", name: "test", description_zh: "" },
  categories: [
    { id: "quality", polarity: "positive", name_zh: "品質", description_zh: "", aliases: [], keywords: [], order: 10, revision: 1, archived: false, entry_count: 3, etag: "p1" },
    { id: "style", polarity: "positive", name_zh: "風格", description_zh: "", aliases: [], keywords: [], order: 20, revision: 1, archived: false, entry_count: 1, etag: "p2" },
    { id: "artifacts", polarity: "negative", name_zh: "瑕疵", description_zh: "", aliases: [], keywords: [], order: 10, revision: 1, archived: false, entry_count: 1, etag: "n1" },
  ],
  combinations: [summary("my-quality", 1), summary("second", 1), summary("old", 2, true)],
  diagnostics: [],
};
const forms = { items: [{ id: "basic-txt2img", display_name: "Basic", fields: [] }] };
const categoryResponse = (polarity: "positive" | "negative", id: string) => ({
  category: {
    schema_version: 1, id, polarity, name_zh: id, description_zh: "", aliases: [], keywords: [], order: 10, revision: 4, archived: false,
    entries: polarity === "positive" ? [
      { id: "zh", name_zh: "  中文名稱  ", description_zh: "", prompt: "zh current", aliases: [], keywords: [], order: 10, revision: 4, archived: false },
      { id: "prompt-only", name_zh: " ", description_zh: "", prompt: "  current prompt  ", aliases: [], keywords: [], order: 20, revision: 4, archived: false },
      { id: "id-only", name_zh: "", description_zh: "", prompt: " ", aliases: [], keywords: [], order: 30, revision: 4, archived: false },
    ] : [
      { id: "blurry", name_zh: "模糊", description_zh: "", prompt: "blurry current", aliases: [], keywords: [], order: 10, revision: 4, archived: false },
    ],
  }, etag: `${polarity}-${id}-4`,
});
const fragment = (kind: "entry" | "literal", snapshot: string, order: number, weight = 1, ref: null | { polarity: "positive" | "negative"; category_id: string; entry_id: string } = null) => ({ kind, ref, snapshot, source_revision: ref ? 2 : null, weight, order });
const combinationDetail = (id = "my-quality", revision = 3) => ({
  combination: {
    schema_version: 1, id, name_zh: id, description_zh: "", aliases: [], keywords: [], order: 10, revision, archived: false, legacy_template: false,
    positive: [
      fragment("entry", "saved zh", 20, 1.2, { polarity: "positive", category_id: "quality", entry_id: "zh" }),
      fragment("entry", "saved prompt", 10, 1, { polarity: "positive", category_id: "quality", entry_id: "prompt-only" }),
      fragment("entry", "saved id", 30, 1, { polarity: "positive", category_id: "quality", entry_id: "id-only" }),
    ],
    negative: [fragment("entry", "saved blurry", 10, 0.8, { polarity: "negative", category_id: "artifacts", entry_id: "blurry" })],
    positive_prompt_snapshot: "stale display only", negative_prompt_snapshot: "stale display only",
  },
  etag: `detail-${revision}`, repaired: true,
  warnings: [{ code: "snapshot", message: "Backend 警告", hint: "", ref: null, details: {} }],
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

function response(data: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => data } as Response;
}

type FetchHandler = (url: string, init?: RequestInit) => Promise<Response> | Response | undefined;
function installFetch(handler?: FetchHandler) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const custom = await handler?.(url, init);
    if (custom) return custom;
    if (url === "/api/prompt-library/migration-status") return response({
      state: "finalized",
      marker_present: false,
      comma_atomic_ready: true,
      atomic_enforcement_active: true,
      run_id: null,
      data_validated: true,
    });
    if (url === "/api/prompt-library/catalog") return response(catalog);
    if (url === "/api/workflow-catalog/generation-forms") return response(forms);
    if (url === "/api/prompt-library/combinations/my-quality") return response(combinationDetail());
    if (url === "/api/prompt-library/combinations/second") return response(combinationDetail("second", 5));
    if (url.endsWith("/categories/positive/quality")) return response(categoryResponse("positive", "quality"));
    if (url.endsWith("/categories/positive/style")) return response(categoryResponse("positive", "style"));
    if (url.endsWith("/categories/negative/artifacts")) return response(categoryResponse("negative", "artifacts"));
    if (url === "/api/generate/") return response({ job_id: "job-1" });
    return response({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function ready() {
  await screen.findByRole("option", { name: "my-quality（my-quality）" });
}
async function loadSaved(id = "my-quality") {
  fireEvent.change(screen.getByLabelText("已儲存組合"), { target: { value: id } });
  fireEvent.click(screen.getByRole("button", { name: "載入組合" }));
  await screen.findByLabelText("目前組合版本");
}
function renderedPrompt(fragments: ReturnType<typeof fragment>[]) {
  return [...fragments]
    .sort((left, right) => left.order - right.order)
    .map((item) => item.weight === 1 ? item.snapshot : `(${item.snapshot}:${item.weight})`)
    .join(",");
}
function composeResponse(
  id: string,
  revision: number,
  positive: ReturnType<typeof fragment>[] = [],
  negative: ReturnType<typeof fragment>[] = [],
) {
  const positivePrompt = renderedPrompt(positive);
  const negativePrompt = renderedPrompt(negative);
  return {
    positive_prompt: positivePrompt, negative_prompt: negativePrompt, positive, negative, warnings: [], snapshot_repaired: false,
    saved_combination: {
      combination: {
        schema_version: 1, id, name_zh: id, description_zh: "", aliases: [], keywords: [], order: 10, revision, archived: false, legacy_template: false,
        positive, negative, positive_prompt_snapshot: positivePrompt, negative_prompt_snapshot: negativePrompt,
      }, etag: `saved-${revision}`, repaired: false, warnings: [],
    },
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("PromptWorkbench saved combinations", () => {
  it("reads only migration status and stays non-editing until finalized enforcement", async () => {
    const fetchMock = installFetch((url) => {
      if (url === "/api/prompt-library/migration-status") {
        return response({
          state: "validating",
          marker_present: true,
          comma_atomic_ready: false,
          atomic_enforcement_active: true,
          run_id: "migration-run",
          data_validated: true,
        });
      }
    });
    render(<PromptWorkbench />);

    expect(await screen.findByRole("status")).toHaveTextContent("遷移尚未完成");
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "/api/prompt-library/migration-status",
    ]);
    expect(screen.queryByLabelText("Positive Prompt 最終文字")).not.toBeInTheDocument();
  });

  it("loads detail tokens, both polarities, order/weights/snapshots, names, repairs and warnings", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);
    await ready();
    await loadSaved();

    expect(screen.getByLabelText("目前組合版本")).toHaveTextContent("revision 3");
    expect(screen.getByLabelText("目前組合版本")).toHaveTextContent("已修復");
    expect(screen.getByRole("alert")).toHaveTextContent("Backend 警告");
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("saved prompt,(saved zh:1.2),saved id");
    expect(screen.getByLabelText("Negative Prompt 最終文字")).toHaveValue("(saved blurry:0.8)");
    expect(screen.getByLabelText("current prompt 內容")).toHaveValue("saved prompt");
    expect(screen.getByLabelText("中文名稱 內容")).toHaveValue("saved zh");
    expect(screen.getByLabelText("id-only 內容")).toHaveValue("saved id");
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/categories/positive/quality"))).toHaveLength(1);
  });

  it("round-trips non-1 weights and refs, then demotes an edited rendered atom", async () => {
    let current: any = combinationDetail();
    const bodies: any[] = [];
    installFetch((url, init) => {
      if (url === "/api/prompt-library/combinations/my-quality") {
        return response(current);
      }
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        bodies.push(body);
        const saved = composeResponse(
          "my-quality",
          body.save_as.expected_revision + 1,
          body.positive,
          body.negative,
        );
        current = saved.saved_combination;
        return response(saved);
      }
    });
    render(<PromptWorkbench />);
    await ready();
    await loadSaved();

    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    expect(await screen.findByRole("status")).toHaveTextContent("組合已儲存");
    expect(bodies[0].positive[1]).toMatchObject({
      kind: "entry",
      snapshot: "saved zh",
      weight: 1.2,
      ref: { polarity: "positive", category_id: "quality", entry_id: "zh" },
    });
    expect(bodies[0].negative[0]).toMatchObject({
      kind: "entry",
      snapshot: "saved blurry",
      weight: 0.8,
    });

    await loadSaved();
    expect(screen.getByLabelText("Positive Prompt 最終文字"))
      .toHaveValue("saved prompt,(saved zh:1.2),saved id");
    fireEvent.change(screen.getByLabelText("Positive Prompt 最終文字"), {
      target: { value: "saved prompt,(saved zh:1.3),saved id" },
    });
    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1].positive[1]).toMatchObject({
      kind: "literal",
      snapshot: "(saved zh:1.3)",
      weight: 1,
    });
    expect(bodies[1].positive[1]).not.toHaveProperty("ref");
  });

  it("requires explicit Backend acknowledgment before persisting blocked provenance", async () => {
    const blocked: any = combinationDetail();
    blocked.combination.positive = [fragment("literal", "legacy fallback", 10)];
    blocked.combination.negative = [];
    blocked.blocking_diagnostics = [{
      id: "diagnostic-1",
      code: "legacy_reference_unresolved",
      original_ref: {
        polarity: "positive",
        category_id: "legacy",
        entry_id: "removed",
      },
      combination_id: "my-quality",
      revision: 3,
      etag: "detail-3",
      polarity: "positive",
      fallback_start_position: 1,
      fallback_count: 1,
      fallback_atom_hashes: ["atom-hash"],
      blocking: true,
    }];
    blocked.document_context_token = "document-token";
    let acknowledgeBody: any;
    let successfulSaveBody: any;
    installFetch((url, init) => {
      if (url === "/api/prompt-library/combinations/my-quality") {
        return response(blocked);
      }
      if (
        url === "/api/prompt-library/combinations/my-quality/acknowledge-literal-conversion"
        && init?.method === "POST"
      ) {
        acknowledgeBody = JSON.parse(String(init.body));
        return response({
          literal_conversion_token: "literal-token",
          diagnostic_ids: ["diagnostic-1"],
        });
      }
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        if (body.save_as.literal_conversion_token !== "literal-token") {
          return response({
            detail: {
              message: "舊來源尚未明示解決",
              code: "unresolved_legacy_reference",
            },
          }, 409);
        }
        successfulSaveBody = body;
        return response(composeResponse(
          body.save_as.id,
          1,
          body.positive,
          body.negative,
        ));
      }
    });
    render(<PromptWorkbench />);
    await ready();
    await loadSaved();

    expect(screen.getByText("舊來源尚未解決")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    await waitFor(() => expect(
      screen.getAllByRole("alert").some((node) =>
        node.textContent?.includes("舊來源尚未明示解決"),
      ),
    ).toBe(true));

    fireEvent.click(screen.getByRole("button", { name: "明示轉為自訂文字" }));
    expect(await screen.findByRole("status")).toHaveTextContent("已明示確認");
    fireEvent.change(screen.getByLabelText("新組合 ID"), { target: { value: "resolved-copy" } });
    fireEvent.click(screen.getByRole("button", { name: "另存新組合" }));
    await waitFor(() => expect(successfulSaveBody).toBeDefined());
    expect(acknowledgeBody).toEqual({ document_context_token: "document-token" });
    expect(successfulSaveBody.save_as).toMatchObject({
      id: "resolved-copy",
      source_combination_id: "my-quality",
      document_context_token: "document-token",
      literal_conversion_token: "literal-token",
    });
  });

  it("replaces only the diagnostic fallback with newly selected source entries", async () => {
    const blocked: any = combinationDetail();
    blocked.combination.positive = [fragment("literal", "legacy fallback", 10)];
    blocked.combination.negative = [];
    blocked.blocking_diagnostics = [{
      id: "diagnostic-1",
      code: "legacy_reference_unresolved",
      original_ref: {
        polarity: "positive",
        category_id: "legacy",
        entry_id: "removed",
      },
      combination_id: "my-quality",
      revision: 3,
      etag: "detail-3",
      polarity: "positive",
      fallback_start_position: 1,
      fallback_count: 1,
      fallback_atom_hashes: ["atom-hash"],
      blocking: true,
    }];
    blocked.document_context_token = "document-token";
    let composeBody: any;
    installFetch((url, init) => {
      if (url === "/api/prompt-library/combinations/my-quality") {
        return response(blocked);
      }
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        composeBody = JSON.parse(String(init.body));
        return response(composeResponse(
          composeBody.save_as.id,
          1,
          composeBody.positive,
          composeBody.negative,
        ));
      }
    });
    render(<PromptWorkbench />);
    await ready();
    await loadSaved();

    fireEvent.click(screen.getByRole("button", { name: "品質" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 中文名稱" }));
    fireEvent.click(screen.getByRole("button", {
      name: "使用目前加入的詞庫來源解決此診斷",
    }));

    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue(
      "zh current",
    );
    expect(screen.queryByDisplayValue("legacy fallback")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    await waitFor(() => expect(composeBody).toBeDefined());
    expect(composeBody.positive).toEqual([
      expect.objectContaining({
        kind: "entry",
        snapshot: "zh current",
        ref: {
          polarity: "positive",
          category_id: "quality",
          entry_id: "zh",
        },
      }),
    ]);
    expect(composeBody.save_as.provenance_resolutions).toEqual([
      expect.objectContaining({
        diagnostic_id: "diagnostic-1",
        replacement_refs: [{
          polarity: "positive",
          category_id: "quality",
          entry_id: "zh",
        }],
      }),
    ]);
  });

  it("resolves and preserves a saved ref using its own polarity instead of its destination list", async () => {
    const crossPolarity = combinationDetail();
    crossPolarity.combination.positive = [
      fragment("entry", "saved cross-polarity snapshot", 10, 1, {
        polarity: "negative", category_id: "quality", entry_id: "zh",
      }),
    ];
    crossPolarity.combination.negative = [];
    let composeBody: any;
    const fetchMock = installFetch((url, init) => {
      if (url === "/api/prompt-library/combinations/my-quality") return response(crossPolarity);
      if (url === "/api/prompt-library/categories/negative/quality") {
        const data = categoryResponse("negative", "quality");
        data.category.entries = [{
          id: "zh", name_zh: "負向品質名稱", description_zh: "", prompt: "current negative quality",
          aliases: [], keywords: [], order: 10, revision: 4, archived: false,
        }];
        return response(data);
      }
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        composeBody = JSON.parse(String(init.body));
        return response(composeResponse("my-quality", 4, composeBody.positive));
      }
    });
    render(<PromptWorkbench />);
    await ready();
    await loadSaved();

    expect(fetchMock).toHaveBeenCalledWith("/api/prompt-library/categories/negative/quality", undefined);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/prompt-library/categories/positive/quality")).toHaveLength(1);
    expect(screen.getByLabelText("負向品質名稱 內容")).toHaveValue("saved cross-polarity snapshot");

    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    await waitFor(() => expect(composeBody).toBeDefined());
    expect(composeBody.positive[0]).toMatchObject({
      snapshot: "saved cross-polarity snapshot",
      ref: { polarity: "negative", category_id: "quality", entry_id: "zh" },
    });
  });

  it("uses encoded detail IDs", async () => {
    const encodedCatalog = { ...catalog, combinations: [summary("含 空白")] };
    const fetchMock = installFetch((url) => {
      if (url === "/api/prompt-library/catalog") return response(encodedCatalog);
      if (url === "/api/prompt-library/combinations/%E5%90%AB%20%E7%A9%BA%E7%99%BD") return response(combinationDetail("含 空白", 2));
    });
    render(<PromptWorkbench />);
    await screen.findByRole("option", { name: "含 空白（含 空白）" });
    await loadSaved("含 空白");
    expect(fetchMock).toHaveBeenCalledWith("/api/prompt-library/combinations/%E5%90%AB%20%E7%A9%BA%E7%99%BD", undefined);
  });

  it("loads with entry-ID labels and a nonblocking warning when category lookup fails", async () => {
    installFetch((url) => url.endsWith("/categories/positive/quality") ? response({ detail: { message: "查詢失敗" } }, 500) : undefined);
    render(<PromptWorkbench />);
    await ready();
    await loadSaved();

    expect(screen.getByLabelText("prompt-only 內容")).toHaveValue("saved prompt");
    expect(screen.getAllByRole("alert").some((node) => node.textContent?.includes("名稱查詢失敗"))).toBe(true);
    expect(screen.getByLabelText("Negative Prompt 最終文字")).toHaveValue("(saved blurry:0.8)");
  });

  it("guards dirty load and blank replacement, preserving on decline and replacing on approval", async () => {
    installFetch();
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    render(<PromptWorkbench />);
    await ready();

    fireEvent.change(screen.getByLabelText("自由文字"), { target: { value: "local" } });
    fireEvent.click(screen.getByRole("button", { name: "加入目前正向" }));
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("local");
    fireEvent.change(screen.getByLabelText("已儲存組合"), { target: { value: "my-quality" } });
    fireEvent.click(screen.getByRole("button", { name: "載入組合" }));
    fireEvent.click(screen.getByRole("button", { name: "建立空白組合" }));
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("local");
    expect(confirm).toHaveBeenCalledTimes(2);

    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "載入組合" }));
    await waitFor(() => expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("saved prompt,(saved zh:1.2),saved id"));
    fireEvent.change(screen.getByLabelText("中文名稱 內容"), { target: { value: "dirty again" } });
    fireEvent.click(screen.getByRole("button", { name: "建立空白組合" }));
    expect(screen.getByText("尚未儲存")).toBeVisible();
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("");
  });

  it("guards a direct final edit and resets it after approved load/new replacement", async () => {
    installFetch();
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    render(<PromptWorkbench />);
    await ready();

    const finalText = screen.getByLabelText("Positive Prompt 最終文字");
    fireEvent.change(finalText, { target: { value: "  exact, (unfinished  " } });
    fireEvent.change(screen.getByLabelText("已儲存組合"), { target: { value: "my-quality" } });
    fireEvent.click(screen.getByRole("button", { name: "載入組合" }));

    expect(finalText).toHaveValue("  exact, (unfinished  ");
    expect(screen.getByText("尚未儲存變更")).toBeVisible();
    expect(confirm).toHaveBeenCalledOnce();

    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "載入組合" }));
    await waitFor(() => expect(finalText).toHaveValue("saved prompt,(saved zh:1.2),saved id"));
    fireEvent.change(finalText, { target: { value: "new direct draft" } });
    fireEvent.click(screen.getByRole("button", { name: "建立空白組合" }));
    expect(finalText).toHaveValue("");
  });

  it("guards beforeunload exactly while the document is dirty", async () => {
    installFetch();
    vi.stubGlobal("confirm", vi.fn(() => true));
    render(<PromptWorkbench />);
    await ready();

    const cleanEvent = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(cleanEvent);
    expect(cleanEvent.defaultPrevented).toBe(false);

    fireEvent.change(screen.getByLabelText("Positive Prompt 最終文字"), { target: { value: "dirty direct" } });
    const dirtyEvent = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(dirtyEvent);
    expect(dirtyEvent.defaultPrevented).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "建立空白組合" }));
    const resetEvent = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(resetEvent);
    expect(resetEvent.defaultPrevented).toBe(false);
  });

  it("uses revision zero for fresh update and Save As, but detail tokens for loaded update", async () => {
    const bodies: unknown[] = [];
    installFetch((url, init) => {
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        bodies.push(body);
        return response(composeResponse(body.save_as.id, body.save_as.expected_revision + 1));
      }
    });
    render(<PromptWorkbench />);
    await ready();

    fireEvent.change(screen.getByLabelText("新組合 ID"), { target: { value: "fresh組合" } });
    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    await screen.findByRole("status");
    expect((bodies[0] as { save_as: unknown }).save_as).toMatchObject({ id: "fresh組合", expected_revision: 0 });

    await loadSaved();
    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect((bodies[1] as { save_as: unknown }).save_as).toMatchObject({ id: "my-quality", expected_revision: 3, expected_etag: "detail-3" });

    fireEvent.change(screen.getByLabelText("新組合 ID"), { target: { value: "copy組合" } });
    fireEvent.click(screen.getByRole("button", { name: "另存新組合" }));
    await waitFor(() => expect(bodies).toHaveLength(3));
    expect((bodies[2] as { save_as: unknown }).save_as).toMatchObject({ id: "copy組合", expected_revision: 0 });
    expect((bodies[2] as { save_as: Record<string, unknown> }).save_as).not.toHaveProperty("expected_etag");
  });

  it("installs the Backend canonical response, clears dirty/success, and clears success after later mutation", async () => {
    installFetch((url, init) => url === "/api/prompt-library/compose" && init?.method === "POST"
      ? response(composeResponse("canonical-id", 1, [fragment("literal", "canonical", 10)]))
      : undefined);
    render(<PromptWorkbench />);
    await ready();
    fireEvent.change(screen.getByLabelText("自由文字"), { target: { value: "canonical" } });
    fireEvent.click(screen.getByRole("button", { name: "加入目前正向" }));
    fireEvent.change(screen.getByLabelText("新組合 ID"), { target: { value: "canonical-id" } });
    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));

    expect(await screen.findByRole("status")).toHaveTextContent("組合已儲存");
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("canonical");
    expect(screen.queryByText("尚未儲存變更")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("自訂文字 內容"), { target: { value: "changed" } });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByText("尚未儲存變更")).toBeVisible();
  });

  it("blocks Update and Save As before requests when visible text is whitespace-only", async () => {
    let composeBody: any;
    const fetchMock = installFetch((url, init) => {
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        composeBody = JSON.parse(String(init.body));
        return response(composeResponse("blank-prompt", 1, []));
      }
    });
    render(<PromptWorkbench />);
    await ready();
    fireEvent.change(screen.getByLabelText("Positive Prompt 最終文字"), { target: { value: "  \t " } });
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("  \t ");
    fireEvent.change(screen.getByLabelText("新組合 ID"), { target: { value: "blank-prompt" } });
    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("正向第 1 段");
    expect(screen.getByRole("alert")).toHaveTextContent("每個 ASCII 逗號都會建立一個 prompt");
    fireEvent.click(screen.getByRole("button", { name: "另存新組合" }));
    fireEvent.change(screen.getByLabelText("Positive Prompt 最終文字"), { target: { value: "valid," } });
    fireEvent.change(screen.getByLabelText("Workflow"), { target: { value: "basic-txt2img" } });
    fireEvent.click(screen.getByRole("button", { name: "開始生圖" }));
    expect(screen.getAllByRole("alert").every((node) =>
      node.textContent?.includes("正向第 2 段"),
    )).toBe(true);
    expect(composeBody).toBeUndefined();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/prompt-library/compose")).toHaveLength(0);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/generate/")).toHaveLength(0);
  });

  it("atomizes free-text Add and blocks its empty atom before Generate", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);
    await ready();

    fireEvent.change(screen.getByLabelText("自由文字"), {
      target: { value: "a,,b" },
    });
    fireEvent.click(screen.getByRole("button", { name: "加入目前正向" }));

    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("a,,b");
    expect(
      screen.getAllByLabelText("自訂文字 內容").map(
        (node) => (node as HTMLTextAreaElement).value,
      ),
    ).toEqual(["a", "", "b"]);

    fireEvent.change(screen.getByLabelText("Workflow"), {
      target: { value: "basic-txt2img" },
    });
    fireEvent.click(screen.getByRole("button", { name: "開始生圖" }));

    expect(
      (await screen.findAllByRole("alert")).some((node) =>
        node.textContent?.includes("正向第 2 段"),
      ),
    ).toBe(true);
    expect(
      fetchMock.mock.calls.filter(([url]) => url === "/api/generate/"),
    ).toHaveLength(0);
  });

  it("materializes an exact direct edit before save and preserves it when save fails", async () => {
    let composeBody: any;
    installFetch((url, init) => {
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        composeBody = JSON.parse(String(init.body));
        return response({ detail: { message: "儲存衝突" } }, 409);
      }
    });
    render(<PromptWorkbench />);
    await ready();
    await loadSaved();
    const finalText = screen.getByLabelText("Positive Prompt 最終文字");
    fireEvent.change(finalText, { target: { value: "  exact raw, (unfinished  " } });
    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));

    await waitFor(() => expect(screen.getAllByRole("alert").some((node) => node.textContent?.includes("儲存衝突"))).toBe(true));
    expect(finalText).toHaveValue("  exact raw, (unfinished  ");
    expect(composeBody.positive).toEqual([
      { kind: "literal", snapshot: "  exact raw", weight: 1, order: 10 },
      { kind: "literal", snapshot: " (unfinished  ", weight: 1, order: 20 },
    ]);
    expect(composeBody.save_as.positive).toEqual(composeBody.positive);
    expect(screen.getAllByLabelText("自訂文字 內容").map((node) => (node as HTMLTextAreaElement).value))
      .toEqual(["  exact raw", " (unfinished  "]);
    expect(screen.getByText("尚未儲存變更")).toBeVisible();
  });

  it("does not let stale load resolution or rejection replace a newer local document", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    let loadCount = 0;
    installFetch((url) => {
      if (url === "/api/prompt-library/combinations/my-quality") {
        loadCount += 1;
        return loadCount === 1 ? first.promise : second.promise;
      }
    });
    render(<PromptWorkbench />);
    await ready();
    fireEvent.change(screen.getByLabelText("已儲存組合"), { target: { value: "my-quality" } });
    fireEvent.click(screen.getByRole("button", { name: "載入組合" }));
    fireEvent.change(screen.getByLabelText("自由文字"), { target: { value: "newer local" } });
    fireEvent.click(screen.getByRole("button", { name: "加入目前正向" }));
    first.resolve(response(combinationDetail()));
    await waitFor(() => expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("newer local"));
    expect(screen.getByText("尚未儲存")).toBeVisible();

    vi.stubGlobal("confirm", vi.fn(() => true));
    fireEvent.click(screen.getByRole("button", { name: "載入組合" }));
    fireEvent.change(screen.getByLabelText("自訂文字 內容"), { target: { value: "newest local" } });
    second.reject(new Error("stale load error"));
    await waitFor(() => expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("newest local"));
    expect(screen.queryByText("stale load error")).not.toBeInTheDocument();
  });

  it("does not let stale save resolution or rejection contaminate a newer local edit", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    let saveCount = 0;
    installFetch((url, init) => {
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        saveCount += 1;
        return saveCount === 1 ? first.promise : second.promise;
      }
    });
    render(<PromptWorkbench />);
    await ready();
    fireEvent.change(screen.getByLabelText("Positive Prompt 最終文字"), { target: { value: "local direct" } });
    fireEvent.change(screen.getByLabelText("新組合 ID"), { target: { value: "race-save" } });
    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    fireEvent.change(screen.getByLabelText("Positive Prompt 最終文字"), { target: { value: "newer direct,filled" } });
    await act(async () => {
      first.resolve(response(composeResponse("race-save", 1)));
    });
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("newer direct,filled");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    fireEvent.change(screen.getByLabelText("Positive Prompt 最終文字"), { target: { value: "newest direct (unfinished" } });
    await act(async () => {
      second.reject(new Error("stale save error"));
    });
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue("newest direct (unfinished");
    expect(screen.queryByText("stale save error")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "更新目前組合" })).toBeEnabled();
  });

  it("rejects path-unsafe Save As IDs without composing", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);
    await ready();
    fireEvent.change(screen.getByLabelText("新組合 ID"), { target: { value: "../逃逸" } });
    fireEvent.click(screen.getByRole("button", { name: "另存新組合" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unicode 字母、數字與連字號");
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/prompt-library/compose")).toHaveLength(0);
  });

  it("NFC-normalizes a decomposed safe Unicode ID before validating and saving", async () => {
    let composeBody: any;
    installFetch((url, init) => {
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        composeBody = JSON.parse(String(init.body));
        return response(composeResponse(composeBody.save_as.id, 1));
      }
    });
    render(<PromptWorkbench />);
    await ready();

    fireEvent.change(screen.getByLabelText("新組合 ID"), { target: { value: "Cafe\u0301" } });
    fireEvent.click(screen.getByRole("button", { name: "另存新組合" }));

    await waitFor(() => expect(composeBody).toBeDefined());
    expect(composeBody.save_as).toMatchObject({ id: "Café", name_zh: "Café", expected_revision: 0 });
    expect(screen.getByLabelText("新組合 ID")).toHaveValue("Café");
    expect(await screen.findByLabelText("目前組合版本")).toHaveTextContent("Café");
  });

  it("preserves loaded combination metadata on Update and Save As", async () => {
    const loaded = combinationDetail();
    Object.assign(loaded.combination, {
      name_zh: "精緻肖像",
      description_zh: "保留這段說明",
      aliases: ["portrait", "人像"],
      keywords: ["detail", "細節"],
      order: 77,
      legacy_template: true,
    });
    const bodies: any[] = [];
    installFetch((url, init) => {
      if (url === "/api/prompt-library/combinations/my-quality") {
        return response(loaded);
      }
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        bodies.push(body);
        const result = composeResponse(
          body.save_as.id,
          body.save_as.expected_revision + 1,
          body.positive,
          body.negative,
        );
        Object.assign(result.saved_combination.combination, {
          name_zh: body.save_as.name_zh,
          description_zh: body.save_as.description_zh,
          aliases: body.save_as.aliases,
          keywords: body.save_as.keywords,
          order: body.save_as.order,
          legacy_template: body.save_as.legacy_template,
        });
        return response(result);
      }
    });
    render(<PromptWorkbench />);
    await ready();
    await loadSaved();

    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    await waitFor(() => expect(bodies).toHaveLength(1));

    await loadSaved();
    fireEvent.change(screen.getByLabelText("新組合 ID"), {
      target: { value: "portrait-copy" },
    });
    fireEvent.click(screen.getByRole("button", { name: "另存新組合" }));
    await waitFor(() => expect(bodies).toHaveLength(2));

    for (const body of bodies) {
      expect(body.save_as).toMatchObject({
        name_zh: "精緻肖像",
        description_zh: "保留這段說明",
        aliases: ["portrait", "人像"],
        keywords: ["detail", "細節"],
        order: 77,
        legacy_template: true,
      });
    }
  });

  it("uses Backend-canonical three-decimal weights for save retry and reload", async () => {
    let composeBody: any;
    installFetch((url, init) => {
      if (url === "/api/prompt-library/compose" && init?.method === "POST") {
        composeBody = JSON.parse(String(init.body));
        const canonical = fragment("literal", "detail", 10, 1.234);
        return response(composeResponse("weighted-canonical", 1, [canonical]));
      }
    });
    render(<PromptWorkbench />);
    await ready();

    fireEvent.change(screen.getByLabelText("自由文字"), {
      target: { value: "detail" },
    });
    fireEvent.click(screen.getByRole("button", { name: "加入目前正向" }));
    fireEvent.change(screen.getByLabelText("自訂文字 權重"), {
      target: { value: "1.2345" },
    });
    fireEvent.change(screen.getByLabelText("新組合 ID"), {
      target: { value: "weighted-canonical" },
    });
    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));

    expect(await screen.findByRole("status")).toHaveTextContent("組合已儲存");
    expect(composeBody.positive[0].weight).toBe(1.234);
    expect(screen.getByLabelText("Positive Prompt 最終文字")).toHaveValue(
      "(detail:1.234)",
    );
    expect(screen.getByLabelText("自訂文字 權重")).toHaveValue(1.234);
  });

  it("rejects a combination ID longer than 128 characters after NFC normalization", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);
    await ready();

    fireEvent.change(screen.getByLabelText("新組合 ID"), { target: { value: `Cafe\u0301${"a".repeat(125)}` } });
    fireEvent.click(screen.getByRole("button", { name: "另存新組合" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("1 到 128 個字元");
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/prompt-library/compose")).toHaveLength(0);
  });
});

describe("PromptWorkbench existing flows", () => {
  it("keeps the newest category selection when an older category read resolves last", async () => {
    const older = deferred<Response>();
    const newest = deferred<Response>();
    let qualityReads = 0;
    let styleReads = 0;
    installFetch((url) => {
      if (url.endsWith("/categories/positive/quality")) {
        qualityReads += 1;
        return qualityReads === 1
          ? response(categoryResponse("positive", "quality"))
          : older.promise;
      }
      if (url.endsWith("/categories/positive/style")) {
        styleReads += 1;
        return styleReads === 1
          ? response(categoryResponse("positive", "style"))
          : newest.promise;
      }
    });
    render(<PromptWorkbench />);
    await ready();

    fireEvent.click(screen.getByRole("button", { name: "品質" }));
    fireEvent.click(screen.getByRole("button", { name: "風格" }));
    newest.resolve(response(categoryResponse("positive", "style")));
    expect(await screen.findByRole("button", { name: "加入 中文名稱" })).toBeVisible();
    expect(screen.getByRole("button", { name: "風格" })).toHaveClass("bg-emerald-700");

    await act(async () => {
      older.resolve(response(categoryResponse("positive", "quality")));
    });
    expect(screen.getByRole("button", { name: "風格" })).toHaveClass("bg-emerald-700");
  });

  it("keeps a newer category and error state when an older category read rejects last", async () => {
    const older = deferred<Response>();
    let qualityReads = 0;
    installFetch((url) => {
      if (!url.endsWith("/categories/positive/quality")) return undefined;
      qualityReads += 1;
      return qualityReads === 1
        ? response(categoryResponse("positive", "quality"))
        : older.promise;
    });
    render(<PromptWorkbench />);
    await ready();

    fireEvent.click(screen.getByRole("button", { name: "品質" }));
    fireEvent.click(screen.getByRole("button", { name: "風格" }));
    expect(await screen.findByRole("button", { name: "加入 中文名稱" })).toBeVisible();
    await act(async () => {
      older.reject(new Error("obsolete category error"));
    });

    expect(screen.queryByText("obsolete category error")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "風格" })).toHaveClass("bg-emerald-700");
  });

  it("invalidates an in-flight category read when polarity changes", async () => {
    const pending = deferred<Response>();
    let qualityReads = 0;
    installFetch((url) => {
      if (!url.endsWith("/categories/positive/quality")) return undefined;
      qualityReads += 1;
      return qualityReads === 1
        ? response(categoryResponse("positive", "quality"))
        : pending.promise;
    });
    render(<PromptWorkbench />);
    await ready();

    fireEvent.click(screen.getByRole("button", { name: "品質" }));
    fireEvent.click(screen.getByRole("button", { name: "負向" }));
    await act(async () => {
      pending.resolve(response(categoryResponse("positive", "quality")));
    });

    expect(screen.queryByRole("button", { name: "加入 中文名稱" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "負向" })).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps source interactions read-only and generates from the exact visible direct text", async () => {
    const fetchMock = installFetch();
    render(<PromptWorkbench />);
    await ready();
    fireEvent.click(screen.getByRole("button", { name: "品質" }));
    const loadedEntry = await screen.findByRole("button", { name: "加入 中文名稱" });
    expect(screen.queryByRole("button", { name: /新增|編輯|封存|恢復/ })).not.toBeInTheDocument();
    fireEvent.click(loadedEntry);
    fireEvent.change(screen.getByLabelText("Positive Prompt 最終文字"), { target: { value: "zh current,  (unfinished " } });
    fireEvent.click(screen.getByRole("button", { name: "負向" }));
    fireEvent.click(screen.getByRole("button", { name: "瑕疵" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 模糊" }));
    fireEvent.change(screen.getByLabelText("Negative Prompt 最終文字"), { target: { value: "blurry current" } });
    fireEvent.change(screen.getByLabelText("Workflow"), { target: { value: "basic-txt2img" } });
    fireEvent.click(screen.getByRole("button", { name: "開始生圖" }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("job-1"));
    const call = fetchMock.mock.calls.find(([url]) => url === "/api/generate/") as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toMatchObject({ prompt: "zh current,  (unfinished ", negative_prompt: "blurry current" });
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(0);
  });

  it("splits a direct edit into exact atomic literals whose card actions work", async () => {
    installFetch();
    render(<PromptWorkbench />);
    await ready();
    fireEvent.click(screen.getByRole("button", { name: "品質" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 中文名稱" }));

    const finalText = screen.getByLabelText("Positive Prompt 最終文字");
    fireEvent.change(finalText, { target: { value: "  raw, (unfinished  " } });
    expect(screen.queryByLabelText("中文名稱 內容")).not.toBeInTheDocument();
    const literalCards = screen.getAllByLabelText("自訂文字 內容");
    expect(literalCards.map((node) => (node as HTMLTextAreaElement).value))
      .toEqual(["  raw", " (unfinished  "]);
    expect(screen.getAllByRole("button", { name: "上移" })[0]).toBeDisabled();
    expect(screen.getAllByRole("button", { name: "下移" })[1]).toBeDisabled();

    fireEvent.change(finalText, { target: { value: "second direct" } });
    const literalCard = screen.getByLabelText("自訂文字 內容");
    fireEvent.change(literalCard, { target: { value: "card edited" } });
    expect(finalText).toHaveValue("card edited");

    fireEvent.change(finalText, { target: { value: "weighted direct" } });
    fireEvent.change(screen.getByLabelText("自訂文字 權重"), { target: { value: "1.5" } });
    expect(finalText).toHaveValue("(weighted direct:1.5)");
    fireEvent.click(screen.getByRole("button", { name: "刪除" }));
    expect(finalText).toHaveValue("");
    expect(screen.queryByLabelText("自訂文字 內容")).not.toBeInTheDocument();
  });

  it("materializes a direct edit before appending a source entry", async () => {
    installFetch();
    render(<PromptWorkbench />);
    await ready();
    const finalText = screen.getByLabelText("Positive Prompt 最終文字");
    fireEvent.change(finalText, { target: { value: "  raw, (unfinished  " } });
    fireEvent.click(screen.getByRole("button", { name: "品質" }));
    fireEvent.click(await screen.findByRole("button", { name: "加入 中文名稱" }));

    expect(finalText).toHaveValue("  raw, (unfinished  ,zh current");
    expect(screen.getAllByLabelText("自訂文字 內容").map((node) => (node as HTMLTextAreaElement).value))
      .toEqual(["  raw", " (unfinished  "]);
    expect(screen.getByLabelText("中文名稱 內容")).toHaveValue("zh current");
  });
});
