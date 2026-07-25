import { describe, expect, it } from "vitest";
import {
  appendFragment,
  commitRawText,
  deserializeFragments,
  emptyComposition,
  moveFragment,
  removeFragment,
  serializeFragments,
  setFragmentText,
  setFragmentWeight,
  type ApiPromptFragment,
} from "./compositionState";

const entry = {
  id: "f-1",
  kind: "entry" as const,
  displayName: "傑作",
  source: { polarity: "positive" as const, categoryId: "quality", entryId: "masterpiece", revision: 1 },
  originalSnapshot: "masterpiece",
  text: "masterpiece",
  weight: "",
};

function sequentialIds(prefix = "ui") {
  let sequence = 0;
  return () => `${prefix}-${++sequence}`;
}

const savedFragments: ApiPromptFragment[] = [
  {
    kind: "entry",
    ref: { polarity: "positive", category_id: "quality", entry_id: "masterpiece" },
    snapshot: "masterpiece",
    source_revision: 7,
    weight: 1,
    order: 20,
  },
  { kind: "literal", snapshot: "cinematic light", weight: 1.25, order: 10 },
  {
    kind: "entry",
    ref: { polarity: "positive", category_id: "quality", entry_id: "best-quality" },
    snapshot: "best quality",
    source_revision: 3,
    weight: 0.8,
    order: 20,
  },
];

