# Resource record foundation

The [p2-02 task](tasks/p2-02-resource-record/task.md) specifies one Backend row
authority, typed resource metadata, the SDXL mapping and bounded read/list routes.
The current main product remains the accepted p2-01 source. p2-02 candidate
**9abe3d1c3237791b684e3b9f5a692879df747361** received independent review1
**FAIL** with four P1 findings; its new resource API/schema implementation has
not been integrated. See [the actual report](tasks/p2-02-resource-record/review-round-1.md)
and [correction1](tasks/p2-02-resource-record/repair-round-1.md).

The original rejected-candidate [technical topic snapshot](tasks/p2-02-resource-record/resource-records-round-1.md)
is retained verbatim with its manifest/evidence. It describes that delivery's
implementation and limits, not accepted main behavior. Correction Coding and
independent exact-commit QA must resolve the actual findings before Producer
integrates the feature and updates this topic to match accepted source.

The [resource identity decision](decisions/civitai-resource-record.md) and
[owner roadmap](roadmap/ROADMAP.md) govern the contract. Preserve stable resource
IDs, immutable old evidence, private configuration and all models/data. Download
jobs/budgets, unknown-local hash lookup, search/MCP replacement and automatic
generation defaults remain separate tasks. No live deployment or Phase2 exit is
claimed by specification or report publication.
