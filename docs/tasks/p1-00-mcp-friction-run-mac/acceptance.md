# Producer acceptance — p1-00 evidence only

Date: 2026-11-24. Coordinator: [AID-142](/AID/issues/AID-142).

## Decision

Accept the no-repair evidence record `c02ebe75a25b949ca3408b5f5bfb0569225832cc`,
following [QA AID-149](/AID/issues/AID-149)'s independent [PASS](review.md).
Its direct approved source/specification parent is
`66e6a7f39d0b202b30095d516f319b4d7fd0e249`; QA's report/registry commit is
`37f016135388a7c49a6445077b64751ab78f767f`. The accepted task includes an expressly
permitted documented-blocker outcome. It does not establish an end-to-end
generate/retrieve/revise journey or release later work.

## Accepted evidence

| Boundary | Evidence and result |
|---|---|
| Offline tests | Coding full Mac Backend: `1900 passed, 124 skipped, 77 warnings in 43.84s`, wall 49.973s, exit 0. Independent QA: the same counts in 44.13s, wall 48.177s, exit 0. Both use `--timeout=60`; QA's `-rs` audit identifies every skip as Windows-only. No tests/skips changed. No new full MCP, Frontend or Windows result. |
| Running services | Current-source stdio reaches Backend ping/resources, same-job status and Gallery metadata. Live OpenAPI omits revision context while current source defines it; explicit supplied context returns null. The loaded Backend commit is unknown. Health/process cwd are not source-identity proof. |
| Real generation | One original completed on explicit local ComfyUI with Illustrious/default and no LoRA. Job `88891201-d6c1-4fad-a40d-98622b32f0ed`; image `4447`; canonical artifact `3862`. This establishes the recorded model/graph/parameter combination only. |
| Retrieved artifact | Metadata only. Returned `/gallery/...` URL was rejected locally before HTTP. No image bytes, revision or successful lineage were retrieved. This does not prove a missing file or broken endpoint. |
| Friction baseline | 23 intervention units across eight incidents: three setup/parser interventions, nine non-MCP diagnostic/retrieval attempts and eleven repeated polls. Zero generation resubmissions or hidden product repairs. Keep this accounting for later comparison. |

## Producer checks

- Read the manifest, complete bounded test results/timings, QA review and its
  independent verification archive, all friction rows/counting rules, and the
  ordered raw stdio. The transcript contains 90 timestamped records, 19 matched
  JSON-RPC request/response pairs, 17 tool calls, one generation submission and
  twelve polls of the same existing job. No timeout or revision submission.
- Downloaded the official Coding manifest/archive and QA report/independent/
  report archives. Manifest and QA report bytes match their Git objects; archive
  task files and both exact patches match the named commits. ZIP integrity passed.
  Integrated the unchanged reviewed evidence, QA report and generated registry.
- Inspected the task-only delta and credential-pattern scan before publication.
  The coordination changes add the bounded repair specification, status/topic
  documents and a memory rule; no production source, tests or workflow changes.
- Producer ran no software suite, live-service probe, generation or image-byte
  retrieval in this round. Test and runtime results above remain attributed to
  Coding/QA. A scratch audit initially tried to parse plain-text ping as JSON;
  correcting that auditor to the actual envelope produced the reconciled counts.

## Next action and gate

[p1-00a](../p1-00a-mac-runtime-and-retrieval/task.md) is a bounded repair inside
Phase 1, using the delegated reference pair. [QA kickoff AID-150](/AID/issues/AID-150)
reviews fixed published specification `edc91b096965f5c05ed58705441b96e143132bbf`;
its saved native plan matches the assignment. AID-142 waits natively on it. Actual
CLEAR is required before Producer creates Coding and delivery-review cards. The
repair aligns the running Backend, provides a consumable locator and proves one
fresh original/revision pair with image bytes and persisted lineage. Runtime/
configuration/docs changes may suffice; source changes require behavioral tests
and exact-commit delivery review. The baseline's legacy/null-context record is
not rewritten.

AID-142 remains open through repair acceptance. [AID-141](/AID/issues/AID-141) and
[AID-143](/AID/issues/AID-143) remain blocked by it; p1-01/02 are not released.
After repair PASS, Producer merges/pushes, updates CURRENT/PROGRESS and continues
the existing order without another routine start confirmation. Three consecutive
zero-intervention runs, CTY's aesthetics/demo and phase-close decision remain
later requirements. No boundary decision or owner interaction is needed now.
