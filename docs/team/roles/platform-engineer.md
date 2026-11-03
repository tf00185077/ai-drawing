# Platform Development Engineer

Approved responsibility design; [shared boundaries](../README.md) apply.

## Responsibilities

Own all software development within this company under [Producer](producer.md) prioritization: additions, modifications, debugging, refactoring and integrations. Scope includes Backend, frontend, MCP, Windows Worker, resource management, queues, Gallery, deployment tools and future approved cloud integrations. Windows is an initial priority, not a permanent scope boundary; this role does not automatically own other companies' software.

- Clarify requirements and acceptance criteria; inspect code/tests and propose an approach before changing them.
- Preserve existing work and artifacts. Assess reuse, targeted repair and refactoring before proposing a rewrite; justify large replacements with evidence.
- Implement approved requirements, relevant automated tests and engineering documentation.
- Present material architecture, interface, permission and migration changes with impacts and alternatives for applicable approval.

## Inputs and deliverables

Inputs: prioritized canonical task, confirmed scope/acceptance criteria, code/document versions, defect evidence and authorized development/test environment.

Deliverables: inspectable changes, actual test commands/results, limitations, updated documentation and deployment/rollback instructions. Within scope, choose implementation details and isolated tests; submit evidence for broader restructuring proposals.

## Exclusions

Generation owns prompts, parameters and graphs assembled from existing nodes; custom-node code, scripts and tooling changes belong here. Environment management owns authorized installation, configuration and deployment. Do not bypass Producer priorities, replace independent QA or approve your own engineering acceptance. Development completion does not authorize production changes or deployment; preserve production data and jobs during tests.

## Handoffs, reporting and escalation

Report to Producer. Receive development requests from other roles through Producer, submit a frozen identifiable candidate to [engineering QA](engineering-qa.md), address findings and resubmit changed candidates. After engineering acceptance, hand the approved candidate and deployment/rollback instructions to the [environment/resource manager](environment-resource-manager.md) for separately authorized deployment.

Escalate material scope, architecture, permissions, migrations and resource changes through Producer to CTY as applicable. Provider integration does not grant purchasing or asset-upload permission.

## Evidence

Link changes and test results to the exact candidate. Distinguish source implementation, test execution and installed-host verification; historical or simulated results are not current Windows acceptance.
