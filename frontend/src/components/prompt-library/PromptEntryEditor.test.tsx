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

  it("hides the id field and prefills values in edit mode", () => {
    const onSubmit = vi.fn();
    render(<PromptEntryEditor mode="edit" initial={{ id: "masterpiece", name_zh: "傑作", description_zh: "品質", prompt: "masterpiece", aliases: ["a"], keywords: ["k"], order: 10 }} onSubmit={onSubmit} onCancel={() => {}} />);
    expect(screen.queryByLabelText("詞條 ID")).not.toBeInTheDocument();
    expect(screen.getByLabelText("詞條中文名稱")).toHaveValue("傑作");
    fireEvent.change(screen.getByLabelText("詞條中文名稱"), { target: { value: "大師傑作" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));
    expect(onSubmit).toHaveBeenCalledWith({
      id: "masterpiece",
      fields: { name_zh: "大師傑作", description_zh: "品質", prompt: "masterpiece", aliases: ["a"], keywords: ["k"], order: 10 },
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
});
