import type { GalleryItem, GalleryListResponse } from "../types/api";

// Internal display model only; the Backend/MCP numeric wire contract is unchanged.
export type GalleryDisplayItem = Omit<GalleryItem, "seed"> & { seed: string | null };
type GalleryDisplayList = Omit<GalleryListResponse, "items"> & { items: GalleryDisplayItem[] };

/** Preserve integer seed lexemes BEFORE JSON.parse can round them to binary64. */
export function parseGalleryList(text: string): GalleryDisplayList {
  // Consume whole JSON strings (including escaped quotes), optionally followed
  // by a numeric property value. Prompt contents must never be treated as keys.
  const protectedText = text.replace(
    /("(?:[^"\\]|\\.)*")(\s*:\s*)(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)|"(?:[^"\\]|\\.)*"/g,
    (token, key: string | undefined, separator: string, number: string) => {
      if (key && JSON.parse(key) === "seed") {
        if (!/^-?(?:0|[1-9]\d*)$/.test(number)) throw new Error("Invalid Gallery seed: expected an integer or null");
        return key + separator + JSON.stringify(number);
      }
      return token;
    },
  );
  const data: GalleryDisplayList = JSON.parse(protectedText);
  for (const item of data.items) {
    if (item.seed !== null && (typeof item.seed !== "string" || !/^-?(?:0|[1-9]\d*)$/.test(item.seed))) {
      throw new Error("Invalid Gallery seed: expected an integer or null");
    }
  }
  return data;
}
