# Decisions · Civitai credential transport

## Settled

- Provider requests are stateless with respect to cookies. Backend-owned credentials
  may travel only in Authorization to canonical HTTPS civitai.com; implicit cookie
  jars, caller Cookie and Proxy-Authorization must not create another channel.
- Verify the final outgoing request after HTTP-client preparation on every initial
  request/redirect, including same-origin and return hops. Removing an explicit
  Authorization header alone does not establish credential isolation.

## Log

### 2026-11-26 · Enforce the existing channel policy after client preparation

- Decision: prevent acceptance/persistence/replay of provider cookies and strip
  disallowed credential headers at the final request boundary while preserving
  allowed canonical Authorization, sticky cross-origin stripping, deadlines and
  response closure. Coding selects the smallest proven implementation.
- Why: HTTP clients may add cookies after a caller-header filter. A domain cookie
  from a canonical response can appear on an allowed CDN request even when the
  caller supplied none and Authorization was removed. Live responses without
  cookies cannot test this negative boundary.
- Provenance: Producer's bounded technical application of the already-cleared
  Authorization-only/canonical-origin contract, following the actual
  p2-01 adverse review.
  It is not a new owner quotation or a changed Phase 2 boundary.
- Applies: retained Civitai request factories, registered acquisition/background
  routes and inspect/install adapters. Observe actual outgoing headers in realistic
  cookie-setting fixtures and prove fault sensitivity. Keep old adverse evidence
  immutable; original selected live HEADs observed no cookies, so no actual
  owner-key disclosure is inferred. Correction 1
  is accepted at exact 24dad88f after independent review 2 PASS cdf63e71;
  [acceptance](../tasks/p2-01-civitai-key-file/acceptance.md) preserves fault and
  fresh source evidence. Source publication is not running-Backend deployment.

## Open questions

None for this bounded correction; product PASS and phase/aesthetic decisions
remain separate from this contract.