describe("compositionState", () => {
  it("renders blank weight as raw text and supplied weight as ComfyUI syntax", () => {
    const state = appendFragment(emptyComposition(), entry);
    expect(state.text).toBe("masterpiece");
    expect(state.fragments[0].range).toEqual({ start: 0, end: 11 });
    expect(setFragmentWeight(state, "f-1", "1.2").text).toBe("(masterpiece:1.2)");
  });

  it("keeps fragment operations and rendered text synchronized", () => {
    let state = appendFragment(emptyComposition(), entry);
    state = appendFragment(state, { id: "f-2", kind: "literal", displayName: "自訂文字", originalSnapshot: "dramatic light", text: "dramatic light", weight: "" });
    expect(state.text).toBe("masterpiece, dramatic light");
    state = setFragmentText(state, "f-1", "masterwork");
    expect(state.text).toBe("masterwork, dramatic light");
    state = moveFragment(state, "f-2", -1);
    expect(state.text).toBe("dramatic light, masterwork");
    expect(removeFragment(state, "f-2").text).toBe("masterwork");
  });

  it("deserializes saved fragments in stable order with refs, revisions, weights, and names", () => {
    const state = deserializeFragments(
      savedFragments,
      "positive",
      sequentialIds(),
      new Map([["positive/quality/masterpiece", "傑作"]]),
    );

    expect(state.fragments.map((fragment) => fragment.id)).toEqual(["ui-1", "ui-2", "ui-3"]);
    expect(state.fragments).toMatchObject([
      {
        kind: "literal",
        displayName: "自訂文字",
        originalSnapshot: "cinematic light",
        text: "cinematic light",
        weight: "1.25",
      },
      {
        kind: "entry",
        displayName: "傑作",
        source: { polarity: "positive", categoryId: "quality", entryId: "masterpiece", revision: 7 },
        originalSnapshot: "masterpiece",
        text: "masterpiece",
        weight: "",
      },
      {
        kind: "entry",
        displayName: "best-quality",
        source: { polarity: "positive", categoryId: "quality", entryId: "best-quality", revision: 3 },
        originalSnapshot: "best quality",
        text: "best quality",
        weight: "0.8",
      },
    ]);
    expect(state.fragments[0]).not.toHaveProperty("source");
    expect(state.text).toBe("(cinematic light:1.25), masterpiece, (best quality:0.8)");
  });

  it("preserves source polarity and uses fresh IDs on every load", () => {
    const api: ApiPromptFragment[] = [{
      kind: "entry",
      ref: { polarity: "positive", category_id: "quality", entry_id: "masterpiece" },
      snapshot: "masterpiece",
      source_revision: 4,
      weight: 1,
      order: 10,
    }];
    const ids = sequentialIds("fresh");

    const first = deserializeFragments(api, "negative", ids, new Map());
    const second = deserializeFragments(api, "negative", ids, new Map());

    expect(first.fragments[0].id).toBe("fresh-1");
    expect(second.fragments[0].id).toBe("fresh-2");
    expect(first.fragments[0].source?.polarity).toBe("positive");
  });

  it("keeps a trailing-comma raw draft outside canonical state until commit", () => {
    const original = appendFragment(emptyComposition(), entry);
    const rawDraft = "masterpiece, ";

    expect(original.text).toBe("masterpiece");
    expect(original.fragments).toHaveLength(1);
    expect(rawDraft).not.toBe(original.text);
  });

  it("commits raw text by replacing every canonical fragment with fresh literals", () => {
    let original = appendFragment(emptyComposition(), entry);
    original = appendFragment(original, {
      id: "old-literal",
      kind: "literal",
      displayName: "自訂文字",
      originalSnapshot: "sharp focus",
      text: "sharp focus",
      weight: "",
    });

    const result = commitRawText(original, "masterpiece, cinematic, sharp focus", sequentialIds("commit"));

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("expected successful commit");
    expect(result.state.fragments.map((fragment) => fragment.id)).toEqual(["commit-1", "commit-2", "commit-3"]);
    expect(result.state.fragments.map((fragment) => fragment.text)).toEqual(["masterpiece", "cinematic", "sharp focus"]);
    expect(result.state.fragments.every((fragment) => fragment.kind === "literal" && !fragment.source)).toBe(true);
    expect(result.state.fragments.every((fragment) => fragment.displayName === "自訂文字")).toBe(true);
  });

  it("does not retain old refs after middle insertion or deletion", () => {
    let original = appendFragment(emptyComposition(), entry);
    original = appendFragment(original, {
      id: "second-entry",
      kind: "entry",
      displayName: "清晰",
      source: { polarity: "positive", categoryId: "quality", entryId: "sharp", revision: 2 },
      originalSnapshot: "sharp focus",
      text: "sharp focus",
      weight: "",
    });

    const inserted = commitRawText(original, "masterpiece, cinematic, sharp focus", sequentialIds());
    const deleted = commitRawText(original, "sharp focus", sequentialIds("delete"));

    expect(inserted.ok && inserted.state.fragments.every((fragment) => fragment.source === undefined)).toBe(true);
    expect(deleted.ok && deleted.state.fragments).toMatchObject([{ kind: "literal", text: "sharp focus" }]);
    expect(deleted.ok && deleted.state.fragments[0].source).toBeUndefined();
  });

  it("splits only top-level commas and parses a valid nested weighted fragment", () => {
    const result = commitRawText(emptyComposition(), "(portrait, close-up), (lighting (warm, soft):1.4), final", sequentialIds());

    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("expected successful commit");
    expect(result.state.fragments.map(({ text, weight }) => ({ text, weight }))).toEqual([
      { text: "(portrait, close-up)", weight: "" },
      { text: "lighting (warm, soft)", weight: "1.4" },
      { text: "final", weight: "" },
    ]);
  });

  it("rejects malformed parentheses without changing the original state object", () => {
    const original = appendFragment(emptyComposition(), entry);
    const result = commitRawText(original, "((broken:1.2), sharp focus", sequentialIds());

    expect(result.ok).toBe(false);
    if ("error" in result) {
      expect(result.state).toBe(original);
      expect(result.error).toContain("括號");
    } else {
      throw new Error("expected failed commit");
    }
  });

  it.each([
    ["(prompt:abc)", "數字"],
    ["(prompt:NaN)", "數字"],
    ["(prompt:0x1)", "十進位"],
    ["(prompt:0b1)", "十進位"],
    ["(prompt:+1)", "十進位"],
    ["(prompt:1e0)", "十進位"],
    ["(prompt:0)", "大於 0"],
    ["(prompt:-0.1)", "大於 0"],
    ["(prompt:2.01)", "不大於 2"],
  ])("rejects invalid weight in %s and leaves the original unchanged", (rawText, message) => {
    const original = appendFragment(emptyComposition(), entry);
    const result = commitRawText(original, rawText, sequentialIds());

    expect(result.ok).toBe(false);
    if ("error" in result) {
      expect(result.state).toBe(original);
      expect(result.error).toContain(message);
    } else {
      throw new Error("expected failed commit");
    }
  });

  it("commits empty raw text as an empty canonical state", () => {
    const result = commitRawText(appendFragment(emptyComposition(), entry), "   ", sequentialIds());

    expect(result).toEqual({ ok: true, state: emptyComposition() });
  });

  it("serializes edited library copies as literals without changing the source", () => {
    const edited = setFragmentText(appendFragment(emptyComposition(), entry), "f-1", "masterwork");
    expect(serializeFragments(edited)).toEqual([{ kind: "literal", snapshot: "masterwork", weight: 1, order: 10 }]);
    expect(entry.originalSnapshot).toBe("masterpiece");
  });
});
