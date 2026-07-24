import discord

from bot.config import Config
from bot.main import build_bot


def test_build_bot_registers_commands():
    config = Config(discord_token="t", guild_id=123, backend_base_url="http://test")
    client, tree, api = build_bot(config)
    guild = discord.Object(id=123)
    names = {c.name for c in tree.get_commands(guild=guild)}
    assert names == {"draw", "result"}
    assert api._base_url == "http://test"
