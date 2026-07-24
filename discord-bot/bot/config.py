"""環境變數載入；缺必要值即 fail-fast。"""
import os
from dataclasses import dataclass


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    discord_token: str
    guild_id: int
    backend_base_url: str


def load_config(env: dict | None = None) -> Config:
    if env is None:
        from dotenv import load_dotenv

        load_dotenv()
        env = dict(os.environ)

    token = env.get("DISCORD_TOKEN")
    guild = env.get("GUILD_ID")
    base = env.get("BACKEND_BASE_URL") or "http://localhost:8000"

    missing = [name for name, value in (("DISCORD_TOKEN", token), ("GUILD_ID", guild)) if not value]
    if missing:
        raise ConfigError(f"缺少環境變數：{', '.join(missing)}")

    try:
        guild_id = int(guild)
    except (TypeError, ValueError):
        raise ConfigError("GUILD_ID 必須是整數")

    return Config(discord_token=token, guild_id=guild_id, backend_base_url=base.rstrip("/"))
