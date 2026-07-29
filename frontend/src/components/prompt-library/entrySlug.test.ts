import { describe, expect, it } from "vitest";
import { slugifyEntryId } from "./entrySlug";

describe("slugifyEntryId", () => {
  it("slugifies English into lowercase-hyphen id", () => {
    expect(slugifyEntryId("Detailed Eyes", [])).toBe("detailed-eyes");
    expect(slugifyEntryId("  best   quality!! ", [])).toBe("best-quality");
    expect(slugifyEntryId("score_9", [])).toBe("score-9");
  });
  it("appends a numeric suffix on collision within the category", () => {
    expect(slugifyEntryId("dress", ["dress"])).toBe("dress-2");
    expect(slugifyEntryId("dress", ["dress", "dress-2"])).toBe("dress-3");
  });
  it("returns the base when there is no collision", () => {
    expect(slugifyEntryId("dress", ["skirt"])).toBe("dress");
  });
  it("throws when the slug is empty (no ascii alphanumerics)", () => {
    expect(() => slugifyEntryId("　！？", [])).toThrowError(/無法從英文產生 ID/);
    expect(() => slugifyEntryId("", [])).toThrowError(/無法從英文產生 ID/);
  });
});
