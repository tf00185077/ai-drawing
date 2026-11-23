import pytest

from bot.config import Config, ConfigError, load_config
from pathlib import Path


def test_load_config_reads_canonical_discord_fields():
    cfg = load_config({"DISCORD_DELIVERY_LEDGER_PATH":"/synthetic/state/ledger.json", "AI_DRAWING_MAINTENANCE_EPOCH":"synthetic-epoch",
        "DISCORD_BOT_TOKEN": "tok",
        "DISCORD_GUILD_ID": "123",
        "BACKEND_BASE_URL": "http://localhost:8000/",
    })
    assert cfg == Config(discord_token="tok", guild_id=123, backend_base_url="http://localhost:8000",delivery_ledger_path=Path("/synthetic/state/ledger.json"),maintenance_epoch="synthetic-epoch")


def test_load_config_keeps_legacy_discord_field_compatibility():
    cfg = load_config({"DISCORD_DELIVERY_LEDGER_PATH":"/synthetic/state/ledger.json", "AI_DRAWING_MAINTENANCE_EPOCH":"synthetic-epoch","DISCORD_TOKEN": "legacy", "GUILD_ID": "456"})
    assert cfg.discord_token == "legacy"
    assert cfg.guild_id == 456


def test_canonical_discord_fields_take_precedence_over_legacy_aliases():
    cfg = load_config({"DISCORD_DELIVERY_LEDGER_PATH":"/synthetic/state/ledger.json", "AI_DRAWING_MAINTENANCE_EPOCH":"synthetic-epoch",
        "DISCORD_BOT_TOKEN": "canonical",
        "DISCORD_TOKEN": "legacy",
        "DISCORD_GUILD_ID": "123",
        "GUILD_ID": "456",
    })
    assert cfg.discord_token == "canonical"
    assert cfg.guild_id == 123


def test_backend_base_url_defaults():
    cfg = load_config({"DISCORD_DELIVERY_LEDGER_PATH":"/synthetic/state/ledger.json", "AI_DRAWING_MAINTENANCE_EPOCH":"synthetic-epoch","DISCORD_BOT_TOKEN": "tok", "DISCORD_GUILD_ID": "1"})
    assert cfg.backend_base_url == "http://localhost:8000"


def test_missing_token_raises():
    with pytest.raises(ConfigError) as e:
        load_config({"DISCORD_DELIVERY_LEDGER_PATH":"/synthetic/state/ledger.json", "AI_DRAWING_MAINTENANCE_EPOCH":"synthetic-epoch","DISCORD_GUILD_ID": "1"})
    assert "DISCORD_BOT_TOKEN" in str(e.value)


def test_non_integer_guild_raises():
    with pytest.raises(ConfigError):
        load_config({"DISCORD_DELIVERY_LEDGER_PATH":"/synthetic/state/ledger.json", "AI_DRAWING_MAINTENANCE_EPOCH":"synthetic-epoch","DISCORD_BOT_TOKEN": "t", "DISCORD_GUILD_ID": "abc"})


def test_operator_requires_token_and_alias_allowlist_together():
    with pytest.raises(ConfigError):
        load_config({"DISCORD_DELIVERY_LEDGER_PATH":"/synthetic/state/ledger.json", "AI_DRAWING_MAINTENANCE_EPOCH":"synthetic-epoch",
            "DISCORD_BOT_TOKEN": "t",
            "DISCORD_GUILD_ID": "1",
            "DISCORD_OPERATOR_TOKEN": "secret",
        })


def test_operator_aliases_parse_to_immutable_allowlist():
    cfg = load_config({"DISCORD_DELIVERY_LEDGER_PATH":"/synthetic/state/ledger.json", "AI_DRAWING_MAINTENANCE_EPOCH":"synthetic-epoch",
        "DISCORD_BOT_TOKEN": "t",
        "DISCORD_GUILD_ID": "1",
        "DISCORD_OPERATOR_TOKEN": "secret",
        "DISCORD_DESTINATION_ALIASES": '{"results":"123"}',
    })
    assert cfg.operator_destinations == (("results", 123),)


def test_relative_ledger_path_is_rejected():
    with pytest.raises(ConfigError):
        load_config({'DISCORD_BOT_TOKEN':'synthetic','DISCORD_GUILD_ID':'1',
                     'DISCORD_DELIVERY_LEDGER_PATH':'relative.json'})


def test_explicit_config_file_no_discovery_and_process_precedence(tmp_path,monkeypatch):
    file=tmp_path/'bot.conf'
    file.write_text('DISCORD_BOT_TOKEN=synthetic-file\nDISCORD_GUILD_ID=123\nDISCORD_DELIVERY_LEDGER_PATH=/synthetic/state/ledger.json\n')
    monkeypatch.setenv('DISCORD_CONFIG_FILE',str(file))
    monkeypatch.setenv('DISCORD_BOT_TOKEN','synthetic-process')
    cfg=load_config()
    assert cfg.discord_token=='synthetic-process'
    assert cfg.guild_id==123
