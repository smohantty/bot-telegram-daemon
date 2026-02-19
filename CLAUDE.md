# Bot Telegram Daemon

Standalone daemon that monitors trading bots via WebSocket and sends status updates to Telegram.

## Architecture

- **WebSocket Client** (`src/ws_client.py`): Connects to bot WebSocket endpoints with auto-reconnect
- **Monitor** (`src/monitor.py`): Orchestrates multiple WS clients, caches bot state, triggers alerts
- **Telegram Bot** (`src/telegram_bot.py`): Handles `/status` and `/help` commands, sends periodic summaries
- **Formatter** (`src/formatter.py`): HTML message formatting for Telegram (ported from Rust bot)

## Schema

The `schema/bot-ws-schema/` git submodule contains the shared JSON Schema for WebSocket events.
Update: `git submodule update --remote schema/bot-ws-schema`

## Running

```bash
uv run python main.py configs/production.yaml
```

## Testing

```bash
uv run pytest tests/
```

## Config

YAML config at `configs/example.yaml` — defines Telegram credentials, bot endpoints, reporting intervals.
