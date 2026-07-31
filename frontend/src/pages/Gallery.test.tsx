import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Gallery from "./Gallery";

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
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
