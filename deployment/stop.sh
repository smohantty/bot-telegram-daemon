#!/bin/bash

SESSION_NAME="telegram-daemon"

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    # Send SIGINT (Ctrl+C) for graceful shutdown
    tmux send-keys -t "$SESSION_NAME" C-c
    sleep 2

    # Kill the session if still alive
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        tmux kill-session -t "$SESSION_NAME"
    fi

    echo "Telegram daemon stopped."
else
    echo "No running session found."
fi
