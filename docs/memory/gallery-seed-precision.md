---
name: gallery-seed-precision
description: "Gallery seeds exceed JavaScript's safe integer range; keep them as strings."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

Seeds in Gallery API responses can exceed `Number.MAX_SAFE_INTEGER`, so `JSON.parse` rounds them and formatting afterwards cannot recover the value.

## Why

A rounded seed reproduces a different image.

## How to apply

Extract the raw seed token before JSON parsing and keep it as a decimal string through display. Test with fixtures above 2^53; wrap long seeds in the image modal.

## Evidence

- `frontend/src/pages/Gallery.tsx`
- `backend/app/schemas/gallery.py`
