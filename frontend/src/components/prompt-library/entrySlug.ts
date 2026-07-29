export function slugifyEntryId(prompt: string, existingIds: readonly string[]): string {
  const base = prompt
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (base === "") {
    throw new Error("無法從英文產生 ID，請確認英文內容");
  }
  const taken = new Set(existingIds);
  if (!taken.has(base)) return base;
  let suffix = 2;
  while (taken.has(`${base}-${suffix}`)) suffix += 1;
  return `${base}-${suffix}`;
}
