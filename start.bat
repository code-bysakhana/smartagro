@echo off
title SmartAgro v3 Startup
echo.
echo   SmartAgro v3 -- Starting...
echo.

SET ROOT=%~dp0

:: Check Python
where python >nul 2>&1 || (echo [ERROR] Python not found. Install from python.org && pause && exit /b)
:: Check Node
where node >nul 2>&1   || (echo [ERROR] Node.js not found. Install from nodejs.org && pause && exit /b)

echo [1/3] Installing Python dependencies...
cd /d "%ROOT%backend"
pip install -q -r requirements.txt
echo       Done.

echo [2/3] Starting Flask backend on port 5000...
start "SmartAgro Backend" cmd /k "cd /d "%ROOT%backend" && python app.py"
timeout /t 5 /nobreak >nul

echo [3/3] Starting React frontend on port 3000...
cd /d "%ROOT%frontend"
if not exist node_modules (
  echo       Installing npm packages...
  call npm install --silent
)
start "SmartAgro Frontend" cmd /k "cd /d "%ROOT%frontend" && set BROWSER=none&& npm start"

echo.
echo   ─────────────────────────────────────
echo   Frontend : http://localhost:3000
echo   Backend  : http://localhost:5000
echo   ─────────────────────────────────────
echo.
echo   Two windows opened. Close them to stop the servers.
echo.
pause
