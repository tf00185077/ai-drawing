> Historical import from `ai-drawing-discord-menu/references/native-discord-bot-validation.md`.
> The original body below is preserved verbatim. Operational advice, platform limits,
> setup permissions, restart/sync instructions, and implementation claims are historical
> and unverified against the current project. They grant no current execution authority.
> Consult the archive index and current project code/specs before any separately authorized work.

# Native ai-drawing Discord Bot Validation

Use this reference when the user asks to build, sync, review, or validate a true native Discord flow such as:

```text
/draw → preset/profile select → Modal → Backend compose/submit → /result → image attachments
```

This is separate from the text-menu fallback. A native bot callback must not route prompt text through Hermes `handle_message()` or an LLM merely to reach the Backend.

## 1. Sync without damaging active work

1. Fetch first and prove the remote branch moved before claiming the new hook was tested.
2. Inspect the primary worktree status and every active worktree/agent.
3. If the primary branch is dirty or an implementation agent is writing another worktree, do not pull/rebase through those edits. Create a clean detached verification worktree at `origin/<default-branch>` and test there.
4. Record the exact remote SHA tested. Integrate the new base into an active feature branch only after its worker batch finishes.

This verifies latest remote code while preserving unrelated local edits; it does not mean the dirty local primary branch was fast-forwarded.

## 2. Deterministic gates

Run from the native bot package with its declared dependency file:

- complete bot tests;
- Python compile/import gate;
- focused review of config, API client, slash-command registration, views/modal callbacks, and result delivery;
- read-only live Backend contract probe: health, style-preset list, and compose with a small override;
- verify the configured Backend port from live state rather than trusting an example default.

Report source tests, live Backend compatibility, Discord runtime activation, and real generation E2E as separate gates. Unit tests and successful compose do not prove command sync or attachment delivery.

## 3. Code-review checklist

### Discord interaction lifecycle

- A slash command must acknowledge/defer within Discord's short initial-response window before waiting on Backend I/O.
- After defer, use the correct edit/followup path; do not call the initial response twice.
- Modal submission should validate locally, defer promptly, then compose/submit.
- Test `/draw`, preset select, profile select, no-profile modal, modal submit, and `/result` callbacks—not only command registration and helper functions.

### Authorization and resource abuse

- Guild-scoped registration limits the server, not users inside it.
- For a shared guild, require explicit user/role allowlisting, rate limits, batch bounds, and per-user concurrency/job ownership before calling it safe.
- Do not allow a guessed job id to expose another user's result.
- A single-user private guild may accept a narrower threat model, but state that assumption explicitly.

### Backend/result contract

- Keep compose payload fields intact, including ordered LoRAs and split-model resources.
- Query Gallery with a prefix only as an optimization; filter returned rows by the full `job_id` before downloading.
- Distinguish transport, HTTP, JSON, and schema errors so contract drift is not mislabeled as “Backend unreachable.”
- Close the async HTTP client during graceful shutdown.

### Attachments and fallback

- Check each file against `interaction.guild.filesize_limit`, not only a hard-coded aggregate.
- Handle upload rejection and partial download failure with a usable fallback.
- Do not assume `http://localhost/...` gallery links are reachable by Discord users. Separate internal Backend URL from user-reachable gallery/public URL when needed.
- Bound download bytes, validate expected media type, preserve successfully fetched images if one item fails, and avoid loading unbounded batches into memory.
- Truncate/redact Backend diagnostics before posting to a public channel.

## 4. Discord application setup with ego-lite

For CTY, if a dedicated Discord Application/Bot is required and none is configured, proactively use ego-lite to open Discord Developer Portal and create/configure it rather than asking CTY to perform the whole setup manually.

Safety boundary:

1. Reuse one named ego-lite task space throughout setup and verification.
2. If the portal is logged out or requests password, MFA, CAPTCHA, token reset confirmation, or privileged authorization, hand off the task space and ask CTY to complete that exact step.
3. Never type or expose passwords, MFA codes, or bot tokens.
4. Do not reuse an ambient `DISCORD_TOKEN` without proving it belongs to this dedicated bot; it may belong to Hermes Gateway or another service.
5. After CTY confirms the handoff step is complete, take over the same task space—do not create a fresh browser session.
6. Configure the minimum intents/scopes needed (`bot` and `applications.commands` for the usual slash-command bot), install only into the selected Guild, and read back the application/bot/guild state.
7. Store credentials only in the repo's ignored runtime configuration or approved secret store; verify presence without printing values.

Required runtime facts:

- dedicated Bot credential configured (value never reported);
- target Guild ID;
- whether the Guild is private/single-user or shared;
- Backend URL reachable from the Bot process;
- ComfyUI ready;
- at least one valid preset/profile;
- user-reachable gallery strategy for fallback links.

## 5. Real E2E matrix

Start with one low-load image unless the user requested otherwise:

1. Start Backend/ComfyUI from the code revision being tested; do not point a new bot worktree at an unrelated older live Backend and call it integrated.
2. Start the bot and verify command sync for the exact Guild.
3. Run `/draw` with a preset that has profiles, submit a small one-image request, and capture the returned job id.
4. Poll through `/result`: queued/running must remain nonterminal; completed must return exactly the job's artifact(s).
5. Verify the Discord attachment is usable without visually judging it when CTY requested blind delivery.
6. Also cover no-profile preset, invalid dimensions/count, failed generation with bounded diagnostics, unknown job id, Backend delay beyond the initial response window, and attachment fallback.
7. For a shared Guild, test unauthorized user and rate-limit behavior before release.

Record command name, Guild, tested revision, Backend revision/URL, job id, terminal status, artifact count, Discord message handle when available, and any accepted limitations. Never fabricate runtime activation from unit-test evidence.
