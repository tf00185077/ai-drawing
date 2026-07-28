import { describe, expect, it } from "vitest";
import { ancestorChain, childCategories, descendantIds, orderedCategoryRows } from "./categoryTree";

const cats = [
  { id: "clothing", parent_id: null, order: 70 },
  { id: "clothing-top", parent_id: "clothing", order: 10 },
  { id: "clothing-bottom", parent_id: "clothing", order: 20 },
  { id: "quality", parent_id: null, order: 10 },
];

describe("orderedCategoryRows", () => {
  it("returns pre-order rows with depth, roots by order then children by order", () => {
    expect(orderedCategoryRows(cats).map((r) => [r.category.id, r.depth])).toEqual([
      ["quality", 0],
      ["clothing", 0],
      ["clothing-top", 1],
      ["clothing-bottom", 1],
    ]);
  });
  it("treats a dangling parent as a root", () => {
    const rows = orderedCategoryRows([{ id: "x", parent_id: "ghost", order: 5 }]);
    expect(rows).toEqual([{ category: { id: "x", parent_id: "ghost", order: 5 }, depth: 0 }]);
  });
});

describe("descendantIds", () => {
  it("collects all descendants excluding the root itself", () => {
    expect([...descendantIds(cats, "clothing")].sort()).toEqual(["clothing-bottom", "clothing-top"]);
    expect([...descendantIds(cats, "quality")]).toEqual([]);
  });
});

describe("ancestorChain", () => {
  it("returns root..self", () => {
    expect(ancestorChain(cats, "clothing-top").map((c) => c.id)).toEqual(["clothing", "clothing-top"]);
    expect(ancestorChain(cats, "quality").map((c) => c.id)).toEqual(["quality"]);
  });
  it("stops on a cycle without hanging", () => {
    const cyclic = [
      { id: "a", parent_id: "b", order: 1 },
      { id: "b", parent_id: "a", order: 1 },
    ];
    const chain = ancestorChain(cyclic, "a").map((c) => c.id);
    expect(chain[chain.length - 1]).toBe("a");
    expect(chain.length).toBeLessThanOrEqual(2);
  });
});

describe("childCategories", () => {
  const cats = [
    { id: "clothing", parent_id: null, order: 70 },
    { id: "clothing-top", parent_id: "clothing", order: 10 },
    { id: "clothing-bottom", parent_id: "clothing", order: 20 },
    { id: "quality", parent_id: null, order: 10 },
    { id: "dangling", parent_id: "ghost", order: 5 },
  ];
  it("returns roots for null parent sorted by order then id, incl dangling-as-root", () => {
    // roots by order: dangling(5), quality(10), clothing(70)
    expect(childCategories(cats, null).map((c) => c.id)).toEqual(["dangling", "quality", "clothing"]);
  });
  it("returns direct children of a parent ordered by order then id", () => {
    expect(childCategories(cats, "clothing").map((c) => c.id)).toEqual(["clothing-top", "clothing-bottom"]);
  });
  it("returns [] for a leaf", () => {
    expect(childCategories(cats, "quality")).toEqual([]);
  });
});
