# Decisions · verification scope and evidence size

Owner-directed 2026-11-27 ([request](../requests/2026-11-27-verification-reassessment.md)).
Applies to every task from p2-04 on and to the p2-02a correction below. Where this
file conflicts with an earlier task spec, handoff, repair note or
[evidence decision](evidence.md), this file wins.

## Settled

- **Public metadata is an allowlist.** Every field an API or MCP reader can see is either a fixed-shape typed value or text taken from a closed set. The system never scans free text to recognize credential-looking content. · why: recognition is open-ended and produced nine p2-02 rejections without a real leak
- **Secrets in scope are the values the system actually holds**: the Civitai key value from `CIVITAI_API_KEY_FILE`, signed download URLs and their query strings, and request auth headers/cookies. A finding about those reaching storage, logs, responses or evidence is P1. Credential-looking text written by a third party inside public Civitai metadata is not a secret this system holds, so it is at most a P3 note.
- **Committed evidence per task is capped at 2 MB in total and 1 MB per file**; a phase-exit folder may reach 10 MB. Raw logs, full suite output and source inventories stay out of Git.
- **Source identity is the Git commit.** The reviewed full SHA plus `git diff --exit-code <reviewed-sha> <merged-sha> -- <changed paths>` replaces freeze inventories, per-file fingerprint lists and Producer integrity JSON.
- **Done when items describe product behavior.** Review mechanics (fault injection, registry reruns, restoration) are how QA works under `reviewspec-review`; they are not Done when items. Only items whose breakage harms the owner's use are P1.
- **Correction rounds are bounded.** A correction review checks the earlier findings and regressions in the changed code. A further finding of the same class after the second rejection is an AMBIGUITY to Producer, who reshapes the design instead of patching again.

## Diagnosis: hard rule or drift?

Mostly drift. The written rules are short and proportionate; the cost came from
task specs, one evidence decision and correction habits that each built on the last.

What the written rules require (unchanged since 11-23/11-24):

| Source | Requires | Verdict |
|---|---|---|
| [QA role page](../team/roles/engineering-qa.md) | Review the exact commit, run the tests, check security boundaries "where relevant" | Proportionate |
| `reviewspec-review` skill | Per `test` item, the smallest production change that should break it; rerun active REGISTRY guards; "a false block costs as much as a false pass, so block only on what you can demonstrate" | Proportionate, but has no threat model and no cap on rounds. "Demonstrate" was satisfied by synthetic strings |
| `reviewspec-core` skill | P0/P1 block; the higher the level, the closer proof must come to the real boundary | Proportionate; makes every P1 item expensive by design |
| [OPERATING-POLICY](../OPERATING-POLICY.md) | Never commit secrets; redact them in shared logs | Proportionate |
| [ROADMAP](../roadmap/ROADMAP.md) Phase 2 | The key is never committed, logged or returned through MCP | Proportionate; names the key value, not arbitrary text |

Where it drifted, in order:

1. **p1-02 round 1 (11-24 19:33).** A planted fault passed the full suites, so the candidate was rejected. This was the skill working as intended. The drift was what followed: every task's added guards joined a registry that only grows (22 → 72 → 87 items), and each review reran the full Backend and MCP suites before and after each planted fault.
2. **p1-05 (11-25).** First large evidence: full SDK message and call logs (about 4.8 MB each) were committed for every attempt, including rejected ones. Folder size: 44 MB.
3. **[evidence decision](evidence.md) after p2-00 (11-26 16:10).** One helper over-redacted five tokenizer hashes. Producer responded by requiring a separately verified "complete declared source inventory". From then on every stage committed an inventory of about 8,000 path fingerprints (about 60,000 lines each). This is the main driver of the growth from 4 MB to 275 MB per task.
4. **p2-02 task spec (11-26).** Producer, not the owner, wrote "Diagnostics expose no raw bad notes, credentials or signed locators", applied it to the free-form `source_evidence`, license values and names, and made all five Done when items P1, including D5, which is review mechanics. No allowlist shape was specified, so the only way to pass was to recognize credentials inside arbitrary text.
5. **p2-02 round 3 (11-26 20:48).** The three-rejection threshold was reached. The threshold text had been changed on 11-26 (`5608e144`) so that Producer "adopts the in-boundary recommendation" and continues. The reassessment ruled out a design change ("do not add a secrecy framework") and kept patching the recognizer. Rounds 4–9 each found a new synthetic spelling: underscore prefix, quotes, serialization, escapes, preceding prose, ledger projection. Per-round evidence grew from 2.1 MB to 37.9 MB. QA recorded that no current credential disclosure was demonstrated.
6. **p2-03 and p2-04.** The same pattern continued: five P1 items, sensitivity and adverse suites, full inventories, and in p2-04 a D-level demand for "full changed-source qualification".

Root cause: nothing in the system defines what is worth protecting or when to stop.
The QA skill says to block on what can be demonstrated, the spec demanded the absence
of a whole class of text, and the threshold no longer stopped anything.

## Allowlist for the resource record

Replaces `safe_text` / `safe_evidence` credential recognition in
`backend/app/services/resource_records.py` (the `_ASSIGNMENT_LABEL`, `_LABEL_ESCAPE`,
`_BEARER_AUTH`, `_BASIC_AUTH`, `_SENSITIVE`, `credential_label`, `_assignment_in_view`,
`_credential_assignment` and `_json_string_view` machinery).

