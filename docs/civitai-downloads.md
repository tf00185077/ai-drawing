# Bounded Civitai downloads

The p2-03 candidate applies the [download decision](decisions/civitai-download-limits.md)
through existing acquisition and retained inspect/select/install. Independent exact
candidate QA and Producer acceptance remain separate. This is source behavior,
not a statement about the running Backend or durable download jobs.

## Effective policy and selection

Backend Settings reads these existing configuration/environment names:

| Setting | Default bytes | Meaning |
|---|---:|---|
| `CIVITAI_DOWNLOAD_MAX_BYTES` | 8589934592 | 8 GiB per selected file |
| `CIVITAI_DOWNLOAD_FREE_SPACE_FLOOR_BYTES` | 21474836480 | 20 GiB observed destination free-space floor |

Both must be positive integers. Environment decimal integer strings are accepted;
direct booleans, floats, null, missing policy attributes and invalid/zero/negative
values refuse. Settings rejects malformed configuration rather than inventing an
unlimited or larger default. Explicit small positive fixture values are supported.
A direct incomplete settings object reports `civitai_download_policy_unavailable`.
Settings validation errors occur when configuration is loaded, before acquisition.

Provider `size`, when non-null, is authoritative bytes; otherwise `sizeKB` means
exactly 1024 bytes per unit. A finite numeric value must yield an exact positive
integer number of bytes using its decimal spelling. Fractional bytes, booleans,
strings, non-finite and nonpositive values are unknown/invalid, never rounded or
truncated. Inspect, acquisition and typed provider snapshots share this rule.
Execution additionally requires a valid 64-hex SHA-256 and size within the cap.

Ordinary checkpoint/LoRA acquisition selects a safetensors candidate even when a
pickle file is primary. A malformed primary still refuses. Retained checkpoint/
LoRA descriptors require a `.safetensors` name; extension comparisons ignore case.
No pickle fallback is submitted. Frozen Anima checkpoint packages retain their
component selection, format eligibility and diffusion/text-encoder/VAE routing.
Other retained kinds keep their existing eligibility. All selected components pass
byte/type/destination admission before any package resource row is mutated.

## Admission, stream and resume

Metadata/policy/type refusal, foreign/unsafe partials, conflicts and insufficient/
unknown admission space create no new row. Admission observes free bytes on the
actual existing destination ancestor filesystem: remaining declared bytes plus
floor must fit. Before every write it observes that free bytes minus that chunk
retain the floor. An unknown/failed observation refuses. These are observations,
not reservations or a persistent aggregate budget; another process can consume
space between observations and writes.

Acquisition commits the existing resource ID before background execution. Retained
install now also commits admission before opening a model body or creating a part.
Failures after admission publish `failed` and the current sanitized reason under
`metadata.source_evidence.acquisition` on that same ID. Old notes and known identity
columns remain evidence. Retained errors include `diagnostic.resource_id`; read it
through existing acquisition status or canonical resource detail. There is no new
attempt table, resource registry, generation job, scheduler, MCP intent or hidden
second submission. An unavailable database can prevent recording a failure; such
an error is returned as `ledger_persistence_failed`, never installation success.

A resumable `.part` needs authority from that existing row: provider, selected
version/file/resource IDs, declared SHA-256 and byte size, complete device/inode/
size/mtime/ctime fingerprint and full prefix SHA-256. Model ID is retained when
known. The helper records this proof in the row after exclusive creation and each
successful chunk. An interrupted invocation closes its handles, retains its bound
prefix and records current failure; this is safe reuse, not process restart/job
recovery. Missing legacy proofs, a different selected identity, changed bytes/stat,
symlinks, multiple links, nonregular or oversized partials refuse unchanged.

A 206 must contain `Content-Range: bytes OFFSET-(SIZE-1)/SIZE`, exactly matching
the retained prefix and selected size. Supplied Content-Length must equal coverage;
missing Content-Length permits chunked transfer. Missing/malformed/mismatched range
refuses before append. A 200 may restart only the exclusively created or verified
associated part, after full fresh-space admission and before truncation. Actual
prefix plus streamed bytes may exceed neither declared size nor cap; each violating
chunk is rejected before writing. Partial bytes count toward the final full-file
hash. Body coverage, final exact size and SHA-256 must all match before publication.

## Ownership, publication and failures

Files open without following a final part symlink; new parts use exclusive creation.
Held descriptor and pathname fingerprints are checked around writes/hash/publication.
Hash verification and the current ProviderOperation deadline precede same-filesystem
`link` creation of the final name. Link creation is atomic and fails if the final
already exists, including a target created after admission. It never replaces a
file, directory or symlink. After verified linking, only the still-owned part name
is removed. Unsupported link publication fails; there is no replacement fallback.

Preexisting exact-file adoption is an explicit full size/hash verification with
unchanged ownership. Acquisition records adoption eligibility before admission;
a later collision, even with identical bytes, cannot be adopted as this download.
Known acquisition rows retain their raw recorded storage path when configured roots
change; a new-root collision cannot redirect or replace that existing identity.
Retained compensation after ledger failure removes only a still-owned publication;
a replaced final survives. Failure cleanup removes only a newly exclusively created
part with unchanged fingerprint and matching observed prefix digest. Foreign,
changed and preexisting partials survive failure. A deadline that prevents cleanup
verification leaves the part rather than extending the deadline or deleting it.

Stable download reasons include `civitai_invalid_file_metadata`,
`civitai_byte_limit_exceeded`, `civitai_unsafe_format`, `civitai_space_unavailable`,
`civitai_insufficient_space`, `civitai_unassociated_partial`,
`civitai_unsafe_partial`, `civitai_file_changed`, `civitai_invalid_range`,
`civitai_target_exists`, `civitai_verification_failed`, `civitai_invalid_body` and
`civitai_download_failed`. Deterministic refusals are not network retries. Provider
429/5xx/network request failures retain the existing three-request bound/backoff;
an interrupted body does not silently submit a fresh download. Existing provider
credential/origin/redirect/deadline codes and recovery hints remain authoritative.

[Credential-file precedence and prepared-header isolation](civitai-credentials.md)
continue through the real ProviderOperation/ProviderDownloadTransport. The same
absolute download deadline spans disk observations, prefix/final hashing, reads,
retries/backoff and publication/row measurement. Iterators, responses and descriptor
handles close on every exit. Public normalization operates on outgoing copies;
internal path/ownership decisions use raw Backend authority. Ordinary source hashes
are preserved. Measured verification is recorded only for the verified publication
or explicit unchanged adoption, never for a colliding file.

## Evidence and limits

See the [Coding manifest](tasks/p2-03-bounded-download/manifest.md) for D1–D5,
compatibility replacements, qualification and actual delivery identity. Offline
synthetic Settings/HTTP/ORM/filesystem fixtures are separate from running-service,
real generation, live model/Gallery retrieval and artistic/Phase 2 acceptance.
No production key/configuration, data, runtime, model or environment changes are
needed by this task. Native Windows behavior requires its own platform run.
