# p2-03 independent kickoff review

Verdict: CLEAR

Review round: kickoff 1; recipient-owned [AID-207](/AID/issues/AID-207).
Producer [AID-146](/AID/issues/AID-146) owns implementation dispatch and acceptance.
This is a specification verdict, not delivery PASS or certification of D1–D5.

## Fixed identity and owner comparison

| Input | Identity |
|---|---|
| Published source | `86837c724d0887d03c24e7d0c94c3b62d803ba9f` |
| Source tree | `8513654d554bab9a0626ba7ed21c1944642b4c6b` |
| Task SHA-256 | `285af6d1419f70e9c5e3b4a7d86f64f5913e6dfebb24e0897d3a67fb21ca32f0` |
| Branch | `qa/aid207-p203-kickoff` |
| Persistent isolated workspace | `/Users/tf00185088/Desktop/tim-project/ai-drawing-qa-aid207-p203-kickoff` |
| Pre-review card pin | AID-207 comment `b33a76b9-fdca-41de-b5e5-f402ff4b464b` |

My reading: CTY authorizes Phase 2 progression under the published roadmap and
delegates ordinary in-boundary recommendations to Producer. The existing Backend
must own resource identity, downloads and provenance. Bounding stock execution is
a necessary increment toward the one-sentence checkpoint/LoRA flow. Durable jobs,
aggregate reservations, search/hash lookup, new MCP contracts, defaults, removals,
three zero-fix runs and CTY's image judgment remain separate requirements.
The [owner words](../../requests/2026-11-26-phase-2-start-and-key-file.md) do not
specify the numerical limits: 8 GiB and 20 GiB are explicitly Producer's delegated
recommendations in the [decision](../../decisions/civitai-download-limits.md).

Difference: none requiring a scope, order, architecture or constraint change.
No owner question is required. The task narrows the next execution increment;
it does not declare the download-job/Phase 2 exit complete. The wake already
contained the verbatim task, so this was not a blinded reading; the separate
scope note records that limitation.

Accepted p2-02 is an actual prerequisite: [acceptance](../p2-02-resource-record/acceptance.md)
names Coding `c705d211f64497df7190120d46f94d94b785d24b` and independent review10
PASS `a94324fef3f264fb361c9761af0ff828eeb77e81`, with 72 active registry rows.
That foundation is present in this pinned source. Its nine rejected deliveries,
five historical P1 findings and earlier records remain unchanged. The accepted
First check still means one bridged chain, 20 interventions, 77 overlapping units
and five missing historical hashes; it supplies neither this feature nor exit proof.

## Findings

No demonstrated P0/P1 specification defect. CLEAR covers the complete published
[task](task.md), handoff, and recipient plan/verbatim inputs
as a kickoff only. The source defects below are the work this task explicitly
requests, rather than grounds to reject a coherent repair specification.

## D1–D5 assessment

| Item | Kickoff assessment and concrete boundary |
|---|---|
| D1 / P1 | Observable and feasible. `Settings` currently exposes credentials/roots but no byte policy. Acquisition `_normalize_file` allows five extensions, weakly validates hash/size and rounds `sizeKB`; `choose_file` prioritizes primary before safetensors. Retained inspect `_size` truncates while descriptor validation checks positive size/hash. Both admission paths therefore need policy/type gates, not a helper-only fix. Validate all selected Anima components before row publication; preserve their existing routing/format eligibility. Existing non-checkpoint/LoRA kinds and strict descriptor/license/refusal semantics remain testable. |
| D2 / P1 | Observable and feasible. The helper currently selects `ab` for any 206 with an offset, never checks Content-Range, streams before checking size/hash, and has no space observation. Prefix association cannot be inferred from filename/length: the helper currently receives only URL/hash/size, so caller context must supply or verify provider/version/file/resource association within the existing authority. Unknown legacy parts must be retained/refused. Remaining-byte admission and every-write checks can observe the destination filesystem without introducing aggregate reservations. |
| D3 / P1 | Observable and feasible, with changes in both callers. The helper calls `os.replace`; `_failure` unlinks any existing `.part`. Acquisition commits rows before the background call and publishes current outcome on that ID. Retained install checks/adopts exact existing targets but currently only persists completion and unconditionally unlinks the final after commit failure. Its admission/failure/compensation and caller projection must therefore be brought under the new contract. Existing exact adoption remains distinct from a racing collision, which cannot be reported as this invocation's verified download. |
| D4 / P1 | Observable and feasible. Both registered paths use the real `ProviderOperation` and `ProviderDownloadTransport`, with configured-file snapshot, final prepared-header isolation, allowed origins/redirects and cancellable HTTP. Preserve these paths. The new disk/hash/publication work must check the same absolute deadline; `_file_digest` currently has no deadline checks. Closure must cover refusal before iterator advancement, midstream abort and all new cap/space/range/collision exits, including backoff. |
| D5 / P1 | Coherent future delivery gate. Independent QA must pin actual final SHA/tree, mutate real production boundaries for all five named faults, retain raw RED results, restore exact bytes, then run affected/full Backend/MCP and fresh exports/consumers. This kickoff neither performs those future mutations nor certifies the new behavior. The registry remains byte-exact with 72 active rows; no new coverage or supersession is recorded here. |

The source observations independently
reproduce nine bounded cases: existing final replaced; missing/wrong-start/
wrong-total ranges accepted; unassociated partial restarted; four bytes written
against a two-byte declaration; a foreign partial symlink removed; inconsistent
size normalization (2.75 declared bytes rounds to 3 versus truncates to 2); and
retained failed install leaving the same existing row `planned` with old notes.
These are current-source observations, not future passing guards. They demonstrate
why helper-only changes and green existing suites do not establish delivery.

