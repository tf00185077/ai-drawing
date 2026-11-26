# Decisions · Phase 2 resource identity

## Settled

- Extend `downloaded_resources` as the authoritative model-resource record. Its
  existing integer IDs remain resource IDs; do not introduce another model
  registry, filename identity store or persistent metadata sidecar.
- Preserve source labels separately from workflow family. One Phase 2 table maps
  `SDXL 1.0`, `Illustrious`, `Pony`, `NoobAI` to `sdxl`; unsupported/unknown labels
  have no matching workflow. This does not establish pair or loader compatibility.
- A resource is not a download attempt or disk reservation. Future attempt/job
  accounting references resource IDs and has one authoritative transactional
  accounting path in the existing Backend database; this increment implements no
  job/budget/reservation schema or competing counters.
- Old source aliases describe image/recipe evidence, not necessarily models.
  Preserve that evidence and its history. Do not invent model identity from an
  alias name, image ID, recipe hash, filename or a missing provider field.
- Typed metadata still crosses an untrusted input boundary. Normalize every
  persisted/public nested field under the secrecy policy, and use the same typed
  validity for filtering/counting and projection. Unknown incoming identity does
  not erase known identity; retained-row retries preserve original notes as well
  as backfill does. These apply the existing record contract to every writer/read.

## Log

### 2026-11-26 · Give quoted scanning an explicit terminal-escape rule

- Decision: retain complete credential-label semantics while making quote/escape
  traversal advance monotonically, including a lone escape at end of input. An
  unmatched tail must not trigger repeated growing suffix scans. Keep both quote
  kinds, opposite-quote recognition and useful ordinary metadata intact.
- Why: a repeated regex branch requiring a character after each backslash can
  prevent its end-of-input alternative from matching. Search then retries at each
  quote. Small positive cases and green secrecy suites miss quadratic work on
  valid ordinary provider/stored descriptions; SQL pagination cannot bound it.
- Reassessment: the fifth delivery rejection changes the open finding: current
  tested R1-R4 cases pass, while new R5 violates existing provider/read bounds.
  Retain identity and secrecy work; correct bounded progress without raising
  timeouts, truncating/hiding safe data or imposing new format exclusions. This
  remains approved scope/CLEAR; report the adopted option under current delegation.
- Evidence: [actual review5](../tasks/p2-02-resource-record/review-round-5.md),
  [registered latency probes](../tasks/p2-02-resource-record/review-round-5-evidence/independent_read_latency.py)
  and [correction5](../tasks/p2-02-resource-record/repair-round-5.md). This is a
  Producer application, not a new owner quote or accepted product behavior.


### 2026-11-26 · Parse complete quoted labels before credential recognition

- Decision: consume a matching quoted assignment/header label as a complete unit,
  then apply the same credential identifier policy as for dictionary keys. Include
  inner leading/trailing whitespace and the literal/serialized forms exercised by
  actual probes; preserve safe neighbors and bounded long-description scanning.
- Why: sharing a recognizer is insufficient when the text extractor drops a
  recognizable quoted label or loses its delimiter during unquoted fallback.
  Matching key controls can pass while writer and old-read text still expose values.
- Reassessment: the fourth p2-02 rejection leaves original R1 unresolved. Retain
  the single-row design, complete-value boundary and passing R2-R4; correct parsing
  and add class/consistency/fault coverage under unchanged task/CLEAR. Current
  delegation permits this in-boundary option; report it with results. No new owner
  requirement, phase boundary change or accepted product behavior is implied.
- Evidence: [actual review4](../tasks/p2-02-resource-record/review-round-4.md),
  [real key controls](../tasks/p2-02-resource-record/review-round-4-evidence/independent_key_controls.py)
  and [correction4](../tasks/p2-02-resource-record/repair-round-4.md).


### 2026-11-26 · Share recognition for credential keys and assignment labels

- Decision: apply one documented credential-label policy to dictionary keys and
  parsed assignment/header identifiers, including prefixed identifiers. Keep
  complete-value exclusion and read-only old-record visibility; preserve unrelated
  safe metadata. This is a small correction inside the current shared boundary.
