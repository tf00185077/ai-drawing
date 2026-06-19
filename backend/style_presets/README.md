# Style Preset Runtime Catalog

This directory stores the structured style preset catalog read by the backend and MCP tools.

`catalog.json` is the runtime source of truth. Each preset `id` must be unique and should match the related note filename and frontmatter in `docs/style-presets/`.

Human notes, creator sources, and experiment logs belong in `docs/style-presets/`; this directory should stay compact, structured, and safe for automated parsing.
