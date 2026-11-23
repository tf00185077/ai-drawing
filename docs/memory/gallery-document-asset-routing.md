---
name: gallery-document-asset-routing
description: "Distinguish Gallery page documents from original-image paths when configuring or reviewing the Vite development proxy."
metadata:
  type: project
  curated_on: "2026-11-11"
---

## Context

The React Gallery page and Backend original images share the `/gallery` path family. In the reviewed development setup, a broad Vite proxy intercepted page documents and caused redirects or missing-page responses; the isolated correction restricted proxy matching to nonempty asset subpaths.

## Why

Successful menu navigation or image retrieval alone can hide a broken direct-entry or reload path.

## How to apply

For Gallery development routing, leave `/gallery` and `/gallery/`, including query strings, with the React application while forwarding original-image subpaths to the Backend. Verify direct navigation, reload and menu navigation separately, then confirm that the actual original-image response retains its expected identity and bytes. A page response and an asset response prove different parts of this route.

Recheck the pinned configuration before reusing the correction. The retained HTTP/browser evidence applies to the task-owned Vite development server; it does not certify Compose or another managed deployment.

## Evidence

- [Vite development proxy](../../frontend/vite.config.js) and [React routes](../../frontend/src/App.tsx) — inspect both sides of the shared path family.
- [Development setup authority](../setup-guide.md#manual-development-optional) — canonical environment and port scope.
- [Retained Gallery repair and independent review](../PROGRESS.md#m1--current-checkpoint-continuation) — routes to the direct-entry/reload counterexamples, corrected routing and same-original browser verification.
