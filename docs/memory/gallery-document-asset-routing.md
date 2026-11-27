---
name: gallery-document-asset-routing
description: "The /gallery page and Backend /gallery/... files share a prefix; the Vite proxy must forward only subpaths."
metadata:
  type: project
  curated_on: "2026-11-25"
---

## Context

The React Gallery page lives at `/gallery` and Backend originals are served under `/gallery/...`. A broad Vite proxy on `/gallery` hijacks page loads, breaking direct navigation and reload.

## Why

Widening the proxy looks harmless in in-app navigation but breaks reload and direct entry.

## How to apply

Proxy only non-empty subpaths to the Backend (main uses `^/gallery/(?![?]|$)`); leave `/gallery` and `/gallery/?...` to React. Test direct entry, reload and in-app navigation separately.

## Evidence

- [Vite proxy configuration](../../frontend/vite.config.js).
