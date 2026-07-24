import discord

from bot.config import Config
from bot.main import build_bot, normalize_job_id


def test_normalize_job_id_accepts_discord_copy_forms():
    job_id = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"
    assert normalize_job_id(job_id) == job_id
    assert normalize_job_id(f"id:{job_id}") == job_id
    assert normalize_job_id(f"`{job_id}`") == job_id
    assert normalize_job_id(f"/result id:{job_id}") == job_id
    assert normalize_job_id(f"  {job_id.upper()}  ") == job_id


def test_normalize_job_id_rejects_missing_or_ambiguous_uuid():
    first = "9bbd2e57-5e7e-43db-99e1-06679b6f0e81"
    second = "11111111-2222-3333-4444-555555555555"
    assert normalize_job_id("not-a-job") is None
    assert normalize_job_id(f"{first} {second}") is None


def test_build_bot_registers_commands():
    config = Config(discord_token="t", guild_id=123, backend_base_url="http://test")
    client, tree, api = build_bot(config)
    guild = discord.Object(id=123)
    names = {c.name for c in tree.get_commands(guild=guild)}
    assert names == {"draw", "result"}
    assert api._base_url == "http://test"
