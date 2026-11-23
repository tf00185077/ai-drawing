import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { afterEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import LoraTrain from "./LoraTrain";

afterEach(() => { vi.unstubAllGlobals(); });

it("shows allocated primary labels from real Backend HTTP serialization", async () => {
  const python = process.env.BACKEND_TEST_PYTHON || "../backend/.venv/bin/python";
  const status = JSON.parse(execFileSync(python, ["-I", "-S", "-B", "../tools/offline_pytest.py", "--script", resolve("../backend/tests/lora_status_http_fixture.py")], {
    encoding: "utf8",
    env: { ...process.env, PYTHONPATH: "../backend", PYTHONDONTWRITEBYTECODE: "1", DATABASE_URL: "sqlite://" },
  }));
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
    ok: true, json: async () => url.endsWith("/status") ? status : url.endsWith("/folders") ? { folders: [] } : { model_family: "sdxl", sdxl: true },
  })));
  render(<LoraTrain />);
  expect(await screen.findByText(/目前：水彩 旅人_002/)).toBeInTheDocument();
  expect(await screen.findByText(/水彩 旅人_003/)).toBeInTheDocument();
  expect(screen.queryByText(/目前：dataset-a/)).not.toBeInTheDocument();
});
