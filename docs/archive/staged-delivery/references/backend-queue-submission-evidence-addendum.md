# Historical supplement: queue submission evidence

Historical evidence only; not proof of a current bug, a current prompt policy, or authorization to cancel, delete, interrupt, or restart anything. Read the [archive index](../INDEX.md) and [project document map](../../../INDEX.md) for context.

Imported 2026-10-01 from the retired skill reference `openclaw-agent-orchestration/references/absorbed-skills/openclaw-mcp-image-generation/references/backend-queue-head-blocking-and-submission-proof.md`. Its queue-head symptoms, distinguishing test, and retry-loop explanation duplicate the [verbatim primary note](ai-drawing-backend-head-of-line-blocking.md); they are not copied again here. The meaningful additional evidence-order, interruption-attribution, and prompt-audit passages are preserved below. This supplement does not import the removed direct-ComfyUI-bypass case.

Interpretation boundary: the historical “at least one” handle rule below establishes downstream evidence, not MCP transport provenance by itself. Correlate the actual agent tool event and matching identifiers before attributing a run to MCP. The language restriction in the prompt-audit example was case-specific, not a universal current project policy.

## Original supplemental passages

## Operational verification order
When a generation request appears stuck:
1. inspect OpenClaw session/tool trace to confirm whether a real generation tool call happened
2. inspect backend queue for `queued` vs `running`
3. inspect ComfyUI `/queue`
4. if a backend job claims `running`, capture its `prompt_id`
5. inspect ComfyUI `/history/{prompt_id}` before calling it a ComfyUI failure

## Submission-proof rule
Do not say the agent "used MCP to generate" unless you can prove at least one of:
- backend returned a real `job_id`
- backend job later returned a real `prompt_id`
- ComfyUI `/queue` or `/history` shows the matching prompt

A session transcript that merely says "submitted" is weaker evidence than queue/history handles.

## ComfyUI error-interpretation rule
If ComfyUI history shows `execution_interrupted` after you manually called `/interrupt`, do **not** classify that as a native ComfyUI workflow failure. It only proves the run was manually stopped.

## Prompt-audit reminder
A run can be operationally healthy and still fail policy:
- MCP call succeeds
- backend queue runs
- ComfyUI receives a prompt
- but the final positive prompt still leaks Chinese or mixed-language fragments

So operational proof and prompt-policy proof must be reported separately.
