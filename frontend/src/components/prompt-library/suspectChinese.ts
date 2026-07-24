const CJK = /[㐀-䶿一-鿿]/;

export function hasCjk(text: string): boolean {
  return CJK.test(text ?? "");
}

function normalize(text: string): string {
  return (text ?? "").trim().replace(/\s+/g, " ").toLowerCase();
}

export type SuspectReason = "missing_chinese" | "echoes_prompt";

export function suspectReason(nameZh: string, prompt?: string): SuspectReason | null {
  if (prompt && normalize(nameZh) === normalize(prompt)) return "echoes_prompt";
  if (!hasCjk(nameZh)) return "missing_chinese";
  return null;
}
