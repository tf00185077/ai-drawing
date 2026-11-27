# Resource record implementation plan

Spec: [cleared task](task.md); base 7f1967742007fa1e6f271b856cdbdeabaa6d761d.
Native execution under explicit in-boundary delegation; separate independent QA follows.

Goal: existing resource-row authority shared by current writers/readers and bounded HTTP reads.
Architecture: additive nullable versioned metadata JSON on DownloadedResource, typed normalization/projection/publication, explicit offline backfill. Existing IDs/path/hash/status remain authoritative. Frozen adapters retain recipe/Anima behavior.
Stack: existing Python 3.11/FastAPI/Pydantic/SQLAlchemy/SQLite.

Constraints: exact D1–D5; synthetic fixtures; no live provider/model action, private reads, shared-main writes, canonical installs, MCP/registry changes, merge or self-PASS.

1. D1: failing ORM mapping/snapshot/evidence/conflict guards; implement shared typed snapshot/publication/projection; GREEN.
2. D2: failing registered non-first acquire and inspect/select/install/background/ledger guards; wire writers and frozen adapters; GREEN and legacy regressions.
3. D3: failing previous-schema whole-table/value/notes/alias/history/file audit; additive startup and explicit idempotent backfill; GREEN.
4. D4: failing HTTP/OpenAPI bounded filters/errors/no-side-effect guards; SQL reads/router; GREEN.
5. D5: freeze software/tests/helpers; effective mapping/verification/writer/backfill/list faults and exact restoration; full Backend/MCP and fresh registry producer/readers; fingerprints, manifest and durable exact delivery.

Review focus: identity conflicts under reuse; incomplete legacy notes never fabricate verification; strict descriptors preserve selected metadata; duplicates and malformed old values remain intact; SQL total/pagination and no read repair.

Progress: initial environment setup used system Python 3.9 by mistake and stopped before writing source; corrected explicitly to python3.11. A nonexistent guessed test name was resolved with rg --files. All subsequent attempts are retained in evidence/*.json/log and manifest.
