import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PromptEntryEditor from "./PromptEntryEditor";

describe("PromptEntryEditor", () => {
  it("submits parsed values in create mode", () => {
    const onSubmit = vi.fn();
    render(<PromptEntryEditor mode="create" onSubmit={onSubmit} onCancel={() => {}} />);

    fireEvent.change(screen.getByLabelText("詞條 ID"), { target: { value: "detailed-eyes" } });
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "細緻眼睛" } });
    fireEvent.change(screen.getByLabelText("詞條說明"), { target: { value: "眼睛細節" } });
    fireEvent.change(screen.getByLabelText("詞條英文 prompt"), { target: { value: "detailed eyes" } });
    fireEvent.change(screen.getByLabelText("詞條別名"), { target: { value: "眼睛, eyes" } });
    fireEvent.change(screen.getByLabelText("詞條排序"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));

    expect(onSubmit).toHaveBeenCalledWith({
      id: "detailed-eyes",
      fields: { name_zh: "細緻眼睛", description_zh: "眼睛細節", prompt: "detailed eyes", aliases: ["眼睛", "eyes"], keywords: [], order: 20 },
    });
  });

  it("rejects an invalid slug without calling onSubmit", () => {
    const onSubmit = vi.fn();
    render(<PromptEntryEditor mode="create" onSubmit={onSubmit} onCancel={() => {}} />);
    fireEvent.change(screen.getByLabelText("詞條 ID"), { target: { value: "Bad ID" } });
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "壞" } });
    fireEvent.change(screen.getByLabelText("詞條說明"), { target: { value: "壞" } });
    fireEvent.change(screen.getByLabelText("詞條英文 prompt"), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeVisible();
  });

  it("shows immutable ID, parses aliases and keywords, and prefills values in edit mode", () => {
    const onSubmit = vi.fn();
    render(<PromptEntryEditor mode="edit" initial={{ id: "masterpiece", name_zh: "傑作", description_zh: "品質", prompt: "masterpiece", aliases: ["a"], keywords: ["k"], order: 10 }} onSubmit={onSubmit} onCancel={() => {}} />);
    expect(screen.getByLabelText("詞條 ID")).toBeDisabled();
    expect(screen.getByLabelText("詞條 ID")).toHaveValue("masterpiece");
    expect(screen.getByLabelText("詞條中文名稱")).toHaveValue("傑作");
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "大師傑作" } });
    fireEvent.change(screen.getByLabelText("詞條別名"), { target: { value: " a, b ,, " } });
    fireEvent.change(screen.getByLabelText("詞條關鍵字"), { target: { value: " k, quality " } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(onSubmit).toHaveBeenCalledWith({
      id: "masterpiece",
      fields: { name_zh: "大師傑作", description_zh: "品質", prompt: "masterpiece", aliases: ["a", "b"], keywords: ["k", "quality"], order: 10 },
    });
  });

  it("rejects a duplicate id in create mode", () => {
    const onSubmit = vi.fn();
    render(<PromptEntryEditor mode="create" existingIds={["masterpiece"]} onSubmit={onSubmit} onCancel={() => {}} />);
    fireEvent.change(screen.getByLabelText("詞條 ID"), { target: { value: "masterpiece" } });
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "傑作" } });
    fireEvent.change(screen.getByLabelText("詞條說明"), { target: { value: "說明" } });
    fireEvent.change(screen.getByLabelText("詞條英文 prompt"), { target: { value: "masterpiece" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeVisible();
  });

  it("rejects non-integer order and disables every field and action while submitting", () => {
    const onSubmit = vi.fn();
    const onCancel = vi.fn();
    const view = render(<PromptEntryEditor mode="create" onSubmit={onSubmit} onCancel={onCancel} />);
    fireEvent.change(screen.getByLabelText("詞條 ID"), { target: { value: "new-entry" } });
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "新詞條" } });
    fireEvent.change(screen.getByLabelText("詞條說明"), { target: { value: "說明" } });
    fireEvent.change(screen.getByLabelText("詞條英文 prompt"), { target: { value: "new entry" } });
    fireEvent.change(screen.getByLabelText("詞條排序"), { target: { value: "1.5" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("整數");

    view.rerender(<PromptEntryEditor mode="create" submitting onSubmit={onSubmit} onCancel={onCancel} />);
    for (const label of ["詞條 ID", "詞條中文名稱", "詞條說明", "詞條英文 prompt", "詞條別名", "詞條關鍵字", "詞條排序"]) {
      expect(screen.getByLabelText(label)).toBeDisabled();
    }
    expect(screen.getByRole("button", { name: "儲存中…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "取消" })).toBeDisabled();
  });
});
