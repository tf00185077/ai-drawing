import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Gallery from "./Gallery";

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
    text: async () => JSON.stringify(data),
  } as Response;
}

const item = {
  id: 42,
  image_path: "image.png",
  checkpoint: "model.safetensors",
  lora: null,
  seed: 1,
  steps: 20,
  cfg: 7,
  prompt: "cat",
  negative_prompt: null,
  created_at: "2026-07-31T00:00:00",
};

afterEach(() => vi.restoreAllMocks());

describe("Gallery rerun execution target", () => {
  it("defaults to local and lets the user rerun on the Windows worker", async () => {
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) =>
      url.includes("/rerun")
        ? response({ job_id: "rerun-1", status: "queued" }, 202)
        : response({ items: [item], total: 1 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<Gallery />);

    fireEvent.click(await screen.findByRole("button", { name: /cat/ }));
    expect(screen.getByLabelText("執行位置")).toHaveValue("local");
    fireEvent.change(screen.getByLabelText("執行位置"), { target: { value: "worker" } });
    fireEvent.click(screen.getByRole("button", { name: "一鍵重現" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url === "/api/gallery/42/rerun")).toBe(true));
    const call = fetchMock.mock.calls.find(([url]) => url === "/api/gallery/42/rerun") as [string, RequestInit];
    expect(call[1].headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(String(call[1].body))).toEqual({ execution_target: "worker" });
  });
});


describe("Gallery exact seed display", () => {
  it.each([
    ["1224040850519066617", "1224040850519066617"],
    ["9007199254740991", "9007199254740991"],
    ["9007199254740992", "9007199254740992"],
    ["9007199254740993", "9007199254740993"],
    ["9223372036854775807", "9223372036854775807"],
    ["18446744073709551615", "18446744073709551615"],
    ["-9223372036854775808", "-9223372036854775808"],
    ["-1", "-1"],
    ["0", "0"],
    ["null", null],
  ])("preserves raw seed %s through fetch, selection and display", async (token, expected) => {
    const raw = JSON.stringify({ items: [item], total: 1 }).replace('"seed":1,', `"seed":${token},`);
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true, status: 200,
      text: async () => raw,
      json: async () => JSON.parse(raw),
    })));
    render(<Gallery />);
    fireEvent.click(await screen.findByRole("button", { name: /cat/ }));
    const seedLabel = screen.queryByText("Seed:");
    if (expected === null) expect(seedLabel).toBeNull();
    else expect(seedLabel?.nextElementSibling?.textContent).toBe(expected);
  });
});


describe("Gallery seed token boundaries", () => {
  it("keeps seed-like prompt text, escaped quotes and other parameters intact", async () => {
    const prompt = 'cat \"seed\":1224040850519066617 and \\ paths';
    const raw = JSON.stringify({ items: [{ ...item, prompt, cfg: 7.5 }], total: 1 })
      .replace('"seed":1,', '"seed":1224040850519066617,');
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, text: async () => raw, json: async () => JSON.parse(raw) })));
    render(<Gallery />);
    fireEvent.click(await screen.findByRole("button", { name: /cat/ }));
    expect(screen.getByText(prompt)).toBeInTheDocument();
    expect(screen.getByText("Seed:").nextElementSibling?.textContent).toBe("1224040850519066617");
    expect(screen.getByText("CFG:").nextElementSibling?.textContent).toBe("7.5");
  });
  it.each(["true", "1.5", "1e30", "{}"])("reports invalid integer seed %s instead of displaying a guessed value", async token => {
    const raw = JSON.stringify({ items: [item], total: 1 }).replace('"seed":1,', `"seed":${token},`);
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, text: async () => raw, json: async () => JSON.parse(raw) })));
    render(<Gallery />);
    expect(await screen.findByText(/Invalid Gallery seed/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cat/ })).toBeNull();
  });
});
