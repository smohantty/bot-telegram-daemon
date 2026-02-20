# CLAUDE.md - Long-Term Memory for Claude Code

## Memory Metadata
- **Last refreshed:** 2026-02-20
- **Project status:** Active development

## Project Overview
Standalone Python daemon that monitors trading bots (Hyperliquid, Lighter) via WebSocket and sends status updates, error alerts, and periodic summaries to Telegram. Connects as a WebSocket client to one or more bot instances.

**Author:** subhransu (smohantty@gmail.com)

## Architecture

### Components
- **Entry point:** `main.py` -- CLI (config path), loads .env, creates Monitor + TelegramBot, handles SIGINT/SIGTERM
- **Monitor:** `src/monitor.py` -- Orchestrates WS clients, caches `BotState` per bot, routes events, triggers alerts, runs periodic report loop
- **WebSocket Client:** `src/ws_client.py` -- Connects to bot WS endpoints, auto-reconnect with exponential backoff (5s -> 60s cap), ping keepalive (30s)
- **Telegram Bot:** `src/telegram_bot.py` -- Handles `/status [label]` and `/help` commands, sends messages (auto-splits >4096 chars)
- **Formatter:** `src/formatter.py` -- HTML message formatting: full status, periodic updates (deltas), error alerts, startup messages
- **Bot State:** `src/bot_state.py` -- Per-bot state cache dataclass (connection status, cached data, error tracking, periodic deltas)
- **Models:** `src/models.py` -- Dataclasses for SystemInfo, SpotGridSummary, PerpGridSummary, StrategyConfig + parsers
- **Config:** `src/config.py` -- YAML loading, Pydantic-style validation, env var resolution for secrets
- **Validator:** `src/validator.py` -- Optional JSON Schema validation of incoming events (disabled in production)
- **Logging:** `src/logging_utils.py` -- Console logging config, noise reduction for websockets/httpx/telegram

### Event Flow
```
Trading Bots (WS servers on :9000, :9001, etc.)
    -> BotWebSocketClient(s) (one per bot endpoint)
        -> Monitor._handle_event(label, event_type, data)
            -> Updates BotState cache
            -> Triggers: initial summary, error alerts, periodic updates
                -> TelegramBot._send_safe(chat_id, html_text)
                    -> Telegram API
```

### Events Handled
| event_type | action |
|------------|--------|
| `info` | Cache SystemInfo (network, exchange) |
| `config` | Cache StrategyConfig (type, symbol) |
| `spot_grid_summary` | Cache summary + maybe send initial summary |
| `perp_grid_summary` | Cache summary + maybe send initial summary |
| `error` | Cache + send error alert (with cooldown) |
| `market_update`, `order_update`, `grid_state` | Ignored |

### Key Patterns
- Initial summary sent once per bot when both `info` and `summary` first received
- Error cooldown prevents Telegram spam (default 60s between alerts per bot)
- Periodic reports show deltas (new trades, profit earned) since last report
- Messages auto-split at 4096 chars (Telegram limit)
- All async (asyncio, websockets, python-telegram-bot)

## Development Commands
- **Package manager:** `uv` (NEVER use `pip install`)
- **Install deps:** `uv sync`
- **Run:** `uv run python main.py configs/production.yaml`
- **Tests:** `uv run pytest tests/ -v`
- **Deploy:** `./deployment/start.sh --config configs/production.yaml` (tmux session)
- **Stop:** `./deployment/stop.sh`

## Tech Stack
- **Python** >=3.10
- **python-telegram-bot** (>=21.0) -- Telegram API
- **websockets** (>=15.0) -- WebSocket client
- **pydantic** (>=2.0) -- Data validation
- **pyyaml** (>=6.0) -- Config parsing
- **python-dotenv** (>=1.0.0) -- Env var loading
- **Dev:** pytest, pytest-asyncio, mypy, ruff, jsonschema

## Config Files

### YAML config (`configs/example.yaml`)
```yaml
telegram: {}  # bot_token & chat_id loaded from env vars

bots:
  - label: "HL-HYPE-Perp"
    url: "ws://192.168.0.25:9000"
  - label: "Lighter-LIT-Spot"
    url: "ws://192.168.0.25:9001"

reporting:
  periodic_interval_minutes: 60   # 0 = disabled
  error_cooldown_seconds: 60
  startup_notification: true

connection:
  reconnect_delay_seconds: 5
  max_reconnect_delay_seconds: 60
  ping_interval_seconds: 30
```

### Environment Variables
```bash
TELEGRAM_BOT_TOKEN="123456789:ABCdefGHI..."
TELEGRAM_CHAT_ID="-1001234567890"
```

## Directory Structure
```
├── main.py                    # Entry point
├── pyproject.toml             # Dependencies & tool config
├── .env.example               # Env var template
├── src/
│   ├── config.py              # YAML config loading & validation
│   ├── models.py              # Data models (SystemInfo, Summaries, Config)
│   ├── ws_client.py           # WebSocket client with auto-reconnect
│   ├── monitor.py             # Monitor orchestrator
│   ├── bot_state.py           # Per-bot state cache
│   ├── telegram_bot.py        # Telegram command handlers & sender
│   ├── formatter.py           # HTML message formatting
│   ├── logging_utils.py       # Logging configuration
│   └── validator.py           # Optional JSON Schema validation
├── tests/
│   ├── conftest.py            # Shared fixtures
│   ├── test_config.py         # Config loading tests
│   ├── test_models.py         # Model parsing tests
│   ├── test_formatter.py      # Formatter tests
│   └── test_monitor.py        # Monitor orchestrator tests
├── configs/
│   ├── example.yaml           # Example (two bots)
│   └── production.yaml        # Production config
├── deployment/
│   ├── start.sh               # Start in tmux
│   └── stop.sh                # Graceful stop
└── schema/
    └── bot-ws-schema/         # Git submodule (shared WS event schema)
```

## Schema
The `schema/bot-ws-schema/` git submodule is the shared JSON Schema for WebSocket events.
Update: `git submodule update --remote schema/bot-ws-schema`

## Code Style Rules
- Ruff: line length 88, target Python 3.12
- Lint rules: E, F, I, B (ignore E501)
- Type hints consistently
- Fully async codebase

## Telegram Commands
- `/status` -- Status of all monitored bots
- `/status <label>` -- Status of a specific bot
- `/help` -- Available commands

## Related Repos
- **lighter-trading-bot** (Python) -- Trading bot for Lighter.xyz DEX (produces WS events)
- **hyperliquid-trading-bot** (Rust) -- Trading bot for Hyperliquid DEX (produces WS events)
- **bot-ws-schema** -- Shared WebSocket event schema (git submodule)
- **bot-dashboard** (React/Electron) -- Real-time trading dashboard (also consumes WS events)
