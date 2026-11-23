---
name: control-file-lock-ownership
description: "Bind lock ownership to the acquired resource and distinguish literal path absence from dangling or foreign entries during recovery."
metadata:
  type: project
  curated_on: "2026-11-06"
---

## Context

An exclusive create acquires a specific filesystem object. Sampling its pathname after closing the descriptor can instead record a replacement with identical bytes; following a dangling symlink can also report a lock as absent while its directory entry remains. Independent review reproduced both cases in the frozen Git checkpoint helper.

## Why

Incorrect ownership or absence claims can delete another writer's lock or report completed recovery while the lock pathname is still occupied.

## How to apply

For an authorized lock-based control-file operation, bind ownership to the resource actually acquired while its descriptor is available. Confirm the literal pathname still identifies that resource before claiming custody or mutating/removing it. Check directory-entry presence without following symlinks; distinguish real absence from dangling, special, unknown or foreign entries, and refuse ambiguity while preserving those entries. Matching contents or elapsed time cannot establish ownership.

Apply the same ownership and absence checks to acquisition and every recovery/completion branch. Retain cooperative writer exclusion and recheck the exact implementation's independent verdict; these checks alone do not establish containment against arbitrary writers.

## Evidence

- [Retained checkpoint review and failed-procedure assessment](../PROGRESS.md#m1--image-request-and-revision-through-mcpthe-existing-ui-active) — routes to the independent lock-substitution and dangling-lock counterexamples in the frozen helper.
