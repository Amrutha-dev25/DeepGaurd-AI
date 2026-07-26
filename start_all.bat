@echo off
title DeepGuard AI Launcher

echo ==========================================
echo         DeepGuard AI Launcher
echo ==========================================

cd /d "%~dp0"

REM ===========================
REM Backend
REM ===========================
start "DeepGuard Backend" cmd.exe /k "cd /d "%~dp0deepguard-ai\backend" && call ..\.venv\Scripts\activate.bat && python -m uvicorn app.api:app --reload --host 127.0.0.1 --port 8000"

timeout /t 3 >nul

REM ===========================
REM Frontend
REM ===========================
start "DeepGuard Frontend" cmd.exe /k "cd /d "%~dp0deepguard-ai\frontend" && npm run dev"

timeout /t 2 >nul

REM ===========================
REM ADK
REM ===========================
start "DeepGuard ADK" cmd.exe /k "cd /d "%~dp0deepguard-ai" && call .venv\Scripts\activate.bat && adk web --host 127.0.0.1 --port 8001"

echo.
echo ========================================== 
echo Starting all services...
echo ==========================================
echo Backend  : http://127.0.0.1:8000
echo Frontend : http://localhost:5173
echo ADK      : http://127.0.0.1:8001
echo.
pause
