# Phase 2 implementation intake after the real First check

Producer's adopted in-boundary order, 2026-11-26, based on [accepted observation](acceptance.md)
and CTY's current [roadmap](../../roadmap/ROADMAP.md). This is intake/order, not
pre-cleared detailed specifications for the whole phase. Owner scope/order/Not
now/exit are unchanged; independent CLEAR and exact delivery QA apply per task.

| Order | Observed gap / bounded task | Evidence / remaining requirement |
|---|---|---|
| 1 — detailed now | p2-01 private key-file loading and credential-safe retained provider request paths | Seven credential-bearing process bridges; active acquire/install still read legacy auth. Remove manual file-key injection without introducing arbitrary credential/file/URL tools. |
| 2 — next specification | Stock bounded safe download execution/admission and truthful async Backend job/status/wait integration | One custom injected transport supplied size/disk/deadline/redirect guards; current acquisition IDs differ from Backend job domain. Preserve safetensors/hash/size/reserve, no overwrite and same-ID truth; choose authoritative reservation/accounting with the unified record design, not a new competing ledger. |
| 3 — next specification | One Backend resource record, existing ledger/alias data migration/reuse and single SDXL-group mapping | Two manually assembled/adopted rows and filename mapping; metadata/defaults are only in evidence. Merge/migrate rather than add a parallel record. Retain source/type/base/family/hash/license/triggers/recommendations; unknown local hash lookup; SDXL 1.0/Illustrious/Pony/NoobAI → sdxl only. Coordinate the record contract before job-budget persistence changes. |
| 4 — next specification | Safe model search/version inspection and replacing old Civitai MCP intents with the coherent resource/download flow | Direct search/inspect bridge; selected version safe but aggregate NSFW mask differed. Truthful counts/ratings/size/license; inspect selected-version safety, safe default, unsupported bases clear. No commercial-use filter. |
| 5 — next specification | Resource-derived workflow/trigger/parameter generation defaults and overrides | Manual default_lora, trigger words, strength and fallback sampling; preserve explicit LoRA semantics, provenance and raw base versus mapped family. |
| 6 — after coherent replacements | Dependency-proven removal plus real end-to-end qualification | Owner Remove list is binding: unused Civitai services/recipe imports/variants/variation sets/generate-like and obsolete MCP intents/tests. Use inventory plus complete static callers/retained data migration, not delete-on-no-profile-count. Then three different sentences/zero fixes, one fresh checkpoint+LoRA download, actual MCP bytes/resource/default/Gallery traces and CTY image demo. |

Download and record contracts are designed together before a persistent budget
or job schema is implemented; order 2/3 may be packaged together if their actual
contract needs it. Only p2-01 is a detailed current spec. No native future Coding
cards presume the other specs are CLEAR. No paid cloud, workflow engine, worker
registry/auth/concurrency, video, training or UI redesign is added.

The seven used Civitai modules include a value type and preparation reads;
12 uncalled modules have not had their removal safety certified. The full
[service inventory](evidence/service-inventory.json) and retained failure ledger
govern later explicit removal specifications. Do not revive recipe/generate-like
features as incidental work. No provider preview or explicit content is needed.

## 2026-11-26 sequencing after p2-01 acceptance

[p2-01 is accepted](../p2-01-civitai-key-file/acceptance.md) after exact delivery
review2 PASS. Adopt [p2-02 resource-record foundation](../p2-02-resource-record/task.md)
from the joint order2/3 dependency before implementing download-job/budget
persistence. The existing local ledger already projects downloaded_resources;
source aliases bind image/recipe evidence. Typed current row identity, metadata,
mapping and compatible publication/reads come first; no competing record or
reservation counter. This is an in-phase dependency refinement, not an owner
scope/order change. Unknown-local identification, complete alias replacement,
stock bounded download jobs and new MCP flow remain subsequent detailed tasks.
Only this bounded foundation is now specified; fresh CLEAR is required.

## 2026-11-27 sequencing after p2-02 acceptance

[p2-02](../p2-02-resource-record/acceptance.md) is accepted after exact review10
PASS. The next bounded part of order2 is [p2-03 stock execution limits](../p2-03-bounded-download/task.md):
actual per-file bytes, destination free-space, safetensors checkpoint/LoRA selection,
valid resume and no-overwrite publication through both retained callers. Adopt
configurable8GiB/file and20GiB observed free-space floor under current delegation.
Persistent download attempts/jobs, aggregate budget/reservations and wait/status
integration follow this prerequisite as a separate detailed task. No generation
queue rewrite or second resource authority. This split does not claim order2 is
done; the old acquisition thread/resourceID remains distinct from a durable job.
Fresh independent kickoff precedes implementation. Owner phase scope/order/Not now,
three different zero-fix sentences/fresh checkpoint+LoRA and CTY demo remain.
