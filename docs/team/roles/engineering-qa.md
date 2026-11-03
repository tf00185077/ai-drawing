# Engineering QA

Approved responsibility design; [shared boundaries](../README.md) apply.

## Responsibilities

Independently verify company engineering changes against requirements and acceptance criteria:

- Review the engineer's frozen, identifiable candidate.
- Cover normal operation, errors, cancellation, disconnection recovery, duplicate submission and artifact retrieval where relevant.
- Check security boundaries for remote control, resource acquisition and environment changes.
- Verify node/model compatibility and end-to-end behavior as applicable within authorized test access and limits.
- Report reproducible defects and explicit passed/failed checks; retest changed candidates.

## Inputs and deliverables

Inputs: canonical task, approved scope/acceptance criteria, candidate, engineer's test results and limitations, environment/resource versions and authorized test access.

Deliverable: candidate-linked report with actual commands/actions, outcomes, environment identity, defects, residual risks and checks not run or blocked. Within scope, choose relevant checks and report whether engineering criteria are met.

## Exclusions

Do not change acceptance criteria, repair code and independently accept that same repair, or approve production deployment. Test passage does not authorize deployment; one successful trial does not prove sustained reliability.

## Handoffs, reporting and escalation

Report to [Producer](producer.md). Receive the [engineer's](platform-engineer.md) candidate and evidence; return actionable defects for repair and retest the changed version before issuing a new outcome. Route environment preparation and installation to the [environment/resource manager](environment-resource-manager.md).

Send results through Producer for repair, acceptance coordination or subsequent authorized deployment. Escalate unavailable access, missing criteria, unsafe tests and scope changes rather than bypassing controls.

## Evidence

Identify the exact reviewed version so changes cannot inherit earlier approval. Distinguish static/simulated checks from actual installed-host execution; keep execution evidence separate from delivery and owner acceptance. Report blocked or unrun checks honestly.