| Field | Public shape |
|---|---|
| IDs, sha256, sizes, status, booleans, `model_family`, `metadata_origin/version` | Unchanged typed values |
| `resource_name`, `resource_type`, `provider`, `air`, `base_model` | Strings from Civitai or the local file name, length-limited to 200 and stripped of control characters. They are public names, not secrets |
| `source_url` | Rebuilt from IDs as `https://civitai.com/models/<model_id>?modelVersionId=<version_id>`; the stored URL is never echoed |
| `local_path` | Unchanged; it is a local path the owner already sees |
| `trigger_words` | List of at most 32 strings, each at most 200 characters and stripped of control characters. They are public creator text that `generate` must apply |
| `recommended_parameters` | Keys limited to `sampler`, `scheduler`, `steps`, `cfg`, `width`, `height`, `clip_skip`; numbers range-checked; sampler and scheduler names at most 64 characters matching `^[A-Za-z0-9_+. -]+$` |
| `license.values` | Only the four `LICENSE_FIELDS`, each a boolean, a known Civitai enum string or a list of them; anything else goes to `missing_fields` |
| `diagnostics` | `code` from a fixed enum; `field` from the record's own field names |
| `source_evidence` | Removed from the public projection. Kept internally, where it holds acquisition state |

Download URLs, signed query strings and auth headers are never stored in any row,
job or log. The only content check is bounded: the exact current key value (and its
URL-encoded form) must not appear in stored metadata, responses, logs or committed
evidence.

## Evidence that is committed

Per task folder, at most:

- `task.md`, `kickoff-review.md`, `implementation-handoff.md` (optional)
- `manifest.md`: Done when matrix, the reviewed full SHA, test commands and pass/fail/skip counts
- `review.md` for the current round, plus one `review-round-<n>.md` per rejected round, each at most 150 lines: findings, a reproduction command and the test that now guards it
- `acceptance.md`: reviewed SHA, merged SHA, the `git diff --exit-code` result, links
- For `manual` or real-run items: a short summary (calls, IDs, timings, image/job IDs) and at most a few small artifacts, such as one PNG or a trimmed log under 1 MB

Not committed: raw SDK or call logs, full pytest output, freeze or candidate
inventories, preservation or fingerprint JSON, per-correction `correction-<n>-evidence/`
trees, Producer integrity JSON, QA helper copies, archives and patches. They may stay
in the agent's worktree or private folder, referenced by path and SHA-256 when useful.

The existing 420 MB under `docs/tasks/` stays in history untouched; nothing new is
added in that form. Pruning it is a separate owner decision.

## Review effort

- **Full suites run once, on the final candidate.** Correction rounds run the affected tests plus the REGISTRY guards.
- **Fault injection follows the skill as written:** one smallest violating change per `test` item, then restore. There are no extra fault catalogs and no full-suite run per fault.
- **REGISTRY guards** are rerun as one pytest invocation, recording only counts. When a guard tests removed behavior (for example the credential-label tests below), Producer marks it superseded in the task that removes it.
- **Producer verifies a merge** by the diff check above. No independent restore, bundle or fingerprint audit.

## Follow-up work

1. **p2-02a: allowlist projection (new, small, before p2-04 implementation).** Implement the table above. Delete the credential-recognition code and its tests (`test_resource_record_credential_labels.py`, `..._credential_values.py`, `..._quoted_labels.py`, `..._quote_contexts.py`, `..._quote_prefix_escapes.py`, `..._serialized_assignments.py`, `..._terminal_escapes.py`, `..._representation_contexts.py`, and the matching parts of `..._acquisition_notes.py` and `..._ledger_projection.py`). Supersede their REGISTRY rows. Add allowlist tests and the exact-key-value absence test. Done when: two P1 items (allowlist projection; key value and signed URLs absent) and one P2 item (old rows still readable).
2. **p2-04 respec.** Producer removes D5-style review mechanics from Done when, re-levels items by owner impact and rewrites Delivery to the committed-evidence list above. Kickoff is re-run on the revised spec; it should take one round.
3. **Rest of Phase 2.** After p2-04, prioritize what an agent can use: Civitai search + inspect, record list/reuse through MCP, workflow selection, defaults. Then the removals and the three real runs.

## Proposed, needs CTY confirmation

- **Rejection threshold stops work.** At 3 rejections of one task, Producer pauses that task and asks CTY with options (narrow the requirement, change the design, or continue), instead of adopting a recommendation and continuing. This changes the settled threshold line in [roadmap decisions](roadmap.md).
- **Add to the `reviewspec-review` skill** (owner library, outside this repo): "Block only on a failure reachable from a value the system actually holds or an input it actually receives; a synthetic string that merely resembles a secret is a note. After a second rejection for the same class of finding, return AMBIGUITY instead of FAIL."

## Log

### 2026-11-27 · Allowlist public metadata and cap committed evidence

- Decision: the rules above.
- Why: p2-02 took ten review rounds and 275 MB, and p2-03 took 64 MB, for about 6k lines of product code, while no agent-facing Phase 2 capability exists yet. See the diagnosis.
- Provenance: owner-directed; the threshold and skill changes are proposed only.
- Supersedes: the "complete declared source inventory" part of the [2026-11-26 evidence decision](evidence.md); the redaction-semantics part stays.

### 2026-11-27 · History rewritten to drop removed evidence and research data

- Decision: owner-approved rewrite of `main` that removes the deleted per-round evidence under `docs/tasks` and the Phase 0 `experiments/`, `research/`, `model_benchmarks/` data from every commit, followed by a force push and deletion of 14 stale remote branches. The pack size went from 76.7 MB to 8.6 MB; the final tree is unchanged.
- Effect: commit SHAs from 2026-07-02 on changed. Commit SHAs cited in docs were remapped to the new history; quoted tree hashes and SHAs inside commit messages still refer to the old history. Existing clones and worktrees must re-clone or reset to the new `main`.
- Backup: a full bundle of the old history is kept outside the repo on the owner's Windows machine (`C:\tmp\ai-drawing-pre-rewrite-2026-11-27.bundle`).
