import { describe, expect, it, vi } from "vitest";
import {
  appendFragment,
  appendLiteralText,
  appendFragmentsDeduped,
  blankSegmentMessage,
  blankSegmentPreflight,
  buildLiteralLabelIndex,
  deserializeFragments,
  distinctCategoriesOf,
  emptyComposition,
  materializeRawText,
  moveFragment,
  removeFragment,
  resolveLiteralDisplayLabel,
  serializeFragments,
  sortFragmentsByRecommendation,
  groupFragmentsByCategory,
  setFragmentText,
  setFragmentWeight,
  LITERAL_GROUP_KEY,
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

describe("sortFragmentsByRecommendation", () => {
  const ids = sequentialIds("s");
  const entryFrag = (categoryId: string, entryId: string) => ({
    id: ids(),
    kind: "entry" as const,
    displayName: entryId,
    source: { polarity: "positive" as const, categoryId, entryId, revision: 1 },
    sourceSnapshotRaw: entryId,
    snapshotRaw: entryId,
    weight: "",
  });

  // 分類 rank：environment=20, quality=10；entry order 忽略時同 rank
  const rankOf = (fragment: { kind: string; source?: { categoryId: string } }): number => {
    if (fragment.kind !== "entry" || !fragment.source) return Number.POSITIVE_INFINITY;
    return { "quality-ratings": 10, environment: 20, actions: 60 }[fragment.source.categoryId] ?? Infinity;
  };

  it("sorts entries by category rank and pushes literals last, stably", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("actions", "hug"));
    state = appendLiteralText(state, "custom tag", ids);
    state = appendFragment(state, entryFrag("quality-ratings", "masterpiece"));
    state = appendFragment(state, entryFrag("environment", "rooftop"));

    const sorted = sortFragmentsByRecommendation(state, rankOf);

    expect(sorted.fragments.map((fragment) => fragment.snapshotRaw)).toEqual([
      "masterpiece",
      "rooftop",
      "hug",
      "custom tag",
    ]);
    // 輸出字串仍是逗號串接、與片段順序一致
    expect(sorted.text).toBe("masterpiece,rooftop,hug,custom tag");
  });

  it("keeps original order among same-rank fragments (stable)", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("actions", "first"));
    state = appendFragment(state, entryFrag("actions", "second"));
    const sorted = sortFragmentsByRecommendation(state, rankOf);
    expect(sorted.fragments.map((fragment) => fragment.snapshotRaw)).toEqual(["first", "second"]);
  });
});

describe("groupFragmentsByCategory", () => {
  const ids = sequentialIds("g");
  const entryFrag = (categoryId: string, entryId: string) => ({
    id: ids(),
    kind: "entry" as const,
    displayName: entryId,
    source: { polarity: "positive" as const, categoryId, entryId, revision: 1 },
    sourceSnapshotRaw: entryId,
    snapshotRaw: entryId,
    weight: "",
  });
  const info = (fragment: { kind: string; source?: { categoryId: string } }) => {
    if (fragment.kind !== "entry" || !fragment.source) return null;
    const meta: Record<string, { displayName: string; order: number }> = {
      "quality-ratings": { displayName: "品質與分級", order: 10 },
      environment: { displayName: "場景與氛圍", order: 20 },
    };
    const found = meta[fragment.source.categoryId];
    return found ? { key: fragment.source.categoryId, ...found } : null;
  };

  it("groups fragments into contiguous runs preserving global order", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("environment", "rooftop"));
    state = appendLiteralText(state, "custom", ids);
    state = appendFragment(state, entryFrag("quality-ratings", "masterpiece"));
    state = appendFragment(state, entryFrag("environment", "sunset"));

    const groups = groupFragmentsByCategory(state.fragments, info);

    // contiguous runs in global order — environment appears twice, not merged or re-sorted
    expect(groups.map((group) => group.displayName)).toEqual([
      "場景與氛圍",
      "自訂文字",
      "品質與分級",
      "場景與氛圍",
    ]);
    expect(groups[0].fragments.map((fragment) => fragment.snapshotRaw)).toEqual(["rooftop"]);
    expect(groups[1].key).toBe("__literal__");
    expect(groups[3].fragments.map((fragment) => fragment.snapshotRaw)).toEqual(["sunset"]);
  });

  it("merges adjacent same-category fragments into one run", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("quality-ratings", "a"));
    state = appendFragment(state, entryFrag("quality-ratings", "b"));
    state = appendFragment(state, entryFrag("environment", "c"));
    const groups = groupFragmentsByCategory(state.fragments, info);
    expect(groups.map((group) => group.key)).toEqual(["quality-ratings", "environment"]);
    expect(groups[0].fragments.map((fragment) => fragment.snapshotRaw)).toEqual(["a", "b"]);
  });
});

