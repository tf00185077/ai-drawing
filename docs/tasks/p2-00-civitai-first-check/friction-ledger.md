# First check friction and operation accounting

This is a nonzero-intervention operational baseline. It does not qualify as a
later zero-fix exit run. Units below are explicitly defined; they are not claimed
to use the older Phase 1 baseline's granularity.

## Measured operations

The chronological [operation ledger](evidence/operations.jsonl) retains **64
instrumented observations: 18 preparation, 32 flow, two recovery and 12 audit**.
An observation is one explicitly recorded call, boundary transition or verification
block. Enter/return observations can describe the same call; do not interpret
64 as 64 HTTP requests. The ledger includes successful and unsuccessful attempts.

The [service inventory](evidence/service-inventory.json) separately accounts for
**14 actual provider HTTP requests: ten 200, two 401, two 307**. This includes
four metadata requests across the failed and corrected acquisition invocations.
The selected download used one transport attempt, two HTTP hops, **228,518,900
new bytes**, zero internal retries and no resume. Three search-result first
versions were considered; only version 1843039 was selected/inspected in detail.
Only one checkpoint version was inspected, 1684912, by actual local hash.
Other versions/images present in raw API bodies were not alternative candidates;
no preview image bytes were fetched.

There was **one generation submission, one bounded MCP wait**, 40 internal
same-ID status GETs during that wait, one post-wait status GET and one new-session
status GET (**42 total**, corroborated by the actual Backend access log).
The wait also enriched one artifact and one image. A new SDK session performed
three reads: status, acquisition 80 and artifact 3878 with content. No timeout,
resubmit, cancellation, fallback or unresolved job remains.

## Capability friction: 15 intervention units

A unit here is one deliberate manual capability bridge/application, even when
several are implemented by one measurement script. Repeated credential-bearing
processes count individually. These are distinct from request/event counts.

| ID | Units | Actual intervention and evidence |
|---|---:|---|
| F1 | 1 | Model search absent from the advertised MCP list; direct safe Civitai API search. `mcp-tool-list.json`, `search-watercolor.json`. |
| F2 | 7 | File-key authentication bridges in seven credential-bearing processes: search; version inspection; checkpoint hash lookup; checkpoint model inspection; HEAD probes; failed pre-admission acquisition; admitted acquisition. The last two temporarily set existing `civitai_authorization`, restore it in `finally`, and leave private disk settings unchanged. `provider.py`, `download-probe.py`, `acquire.py`, operation ledger. |
| F3 | 1 | Injected bounded real streaming transport enforces the brief's extension/size/total-byte/disk/deadline/redirect guards absent from the stock downloader. It uses current acquisition/safe-download/persistence code. `acquisition-guard.json`, `acquire.py`. |
| F4 | 1 | Assemble current inspect/select/install input from actual hash/version/model metadata because the existing local checkpoint had no resource row. `checkpoint-current-inspect-select.json`. |
| F5 | 1 | Map provider filename `Illustrious-XL-v2.0-stable.safetensors` to actual existing local filename `Illustrious-XL-v2.0.safetensors`, with exact size/hash/file ID corroboration. Current installer rehashes and adopts the existing bytes; no copy/rename/overwrite. `checkpoint-local-name-mapping.json`, `checkpoint-registration.json`. |
| F6 | 1 | Manually map Illustrious to the brief's `sdxl` group and select existing `default_lora`, checking actual loader schema and tensor architecture. Current acquisition records `illustrious`; no product relabeling. `selection.json`. |
| F7 | 1 | Manually append actual `ArsMJStyle, Watercolor` trigger words. Current generation does not derive them from the resource row. `generation-request.json`, compiled graph. |
| F8 | 1 | Apply model-description starting strength ~1 to model and CLIP at 1.0; version-specific strength and separate CLIP recommendation are absent. `selection.json`. |
| F9 | 1 | Apply the brief's fallback size/steps/CFG/Euler/normal, fresh fixed seed, batch one and explicit empty negative override. Example-image parameters are not treated as recommendations. `generation-request.json`. |
| Total | **15** | No product repair. |

## Execution/recovery friction: five intervention units

| ID | Units | Failure and actual handling |
|---|---:|---|
| R1 | 1 | Prior provider-session quota interruption after saved preflight; resume preserved its files and private snapshot. No repeated preflight mutation or provider/job submission. |
| R2 | 1 | Premature local hash-lookup invocation hit `FileNotFoundError` while the independent hash calculation was still running. No HTTP request occurred; after the same calculation completed, one real hash lookup was made. |
| R3 | 1 | Initial detached launcher was reaped before any import/key bridge/acquisition row/file action. An empty console and absent live process were checked; replacement runs in the owning tool session. |
| R4 | 1 | First foreground acquisition imported isolated worktree code, whose import-relative config lacked the existing private `.env`; it made two successful metadata reads but failed `sqlite3.OperationalError: no such table: downloaded_resources` before ledger admission. Live DB confirmed no selected row. The counted recovery used the actual existing runtime import root, already fingerprint-equal to the fixed source. No schema/config/product repair; the ignored zero-byte worktree database is retained. Original metadata responses are retained under `*-attempt1.json`. |
| R5 | 1 | Accounting helper's secret-key filter rejected integer HTTP-status dictionary keys. Convert keys to text for matching and rerun only offline accounting. No product/provider operation repeated. |
| Total | **5** | Capability plus recovery friction: **20 intervention units**. |

## Preparation, audit and delivery scope

All non-flow work counts as work. The 64-event ledger records private key access,
source/import/package/runtime/schema/job/root/disk checks, a private DB snapshot,
MCP discovery, existing ledger/alias inspection, checkpoint hashing, loader schemas,
post-download hashing, new-session persistence/content reads, graph/history
correlation and complete old-row/schema/process/source preservation checks.

The following transcript-level work was not instrumented as a product call:
loading role/skill/owner/source documents; Git/worktree discovery and isolation;
reading native kickoff CLEAR and the issue continuation; source-path/call-graph
inspection; authoring the measurement helpers; inspecting same-job tool output;
and writing/reconciling this manifest, inventory and ledger. These are **seven
additional preparation/audit work blocks**, counted once each; the last block
includes the evidence-only verification script, index and secret scan. Thus the
pre-delivery account is **71 observation/work-block units**, with the 20 friction
units an overlapping classification, not an extra 20 to add.

Packaging, exact Git freeze, official uploads/work-product creation, upload
read-back and final native disposition are subsequent delivery work blocks.
Their actual counts and failures are recorded in the official delivery receipt
on AID-178. They are not a claim of zero effort or zero friction. No future
operation is counted as completed in this file.

Runtime source attestation is limited to the preserved prior process identity,
unchanged recorded source, equivalent-interpreter imports/settings and live
schema, plus this actual graph/persistence round trip. No universal in-process
module attestation or dynamic per-helper profiler was available. Seven Civitai
modules have call-path evidence (one is only a value type), and 12 others have
no operational invocation; importing an API module is not exercising all of its
services. This inventory does not authorize deletion of any service.
