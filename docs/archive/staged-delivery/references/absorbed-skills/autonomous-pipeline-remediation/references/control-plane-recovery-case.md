# Imported historical source

Source: `autonomous-staged-change-delivery/references/absorbed-skills/autonomous-pipeline-remediation/references/control-plane-recovery-case.md`. Original SHA-256: `e2e75b255ed90982c3b3ff964bd9003fc0f3ce3be857a36f65c952010e55dacd`.

Historical and version-sensitive; not current project policy, status, or authorization. Revalidate against this project's current entrypoint and authoritative records before any separately authorized execution. Original language is preserved below.

---

# Civitai pipeline control-plane recovery case

This case records durable control-plane lessons from a live image-recipe pipeline. Product-specific IDs and transient timestamps are intentionally omitted.

## Repeated dirty-scope mismatch

A worker declared both Git-visible changes and an ignored runtime artifact in `files_changed`. The dispatcher compared that list with `git status`, which never includes ignored artifacts, so every otherwise-valid blocked result became `FAILED`.

Durable fix:

- Keep `files_changed` equal to Git-visible dirty paths.
- Add optional `evidence_files` for ignored artifacts.
- Validate evidence paths separately: under the evidence root, no traversal, file exists, allowed glob matches, never committed.
- Support legacy results by safely classifying known evidence-root entries.
- Permit an absolute path only when it exactly equals the current run's own machine-result path; normalize it to the project-relative path. Reject all other absolute paths.
- Add regressions for valid evidence, missing evidence, traversal, own-result normalization and legacy classification.

## Recovery cannot contradict the source stage

The source stage allowed exactly one external job and forbade retry. Adding an owner note saying “one recovery is authorized” did not override that frozen prohibition; workers correctly continued to block.

Durable fix:

- Keep the failed job immutable.
- Repair production first.
- Create a separate recovery stage with a fresh, explicit one-job budget.
- Carry forward only the valid dirty scope/evidence.
- State that the original failed job is preserved, one new recovery job is permitted, and a second recovery remains forbidden.
- Dispatch via the real scheduler.

## PID-dead false alarms

The watchdog repeatedly reported `PID dead while run RUNNING` after workers had already written valid results but before the next dispatcher tick.

Durable fix:

- Check machine result before PID liveness.
- If a valid result exists, report result status and wait for harvest.
- Report a crash only when PID is dead and no valid result exists after the grace/harvest window.
- Track the newest active recovery stage rather than an older historical failed source stage.

## Polling and owner progress

Polling gaps are acceptable within cadence. A remediation is stalled only when the owner exceeds the agreed start/progress SLO. Validate project evidence, not cron `ok`:

- selected stage/run and blocker signature;
- owner claim/heartbeat;
- red test or real diagnostic;
- relevant diff/commit;
- official resume and new scheduler-dispatched run.

If an owner returns `NO_ACTION` because it believes Judge or user authorization is required for a local repair, correct the role mapping: owner may repair production and create a bounded recovery contract, while the worker remains forbidden from expanding its own frozen scope.

## Integration defects revealed sequentially

A successful control-plane fix can expose the next legitimate boundary defect. In this case the sequence included audited resource filename binding, JSON/base64 binary transport and source sampler label translation. Treat each as a new blocker signature, use TDD, and do not claim the whole pipeline fixed merely because the prior blocker disappeared.
