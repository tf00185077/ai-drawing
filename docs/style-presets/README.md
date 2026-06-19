# Style Presets

Human-facing notes for creator/style recipes live here. The runtime catalog lives at `backend/style_presets/catalog.json`.

Rules:

- Use the same stable kebab-case `preset_id` in the catalog, note frontmatter, and note filename.
- Keep creator/source context, trial notes, and example prompts in Markdown.
- Keep machine-readable resource names and generation defaults in `backend/style_presets/catalog.json`.

Suggested layout — one Markdown note per preset, self-contained:

```text
docs/style-presets/
├── _template.md
└── creator-a.md
```

Each note already carries its own resource pairing, source notes, and experiment
log (see `_template.md`), so checkpoint/LoRA context lives inline in the preset
note. Only split into shared `resource-notes/` or standalone `experiments/`
folders if a resource is reused across many presets or an experiment log grows
too large to inline.
