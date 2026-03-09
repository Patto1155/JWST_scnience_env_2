@echo off
REM Start JWST Discovery System - All-in-One

echo Starting API server...
start "JWST API" python run_api.py

echo Waiting for API to be ready...
timeout /t 5 /nobreak > nul

echo.
echo ========================================
echo JWST Discovery System Ready!
echo ========================================
echo.
echo API Server is running in separate window
echo.
echo Run a discovery:
echo   python run_discovery.py --stream --model deepseek-v3.2
echo.
echo OR watch a specific run:
echo   python stream_discovery_win.py RUN_ID
echo.

pause