- Why: regex word boundaries treat underscore as part of a word, so an explicit
  prefixed assignment can evade a recognizer that handles the same credential key.
  Idempotence and complete-value removal do not establish recognition coverage.
- Reassessment: after three p2-02 delivery rejections, retain the single-row
  design/passing R2-R4 and replace the inconsistent label assumption. No phase
  scope/order/architecture/Not now change is required. CTY's current delegation
  permits adoption and continued independent QA; report the threshold with results.
- Evidence: [actual review3](../tasks/p2-02-resource-record/review-round-3.md) and
  [correction3](../tasks/p2-02-resource-record/repair-round-3.md). This is Producer's
  application/reassessment, not a new owner quote or accepted product behavior.


### 2026-11-26 · Exclude complete recognizable credential values

- Decision: treat a recognizable credential-bearing free-text value as a complete
  safety unit. Remove/redact the complete affected value, or refuse unsafe input
  before publication if a typed contract cannot survive; safe public reads of old
  snapshots stay read-only and retain the resource. Keep unrelated safe fields and
  ordinary hashes. Test full values across actual writers/readers, not only URLs.
- Why: removing only a label/scheme or the first token leaves a secret suffix;
  repeated normalization then loses the evidence needed to recognize it. Basic
  auth, later cookies and quoted multiword values demonstrate this boundary.
- Provenance: Producer's application of existing R1/C1 after independent
  [review2](../tasks/p2-02-resource-record/review-round-2.md), not a new owner quote,
  requirement or scope. [Correction2](../tasks/p2-02-resource-record/repair-round-2.md)
  retains the passing R2-R4 obligations and requires fresh exact delivery QA.


### 2026-11-26 · Keep validation and preservation at every resource boundary

- Decision: apply the existing secrecy policy to complete typed snapshots at
  publication and public projection; exact filters/counts use the projection's
  typed validity; absence cannot erase known identity; retained-row retries keep
  original notes as immutable evidence while current errors remain truthful.
- Why: Pydantic typing does not sanitize arbitrary nested strings, a separate SQL
  JSON interpretation can select a record the canonical projection rejects, and
  assignment/error branches can bypass otherwise-correct shared publication.
- Provenance: Producer's implementation application after source and independent
  [R1–R4 evidence](../tasks/p2-02-resource-record/review-round-1.md), not a new owner
  quote or scope. [Correction1](../tasks/p2-02-resource-record/repair-round-1.md)
  must prove these existing contract boundaries with fresh exact delivery QA.

### 2026-11-26 · Establish resource identity before download accounting

- Decision: take the bounded [p2-02 foundation](../tasks/p2-02-resource-record/task.md)
  before the stock download-job/budget task. Use a normalized, versioned metadata
  projection on the existing resource row and migrate legacy notes without
  destroying their original evidence. Existing acquisition/install producers and
  the local-ledger reader must share this authority.
- Why: current acquisition IDs are resource-row IDs, the local ledger is already
  a projection of those rows, and source aliases bind immutable image targets.
  Implementing an independent registry or budget keyed by filename would create
  another identity and make dedupe/reuse/migration harder.
- Alternatives: a new model table duplicates existing IDs; a standalone job-budget
  ledger first leaves identity and reuse unresolved. Keeping untyped notes as the
  only public contract retains competing family/metadata interpretations.
- Provenance: Producer's in-boundary choice from the accepted real First check,
  [ranked intake](../tasks/p2-00-civitai-first-check/implementation-intake.md), actual
  source/ORM inspection and CTY's [current delegation](../requests/2026-11-26-phase-2-start-and-key-file.md).
  It changes no approved phase scope/order/architecture and is not an owner quote.
- Applies: this source foundation and later download/search/default specifications.
  Unknown-local hash lookup, complete legacy alias removal, new MCP replacement
  tools and actual downloads remain later tasks. Those need their own CLEAR and
  exact delivery review; this decision does not implement or pre-clear them.

## Open questions

None for the bounded foundation. Future detailed download admission/reservation,
unknown-local identification and MCP replacement contracts remain unimplemented.
