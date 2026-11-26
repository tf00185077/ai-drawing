# Decisions · evidence capture

## Settled

- Redact credential fields/actual secret values and sensitive query values while preserving nonsecret source-path keys and their hashes. A substring match for token must not erase tokenizer paths. Exclude private key content/digests entirely. Producer-adopted technical safeguard under the existing secrecy/preservation requirements.
- A missing before-run fingerprint remains a limitation; matching current files to Git is supplemental evidence and never reconstructs a historical measurement.

## Log

### 2026-11-26 · Preserve useful source fingerprints during secret redaction

- Decision: future evidence helpers use credential-field semantics and actual-value exclusion, preserve ordinary path/hash data and separately verify a complete declared source inventory. Keep original packets immutable.
- Why: [p2-00 independent review](../tasks/p2-00-civitai-first-check/review.md) finds five ComfyUI tokenizer paths masked by the hand-run helper's broad dictionary-key filter. Other hashes/current Git corroboration supported the bounded observation; they did not restore the missing earlier values.
- Provenance: Producer adoption after exact observation PASS with a P2 evidence-usability limitation, within approved credential/privacy and source-verification requirements. This is not a new owner quotation or a waiver of the limitation.
- Applies: before saving source fingerprints or provider/download/credential evidence. Verify that credential fields/signed values stay hidden and ordinary paths/model hashes remain checkable; do not execute retained old helpers as if corrected.

## Open questions

None; actual task results/receipts stay in task records.
