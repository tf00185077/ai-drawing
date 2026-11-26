# Resource record foundation

The [p2-02 task](tasks/p2-02-resource-record/task.md) specifies existing-row
metadata authority, one SDXL mapping and bounded reads. Main's product remains
accepted p2-01; p2-02 product/tests remain unintegrated.

Original candidate9abe3d1c received [review1 FAIL](tasks/p2-02-resource-record/review-round-1.md)
with four P1 findings. Corrected candidate **6fbcb24602e23d72363834cc9437a4a14f216386**
received [review2 FAIL](tasks/p2-02-resource-record/review-round-2.md): R2-R4 pass,
but R1 complete credential-value secrecy remains incomplete. This is two rejected
deliveries and one unresolved original finding. [Correction2](tasks/p2-02-resource-record/repair-round-2.md)
proceeds under unchanged kickoff CLEAR/task, then independent exact delivery QA3.

The [original technical topic](tasks/p2-02-resource-record/resource-records-round-1.md)
and [correction1 technical topic](tasks/p2-02-resource-record/resource-records-correction-1.md)
are immutable implementation snapshots with their reports/manifests/evidence;
they describe rejected deliveries, not accepted main behavior. Producer updates
this topic to current implemented behavior only after independent PASS/integration.

The [resource decision](decisions/civitai-resource-record.md) and
[roadmap](roadmap/ROADMAP.md) govern the contract. Preserve stable IDs, old evidence,
private settings/runtime and all models/data. Download jobs/budgets, hash lookup,
search/MCP replacement and generation defaults remain later tasks. No deployment,
complete Phase2 flow, phase exit or CTY aesthetic verdict is claimed here.
