@echo off
title DeepGuard AI Launcher

echo =====================================
echo Starting DeepGuard AI...
echo =====================================

cd /d "%~dp0"

:: ============================
:: Backend
:: ============================
start "Backend" cmd /k ^
"cd /d "%~dp0deepguard-ai" && python -m uvicorn app.api:app --reload --host 127.0.0.1 --port 8000"

timeout /t 5 >nul

:: ============================
:: Frontend
:: ============================
start "Frontend" cmd /k ^
"cd /d "%~dp0ai-deepfake-forensics-lab" && npm install && npm run dev"

:: ============================
:: MCP Server
:: ============================
start "MCP Server" cmd /k ^
"cd /d "%~dp0deepguard-ai" && python -m fastmcp.server --port 8090"

:: ============================
:: ADK Playground
:: Replace this command if your project uses a different ADK startup command.
:: ============================
start "ADK Playground" cmd /k ^
"cd /d "%~dp0deepguard-ai" && adk web"

echo.
echo Backend  : http://localhost:8000
echo Frontend : Check the URL printed by Vite (usually http://localhost:5173)
echo MCP      : http://localhost:8090
echo.

pause