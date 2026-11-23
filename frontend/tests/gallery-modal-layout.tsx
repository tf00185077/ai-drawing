// Deterministic layout fixture only. Actual-App evidence uses the real Backend.
import React from "react";
import { createRoot } from "react-dom/client";
import Gallery from "../src/pages/Gallery";
import "../src/index.css";

const prompt = "Full prompt remains readable. ".repeat(220);
const filename = "unbroken_metadata_" + "x".repeat(180) + ".safetensors";
const raw = JSON.stringify({items: [{
  id: 4446,
  image_path: "fixture.svg",
  image_url: "data:image/svg+xml," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024"><rect width="1536" height="1024" fill="#334155"/></svg>'
  ),
  checkpoint: filename,
  lora: filename,
  seed: null,
  steps: 32,
  cfg: 5,
  prompt,
  negative_prompt: "negative_" + "y".repeat(240),
  created_at: "2026-11-12T04:14:53",
}], total: 1}).replace('"seed":null', '"seed":1224040850519066617');

window.fetch = async (input) => {
  if (typeof input === "string" && input.startsWith("/api/gallery/?")) {
    return new Response(raw, {status: 200, headers: {"Content-Type": "application/json"}});
  }
  throw new Error("Layout fixture forbids other requests");
};
createRoot(document.getElementById("root")!).render(<Gallery />);
