---
name: source-snapshot-file-permissions
description: Preserve numeric POSIX permissions separately from Git file modes when preparing source snapshots and rollback kits.
metadata:
  type: project
---

## Context

Git regular-file modes `100644` and `100755` distinguish executable classes, not the original numeric POSIX permissions. Integration kit `92e96e9fa73dbfad28f0fa36108d60f4a1cacf40` recorded only that Git projection. Its capture normalized 45 selected files from `0600` to `0644` and one from `0711` to `0755`. The original QA report describes all 46 as `0600`; the retained `posix-mode-audit.json` and complete numeric-mode snapshot establish the more precise breakdown.

Independent scratch replay of the actual canonical permission metadata showed five patched files become `0600 → 0644 → 0644` through apply and rollback, while every helper step reported PASS. Bytes were restored, numeric permissions were not. This kit failed its preservation criterion; previously accepted feature source remains accepted within its separate offline scope. No canonical application or deployment occurred.

The separately frozen packaging revision `aid36-posix-v1` passed independent offline review with the same Git source commit/tree. Hash-bound numeric sidecars and archive attributes retain all 920 original permissions, including `0711`; scratch apply and rollback preserve the five `0600` files and all original bytes/absences. The new kit's controls SHA256 is `6f08dc085f3b69a5e401bde917655411e8251e152a45fcf6e0d5e134e13383b4`. This accepts that specific kit's preservation behavior, without rewriting the old FAIL or establishing canonical integration.

## Why

An archive baseline already normalized to Git modes can pass a round trip while losing the user's original permissions. A matching Git tree and byte hashes do not establish preservation of numeric POSIX modes.

## How to apply

For source-preservation and rollback work, retain original numeric permission metadata bound to the exact selected paths and preimage hashes, separately from Git tree identity. Reconstruct that metadata in scratch before testing. Verify bytes, numeric permissions and original absences after apply and rollback, and reject permission drift before writes. Preserve unrelated files and never normalize the canonical workspace to make a preflight pass.

Read both the Git source identity and the separately hash-bound kit revision before use. Current canonical authority/memory bytes can differ from a frozen preimage. Every selected write preimage must still reject drift; preserved nonwrite authority is a separate domain and must not be overwritten to match an older snapshot. Preserve those newer bytes when planning actual integration, and assess runtime consumers and reload behavior before writing into a live source location. These findings concern selected regular files and POSIX numeric permissions. They do not establish ACL, extended-attribute, ownership, concurrent-writer, disk-failure or installed Windows preservation, nor grant merge, service or deployment authority.

An operation projection tree identifies the selected before/after write domain, not the complete product source. Bind the exact product commit/tree and the separately frozen kit/controls identity, and explicitly list assembly exceptions for preserved current authority and any reviewed topic-doc merge. A current-only memory ref is not a missing product file to delete. The independently reviewed newer kit reuses the old helpers unchanged with new path metadata: later authority/memory updates survive source apply and rollback while write-path drift still refuses before changes. This is scratch source-preservation evidence, not permission to create a scratch marker in canonical or to adopt source.

## Evidence

- [New-baseline source kit](http://127.0.0.1:3100/AID/issues/AID-52#document-engineering-handoff), revision `f84facab-0e8b-4751-8248-508ebedd1444`, and [independent packaging PASS](http://127.0.0.1:3100/AID/issues/AID-53#document-qa-report), revision `0d80ae61-b3c1-4c25-b48b-ca3e8e179340`: `aid52-source-kit-v1`, controls SHA256 `143e04fcd1c53a28ed9807cd1c512dd00f59a36634c96e3713a8750fdd1ba049`, exact product source `9b96655ea4994932854ea6028f25a58fe4a6302e`. The reviewed write projection excludes current authority prefixes; full assembly has eight explicit authority/topic exceptions. Independent capture-after changes, numeric/absence preservation and zero-partial-write refusals pass. [QA evidence](http://127.0.0.1:3100/api/attachments/7aefcdfd-77a8-4909-8d0c-2fbe49db70d2/content?download=1), SHA256 `713a692d6c732bd6ff02cd32e4c3b8f94cfa42184e4208cb3cb24c3a34379ff7`. The review does not certify runtime consumers, state rollback or live adoption.

- [Frozen integration handoff](http://127.0.0.1:3100/AID/issues/AID-34#document-engineering-handoff), revision `95766eb9-5324-4347-9e74-1d9975ed74c0`, candidate `92e96e9fa73dbfad28f0fa36108d60f4a1cacf40`; `source_ops.info()` and capture use executable-bit-only projection.
- [Independent FAIL](http://127.0.0.1:3100/AID/issues/AID-35#document-qa-report), revision `e00cc667-8ac3-4169-9499-4118ef593d8e`, QA35-01. [Immutable evidence](http://127.0.0.1:3100/api/attachments/d7062d69-35ca-4c02-9f1e-425146b19d2b/content?download=1), SHA256 `c20ce6a5a225396a415304da7680eeb67d3743555b7a4e9590befa6055bdba7f`: `evidence/posix-mode-audit.json`, `posix-mode-roundtrip.json`, `posix-mode-assertion-confirmed.log` and `qa_posix_modes.py`.
- [Frozen repaired kit](http://127.0.0.1:3100/AID/issues/AID-36#document-engineering-handoff), revision `83e2df15-a080-4973-9927-92fc501300af`, and [independent PASS](http://127.0.0.1:3100/AID/issues/AID-37#document-qa-report), revision `880a519a-c561-48f1-8761-9563606086e7`: original five failures RED→GREEN, 920/947 complete numeric-mode checks, 0711, permission-drift and archive-attribute refusal counterexamples. [Kit ZIP](http://127.0.0.1:3100/api/attachments/efca895a-6c3f-49f3-9310-2d731da143e4/content?download=1), SHA256 `2e834b8142a47366c76c58daea2737bb8fdc64a5804bc0f12f1c64525c6d0fa0`.
