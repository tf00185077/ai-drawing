---
name: ordinary-generation-revision-lineage
description: Gallery rerun is not a revision; use the revision context fields on generate to record lineage.
metadata:
  type: project
---

`gallery_rerun` replays recorded parameters; it does not create a new revision. A revision is a new `POST /api/generate/` request carrying a revision context (`request_ref`, `brief_revision`, optional `parent_artifact_id`, `feedback_ref`, `feedback_summary`). The Backend derives parent identity and stores it with the outputs; older images without context show as `legacy`.

**How to apply:** when changing a result based on feedback, send a new generate request with `parent_artifact_id` set rather than rerunning.

Source: `backend/app/schemas/generate.py` (`RevisionContextRequest`, `RevisionContext`).
