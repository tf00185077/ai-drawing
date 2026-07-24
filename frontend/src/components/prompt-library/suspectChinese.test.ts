import { describe, expect, it } from "vitest";
import { hasCjk, suspectReason } from "./suspectChinese";

describe("suspectChinese", () => {
  it("detects CJK ideographs", () => {
    expect(hasCjk("傑作")).toBe(true);
    expect(hasCjk("masterpiece")).toBe(false);
    expect(hasCjk("")).toBe(false);
  });

  it("flags name_zh with no Chinese as missing_chinese", () => {
    expect(suspectReason("masterpiece detail", "masterpiece")).toBe("missing_chinese");
  });

  it("flags name_zh echoing the prompt as echoes_prompt", () => {
    expect(suspectReason("Masterpiece", "masterpiece")).toBe("echoes_prompt");
    expect(suspectReason("  best  quality ", "best quality")).toBe("echoes_prompt");
  });

  it("passes meaningful Chinese", () => {
    expect(suspectReason("傑作", "masterpiece")).toBeNull();
    expect(suspectReason("最佳品質")).toBeNull();
  });
});
