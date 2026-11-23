---
name: gallery-seed-precision
description: "Preserve raw Gallery seed integers through JSON parsing and verify the full value is visible in the initial modal layout."
metadata:
  type: project
  curated_on: "2026-11-13"
---

## Context

Gallery's numeric API can carry integer seeds that JavaScript `Number` cannot represent exactly. The reviewed isolated repair protected seed integer tokens before JSON parsing and retained decimal strings in the internal display model, leaving the public numeric contract and ID-based rerun unchanged.

An exact decimal string can still overflow its initial modal column when the image and unbroken metadata compete for width.

## Why

A rounded or partly hidden display prevents the reader from inspecting recorded generation parameters even when the correct original image is shown. Formatting an already rounded number cannot recover the original token; parsing fidelity alone cannot establish readable layout.

## How to apply

When changing Gallery parsing or display, preserve the raw seed integer token before conversion to `Number`, then retain its decimal string through list selection and rendering. Use JSON-aware handling that leaves prompt strings and unrelated fields intact and preserves null. Check raw-token fixtures beyond the safe-integer range and compare the displayed value with the original response token; fixtures constructed from an already rounded number cannot establish fidelity.

For modal layout changes, verify every seed text fragment is visible at the initial horizontal scroll position. Include long unbroken metadata, full prompts, the actual image aspect ratio and a vertical scrollbar, checking both sides of responsive breakpoints. The reviewed correction bounded columns and image width and wrapped metadata; retain full text and usable controls after vertical scrolling rather than hiding overflow or shrinking values. Keep synthetic layout fixtures distinct from actual same-original retrieval.

Recheck the pinned source and deployed contract before reuse. The isolated parser and layout repairs establish fidelity within their reviewed scopes, not canonical adoption or generation support for every fixture value.

## Evidence

- [Gallery response and rerun schemas](../../backend/app/schemas/gallery.py) — numeric seed/null and ID-based rerun contracts.
- [Canonical Gallery consumer](../../frontend/src/pages/Gallery.tsx) — inspect the current response parser and seed rendering before assuming the repair is present.
- [Retained Gallery repairs and independent reviews](../PROGRESS.md#m1--current-checkpoint-continuation) — routes to the raw-token regressions, initial-layout counterexample and bounded correction, and actual same-original application verification.
