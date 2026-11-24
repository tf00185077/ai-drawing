---
name: discord-bot-config-and-ledger
description: "Discord bot start-up needs explicit config and an already provisioned delivery ledger; it does not read .env."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

Settings come only from the process environment or an absolute `DISCORD_CONFIG_FILE`; the bot does not search for `.env`. `DISCORD_DELIVERY_LEDGER_PATH` must be absolute and point to an existing, provisioned ledger; a missing, old-format, corrupt or wrongly bound ledger keeps the bot closed, with no automatic init or migration. A new empty ledger is created only offline with `DeliveryLedger.provision(...)`, which refuses to overwrite. Failed or uncertain sends leave a no-resend hold that `force_resend` cannot override.

## Why

Starting the bot the old way fails, and fixing it by provisioning over an existing ledger would erase delivery history.

## How to apply

Set the variables explicitly before starting. Provision a ledger only for a fresh install, never over an existing file. Treat a hold as needing a human decision.

## Evidence

- `discord-bot/bot/config.py`
- `discord-bot/bot/delivery.py`, `discord-bot/bot/attempt_store.py`
