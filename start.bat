@echo off
cd /d "%~dp0"

start "FastAPI" cmd /k "cd /d "%~dp0" && uv run python app/main.py"
start "Listener" cmd /k "cd /d "%~dp0" && uv run python -m listener.main"