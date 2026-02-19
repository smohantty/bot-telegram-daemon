# Bot Telegram Daemon

Standalone daemon that monitors trading bots via WebSocket and sends periodic status summaries to Telegram. Replaces the embedded Telegram reporter previously built into individual bots.

## How It Works

### Bot Discovery

The daemon does **not** auto-discover bots on the network. You explicitly list the WebSocket endpoints of your running bots in a YAML config file:

```yaml
bots:
  - label: "HL-HYPE-Perp"
    url: "ws://192.168.0.25:9000"
  - label: "Lighter-LIT-Spot"
    url: "ws://192.168.0.25:9001"
```

Each bot (hyperliquid-trading-bot, lighter-trading-bot) exposes a WebSocket server that broadcasts status events. The daemon connects to these endpoints as a client — the same protocol the dashboard uses.

**On connect**, each bot replays its current state (config, system info, latest summary), so the daemon immediately has up-to-date data. After that, it receives real-time event updates.

**If a bot is offline**, the daemon retries with exponential backoff (configurable). When the bot comes back, the daemon reconnects automatically and resumes monitoring.

### What Gets Reported

- **Periodic summaries** — Consolidated status of all bots sent at a configurable interval (default: every 60 minutes)
- **Error alerts** — Immediate notification when a bot reports an error, with cooldown to prevent spam
- **On-demand status** — Send `/status` in Telegram to get current status of all bots at any time
- **Startup notification** — Optional message when the daemon starts, listing all monitored bots

## Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager

### 1. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to create a bot
3. BotFather will give you a **bot token** like `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ`
4. Save this token — you'll need it for the config

### 2. Get Your Chat ID

You need the chat ID where the bot should send messages. This can be a private chat, group, or channel.

**For a private chat:**
1. Send any message to your new bot
2. Open `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` in a browser
3. Find `"chat":{"id": ...}` in the response — that number is your chat ID

**For a group:**
1. Add the bot to your group
2. Send a message in the group
3. Check the same `/getUpdates` URL — the chat ID will be a negative number like `-1001234567890`

### 3. Configure

**Set Telegram credentials via environment variables** (recommended):

```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
export TELEGRAM_CHAT_ID="-1001234567890"
```

Then create your config file:

```bash
cp configs/example.yaml configs/production.yaml
```

Edit `configs/production.yaml` — only the bot endpoints and reporting settings go here (no secrets):

```yaml
telegram: {}   # credentials come from env vars

bots:
  - label: "HL-HYPE-Perp"          # Display name in Telegram messages
    url: "ws://192.168.0.25:9000"   # WebSocket URL of the bot
  - label: "Lighter-ETH-Spot"
    url: "ws://192.168.0.25:9001"

reporting:
  periodic_interval_minutes: 60     # 0 = disable periodic reports
  error_cooldown_seconds: 60
  startup_notification: true

connection:
  reconnect_delay_seconds: 5
  max_reconnect_delay_seconds: 60
  ping_interval_seconds: 30
```

> **Note:** Env vars always take precedence over YAML values. You can also set `bot_token` and `chat_id` directly in the YAML, but env vars keep secrets out of version control.

> **Note:** The `url` can omit the `ws://` prefix — it will be added automatically.

### 4. Install Dependencies

```bash
uv sync
```

### 5. Run

**Direct:**
```bash
uv run python main.py configs/production.yaml
```

**With tmux (recommended for servers):**
```bash
./deployment/start.sh --config configs/production.yaml
```

**Stop:**
```bash
./deployment/stop.sh
# or Ctrl+C if running directly
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/status` | Status of all monitored bots |
| `/status <label>` | Status of a specific bot (e.g. `/status HL-HYPE-Perp`) |
| `/help` | List available commands |

## Configuration Reference

| Section | Field | Default | Description |
|---------|-------|---------|-------------|
| `telegram.bot_token` | — | *required* | Telegram bot API token from BotFather (or set `TELEGRAM_BOT_TOKEN` env var) |
| `telegram.chat_id` | — | *required* | Target chat/group ID (or set `TELEGRAM_CHAT_ID` env var) |
| `bots[].label` | — | *required* | Human-readable name shown in messages |
| `bots[].url` | — | *required* | WebSocket URL of the bot |
| `reporting.periodic_interval_minutes` | 60 | | Consolidated summary interval (0 = disabled) |
| `reporting.error_cooldown_seconds` | 60 | | Min gap between repeated error alerts per bot |
| `reporting.startup_notification` | true | | Send message when daemon starts |
| `connection.reconnect_delay_seconds` | 5 | | Initial reconnect delay |
| `connection.max_reconnect_delay_seconds` | 60 | | Max backoff cap |
| `connection.ping_interval_seconds` | 30 | | WebSocket keepalive ping interval |

## Adding a New Bot

1. Ensure the bot is running and its WebSocket server is accessible from the daemon's host
2. Add an entry to the `bots` list in your config:
   ```yaml
   bots:
     - label: "My-New-Bot"
       url: "ws://10.0.0.5:9000"
   ```
3. Restart the daemon

## Testing

```bash
uv run pytest tests/ -v
```

## Schema

This project uses the shared [bot-ws-schema](https://github.com/smohantty/bot-ws-schema) as a git submodule for WebSocket event definitions.

Update the schema:
```bash
git submodule update --remote schema/bot-ws-schema
```
