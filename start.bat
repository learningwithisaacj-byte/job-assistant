@echo off
:: start.bat – Start Job Assistant AI on Windows
:: Usage: double-click or run: start.bat

echo.
echo ╔═══════════════════════════════════════════╗
echo ║         🚀 Job Assistant AI               ║
echo ╚═══════════════════════════════════════════╝
echo.

:: Check .env
if not exist .env (
  echo ⚠️  .env not found. Copying from .env.example...
  copy .env.example .env
  echo ✏️  Edit .env and add your ANTHROPIC_API_KEY, then re-run.
  pause
  exit /b 1
)

:: Create venv if needed
if not exist venv (
  echo 📦 Creating virtual environment...
  python -m venv venv
)

call venv\Scripts\activate.bat

:: Install deps
echo 📦 Installing dependencies...
pip install -r requirements.txt -q

:: Create output dirs
if not exist outputs\uploads mkdir outputs\uploads
if not exist outputs\resumes mkdir outputs\resumes
if not exist outputs\cover_letters mkdir outputs\cover_letters

echo.
echo 🚀 Starting FastAPI backend on http://localhost:8000 ...
start "Job Assistant API" cmd /c "venv\Scripts\activate && uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 2 /nobreak >nul

echo 🎨 Starting Streamlit frontend on http://localhost:8501 ...
start "Job Assistant UI" cmd /c "venv\Scripts\activate && streamlit run frontend\app.py"

echo.
echo ╔═══════════════════════════════════════════╗
echo ║  ✅ Job Assistant AI is running!          ║
echo ║                                           ║
echo ║  App:      http://localhost:8501          ║
echo ║  API docs: http://localhost:8000/docs     ║
echo ╚═══════════════════════════════════════════╝
echo.
pause
