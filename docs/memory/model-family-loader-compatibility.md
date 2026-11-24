---
name: model-family-loader-compatibility
description: "Which loader each model family needs; filenames do not prove compatibility or installation."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

A checkpoint loader is not compatible with every family: split Anima, Qwen and Wan models need their own diffusion-model, encoder and VAE loaders. Anima graphs use `LoraLoaderModelOnly`, which consumes model strength only, and a `CLIPLoader` of type `qwen_image`; `LoraLoader` patches model and CLIP. Pose, subject, mask, first/last frame and audio inputs are not interchangeable between graphs. Ordinary generation goes straight to ComfyUI `/prompt` with no preflight, so missing models, nodes and capacity errors come back from ComfyUI.

## Why

Phase 2 selects workflows from chosen resources; matching by filename or a generic checkpoint loader produces graphs that fail in ComfyUI.

## How to apply

Read the loader inputs in the chosen graph and its `.meta.json` before matching resources. Confirm the files exist on the target host; a filename or a historical path is not proof of installation, version or license.

## Evidence

- `backend/workflows/` graphs and `.meta.json`
- `backend/app/core/workflow_manifest.py`
