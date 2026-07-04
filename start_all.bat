@echo off
echo Starting DeepGuard AI...
start cmd /k "cd /d %~dp0deepguard-ai && uv run uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3
start cmd /k "cd /d %~dp0ai-deepfake-forensics-lab && npm run dev"
timeout /t 3
start cmd /k "cd /d %~dp0deepguard-ai && uv run adk web app --host 127.0.0.1 --port 18081 --reload_agents"
echo All services started!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo ADK Playground: http://localhost:18081
pause
