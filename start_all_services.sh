#!/bin/bash
# Start All Cortex Services - Discord, iMessage, Browser Automation, Research

echo "🚀 Starting Cortex AI Services..."
echo ""

# Kill any existing services
echo "🛑 Stopping existing services..."
pkill -f "backend/main.py"
pkill -f "backend/discord_bot.py"
pkill -f "backend/imessage_bridge.py"
pkill -f "backend/stagehand_service.py"
pkill -f "backend/research_service.py"
sleep 2

# Start Backend API
echo "🔧 Starting Backend API (port 8003)..."
python3 backend/main.py > logs/backend.log 2>&1 &
sleep 2

# Start Discord Bot
echo "💬 Starting Discord Bot..."
python3 backend/discord_bot.py > logs/discord.log 2>&1 &
sleep 2

# Start iMessage Bridge
echo "📱 Starting iMessage Bridge (port 8100)..."
python3 backend/imessage_bridge.py > logs/imessage.log 2>&1 &
sleep 2

# Start Stagehand Browser Automation
echo "🌐 Starting Stagehand Browser Service (port 5005)..."
python3 backend/stagehand_service.py > logs/stagehand.log 2>&1 &
sleep 2

# Start Research Service with Bright Data
echo "🔍 Starting Research Service (port 5006)..."
python3 backend/research_service.py > logs/research.log 2>&1 &
sleep 2

echo ""
echo "✅ All services started!"
echo ""
echo "📊 Service Status:"
echo "  - Backend API:        http://127.0.0.1:8003"
echo "  - Discord Bot:        Running"
echo "  - iMessage Bridge:    http://127.0.0.1:8100"
echo "  - Stagehand Browser:  http://127.0.0.1:5005"
echo "  - Research Service:   http://127.0.0.1:5006"
echo ""
echo "📝 Logs:"
echo "  - Backend:   tail -f logs/backend.log"
echo "  - Discord:   tail -f logs/discord.log"
echo "  - iMessage:  tail -f logs/imessage.log"
echo "  - Stagehand: tail -f logs/stagehand.log"
echo "  - Research:  tail -f logs/research.log"
echo ""
echo "🎯 Ready to receive tasks via Discord or iMessage!"
