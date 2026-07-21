import { describe, expect, it } from "vitest";
import {
  appendFragment,
  emptyComposition,
  moveFragment,
  reconcileComposedText,
  removeFragment,
  serializeFragments,
  setFragmentText,
  setFragmentWeight,
} from "./compositionState";

const entry = {
  id: "f-1",
  kind: "entry" as const,
  source: { polarity: "positive" as const, categoryId: "quality", entryId: "masterpiece", revision: 1 },
  originalSnapshot: "masterpiece",
  text: "masterpiece",
  weight: "",
};

describe("compositionState", () => {
  it("renders blank weight as raw text and supplied weight as ComfyUI syntax", () => {
    const state = appendFragment(emptyComposition(), entry);
    expect(state.text).toBe("masterpiece");
    expect(state.fragments[0].range).toEqual({ start: 0, end: 11 });
    expect(setFragmentWeight(state, "f-1", "1.2").text).toBe("(masterpiece:1.2)");
  });

  it("keeps fragment operations and rendered text synchronized", () => {
    let state = appendFragment(emptyComposition(), entry);
    state = appendFragment(state, { id: "f-2", kind: "literal", originalSnapshot: "dramatic light", text: "dramatic light", weight: "" });
    expect(state.text).toBe("masterpiece, dramatic light");
    state = setFragmentText(state, "f-1", "masterwork");
    expect(state.text).toBe("masterwork, dramatic light");
    state = moveFragment(state, "f-2", -1);
    expect(state.text).toBe("dramatic light, masterwork");
    expect(removeFragment(state, "f-2").text).toBe("masterwork");
  });

  it("maps a final-text edit back to the affected fragment", () => {
    let state = appendFragment(emptyComposition(), entry);
    state = appendFragment(state, { id: "f-2", kind: "literal", originalSnapshot: "dramatic light", text: "dramatic light", weight: "" });
    const edited = reconcileComposedText(state, "masterwork, dramatic light");
    expect(edited.fragments[0].text).toBe("masterwork");
    expect(edited.text).toBe("masterwork, dramatic light");
    expect(edited.warning).toBeNull();
  });

  it("creates a literal fragment for text inserted at a separator", () => {
    let state = appendFragment(emptyComposition(), entry);
    state = appendFragment(state, { id: "f-2", kind: "literal", originalSnapshot: "sharp focus", text: "sharp focus", weight: "" });
    const edited = reconcileComposedText(state, "masterpiece, cinematic, sharp focus");
    expect(edited.fragments.map((fragment) => fragment.text)).toEqual(["masterpiece", "cinematic", "sharp focus"]);
    expect(edited.warning).toBeNull();
  });

  it("keeps malformed ambiguous text editable and reports a warning", () => {
    let state = appendFragment(emptyComposition(), entry);
    state = appendFragment(state, { id: "f-2", kind: "literal", originalSnapshot: "sharp focus", text: "sharp focus", weight: "" });
    const edited = reconcileComposedText(state, "((broken:1.2), sharp focus");
    expect(edited.text).toBe("((broken:1.2), sharp focus");
    expect(edited.warning).toBeTruthy();
  });

  it("serializes edited library copies as literals without changing the source", () => {
    const edited = setFragmentText(appendFragment(emptyComposition(), entry), "f-1", "masterwork");
    expect(serializeFragments(edited)).toEqual([{ kind: "literal", snapshot: "masterwork", weight: 1, order: 10 }]);
    expect(entry.originalSnapshot).toBe("masterpiece");
  });
});
