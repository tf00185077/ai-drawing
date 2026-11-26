# Civitai credentials on the owner Mac

## Key-file locator

CTY's authorized Civitai API key file is:

`/Users/tf00185088/Desktop/civitai.txt`

The file is outside this repository and readable by the local owner account. Keep
its owner-only permissions (`0600`). The path is documentation; the key value
stays in that private file. Producer and its authorized executors read the file
locally when Phase 2 needs authenticated Civitai access. Read and trim its contents
inside the process that needs them; report only presence/readability and the
sanitized operation result. Do not print the key or put it in task descriptions,
evidence, URLs, shell arguments, shared logs, MCP results or Git.

## Configuration and implementation boundary

The approved Phase 2 Backend configuration contract is:

```dotenv
CIVITAI_API_KEY_FILE=/Users/tf00185088/Desktop/civitai.txt
```

Use this absolute host path in private configuration. A container or a different
machine needs an explicitly mapped readable private path; the host path does not
prove access there. Do not copy the key into a repository or an artifact bundle.

The pre-Phase-2 Backend currently reads `CIVITAI_AUTHORIZATION`; this documentation
change does not implement or deploy a `CIVITAI_API_KEY_FILE` reader. Producer must
trace the actual authentication path during the First check, record any manual
in-process credential bridge as an intervention, and route the planned file reader
through Coding and independent exact-commit QA. A readable file is not evidence
that Civitai accepts the key or that a running Backend has loaded it. Preserve
existing private configuration, running jobs and all model/output data.

If the file becomes missing, unreadable or empty, report that concrete failure
with this known path rather than asking for a location already supplied. Free-key
restrictions, Early Access refusal and rate limits remain real outcomes; the key
does not authorize paid access or expand the approved project boundary.

## Authority

[CTY's Phase 2 start and key-file direction](requests/2026-11-26-phase-2-start-and-key-file.md)
fixes this locator and authorizes continued execution within the accepted roadmap.
The [Phase 2 roadmap](roadmap/ROADMAP.md#phase-2--one-sentence-flow-resources--workflow--image-active-2026-11-26)
and [operating policy](OPERATING-POLICY.md) govern the work.
