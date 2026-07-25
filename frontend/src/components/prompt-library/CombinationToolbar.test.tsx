import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CombinationToolbar from "./CombinationToolbar";

const combinations = [
  { id: "live", name_zh: "常用組合", revision: 1, etag: "summary-1", archived: false },
  { id: "other", name_zh: "其他組合", revision: 1, etag: "summary-other", archived: false },
  { id: "archived", name_zh: "已封存", revision: 2, etag: "summary-2", archived: true },
] as never;

function props(overrides = {}) {
  return {
    combinations,
    selectedId: "live",
    onSelectedIdChange: vi.fn(),
    onLoad: vi.fn(),
    onBlank: vi.fn(),
    document: { id: "live", revision: 3, repaired: true, dirty: false },
    targetId: "copy組合",
    onTargetIdChange: vi.fn(),
    onUpdate: vi.fn(),
    onSaveAs: vi.fn(),
    busy: false,
    warnings: ["快照已修復"],
    success: "組合已更新",
    error: "",
    ...overrides,
  };
}

describe("CombinationToolbar", () => {
  it("excludes archived summaries and presents loaded detail identity and messages", () => {
    render(<CombinationToolbar {...props()} />);

    expect(screen.getByRole("option", { name: "常用組合（live）" })).toBeVisible();
    expect(screen.queryByRole("option", { name: /已封存/ })).not.toBeInTheDocument();
    const identity = screen.getByLabelText("目前組合版本");
    expect(identity).toHaveTextContent("live");
    expect(identity).toHaveTextContent("revision 3");
    expect(identity).toHaveTextContent("已修復");
    expect(screen.getByRole("status")).toHaveTextContent("組合已更新");
    expect(screen.getByRole("alert")).toHaveTextContent("快照已修復");
  });

  it("invokes selection, load, blank, update, and Save As callbacks", () => {
    const callbacks = props();
    render(<CombinationToolbar {...callbacks} />);

    fireEvent.change(screen.getByLabelText("已儲存組合"), { target: { value: "other" } });
    fireEvent.click(screen.getByRole("button", { name: "載入組合" }));
    fireEvent.click(screen.getByRole("button", { name: "建立空白組合" }));
    fireEvent.change(screen.getByLabelText("新組合 ID"), { target: { value: "新組合" } });
    fireEvent.click(screen.getByRole("button", { name: "更新目前組合" }));
    fireEvent.click(screen.getByRole("button", { name: "另存新組合" }));

    expect(callbacks.onSelectedIdChange).toHaveBeenCalledWith("other");
    expect(callbacks.onLoad).toHaveBeenCalledTimes(1);
    expect(callbacks.onBlank).toHaveBeenCalledTimes(1);
    expect(callbacks.onTargetIdChange).toHaveBeenCalledWith("新組合");
    expect(callbacks.onUpdate).toHaveBeenCalledTimes(1);
    expect(callbacks.onSaveAs).toHaveBeenCalledTimes(1);
  });

  it("shows an unsaved identity and disables replacement/save actions while busy", () => {
    render(<CombinationToolbar {...props({ document: { id: null, revision: null, repaired: false, dirty: true }, busy: true })} />);

    expect(screen.getByText("尚未儲存")).toBeVisible();
    for (const name of ["載入組合", "建立空白組合", "更新目前組合", "另存新組合"]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
  });

  it("requires a selected combination for load and a target ID for unsaved saves", () => {
    render(<CombinationToolbar {...props({ selectedId: "", targetId: "", document: { id: null, revision: null, repaired: false, dirty: false } })} />);

    expect(screen.getByRole("button", { name: "載入組合" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "更新目前組合" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "另存新組合" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "建立空白組合" })).toBeEnabled();
  });
});
