@echo off
chcp 65001 >nul
title ChemAI 智能教学系统
color 0A
cd /d "%~dp0"
echo ========================================
echo    ChemAI 智能教学系统启动中...
echo ========================================
echo.
echo 1. 停止旧服务...
taskkill /F /IM python.exe 2>nul
timeout /t 2 >nul
echo.
echo 2. 删除旧数据库(如有结构变化)...
if exist chemai.db del chemai.db
echo.
echo 3. 启动后端服务 (http://localhost:8000)...
start http://localhost:8000/teacher
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
