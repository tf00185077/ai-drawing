---
name: gallery-document-asset-routing
description: The /gallery page route and Backend original-image paths share a prefix; the Vite dev proxy must only forward asset subpaths.
metadata:
  type: project
---

The React Gallery page lives at `/gallery` and Backend originals are served under `/gallery/...`. A broad Vite proxy on `/gallery` hijacks page loads, breaking direct navigation and reload.

**How to apply:** proxy only non-empty subpaths (`/gallery/<something>`) to the Backend; leave `/gallery` and `/gallery/?...` to React. Test direct entry, reload and in-app navigation separately.

Source: `frontend/vite.config.js`. Main uses the narrow pattern `^/gallery/(?![?]|$)`.
