## Why

After an agent decides a dataset can be trained, Hermes still needs a standard handoff for asking the user, starting the explicit training run, monitoring it, registering the output, smoke-testing the LoRA, and reporting the result. This change captures the runbook and report contract so training remains user-directed and auditable.

## What Changes

- Add an OpenSpec capability for the agent-guided LoRA training handoff runbook.
- Define the standard pre-start report that Hermes/OpenClaw presents before an explicit training request.
- Define the monitor/register/smoke-test workflow using the existing MCP training tools.
- Define the terminal report for completed, failed, or cancelled training runs.
- Keep the runbook manual-first: no step starts training until the user asks to train the specific LoRA.

## Capabilities

### New Capabilities
- `lora-training-agent-handoff-runbook`: Standard agent handoff reports and runbook for explicit LoRA training.

### Modified Capabilities
- None.

## Impact

- Affected OpenSpec documentation: new capability spec for handoff/runbook behavior.
- Affected future implementation areas: agent prompts/runbooks, optional helper templates, MCP usage tests if helpers are added later.
- Prerequisite: `add-agent-guided-lora-training-decision` and existing archived MCP training tools for start/status/logs/cancel/smoke-test.
