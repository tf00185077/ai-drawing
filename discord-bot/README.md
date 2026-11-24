# AI Drawing Discord bot

Slash commands that call the Backend directly (no LLM), plus an operator endpoint MCP uses to post finished results.

## Setup

Settings are read only from the process environment or an absolute `DISCORD_CONFIG_FILE`; `.env` is not searched.

| Setting | Purpose |
|---|---|
| `DISCORD_TOKEN` | Bot token |
| `GUILD_ID` | Server ID |
| `BACKEND_BASE_URL` | Backend URL (default `http://localhost:8000`) |
| `DISCORD_DELIVERY_LEDGER_PATH` | Absolute path to an already provisioned delivery ledger |

The bot needs the `applications.commands` scope. Ledger rules: [Discord bot config and ledger](../docs/memory/discord-bot-config-and-ledger.md).

```bash
cd discord-bot
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m bot.main
```

## Commands

- `/draw` — pick execution target, preset (and profile), then prompt, size and count; returns a job ID.
- `/result id:<job_id>` — posts the persisted results of an image or video job.
- `/animegen_i2v`, `/wan22_animate`, `/minimax_h3_i2v` — fixed video commands. **Frozen**: kept working, not developed further; the Phase 4 image-to-video tool replaces them. Frame rules: [video frames and FILM](../docs/memory/video-frame-and-film-rules.md).

## Operator / MCP result delivery (optional)

With `DISCORD_OPERATOR_TOKEN` and `DISCORD_DESTINATION_ALIASES` set, the bot serves an authenticated endpoint on `127.0.0.1:8765` that posts a completed `job_id` to an allowlisted alias. MCP calls it through `deliver_generation_result_to_discord` with the same token in `MCP_DISCORD_OPERATOR_TOKEN`. Deliveries are de-duplicated per job and channel.

## Tests

```bash
cd discord-bot && python -m pytest -v
```

## Known limits

- The Backend queue is in memory; a restart loses queued and running jobs. Finished results stay available to `/result`.
- More than 25 presets needs paging in the selector.
- `/result` matches the Gallery by the first 8 characters of the job ID.
- Results over about 24 MB are posted as Gallery links instead of attachments.
