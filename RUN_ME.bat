@echo off
echo.
echo ================================================
echo JWST Deep Discovery System
echo ================================================
echo.
echo This will start:
echo   1. API Server (background)
echo   2. Discovery run with live streaming
echo.
echo Press Ctrl+C to stop anytime
echo.
pause

REM Start API in background
echo Starting API server...
start /B python run_api.py > api.log 2>&1

REM Wait for API to start
echo Waiting for API to initialize...
timeout /t 8 /nobreak > nul

REM Test if API is up
python -c "import requests; requests.get('http://localhost:8000/health', timeout=2)" 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: API failed to start!
    echo Check api.log for details
    pause
    exit /b 1
)

echo.
echo API is ready!
echo.
echo ================================================
echo Starting Discovery with Live Streaming...
echo ================================================
echo.

REM Run discovery with streaming
python run_discovery.py --stream --model deepseek-v3.2 --steps 30

echo.
echo ================================================
echo Discovery Complete!
echo ================================================
echo.
echo API server is still running in background.
echo Press any key to stop it...
pause > nul

REM Kill API server
taskkill /F /FI "WINDOWTITLE eq python run_api.py*" > nul 2>&1

echo API server stopped.
