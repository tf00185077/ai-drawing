# Git-tracked Prompt Library Design

## Goal

Make Prompt Library edits performed through Docker write directly to the repository's `prompt_library/` directory so saved combinations can be reviewed, committed, and pushed with Git.

## Current behavior

Local backend development already defaults to the repository's `prompt_library/`. Docker overrides that setting with `/data/prompt_library`, bind-mounted from `data/prompt_library`, and seeds the runtime directory from the image when it is empty. Consequently, combinations saved through Docker are runtime data excluded from Git.

## Design

Docker Compose will bind-mount `./prompt_library` at `/workspace/prompt_library` and set `PROMPT_LIBRARY_DIR` to that container path. The Prompt Library provider remains unchanged: categories, entries, and combinations continue to share one library root, while combination saves naturally create or update `prompt_library/combinations/<id>.json` on the host.

The image's packaged Prompt Library seed and generic data-directory bootstrap remain available for compatibility, but the standard Compose deployment no longer uses `/data/prompt_library`. Existing files under `data/prompt_library` are deliberately left untouched and are not migrated automatically.

The launcher-generated environment must use the same container path so setup and reconfiguration cannot override the Compose default back to `/data/prompt_library`.

## Safety and compatibility

- Existing runtime Prompt Library data is preserved in place.
- No API or JSON schema changes are required.
- Direct writes will appear as normal Git working-tree changes.
- Non-Docker backend development keeps its current project-root default.

