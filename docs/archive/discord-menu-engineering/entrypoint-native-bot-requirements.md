# Historical native-Bot requirements from the former entrypoint

These exact source bullets are preserved as historical, unverified engineering context,
not current instructions or permission to configure applications, reuse credentials, restart
services, or execute workflows. Any embedded blanket setup grant is explicitly inactive.
The reference paths in the source bullets resolve within this archive. Current project
code/specs and explicit user scope govern any future implementation.

- If the user wants a true native Discord flow—slash command → Modal → non-LLM callback → Backend generation → artifact reply—stop treating this text-menu skill as the solution. Switch to the Hermes Discord platform/plugin software-change workflow and load `references/native-discord-bot-validation.md`. Inspect the live adapter and extension points, keep prompt transport outside `handle_message()`/agent dispatch, propose architecture and tests before editing, and never offer `clarify` as a temporary equivalent unless the user explicitly accepts a conversational fallback. For CTY, proactively use ego-lite to create/configure a dedicated Discord Application when needed; hand off only for login, MFA, CAPTCHA, token reset, or privileged authorization, then resume the same task space. Do not reuse an ambient Discord token unless its ownership is proven.
- When the native command wraps a fixed video workflow, also load `references/backend-owned-fixed-video-commands.md`. Keep the Bot thin, the graph Backend-owned, attachment paths opaque, FILM inside the job's all-or-nothing completion boundary, and `total_seconds` explicitly defined as first-to-last span rather than container duration.
