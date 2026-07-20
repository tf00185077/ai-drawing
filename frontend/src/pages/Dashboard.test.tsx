import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "./Dashboard";

const healthyStatus = {
  application: "healthy",
  comfyui: {
    mode: "managed",
    state: "connected",
    configured: true,
    reachable: true,
    model_count: 1,
    checkpoint_count: 1,
    diffusion_model_count: 0,
    warnings: [],
    hint: "Ready to generate images.",
  },
};

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response;
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Dashboard", () => {
  it("loads ComfyUI status once and retains the existing module cards", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(healthyStatus));
    vi.stubGlobal("fetch", fetchMock);

    renderDashboard();

    expect(screen.getByText("正在讀取 ComfyUI 狀態…")).toBeInTheDocument();
    expect(await screen.findByRole("status", { name: "ComfyUI 狀態" })).toHaveTextContent(
      "ComfyUI 已就緒",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/system/status",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(screen.getByRole("link", { name: /生圖/ })).toHaveAttribute("href", "/generate");
    expect(screen.getByRole("link", { name: /圖庫/ })).toHaveAttribute("href", "/gallery");
    expect(screen.getByRole("link", { name: /LoRA 文件/ })).toHaveAttribute("href", "/lora-docs");
    expect(screen.getByRole("link", { name: /LoRA 訓練/ })).toHaveAttribute("href", "/lora-train");
  });

  it.each([
    ["network failure", () => Promise.reject(new Error("offline"))],
    ["non-success response", () => Promise.resolve(response({ detail: "unavailable" }, 503))],
    ["malformed response", () => Promise.resolve(response({ application: "healthy" }))],
  ])("shows a safe error for a %s", async (_scenario, fetchResult) => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(fetchResult));

    renderDashboard();

    expect(await screen.findByRole("alert")).toHaveTextContent("無法讀取 ComfyUI 狀態。");
    expect(screen.queryByRole("status", { name: "ComfyUI 狀態" })).not.toBeInTheDocument();
  });

  it("aborts the request on unmount without updating state", () => {
    let requestSignal: AbortSignal | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => {
        requestSignal = init.signal as AbortSignal;
        return new Promise<Response>(() => undefined);
      }),
    );

    const { unmount } = renderDashboard();
    unmount();

    expect(requestSignal?.aborted).toBe(true);
  });
});
