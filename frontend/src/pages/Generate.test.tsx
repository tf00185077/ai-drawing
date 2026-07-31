import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Generate from "./Generate";

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response;
}

afterEach(() => vi.restoreAllMocks());

describe("Generate execution target", () => {
  it("defaults to Mac local and sends the exact local wire value", async () => {
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) =>
      url.endsWith("/queue")
        ? response({ queue_running: [], queue_pending: [] })
        : response({ job_id: "job-local", status: "queued" }, 202),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<Generate />);

    expect(screen.getByLabelText("執行位置")).toHaveValue("local");
    fireEvent.change(screen.getByPlaceholderText("必填，例如: 1girl, solo, ..."), { target: { value: "cat" } });
    fireEvent.click(screen.getByRole("button", { name: "生成" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url === "/api/generate/")).toBe(true));
    const call = fetchMock.mock.calls.find(([url]) => url === "/api/generate/") as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toMatchObject({ prompt: "cat", execution_target: "local" });
  });

  it("sends the exact worker wire value when Windows worker is selected", async () => {
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) =>
      url.endsWith("/queue")
        ? response({ queue_running: [], queue_pending: [] })
        : response({ job_id: "job-worker", status: "queued" }, 202),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<Generate />);

    fireEvent.change(screen.getByLabelText("執行位置"), { target: { value: "worker" } });
    fireEvent.change(screen.getByPlaceholderText("必填，例如: 1girl, solo, ..."), { target: { value: "dog" } });
    fireEvent.click(screen.getByRole("button", { name: "生成" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url === "/api/generate/")).toBe(true));
    const call = fetchMock.mock.calls.find(([url]) => url === "/api/generate/") as [string, RequestInit];
    expect(JSON.parse(String(call[1].body)).execution_target).toBe("worker");
  });
});
