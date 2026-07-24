import pytest

from bot.config import Config, ConfigError, load_config


def test_load_config_reads_canonical_discord_fields():
    cfg = load_config({
        "DISCORD_BOT_TOKEN": "tok",
        "DISCORD_GUILD_ID": "123",
        "BACKEND_BASE_URL": "http://localhost:8000/",
    })
    assert cfg == Config(discord_token="tok", guild_id=123, backend_base_url="http://localhost:8000")


def test_load_config_keeps_legacy_discord_field_compatibility():
    cfg = load_config({"DISCORD_TOKEN": "legacy", "GUILD_ID": "456"})
    assert cfg.discord_token == "legacy"
    assert cfg.guild_id == 456


def test_canonical_discord_fields_take_precedence_over_legacy_aliases():
    cfg = load_config({
        "DISCORD_BOT_TOKEN": "canonical",
        "DISCORD_TOKEN": "legacy",
        "DISCORD_GUILD_ID": "123",
        "GUILD_ID": "456",
    })
    assert cfg.discord_token == "canonical"
    assert cfg.guild_id == 123


def test_backend_base_url_defaults():
    cfg = load_config({"DISCORD_BOT_TOKEN": "tok", "DISCORD_GUILD_ID": "1"})
    assert cfg.backend_base_url == "http://localhost:8000"


def test_missing_token_raises():
    with pytest.raises(ConfigError) as e:
        load_config({"DISCORD_GUILD_ID": "1"})
    assert "DISCORD_BOT_TOKEN" in str(e.value)


def test_non_integer_guild_raises():
    with pytest.raises(ConfigError):
        load_config({"DISCORD_BOT_TOKEN": "t", "DISCORD_GUILD_ID": "abc"})
