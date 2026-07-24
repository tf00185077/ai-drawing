import pytest

from bot.config import Config, ConfigError, load_config


def test_load_config_reads_all_fields():
    cfg = load_config({
        "DISCORD_TOKEN": "tok",
        "GUILD_ID": "123",
        "BACKEND_BASE_URL": "http://localhost:8000/",
    })
    assert cfg == Config(discord_token="tok", guild_id=123, backend_base_url="http://localhost:8000")


def test_backend_base_url_defaults():
    cfg = load_config({"DISCORD_TOKEN": "tok", "GUILD_ID": "1"})
    assert cfg.backend_base_url == "http://localhost:8000"


def test_missing_token_raises():
    with pytest.raises(ConfigError) as e:
        load_config({"GUILD_ID": "1"})
    assert "DISCORD_TOKEN" in str(e.value)


def test_non_integer_guild_raises():
    with pytest.raises(ConfigError):
        load_config({"DISCORD_TOKEN": "t", "GUILD_ID": "abc"})
