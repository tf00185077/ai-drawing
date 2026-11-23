# Windows worker: source and acceptance gaps

This page describes source, not an installation/update SOP or installed-host verification. Remote execution requires compute requirements and operating policy. Product repairs do not block company onboarding; see [Goal](GOAL.md).

## Owner report

The owner last reported the Windows Worker as not installed and has now deferred installation and result reporting. The reviewed installation handoff remains available, but user installation is no longer the prerequisite for advancing the company agenda. This is not installation success or permanent cancellation of the Windows direction. The former installation-result card was superseded; retain the completed guide, source package and independent QA. See the [latest owner direction](http://127.0.0.1:3100/AID/issues/AID-4#comment-bf46ca77-46f4-4938-91c2-d4d6c4116f18). Any future resumption must reconcile actual installed state before proposing host checks. No agent installation, host connection, download, remote command, service or deployment permission follows from deferral.

Previous failed Worker/updater attempts are historical. Broad terminal access followed failed narrower API attempts to get generation working. A LAN address change remains a hypothesis: contemporaneous logs, configuration and installed-version records are insufficient to establish the cause. Earlier progress reports do not prove installation or deployment success.

## Source paths and security

- `backend/app/services/nvidia_worker.py`: configured URL, discovery, runtime URL cache and Worker client.
- `backend/app/api/workers.py`: Backend status and PowerShell proxy API.
- `worker/windows/worker.py`: Worker status, PowerShell commands and ComfyUI proxies.
- `worker/windows/Install-Worker.ps1` and `Start-Worker.ps1`: installation/startup and retained updater/recovery logic.

The Worker exposes status, PowerShell submit/status/cancel and ComfyUI `/prompt`, `/queue`, `/history/{prompt_id}`, `/view` and `/upload/image` proxies. PowerShell routes lack authentication: reachable clients can execute commands under the Worker account. Hostname/protocol filtering is not authentication. Keep this interface private; tool availability does not authorize remote administration.

## Retired API versus retained updater

Managed-update/restart HTTP, resource-plan/content and workflow-preflight routes are retired. Token/pairing does not authorize open-control requests. Backend startup no longer launches the managed-update coordinator; old update state does not gate generation.

Legacy updater modules/tests remain. Installation can create updater components/tasks; `Start-Worker.ps1` can invoke recovery when files exist. Retired routes can return 404 without an IP change. Inspect installed versions and recovery state before changing startup recovery; old updater plans are not current instructions.

## Configuration and discovery

Backend settings: `NVIDIA_WORKER_URL`, `NVIDIA_WORKER_DISCOVERY_ENABLED`, `NVIDIA_WORKER_HOSTNAME`, `NVIDIA_WORKER_PROTOCOL_VERSION`, `NVIDIA_WORKER_DISCOVERY_CIDR`. See `backend/app/config.py` for defaults; use deployment-owned values.

- Discovery defaults off. It scans IPv4 `/24` on the worker port, not DNS/mDNS; the configured CIDR must contain the failed IPv4 address.
- Only connection errors/connect timeouts trigger discovery. Read timeouts/HTTP failures do not resubmit side-effecting requests.
- Discovery requires one matching hostname/protocol candidate. The process-local URL cache has no TTL; settings and discovered-URL caches are separate.
- The worktree fix ignores discovered-URL cache when discovery is disabled. Enabled cache/rediscovery behavior is unchanged. A mocked regression covers the fix; Windows deployment is unverified.
- Health can accept a responding host with the wrong hostname/protocol; cache and scan comparisons differ in casing. Neither finding establishes the owner's failure cause.

Supported generation interfaces accept `local`/`worker`, defaulting to `local` when omitted. This is a source default, not company routing policy. MCP direct ComfyUI operations use a separate URL, unaffected by `execution_target`. Status or PowerShell success does not establish CUDA/model/node readiness or artifact recovery.

## Installation handoff and next evidence

The [frozen first-installation guide](http://127.0.0.1:3100/AID/issues/AID-10#document-installation-guide) and its downloadable source snapshot have [independent static QA](http://127.0.0.1:3100/AID/issues/AID-11#document-qa-report) for a standalone venv and normal-user foreground Worker on `127.0.0.1:8791`. They prepare the control layer only; Windows execution and installation success still require the user's result. Keep the reviewed guide unchanged and use its exact source hashes. The full installer at the reviewed commit omits a required module from its copy/migration chain; Setup and Enable helpers exist, but neither is the selected first-install route. See the guide and QA for version-specific evidence rather than substituting legacy commands.

1. Inspect the current installation entry points and their transitive files. Distinguish first installation from upgrade, migration, cleanup and enablement of an existing scheduled task. A legacy README or missing helper is not a usable initial-installation route.
2. Deliver an independently reviewed guide and identifiable file/source references. State which commands download dependencies, change firewall or scheduled tasks, start services or alter existing paths. Preserve existing ComfyUI, models, datasets, outputs and unrelated services. Mark Windows checks not actually executed.
3. Wait for the user's installation result and identifiable version/log evidence. Do not substitute historical attempts or the presence of source files for installation completion.
4. Only then propose the applicable bounded connection, resource and functional checks. Validate hostname/protocol, target resources, artifact retrieval and failure recovery within their separate authority.
5. Keep management authentication, training routing and deployment acceptance separate. Open PowerShell control remains unresolved security exposure; source defaults do not constitute an approved operating policy.

The cache fix does not establish recovery from the original incident, secure the Worker or complete acceptance. These are product tasks for the company after activation, not prerequisites to creating it.
