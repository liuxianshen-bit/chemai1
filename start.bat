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
echo 2. Database check...
set /p RESET="Reset database? (y/N): "
if /i "%RESET%"=="y" (
    del chemai.db 2>nul
    echo Database reset.
) else (
    echo Keeping existing database.
)
echo.
if "%CHEMAI_PORT%"=="" set CHEMAI_PORT=8001
echo 3. Starting backend server on http://localhost:%CHEMAI_PORT% ...
start http://localhost:%CHEMAI_PORT%/
python -m uvicorn app.main:app --host 127.0.0.1 --port %CHEMAI_PORT% --reload
pause
