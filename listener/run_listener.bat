@echo off
cd /d "%~dp0"
uv run python -m listener.main
pause
