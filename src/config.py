"""Configuration models and YAML loader."""

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str


class BotEndpoint(BaseModel):
    label: str
    url: str  # e.g. "ws://localhost:9000"

    @field_validator("url")
    @classmethod
    def normalize_ws_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("ws://", "wss://")):
            v = f"ws://{v}"
        return v


class ReportingConfig(BaseModel):
    periodic_interval_minutes: int = 60
    error_cooldown_seconds: int = 60
    startup_notification: bool = True


class ConnectionConfig(BaseModel):
    reconnect_delay_seconds: int = 5
    max_reconnect_delay_seconds: int = 60
    ping_interval_seconds: int = 30


class DaemonConfig(BaseModel):
    telegram: TelegramConfig
    bots: list[BotEndpoint]
    reporting: ReportingConfig = ReportingConfig()
    connection: ConnectionConfig = ConnectionConfig()


def load_config(path: str | Path) -> DaemonConfig:
    """Load and validate daemon configuration from a YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return DaemonConfig(**raw)