## Caller, dependency and retained-contract inventory

Production callsites were searched across Backend, MCP, scripts and Discord:

- Registered MCP `civitai_resource_acquire` → `POST /api/civitai/resources/acquire`
  → `start_acquisition` → `_run/_run_one` → shared `safe_download` with production
  streaming transport. `civitai_resource_status` reads that same resource ID.
  The retained `generate_like` path also calls `start_acquisition`; preserve its
  alias/recipe/planning behavior rather than creating another downloader.
- Registered HTTP `/api/civitai-recipes/resource-inspect`, `resource-select` and
  `resource-install` → canonical descriptor → `install_civitai_resource` → the
  same helper. These retained strict operations are HTTP routes, not additional
  registered MCP intents. Installation must still reject caller overwrite,
  destinations and malformed descriptors, and preserve exact-file adoption.
- Both writers feed `DownloadedResource`, `provider_snapshot`, `publish_metadata`
  and `measured_evidence`. Canonical `/api/resources` list/detail, acquisition
  summary/status and `/api/civitai-recipes/local-ledger` read that authority.
  Preserve selected IDs, the sole four-label Phase 2 family mapping, declared
  versus measured evidence, old notes, internal executable locators and the
  complete-value public normalization policy.
- Frozen Anima acquisition uses `downloadable_files` and `_anima_component`,
  producing diffusion-model/text-encoder/VAE rows. Retained install's kind/root
  whitelist and package refusal remain unchanged. A blanket extension restriction
  in `_normalize_file` would incorrectly alter these other retained kinds.
- Provider credentials/deadlines, final request headers, response/body ownership,
  digest cache, existing file adoption, ledger rollback and final-file compensation
  are affected dependencies. The catalog remains 31 tools. No cancellation API,
  durable attempt, generation job, wait integration or new registry is implied.

Relevant fixed source: [helper](../../../backend/app/services/civitai_safe_download.py)
lines 91–103, 118–177, 181–239;
[acquisition](../../../backend/app/services/civitai_resource_acquire.py)
lines 185–244, 340–475, 517–574;
[retained install](../../../backend/app/services/civitai_resource_install.py)
lines 113–120, 243–275, 313–431;
[provider](../../../backend/app/services/civitai_provider.py)
lines 126–206, 208–278, 281–332;
[resource publication](../../../backend/app/services/resource_records.py)
lines 270–278, 285–322. Ordinary source body hashes are indexed in
reviewed-source-inventory.json.

## Bounded implementation and delivery notes

1. Choose and document one strict effective policy and one exact selected-size
   interpretation shared by both callers and typed metadata. Reject booleans,
   non-finite/nonpositive values and invalid hashes before side effects. The
   current rounding/truncation difference must not become a silent size change.
   Verify real environment Settings loading as well as direct invalid fixtures.
2. Preserve ordinary safe reuse and failed-row retry. The same-ID retry tests
   sometimes leave a verified final on disk after changing its row status; meet
   both no-overwrite and safe reuse through explicit verification/adoption rather
   than replacement or deleting the fixture. Old-note read tests also seed legacy
   parts solely for progress; read-only status must not repair those parts.
3. State the actual admission point for retained install and publish post-admission
   failures on the existing row/current outcome. This is in scope: do not narrow
   the same-ID guarantee to acquisition or add a competing attempt table. Handle
   credential/space/policy refusal before admission without a new resource row.
4. Hold verifiable ownership through open/write/hash/publication/cleanup. Race
   tests must cover a target created after preflight and a replacement final before
   retained-install compensation; its current unconditional `unlink` is unsafe.
   Preserve foreign/linked/changed partials even when the target remains untouched.
5. Current compatibility assertions needing explicit fixture/feature replacement
   include raw unassociated-part success in `test_206_resumes_from_part_offset_and_atomically_publishes_only_after_hash_and_size`
   and `test_200_ignoring_range_overwrites_part_safely_instead_of_concatenating`
   in `test_civitai_safe_download.py`. Introduce real associated-part positive
   fixtures plus legacy/foreign preservation negatives. Retained
   `test_http_size_sha_failures_leave_no_final_or_ledger` currently requires zero
   rows after admitted stream failure; replace that obsolete row-count assertion
   with truthful failed same-ID evidence while retaining its file/hash checks.
   Review `test_ledger_commit_failure_removes_only_new_publication_and_row` and
   symlink-part cases for admission and ownership semantics. Keep genuine
   pre-admission no-row, exact adoption, immutable identity, closure, sanitized
   projections, package-routing and registry guards. No silent deletion/skip.

These notes are implementation risks within the existing explicit contract, not
additional owner decisions or approval of a detailed future schema. Coding chooses
the smallest implementation after this actual CLEAR; any material changed task
needs renewed kickoff, and every changed delivery needs exact-commit QA.

## Verification and limits

See verification.md for fresh commands/results,
guard receipts, environment and failed-attempt accounting. All original tracked
source bodies and the registry are checked against the pinned Git tree. Shared
main's 14 dirty memory body hashes/statuses are separately preserved; no private
key/config, canonical environment, runtime, data or other worktree was repaired.

Offline only: isolated Settings/HTTP/background/ORM tests and synthetic temporary
files. Running service: untested, no start/restart/deployment/backfill. Real provider
download or generation: none. Artifact retrieval: synthetic fixture bytes and
official review attachments only; no live model/Gallery bytes. No Frontend/native
Windows result or artistic/Phase 2 exit is claimed. Product code/tests remain
unchanged; the stock gaps remain until a separately reviewed implementation.
