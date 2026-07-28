export interface CategoryNodeLike {
  id: string;
  parent_id?: string | null;
  order: number;
}

function childrenByParent<T extends CategoryNodeLike>(
  categories: readonly T[],
): { roots: T[]; children: Map<string, T[]> } {
  const ids = new Set(categories.map((category) => category.id));
  const children = new Map<string, T[]>();
  const roots: T[] = [];
  for (const category of categories) {
    const parentId = category.parent_id ?? null;
    if (parentId && ids.has(parentId)) {
      const bucket = children.get(parentId) ?? [];
      bucket.push(category);
      children.set(parentId, bucket);
    } else {
      roots.push(category);
    }
  }
  const bySiblingOrder = (a: T, b: T) => a.order - b.order || a.id.localeCompare(b.id);
  roots.sort(bySiblingOrder);
  for (const bucket of children.values()) bucket.sort(bySiblingOrder);
  return { roots, children };
}

export function orderedCategoryRows<T extends CategoryNodeLike>(
  categories: readonly T[],
): { category: T; depth: number }[] {
  const { roots, children } = childrenByParent(categories);
  const rows: { category: T; depth: number }[] = [];
  const visit = (category: T, depth: number, guard: Set<string>) => {
    if (guard.has(category.id)) return;
    guard.add(category.id);
    rows.push({ category, depth });
    for (const child of children.get(category.id) ?? []) visit(child, depth + 1, guard);
  };
  const guard = new Set<string>();
  for (const root of roots) visit(root, 0, guard);
  return rows;
}

export function descendantIds(
  categories: readonly CategoryNodeLike[],
  rootId: string,
): Set<string> {
  const { children } = childrenByParent(categories);
  const result = new Set<string>();
  const stack = [...(children.get(rootId) ?? [])];
  while (stack.length > 0) {
    const node = stack.pop()!;
    if (result.has(node.id)) continue;
    result.add(node.id);
    stack.push(...(children.get(node.id) ?? []));
  }
  return result;
}

export function ancestorChain<T extends CategoryNodeLike>(
  categories: readonly T[],
  id: string,
): T[] {
  const byId = new Map(categories.map((category) => [category.id, category]));
  const chain: T[] = [];
  const guard = new Set<string>();
  let cursor: string | null = id;
  while (cursor) {
    const node = byId.get(cursor);
    if (!node || guard.has(cursor)) break;
    guard.add(cursor);
    chain.push(node);
    cursor = node.parent_id ?? null;
  }
  return chain.reverse();
}
