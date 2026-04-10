@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Local Vision Search

echo ============================================
echo   Local Vision Search v2.0
echo ============================================
echo.

:: Start backend in minimized window
echo [1/2] Starting Backend API server...
start "Backend API" /min python -m src.api.server
echo       Backend API starting on port 8001

:: Wait for backend to be ready (max 30s)
echo       Waiting for backend to be ready...
set READY=0
for /L %%i in (1,1,30) do (
    if !READY! == 0 (
        curl -s -o nul -w "" http://127.0.0.1:8001/version_check >nul 2>&1
        if !errorlevel! == 0 (
            set READY=1
        ) else (
            timeout /t 1 /nobreak >nul
        )
    )
)
if !READY! == 1 (
    echo       Backend API is ready!
) else (
    echo       Backend may still be loading, continuing...
)

:: Start frontend in minimized window
echo [2/2] Starting Frontend dev server...
start "Frontend UI" /min cmd /c "cd /d %~dp0web && npm run dev"
timeout /t 4 /nobreak >nul
echo       Frontend dev server started on port 5173

echo.
echo ============================================
echo   All services running!
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8001
echo ============================================
echo.

:: Auto open browser
start "" http://localhost:5173

echo Press any key to stop all services...
pause >nul

:: Cleanup
echo.
echo Stopping services...
taskkill /fi "windowtitle eq Backend API" /f >nul 2>&1
taskkill /fi "windowtitle eq Frontend UI" /f >nul 2>&1
echo All services stopped.
timeout /t 2 /nobreak >nul
endlocal
