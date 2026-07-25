import { describe, expect, it, vi } from "vitest";
import {
  appendFragment,
  appendLiteralText,
  blankSegmentMessage,
  blankSegmentPreflight,
  buildLiteralLabelIndex,
  deserializeFragments,
  emptyComposition,
  materializeRawText,
  moveFragment,
  removeFragment,
  resolveLiteralDisplayLabel,
  serializeFragments,
  setFragmentText,
  setFragmentWeight,
  type ApiPromptFragment,
} from "./compositionState";

const entry = {
  id: "f-1",
  kind: "entry" as const,
  displayName: "傑作",
  source: {
    polarity: "positive" as const,
    categoryId: "quality",
    entryId: "masterpiece",
    revision: 1,
  },
  sourceSnapshotRaw: "masterpiece",
  snapshotRaw: "masterpiece",
  weight: "",
};

function sequentialIds(prefix = "ui") {
  let sequence = 0;
  return () => `${prefix}-${++sequence}`;
}

describe("comma-atomic compositionState", () => {
  it("renders exact snapshots and joins with one literal comma", () => {
    let state = appendFragment(emptyComposition(), entry);
    state = appendFragment(state, {
      id: "literal",
      kind: "literal",
      snapshotRaw: " detail ",
      sourceSnapshotRaw: " detail ",
      weight: "1.2",
    });

    expect(state.text).toBe("masterpiece,( detail :1.2)");
    expect(state.fragments.map((item) => item.renderedRaw)).toEqual([
      "masterpiece",
      "( detail :1.2)",
    ]);
    expect(state.fragments[1].range).toEqual({ start: 12, end: 26 });
  });

  it("splits every U+002C and preserves leading trailing consecutive empties", () => {
    const state = materializeRawText(
      emptyComposition(),
      "a,,b,",
      sequentialIds(),
    );

    expect(state.fragments.map((item) => item.snapshotRaw)).toEqual([
      "a",
      "",
      "b",
      "",
    ]);
    expect(state.text).toBe("a,,b,");
    expect(serializeFragments(state).map((item) => item.snapshot)).toEqual([
      "a",
      "",
      "b",
      "",
    ]);
  });

  it("does not protect quoted parenthesized weighted commas or split U+FF0C", () => {
    const ids = sequentialIds();
    expect(
      materializeRawText(emptyComposition(), '"a,b"', ids).fragments.map(
        (item) => item.snapshotRaw,
      ),
    ).toEqual(['"a', 'b"']);
    expect(
      materializeRawText(emptyComposition(), "(a,b:1.2)", ids).fragments.map(
        (item) => item.snapshotRaw,
      ),
    ).toEqual(["(a", "b:1.2)"]);
    expect(
      materializeRawText(emptyComposition(), "a，b", ids).fragments.map(
        (item) => item.snapshotRaw,
      ),
    ).toEqual(["a，b"]);
  });

  it("preserves unchanged weighted refs and demotes changed rendered atoms without parsing", () => {
    const api: ApiPromptFragment[] = [
      {
        kind: "entry",
        ref: {
          polarity: "positive",
          category_id: "quality",
          entry_id: "detail",
        },
        snapshot: "detail",
        source_revision: 7,
        weight: 1.2,
        order: 10,
      },
      { kind: "literal", snapshot: "light", weight: 1, order: 20 },
    ];
    const loaded = deserializeFragments(
      api,
      "positive",
      sequentialIds(),
      new Map([["positive/quality/detail", "細節"]]),
    );

    const otherChanged = materializeRawText(
      loaded,
      "(detail:1.2),new light",
      sequentialIds("edit"),
    );
    expect(otherChanged.fragments[0]).toMatchObject({
      id: loaded.fragments[0].id,
      kind: "entry",
      snapshotRaw: "detail",
      weight: "1.2",
      source: { entryId: "detail", revision: 7 },
    });

    const weightTextChanged = materializeRawText(
      loaded,
      "(detail:1.3),light",
      sequentialIds("demoted"),
    );
    expect(weightTextChanged.fragments[0]).toMatchObject({
      kind: "literal",
      snapshotRaw: "(detail:1.3)",
      weight: "",
      renderedRaw: "(detail:1.3)",
    });
    expect(weightTextChanged.fragments[0].source).toBeUndefined();
  });

  it("uses common prefix and suffix so insertion never shifts refs", () => {
    let state = appendFragment(emptyComposition(), entry);
    state = appendFragment(state, {
      ...entry,
      id: "f-2",
      source: { ...entry.source, entryId: "best-quality" },
      snapshotRaw: "best quality",
      sourceSnapshotRaw: "best quality",
      displayName: "最佳品質",
    });
    const inserted = materializeRawText(
      state,
      "masterpiece,new,best quality",
      sequentialIds("new"),
    );

    expect(inserted.fragments.map((item) => item.id)).toEqual([
      "f-1",
      "new-1",
      "f-2",
    ]);
    expect(inserted.fragments[1].kind).toBe("literal");
    expect(inserted.fragments[2].source?.entryId).toBe("best-quality");
  });

  it("card content demotes provenance while weight-only edit preserves it", () => {
    const state = appendFragment(emptyComposition(), entry);
    const weighted = setFragmentWeight(state, "f-1", "1.3");
    expect(weighted.fragments[0].source?.entryId).toBe("masterpiece");
    expect(weighted.fragments[0].snapshotRaw).toBe("masterpiece");

    const edited = setFragmentText(weighted, "f-1", "masterwork");
    expect(edited.fragments[0].kind).toBe("literal");
    expect(edited.fragments[0].source).toBeUndefined();
    expect(edited.fragments[0].weight).toBe("1.3");
    expect(edited.text).toBe("(masterwork:1.3)");
  });

  it("treats commas entered through a card edit as atomic boundaries", () => {
    const state = appendFragment(emptyComposition(), entry);

    const edited = setFragmentText(
      state,
      "f-1",
      "a,,b",
      (value) => value || "自訂文字",
      sequentialIds("card"),
    );

    expect(edited.fragments.map((item) => item.snapshotRaw)).toEqual([
      "a",
      "",
      "b",
    ]);
    expect(edited.fragments.every((item) => item.kind === "literal")).toBe(true);
    expect(edited.text).toBe("a,,b");
    expect(blankSegmentPreflight(edited, emptyComposition())).toEqual([
      { polarity: "positive", position: 2 },
    ]);
  });

  it("does not discard an existing empty card when free text is appended", () => {
    const emptyCard = setFragmentText(
      appendFragment(emptyComposition(), {
        id: "f-1",
        kind: "literal",
        snapshotRaw: "present",
        sourceSnapshotRaw: "present",
        weight: "",
      }),
      "f-1",
      "",
    );

    const appended = appendLiteralText(
      emptyCard,
      "next",
      () => "f-2",
    );

    expect(appended.text).toBe(",next");
    expect(appended.fragments.map((fragment) => fragment.snapshotRaw)).toEqual([
      "",
      "next",
    ]);
    expect(blankSegmentPreflight(appended, emptyComposition())).toEqual([
      { polarity: "positive", position: 1 },
    ]);
  });

  it("canonicalizes weight rendering and serialization to Backend precision", () => {
    const state = appendFragment(emptyComposition(), entry);

    const weighted = setFragmentWeight(state, "f-1", "1.2345");

    expect(weighted.text).toBe("(masterpiece:1.234)");
    expect(weighted.fragments[0].renderedRaw).toBe("(masterpiece:1.234)");
    expect(serializeFragments(weighted)[0].weight).toBe(1.234);
  });

  it("counts moves and deletes empty slots without filtering", () => {
    const original = materializeRawText(
      emptyComposition(),
      "a,,b",
      sequentialIds(),
    );
    const emptyId = original.fragments[1].id;
    const moved = moveFragment(original, emptyId, 1);
    expect(moved.fragments.map((item) => item.snapshotRaw)).toEqual([
      "a",
      "b",
      "",
    ]);
    expect(moved.text).toBe("a,b,");
    expect(removeFragment(moved, emptyId).text).toBe("a,b");
  });

  it("represents an empty lane as zero segments but whitespace as one invalid segment", () => {
    expect(materializeRawText(emptyComposition(), "", sequentialIds())).toEqual(
      emptyComposition(),
    );
    const whitespace = materializeRawText(
      emptyComposition(),
      " \t ",
      sequentialIds(),
    );
    expect(whitespace.fragments).toHaveLength(1);
    expect(whitespace.fragments[0].snapshotRaw).toBe(" \t ");
    expect(blankSegmentPreflight(whitespace, emptyComposition())).toEqual([
      { polarity: "positive", position: 1 },
    ]);
  });

  it("uses deterministic unique labels without inventing refs", () => {
    const entries = [
      {
        id: "masterpiece",
        name_zh: "傑作",
        description_zh: "",
        prompt: " masterpiece ",
        aliases: [],
        keywords: [],
        order: 10,
        revision: 1,
        archived: false,
      },
      {
        id: "duplicate-a",
        name_zh: "細節甲",
        description_zh: "",
        prompt: "detail",
        aliases: [],
        keywords: [],
        order: 20,
        revision: 1,
        archived: false,
      },
      {
        id: "duplicate-b",
        name_zh: "細節乙",
        description_zh: "",
        prompt: "DETAIL",
        aliases: [],
        keywords: [],
        order: 30,
        revision: 1,
        archived: false,
      },
    ];
    const index = buildLiteralLabelIndex(entries);
    expect(resolveLiteralDisplayLabel("MASTERPIECE", index)).toBe("傑作");
    expect(resolveLiteralDisplayLabel(" detail ", index)).toBe("自訂文字");
    expect(resolveLiteralDisplayLabel("", index)).toBe("自訂文字");

    const typed = materializeRawText(
      emptyComposition(),
      "MASTERPIECE",
      sequentialIds(),
      (value) => resolveLiteralDisplayLabel(value, index),
    );
    expect(typed.fragments[0]).toMatchObject({
      kind: "literal",
      displayName: "傑作",
    });
    expect(serializeFragments(typed)[0]).not.toHaveProperty("ref");
    expect(serializeFragments(typed)[0]).not.toHaveProperty("displayName");
  });

  it("reports every polarity and 1-based blank position", () => {
    const positive = materializeRawText(
      emptyComposition(),
      "a,,b,",
      sequentialIds("p"),
    );
    const negative = materializeRawText(
      emptyComposition(),
      ",bad, ",
      sequentialIds("n"),
    );
    const invalid = blankSegmentPreflight(positive, negative);

    expect(invalid).toEqual([
      { polarity: "positive", position: 2 },
      { polarity: "positive", position: 4 },
      { polarity: "negative", position: 1 },
      { polarity: "negative", position: 3 },
    ]);
    expect(blankSegmentMessage(invalid)).toBe(
      "正向第 2、4 段；負向第 1、3 段：每個 ASCII 逗號都會建立一個 prompt；請填入內容或移除該空白段。",
    );
  });

  it("retains a literal UI id for a one-to-one edit only", () => {
    const ids = vi.fn(sequentialIds("raw"));
    const first = materializeRawText(emptyComposition(), "first", ids);
    const second = materializeRawText(first, "second", ids);
    expect(second.fragments[0].id).toBe(first.fragments[0].id);
    expect(ids).toHaveBeenCalledOnce();
  });
});
