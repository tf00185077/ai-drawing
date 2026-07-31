import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import GenerationPanel from "./GenerationPanel";

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response;
}

afterEach(() => vi.restoreAllMocks());

describe("GenerationPanel execution target", () => {
  it("defaults to local and submits the selected worker wire value", async () => {
    const fetchMock = vi.fn(async () => response({ job_id: "job-1" }, 202));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <GenerationPanel
        forms={[{ id: "basic", display_name: "Basic" }]}
        positivePrompt="cat"
        negativePrompt="blur"
        preflight={() => null}
      />,
    );

    expect(screen.getByLabelText("執行位置")).toHaveValue("local");
    fireEvent.change(screen.getByLabelText("Workflow"), { target: { value: "basic" } });
    fireEvent.change(screen.getByLabelText("執行位置"), { target: { value: "worker" } });
    fireEvent.click(screen.getByRole("button", { name: "開始生圖" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({
      template: "basic",
      prompt: "cat",
      execution_target: "worker",
    });
  });
});
