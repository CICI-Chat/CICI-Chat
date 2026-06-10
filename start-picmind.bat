@echo off
setlocal
set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"

if not exist "%BACKEND_DIR%\.env" (
  > "%BACKEND_DIR%\.env" echo WATCH_FOLDERS=D:/picmind-images
  >> "%BACKEND_DIR%\.env" echo DB_PATH=./data/picmind.db
)

start "PicMind Backend" /D "%BACKEND_DIR%" cmd /k uv run uvicorn app.main:app --reload
start "PicMind Frontend" /D "%PROJECT_DIR%" cmd /k npm --prefix "%FRONTEND_DIR%" run dev -- --host 127.0.0.1

start "" code "%PROJECT_DIR%picmind.code-workspace"

timeout /t 5 /nobreak >nul
start "" "http://localhost:5173/"
