import { describe, expect, it, vi } from "vitest";
import {
  appendFragment,
  deserializeFragments,
  emptyComposition,
  materializeRawText,
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

  it("materializes exact visible text as one identity-safe literal without parsing", () => {
    const original = appendFragment(emptyComposition(), entry);
    const state = materializeRawText(original, "  masterpiece,  (unfinished ", sequentialIds("raw"));

    expect(state.text).toBe("  masterpiece,  (unfinished ");
    expect(state.fragments).toMatchObject([{
      id: "raw-1", kind: "literal", displayName: "自訂文字",
      originalSnapshot: "  masterpiece,  (unfinished ", text: "  masterpiece,  (unfinished ", weight: "", directEdit: true,
    }]);
    expect(state.fragments[0].source).toBeUndefined();
    expect(serializeFragments(state)).toEqual([
      { kind: "literal", snapshot: "  masterpiece,  (unfinished ", weight: 1, order: 10 },
    ]);
  });

  it("preserves the direct literal ID across edits and allocates a fresh ID only for the first edit", () => {
    const idFactory = vi.fn(sequentialIds("raw"));
    const structured = appendFragment(emptyComposition(), entry);
    const first = materializeRawText(structured, "first, ", idFactory);
    const second = materializeRawText(first, "second (unfinished", idFactory);

    expect(first.fragments[0].id).toBe("raw-1");
    expect(second.fragments[0].id).toBe("raw-1");
    expect(idFactory).toHaveBeenCalledOnce();
    expect(second.fragments[0].source).toBeUndefined();
  });

  it("keeps blank visible text exactly while serializing empty and resets direct identity after blank", () => {
    const idFactory = vi.fn(sequentialIds("raw"));
    const direct = materializeRawText(emptyComposition(), "literal", idFactory);
    const whitespace = materializeRawText(direct, "  \t ", idFactory);
    const resumed = materializeRawText(whitespace, "literal again", idFactory);

    expect(whitespace).toEqual({ fragments: [], text: "  \t ", warning: null });
    expect(serializeFragments(whitespace)).toEqual([]);
    expect(resumed.fragments[0].id).toBe("raw-2");
  });

  it("serializes edited library copies as literals without changing the source", () => {
    const edited = setFragmentText(appendFragment(emptyComposition(), entry), "f-1", "masterwork");
    expect(serializeFragments(edited)).toEqual([{ kind: "literal", snapshot: "masterwork", weight: 1, order: 10 }]);
    expect(entry.originalSnapshot).toBe("masterpiece");
  });
});
