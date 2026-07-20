import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import SystemStatusCard, { type ComfyUIStatus } from "./SystemStatusCard";

const baseStatus: ComfyUIStatus = {
  mode: "managed",
  state: "connected",
  configured: true,
  reachable: true,
  model_count: 3,
  checkpoint_count: 2,
  diffusion_model_count: 1,
  warnings: [],
  hint: "Ready to generate images.",
};

describe("SystemStatusCard", () => {
  it.each([
    ["connected", "ComfyUI 已就緒"],
    ["not_configured", "ComfyUI 尚未設定"],
    ["unreachable", "ComfyUI 無法連線"],
    ["no_models", "ComfyUI 已連線，尚無模型"],
    ["degraded", "ComfyUI 可使用，但需要注意"],
  ] as const)("renders an explicit semantic label for %s", (state, label) => {
    render(<SystemStatusCard status={{ ...baseStatus, state }} />);

    expect(screen.getByRole("status", { name: "ComfyUI 狀態" })).toHaveTextContent(label);
  });

  it("shows configuration, reachability, model counts, hint, and warnings", () => {
    render(
      <SystemStatusCard
        status={{
          ...baseStatus,
          warnings: ["The checkpoint directory cannot be read.", "One model path is missing."],
        }}
      />,
    );

    expect(screen.getByText("設定：是")).toBeInTheDocument();
    expect(screen.getByText("可連線：是")).toBeInTheDocument();
    expect(screen.getByText("模型：3（Checkpoint 2、Diffusion Model 1）")).toBeInTheDocument();
    expect(screen.getByText("Ready to generate images.")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "ComfyUI 警告" })).toHaveTextContent(
      "The checkpoint directory cannot be read.",
    );
    expect(screen.getByRole("list", { name: "ComfyUI 警告" })).toHaveTextContent(
      "One model path is missing.",
    );
  });
});
