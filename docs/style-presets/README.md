# Style Presets

Human-facing notes for creator/style recipes live here. The runtime catalog lives at `backend/style_presets/catalog.json`.

Rules:

- Use the same stable kebab-case `preset_id` in the catalog, note frontmatter, and note filename.
- Keep creator/source context, trial notes, and example prompts in Markdown.
- Keep machine-readable resource names and generation defaults in `backend/style_presets/catalog.json`.

Suggested layout:

```text
docs/style-presets/
├── _template.md
├── creator-a.md
├── resource-notes/
│   ├── checkpoints/
│   └── loras/
└── experiments/
```
