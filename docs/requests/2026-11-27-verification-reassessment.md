# Verification reassessment: allowlist and lean evidence

## Source

CTY, in a Claude Code review session on `main` at `b35950fc`, 2026-11-27, after
reviewing why Phase 2 tasks needed up to ten review rounds and about 420 MB of
committed evidence.

## Owner words preserved verbatim

> 先幫我評估QA會這樣要求的原因，是他的身分文件有過硬的限制還是歷史疊代後出現的偏移，然後幫我寫重新評估文件，改成白名單並精簡 evidence

## Application

Public resource metadata moves from recognizing credential-looking text to a typed
allowlist, and committed evidence is cut to a fixed small set. The full diagnosis
and the new rules are in the [verification-scope decision](../decisions/verification-scope.md).
This changes how work is verified, not the destination, phase order, Phase 2 scope,
Not now list or the three-consecutive-real-run exit rule.

## Follow-up in the same session

After the cleanup and history rewrite, CTY confirmed both proposed roadmap changes:

> 照這樣做，第2點也一起補

Applied: 3 review rejections of one task now pause it for a CTY decision, and the
Phase 2 resource-record scope states the allowlist and the secrets in scope. The
`reviewspec-review` skill change remains a proposal.