describe("appendFragmentsDeduped", () => {
  const ids = sequentialIds("ap");
  const entryFrag = (categoryId: string, entryId: string) => ({
    id: ids(),
    kind: "entry" as const,
    displayName: entryId,
    source: { polarity: "positive" as const, categoryId, entryId, revision: 1 },
    sourceSnapshotRaw: entryId,
    snapshotRaw: entryId,
    weight: "",
  });

  it("appends only non-duplicate entry refs and keeps the single comma-joined text", () => {
    let target = emptyComposition();
    target = appendFragment(target, entryFrag("quality-ratings", "masterpiece"));
    const incoming = [
      entryFrag("quality-ratings", "masterpiece"), // duplicate ref → skipped
      entryFrag("environment", "rooftop"), // new → kept
    ];
    const result = appendFragmentsDeduped(target, incoming as never);
    expect(result.fragments.map((f) => f.snapshotRaw)).toEqual(["masterpiece", "rooftop"]);
    expect(result.text).toBe("masterpiece,rooftop");
  });

  it("always appends literals and dedupes duplicates within the incoming batch", () => {
    let target = emptyComposition();
    target = appendLiteralText(target, "solo", ids);
    const incoming = [
      { id: ids(), kind: "literal" as const, displayName: "自訂文字", snapshotRaw: "solo", sourceSnapshotRaw: "solo", weight: "" },
      entryFrag("environment", "rooftop"),
      entryFrag("environment", "rooftop"), // duplicate within batch → skipped
    ];
    const result = appendFragmentsDeduped(target, incoming as never);
    // literal "solo" appended again (literals are not deduped); rooftop appears once
    expect(result.fragments.map((f) => f.snapshotRaw)).toEqual(["solo", "solo", "rooftop"]);
  });

  it("returns the same target when nothing new is added", () => {
    let target = emptyComposition();
    target = appendFragment(target, entryFrag("quality-ratings", "a"));
    const result = appendFragmentsDeduped(target, [entryFrag("quality-ratings", "a")] as never);
    expect(result).toBe(target);
  });
});

describe("distinctCategoriesOf", () => {
  const ids = sequentialIds("dc");
  const entryFrag = (categoryId: string, entryId: string) => ({
    id: ids(),
    kind: "entry" as const,
    displayName: entryId,
    source: { polarity: "positive" as const, categoryId, entryId, revision: 1 },
    sourceSnapshotRaw: entryId,
    snapshotRaw: entryId,
    weight: "",
  });
  const info = (fragment: { kind: string; source?: { categoryId: string } }) => {
    if (fragment.kind !== "entry" || !fragment.source) return null;
    const meta: Record<string, { displayName: string; order: number }> = {
      "quality-ratings": { displayName: "品質與分級", order: 10 },
      environment: { displayName: "場景與氛圍", order: 20 },
    };
    const found = meta[fragment.source.categoryId];
    return found ? { key: fragment.source.categoryId, ...found } : null;
  };

  it("returns distinct categories ordered by order, literals last", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("environment", "rooftop"));
    state = appendLiteralText(state, "custom", ids);
    state = appendFragment(state, entryFrag("quality-ratings", "masterpiece"));
    state = appendFragment(state, entryFrag("environment", "sunset"));

    const categories = distinctCategoriesOf(state.fragments, info);
    expect(categories.map((c) => c.key)).toEqual(["quality-ratings", "environment", LITERAL_GROUP_KEY]);
    expect(categories[2].displayName).toBe("自訂文字");
  });

  it("omits the literal entry when there are no literals", () => {
    let state = emptyComposition();
    state = appendFragment(state, entryFrag("quality-ratings", "a"));
    const categories = distinctCategoriesOf(state.fragments, info);
    expect(categories.map((c) => c.key)).toEqual(["quality-ratings"]);
  });
});
