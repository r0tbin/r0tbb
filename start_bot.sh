#!/bin/bash

# R0TBB Bot Startup Script
# Ensures only one instance runs at a time

BOT_SCRIPT="simple_bot.py"
BOT_DIR="/home/l0n3/r0tbb"

cd "$BOT_DIR"

# Kill any existing bot processes
echo "🔄 Stopping existing bot instances..."
pkill -f "$BOT_SCRIPT" 2>/dev/null
sleep 2

# Check if any processes are still running
if pgrep -f "$BOT_SCRIPT" > /dev/null; then
    echo "⚠️  Force killing remaining processes..."
    pkill -9 -f "$BOT_SCRIPT" 2>/dev/null
    sleep 1
fi

# Start the bot
echo "🚀 Starting r0tbb bot..."
python3 "$BOT_SCRIPT" &

# Wait a moment and check if it started successfully
sleep 3
if pgrep -f "$BOT_SCRIPT" > /dev/null; then
    echo "✅ Bot started successfully!"
    echo "📱 Bot is running in background"
    echo "🔧 Use 'pkill -f simple_bot' to stop the bot"
else
    echo "❌ Failed to start bot"
    exit 1
fi
