# Imported historical source

Source: `autonomous-staged-change-delivery/references/absorbed-skills/autonomous-pipeline-remediation/references/civitai-live-case.md`. Original SHA-256: `283ea4224eefdedd6c39313097fc52ae79b66ec41fc39f912e074b759e14d02b`.

Historical and version-sensitive; not current project policy, status, or authorization. Revalidate against this project's current entrypoint and authoritative records before any separately authorized execution. Original language is preserved below.

---

# Civitai live pipeline case

This is supporting detail for the class-level remediation workflow, not a one-off skill.

## Compatibility defects discovered at the real boundary

### Images API request shape

A public image lookup succeeded through the collection query form:

`/api/v1/images?imageId={image_id}&withMeta=true`

The item-path form `/api/v1/images/{image_id}?withMeta=true` returned not-found. Durable test pattern:

- Fake transport returns an `items` payload.
- Assert exact collection URL.
- Assert both `imageId` and `withMeta` query parameters.
- Preserve raw payload and canonical source identity.

### CDN redirects

The media URL returned an HTTP redirect. A production transport that did not follow redirects received empty/non-image bytes and surfaced `media_decode_error`.

Durable test pattern:

- Patch the HTTP client.
- Exercise both JSON and byte transport methods.
- Assert `follow_redirects=True` for API and media calls.
- Restart the live backend before repeating the real wrapper smoke.

### Nested generation metadata

Observed Images API payloads may contain generation metadata under `image.meta.meta`, while older fixtures place it under `image.meta`.

A correct normalizer should:

- Preserve the complete raw payload unchanged.
- Select or safely merge the actual generation metadata container.
- Keep field references pointed at the true source path (`/meta/...` versus `/meta/meta/...`).
- Recover prompt, negative prompt, seed, steps, CFG, sampler, dimensions and ordered resources.
- Avoid treating a short model hash as a verified full SHA-256; resolve it against an independently hashed local ledger before build/run.
- Add an offline fixture mirroring the live nesting and unknown fields.

### Immutable identity from short hashes

Some public image resources expose a short model hash while the local ledger stores a full SHA-256. Do not discard the short hash, pad it, or treat a filename match as immutable identity.

Safe enrichment pattern:

1. Use independently provided model-version identity when present.
2. Fetch the model-version file list.
3. Require a sole compatible resource and a unique file whose API hash starts with the observed short hash.
4. Bind model version ID, file ID and full API SHA only after that unique match.
5. Resolve against the independently hashed local ledger and require full-hash verification.
6. Zero or multiple matches remain unresolved.

A real wrapper smoke must inspect `ready`, `resolved`, and `hash_verified`, not just HTTP 200.

### Missing base sampling fields

A public recipe can pass import and strict resource resolution yet still fail build because base sampling metadata omits scheduler or denoise. Do not copy hires denoise into the base pass or invent a scheduler merely to satisfy the compiler.

Investigate in this order:

1. Search all source/API representations for an auditable value.
2. Determine whether the source ecosystem defines a deterministic default and preserve provenance if using it.
3. Treat base txt2img denoise as a semantic constant only if the compiler contract explicitly models that rule.
4. If a field cannot be uniquely derived, improve candidate selection to require complete metadata or fail closed.
5. Add a real-payload offline fixture and compiler regression for the chosen policy.

## Verification sequence

1. ComfyUI and backend health checks.
2. Red focused test for the observed request/payload shape.
3. Minimal production correction.
4. Focused acquisition/API tests.
5. Separate complete backend and MCP suites.
6. Restart backend if needed.
7. Invoke the real MCP wrapper against one public image.
8. Inspect recipe resources, passes/sampling and reproduction diagnostics—not only `ok=true`.
9. Confirm queue remains empty until strict resolve and build succeed.
10. Commit repair, owner-resume, and wait for the real dispatcher cron.

## Control-plane lesson

A frozen CIV-G executor correctly stopped when production code was out of scope. The owner layer should preserve that result, create a separate repair commit, resume the unchanged frozen stage, and continue until its acceptance contract is satisfied. A read-only watchdog may report the blocker but cannot replace this owner cycle.