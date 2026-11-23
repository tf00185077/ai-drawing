---
name: native-interaction-card-lineage
description: In Paperclip, a new question card expires the same agent's older pending card of the same kind on the same issue.
metadata:
  type: project
---

When an agent creates an `ask_user_questions` or `request_confirmation` card, Paperclip expires that agent's older pending card of the same kind on the same issue. The earlier question then has no way to be answered.

**How to apply:** put questions that must stay open into one card, or wait for the earlier card's answer before asking again.
