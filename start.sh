#!/usr/bin/env bash
# start.sh – Start both the API and Streamlit in one command
# Usage: ./start.sh
# Stop:  Ctrl+C (kills both processes)

set -e

echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║         🚀 Job Assistant AI               ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Check .env exists
if [ ! -f .env ]; then
  echo "⚠️  .env file not found. Creating from .env.example..."
  cp .env.example .env
  echo "✏️  Please edit .env and add your ANTHROPIC_API_KEY, then re-run."
  exit 1
fi

# Check API key
if grep -q "sk-ant-\.\.\." .env || ! grep -q "ANTHROPIC_API_KEY=sk-" .env; then
  echo "⚠️  ANTHROPIC_API_KEY not set in .env"
  echo "   Get your key at: https://console.anthropic.com"
  exit 1
fi

# Check venv
if [ ! -d "venv" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv venv
fi

# Activate venv
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null

# Install deps
echo "📦 Installing dependencies..."
pip install -r requirements.txt -q

# Create output dirs
mkdir -p outputs/uploads outputs/resumes outputs/cover_letters

echo ""
echo "🚀 Starting FastAPI backend on http://localhost:8000 ..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

sleep 2

echo "🎨 Starting Streamlit frontend on http://localhost:8501 ..."
streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0 &
UI_PID=$!

echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║  ✅ Job Assistant AI is running!          ║"
echo "║                                           ║"
echo "║  🖥️  App:      http://localhost:8501      ║"
echo "║  📡 API docs: http://localhost:8000/docs  ║"
echo "║                                           ║"
echo "║  Press Ctrl+C to stop                    ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Wait for Ctrl+C
trap "echo ''; echo 'Stopping...'; kill $API_PID $UI_PID 2>/dev/null; exit 0" INT TERM
wait
