---
name: gallery-seed-precision
description: Generation seeds exceed JavaScript's safe integer range; parse them as strings in the Gallery.
metadata:
  type: project
---

Seeds in Gallery API responses can exceed `Number.MAX_SAFE_INTEGER`, so `JSON.parse` rounds them. Formatting afterwards cannot recover the value.

**How to apply:** extract the raw seed token before JSON parsing and keep it as a decimal string through display. Test with fixtures above 2^53. Long seeds also need wrapping in the image modal so the full value stays visible.

Source: `frontend/src/pages/Gallery.tsx`, `backend/app/schemas/gallery.py`.
