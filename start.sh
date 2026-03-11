#!/bin/bash
# APEX-SWARM — Full Stack Startup Script
# Starts all services: Backend → Frontend → TinyClaw → TinyOffice

MOONSHOT_DIR="/Users/vishnuvardhanmedara/Moonshot"

echo "🌙 Starting APEX-SWARM..."
echo ""

# Check MongoDB
if ! pgrep -x mongod > /dev/null; then
  echo "⚡ Starting MongoDB..."
  brew services start mongodb-community
fi

# Check Redis
if ! pgrep -x redis-server > /dev/null; then
  echo "⚡ Starting Redis..."
  brew services start redis
fi

# Kill existing tmux sessions
tmux kill-session -t apex-backend 2>/dev/null
tmux kill-session -t apex-frontend 2>/dev/null
tmux kill-session -t tinyoffice 2>/dev/null

sleep 1

# 1. Backend
echo "🤖 Starting FastAPI backend (port 8000)..."
tmux new-session -d -s apex-backend -x 220 -y 50 \
  "cd $MOONSHOT_DIR && source .venv/bin/activate && uvicorn backend.server:app --port 8000 --reload 2>&1 | tee /tmp/apex-backend.log"

sleep 2

# 2. Frontend
echo "🖥️  Starting Next.js frontend (port 3000)..."
tmux new-session -d -s apex-frontend -x 220 -y 50 \
  "cd $MOONSHOT_DIR/frontend && npm run dev 2>&1 | tee /tmp/apex-frontend.log"

# 3. TinyClaw daemon (Telegram + agents)
echo "🧠 Starting TinyClaw daemon (Telegram + 11 agents)..."
cd /Volumes/AaryaSDD2TB/vishnuvardhanmedara-mac/MoonshotV3-TinyClawFramework/official-tinyclaw-framework && \
  bash ./tinyclaw.sh start 2>/dev/null

sleep 2

# 4. TinyOffice (/office)
echo "🏢 Starting TinyOffice (port 4001 → /office)..."
tmux new-session -d -s tinyoffice -x 220 -y 50 \
  "cd $MOONSHOT_DIR/tinyclaw/tinyoffice && npm run dev -- -p 4001 2>&1 | tee $MOONSHOT_DIR/tinyclaw/tinyoffice.log"

sleep 3

# 5. Start swarm scan loop
echo "🚀 Starting APEX-SWARM scan loop..."
curl -s -X POST http://localhost:8000/api/swarm/start > /dev/null

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ APEX-SWARM is live!"
echo ""
echo "  🌐 Dashboard:   http://localhost:3000"
echo "  🏢 Office:      http://localhost:3000/office"
echo "  🔧 API:         http://localhost:8000"
echo "  🤖 TinyClaw:    http://localhost:3777"
echo "  📱 Telegram:    @blackpanthertinyclaw01bot"
echo ""
echo "  tmux attach -t apex-backend   # backend logs"
echo "  tmux attach -t apex-frontend  # frontend logs"
echo "  tmux attach -t tinyoffice     # tinyoffice logs"
echo "  tmux attach -t tinyclaw       # tinyclaw agents"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
