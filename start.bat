@echo off
setlocal enabledelayedexpansion
echo ========================================
echo   Malla Mesh Network Monitor
echo ========================================
echo.
echo Starting services: postgres, db-init, malla-capture, malla-web (port 8080)
echo.
docker compose build || goto :err
docker compose up -d || goto :err
echo.
echo Viewing logs. Press Ctrl+C to stop tailing (services keep running).
docker compose logs -f
goto :eof
:err
echo Failed to start. Check Docker Desktop and configuration.
exit /b 1
