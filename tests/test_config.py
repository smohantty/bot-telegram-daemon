"""Tests for configuration loading and validation."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.config import DaemonConfig, TelegramConfig, load_config


def _write_config(data: dict, path: Path) -> Path:
    """Write a config dict to a YAML file."""
    config_path = path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(data, f)
    return config_path


class TestConfigLoading:
    """Test YAML config loading and Pydantic validation."""

    def test_load_minimal_config(self, tmp_path: Path) -> None:
        """Minimal valid config: telegram + one bot."""
        data = {
            "telegram": {"bot_token": "tok123", "chat_id": "-100123"},
            "bots": [{"label": "Bot1", "url": "ws://localhost:9000"}],
        }
        path = _write_config(data, tmp_path)
        config = load_config(path)

        assert config.telegram.bot_token == "tok123"
        assert config.telegram.chat_id == "-100123"
        assert len(config.bots) == 1
        assert config.bots[0].label == "Bot1"
        assert config.bots[0].url == "ws://localhost:9000"

    def test_defaults_applied(self, tmp_path: Path) -> None:
        """Optional sections get defaults."""
        data = {
            "telegram": {"bot_token": "tok", "chat_id": "123"},
            "bots": [{"label": "B", "url": "ws://localhost:9000"}],
        }
        path = _write_config(data, tmp_path)
        config = load_config(path)

        assert config.reporting.periodic_interval_minutes == 60
        assert config.reporting.error_cooldown_seconds == 60
        assert config.reporting.startup_notification is True
        assert config.connection.reconnect_delay_seconds == 5
        assert config.connection.max_reconnect_delay_seconds == 60
        assert config.connection.ping_interval_seconds == 30

    def test_full_config(self, tmp_path: Path) -> None:
        """Fully specified config."""
        data = {
            "telegram": {"bot_token": "tok", "chat_id": "123"},
            "bots": [
                {"label": "A", "url": "ws://host1:9000"},
                {"label": "B", "url": "wss://host2:9001"},
            ],
            "reporting": {
                "periodic_interval_minutes": 30,
                "error_cooldown_seconds": 120,
                "startup_notification": False,
            },
            "connection": {
                "reconnect_delay_seconds": 10,
                "max_reconnect_delay_seconds": 120,
                "ping_interval_seconds": 60,
            },
        }
        path = _write_config(data, tmp_path)
        config = load_config(path)

        assert len(config.bots) == 2
        assert config.reporting.periodic_interval_minutes == 30
        assert config.connection.reconnect_delay_seconds == 10

    def test_url_normalization(self, tmp_path: Path) -> None:
        """URLs without ws:// prefix get it added."""
        data = {
            "telegram": {"bot_token": "tok", "chat_id": "123"},
            "bots": [{"label": "B", "url": "localhost:9000"}],
        }
        path = _write_config(data, tmp_path)
        config = load_config(path)
        assert config.bots[0].url == "ws://localhost:9000"

    def test_url_preserves_wss(self, tmp_path: Path) -> None:
        """wss:// prefix is preserved."""
        data = {
            "telegram": {"bot_token": "tok", "chat_id": "123"},
            "bots": [{"label": "B", "url": "wss://secure:9000"}],
        }
        path = _write_config(data, tmp_path)
        config = load_config(path)
        assert config.bots[0].url == "wss://secure:9000"

    def test_missing_file_raises(self) -> None:
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path.yaml")

    def test_missing_telegram_raises(self, tmp_path: Path) -> None:
        """Config without telegram section raises validation error."""
        data = {"bots": [{"label": "B", "url": "ws://localhost:9000"}]}
        path = _write_config(data, tmp_path)
        with pytest.raises(Exception):  # Pydantic ValidationError
            load_config(path)

    def test_missing_bots_raises(self, tmp_path: Path) -> None:
        """Config without bots section raises validation error."""
        data = {"telegram": {"bot_token": "tok", "chat_id": "123"}}
        path = _write_config(data, tmp_path)
        with pytest.raises(Exception):
            load_config(path)


class TestEnvVarConfig:
    """Test environment variable support for Telegram credentials."""

    def test_env_vars_override_yaml(self, tmp_path: Path) -> None:
        """Env vars take precedence over YAML values."""
        data = {
            "telegram": {"bot_token": "yaml-token", "chat_id": "yaml-chat"},
            "bots": [{"label": "B", "url": "ws://localhost:9000"}],
        }
        path = _write_config(data, tmp_path)
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "env-token",
            "TELEGRAM_CHAT_ID": "env-chat",
        }):
            config = load_config(path)
        assert config.telegram.bot_token == "env-token"
        assert config.telegram.chat_id == "env-chat"

    def test_env_vars_without_yaml_values(self, tmp_path: Path) -> None:
        """Env vars work when YAML has empty telegram section."""
        data = {
            "telegram": {},
            "bots": [{"label": "B", "url": "ws://localhost:9000"}],
        }
        path = _write_config(data, tmp_path)
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "env-token",
            "TELEGRAM_CHAT_ID": "env-chat",
        }):
            config = load_config(path)
        assert config.telegram.bot_token == "env-token"
        assert config.telegram.chat_id == "env-chat"

    def test_partial_env_var_token_only(self, tmp_path: Path) -> None:
        """Env token overrides YAML, chat_id from YAML."""
        data = {
            "telegram": {"bot_token": "yaml-token", "chat_id": "yaml-chat"},
            "bots": [{"label": "B", "url": "ws://localhost:9000"}],
        }
        path = _write_config(data, tmp_path)
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "env-token"}, clear=False):
            # Ensure TELEGRAM_CHAT_ID is not set
            env = os.environ.copy()
            env.pop("TELEGRAM_CHAT_ID", None)
            with patch.dict(os.environ, env, clear=True):
                config = load_config(path)
        assert config.telegram.bot_token == "env-token"
        assert config.telegram.chat_id == "yaml-chat"

    def test_missing_both_raises(self, tmp_path: Path) -> None:
        """Missing token from both env and YAML raises error."""
        data = {
            "telegram": {},
            "bots": [{"label": "B", "url": "ws://localhost:9000"}],
        }
        path = _write_config(data, tmp_path)
        # Ensure env vars are not set
        env = os.environ.copy()
        env.pop("TELEGRAM_BOT_TOKEN", None)
        env.pop("TELEGRAM_CHAT_ID", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception, match="bot_token is required"):
                load_config(path)

    def test_telegram_config_directly_from_env(self) -> None:
        """TelegramConfig can be created with just env vars."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "direct-token",
            "TELEGRAM_CHAT_ID": "direct-chat",
        }):
            tc = TelegramConfig()
        assert tc.bot_token == "direct-token"
        assert tc.chat_id == "direct-chat"
