"""Configuration models and YAML loader.

Telegram credentials (bot_token, chat_id) can be provided via environment
variables ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID``.  Values in the
YAML file are used as fallback — env vars always take precedence.
"""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator, model_validator


class TelegramConfig(BaseModel):
    bot_token: str = ""
    chat_id: str = ""

    @model_validator(mode="before")
    @classmethod
    def _resolve_env_vars(cls, values: dict) -> dict:  # type: ignore[override]
        """Override token / chat_id from env vars if set."""
        env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        env_chat = os.environ.get("TELEGRAM_CHAT_ID")
        if env_token:
            values["bot_token"] = env_token
        if env_chat:
            values["chat_id"] = env_chat
        return values

    @model_validator(mode="after")
    def _check_required(self) -> "TelegramConfig":
        """Ensure both fields are present (from YAML or env)."""
        if not self.bot_token:
            raise ValueError(
                "bot_token is required — set TELEGRAM_BOT_TOKEN env var "
                "or provide it in the YAML config"
            )
        if not self.chat_id:
            raise ValueError(
                "chat_id is required — set TELEGRAM_CHAT_ID env var "
                "or provide it in the YAML config"
            )
        return self


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
    card_theme: Literal["dark", "light", "text"] = "light"


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
