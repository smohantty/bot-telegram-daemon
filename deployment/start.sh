#!/bin/bash
set -e

SESSION_NAME="telegram-daemon"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
CONFIG_PATH=""

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --config) CONFIG_PATH="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$CONFIG_PATH" ]; then
    echo "Usage: ./deployment/start.sh --config configs/my_config.yaml"
    exit 1
fi

cd "$PROJECT_ROOT"

# Check if already running
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Session '$SESSION_NAME' is already running."
    echo "Attach with: tmux attach -t $SESSION_NAME"
    echo "Or stop with: ./deployment/stop.sh"
    exit 0
fi

# Start in tmux
tmux new-session -d -s "$SESSION_NAME"
tmux send-keys -t "$SESSION_NAME" "cd $PROJECT_ROOT && uv run python main.py \"$CONFIG_PATH\"" C-m

echo "Telegram daemon started in tmux session '$SESSION_NAME'."
echo "Attach with: tmux attach -t $SESSION_NAME"
