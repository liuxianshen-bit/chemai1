@echo off
title ChemAI Server
cd /d "%~dp0"
echo ========================================
echo    ChemAI Server Starting...
echo ========================================
echo.
echo 1. Stopping old services...
taskkill /F /IM python.exe 2>nul
timeout /t 2 >nul
echo.
echo 2. Removing old database...
del chemai.db 2>nul
echo Database reset.
echo.
echo 3. Starting backend server on http://localhost:8001 ...
start http://localhost:8001/
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
pause
