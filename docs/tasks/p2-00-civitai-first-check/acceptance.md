# Accepted Phase 2 First check observation

Producer [AID-146](/AID/issues/AID-146) accepts exact [Coding AID-178](/AID/issues/AID-178)
`a9de23389fb29ce4f6f8191184c9279670201abf` after actual independent [QA AID-179](/AID/issues/AID-179)
D1–D5 observation **PASS**, report/evidence `cec8087e2812ef29fdd0f4bdd70223deb796e9c0`.
Actual kickoff [AID-177](/AID/issues/AID-177) is round-1 **CLEAR** at unchanged brief
`0ccf65c`, report `4702a662a88bf5611dcee9c5da1964a21a41aa74`. No kickoff ambiguity,
implementation rejection or repair is introduced by this evidence-only task.
Original [manifest](manifest.md), [independent report](review.md), [ledger](friction-ledger.md)
and raw evidence remain unchanged; their pending-acceptance wording is historical.

| Done when | Actual accepted observation |
|---|---|
| D1 baseline/source/access | Actual source/import/package/runtime/root/job/key-access/budget observations; 147 fixed-source fingerprints match Git. Runtime source is bounded, with the five-hash limit below. |
| D2 provider/download | Real safe search and one selected login-required free-key file: anonymous HEAD/GET 401, credentialed route 307, credential-free CDN 200; 228,518,900 actual LoRA bytes match provider size/SHA-256. |
| D3 registration/image | Two current resource rows (80 new LoRA, 81 adopted existing checkpoint), sole local default_lora job, actual LoRA/trigger/parameter/graph/PNG/persistence linkage and retrieved bytes. |
| D4 full accounting | 15 capability + five recovery interventions = 20; 64 observations + seven prep/audit + six completed delivery blocks = 77 work units. Overlapping classifications are not added; 14 provider requests, one submit, one wait, 42 same-ID status GETs; seven used modules including a value type, 12 operationally untouched. |
| D5 independent delivery | Exact full Coding/QA/kickoff commits, 14 official downloads, all indexed packets and independent bundle/patch reconstruction verified. QA completes observation review on its own card, no product repair. |

## Actual image and resource chain

LoRA model 551903/version 1843039/file 1743033,
`WatercolorMJ7Illustrious.safetensors`, resource 80; actual SHA-256
`77d71396e29a26225a6dce2544930e58983fc12a754f8fb602df11ee383ee34b`.
Existing checkpoint 6,938,040,674 bytes/hash `c2a1a3eaa13d4c107dc7e00c3fe830cab427aa026362740ea094745b3422a331`
correlates to model 1489531/version 1684912/file 1586063 and resource 81.
The counted provider/local-name mapping adopts existing bytes, no checkpoint
redownload, rename or overwrite. License retained, no commercial-use filter.
Selected LoRA version level 1 was used; model aggregate level 23 despite
nsfw=false remains an explicit safe-search design gap. No preview was fetched.

Job `da6a825f-5687-4b7e-94e2-f213ae33150c`, Comfy prompt
`82c8a922-706e-4727-8e9e-503de19e7444`, image 4463, artifact **3878**.
Local/default_lora, seed 638386492, 512×512, 20 steps, CFG 7, Euler/normal,
LoRA model/CLIP 1.0/1.0; actual `ArsMJStyle, Watercolor` triggers manually
appended to the blue-cup still-life prompt. Submitted/persisted/history/PNG
graphs agree, sampler/LoRA uncached and 20 real steps. The 18.49-second log
value is total prompt execution, not isolated inference/performance acceptance.

Original 333,502-byte PNG equals QA's independently
retrieved copy, SHA-256 `8268b9571b8b9535b9500994a021919de317f84b1fbb36d9b74468d969ca3673`.
Producer views this byte-verified official copy: a blue cup on a wooden table,
no people. CTY alone judges aesthetics. The full new-session MCP/Gallery/graph
proof supports one technical pair, not automatic defaults or Phase 2 exit.

## Limits, privacy and preservation

Accept **P2 fingerprint-redaction limitation** as reported, with no rewritten
original measurement. Five ComfyUI paths containing tokenizer lost their
before-run hashes to the evidence helper's broad token-key filter. The other
787 Comfy fingerprints and 137 Backend runtime hashes matched independent QA;
five current files match recorded Git objects, which cannot replace missing
before-run measurements. [Decision](../../decisions/evidence.md) prevents this
loss in future helpers. No P0/P1 finding or real secret disclosure is evidenced.

The ledger retains all failed operations, wrong import-root missing-table
failure before admission, counted credential/transport/registration/default
bridges and bounded recovery. No unresolved measured job, generation resubmit,
worker fallback, product repair or restart. QA preserves all 9,218 old rows in
15 tables/schema; only two resources, one image/artifact added. No exhaustive
whole-disk inventory is claimed. Retain AID-178 private before snapshot/helpers,
all AID-171/AID-151 runtime/config/backups, canonical environments and every
model/dataset/output/Gallery record; publication is not runtime deployment.

This baseline defines its own units; do not compare 20 with the original Phase 1
23 as a measured improvement. Phase 1 baseline/eight incidents, old 81 and later
Coding 36/QA 15 retain their own limits. The Phase 2 three-different-sentence,
at-least-one-new-checkpoint-plus-LoRA, automatic resource/default flow and zero-fix
exit remain unmet. No broad auth/refusal/Early Access/rate-limit/cancellation claim.

## Verification levels

- Offline: QA fresh Backend 1916 passed/124 skips; MCP 666/four skips; registered PNG six passed; frontend 226/one skip/build passed, all 18 registry rows unchanged. Coding replay 23/QA audit 37 assertions passed. Windows unrun. Producer checks exact source/packet/Git/PNG/count/document/publication identity, no redundant full suite on identical product inputs.
- Running product: original measured runtime/queue/schema/source and QA's four local GETs/actual file and row comparisons. Producer makes no new product/provider probe, restart or deployment.
- Real provider/generation: one free-key login-required LoRA download and one local checkpoint+LoRA job, preserved with all manual interventions; QA/Producer submit no replacement work.
- Retrieval: original MCP canonical PNG plus QA local Gallery HTTP re-read; Producer views official copies only, not a new live Gallery read.

All 14 official uploads/three receipts are verified against named hashes and
native/Git identities; ZIPs contain 79/90/119 indexed payloads (80/91/120 members),
all exact immutable bodies/metadata. Three bundles verify prerequisites and fetch
in a new bare store; kickoff binary/full-index patch reconstructs its exact tree.
One initial shallow-source fetch required --update-shallow; corrected verification
passes, without source/evidence changes. Raw log whitespace stays untouched.
Integrity receipt records the
full checks and 147 source fingerprints.

## Next work from the measured gaps

[Bounded implementation intake](implementation-intake.md) orders work inside
Phase 2. First is [private key loading/credential-safe requests](../p2-01-civitai-key-file/task.md),
with its own fresh independent CLEAR and exact-commit QA. No routine owner question
or architecture/phase change. First check acceptance authorizes no unreviewed code.
