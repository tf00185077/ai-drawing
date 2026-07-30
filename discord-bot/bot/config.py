"""環境變數載入；缺必要值即 fail-fast。"""
import json
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    discord_token: str
    guild_id: int
    backend_base_url: str
    operator_token: str | None = None
    operator_destinations: tuple[tuple[str, int], ...] = ()
    operator_port: int = 8765
    delivery_ledger_path: Path = Path(".state/result-deliveries.json")


def load_config(env: dict | None = None) -> Config:
    if env is None:
        from dotenv import load_dotenv

        repo_env = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(repo_env)
        load_dotenv()
        env = dict(os.environ)

    token = env.get("DISCORD_BOT_TOKEN") or env.get("DISCORD_TOKEN")
    guild = env.get("DISCORD_GUILD_ID") or env.get("GUILD_ID")
    base = env.get("BACKEND_BASE_URL") or "http://localhost:8000"
    operator_token = env.get("DISCORD_OPERATOR_TOKEN")
    raw_destinations = env.get("DISCORD_DESTINATION_ALIASES", "")

    missing = [
        name
        for name, value in (
            ("DISCORD_BOT_TOKEN", token),
            ("DISCORD_GUILD_ID", guild),
        )
        if not value
    ]
    if missing:
        raise ConfigError(f"缺少環境變數：{', '.join(missing)}")
    assert isinstance(token, str) and isinstance(guild, str)

    try:
        guild_id = int(guild)
    except (TypeError, ValueError):
        raise ConfigError("GUILD_ID 必須是整數")

    try:
        operator_port = int(env.get("DISCORD_OPERATOR_PORT", "8765"))
    except (TypeError, ValueError):
        raise ConfigError("DISCORD_OPERATOR_PORT 必須是整數")
    if not 1 <= operator_port <= 65535:
        raise ConfigError("DISCORD_OPERATOR_PORT 必須介於 1 到 65535")

    destinations: tuple[tuple[str, int], ...] = ()
    if raw_destinations:
        try:
            parsed = json.loads(raw_destinations)
            if (
                not isinstance(parsed, dict)
                or not parsed
                or not all(
                    isinstance(alias, str)
                    and bool(alias)
                    and alias.replace("-", "").replace("_", "").isalnum()
                    and isinstance(channel_id, (str, int))
                    and not isinstance(channel_id, bool)
                    for alias, channel_id in parsed.items()
                )
            ):
                raise ValueError
            destinations = tuple(
                sorted((alias, int(channel_id)) for alias, channel_id in parsed.items())
            )
            if any(channel_id <= 0 for _, channel_id in destinations):
                raise ValueError
        except (json.JSONDecodeError, TypeError, ValueError):
            raise ConfigError(
                "DISCORD_DESTINATION_ALIASES 必須是 alias 到 Discord channel ID 的 JSON object"
            )
    if bool(operator_token) != bool(destinations):
        raise ConfigError(
            "DISCORD_OPERATOR_TOKEN 與 DISCORD_DESTINATION_ALIASES 必須一起設定"
        )

    return Config(
        discord_token=token,
        guild_id=guild_id,
        backend_base_url=base.rstrip("/"),
        operator_token=operator_token,
        operator_destinations=destinations,
        operator_port=operator_port,
        delivery_ledger_path=Path(
            env.get("DISCORD_DELIVERY_LEDGER_PATH", ".state/result-deliveries.json")
        ),
    )
