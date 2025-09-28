@echo off
echo ========================================
echo   Malla Mesh Network Monitor
echo ========================================
echo.
echo This will start ALL services at once:
echo - PostgreSQL database (port 5432)
echo - MQTT capture service
echo - Web UI frontend (port 5008)
echo.
echo Make sure you have Docker installed and running.
echo.
echo Press Ctrl+C to stop all services
echo.

REM Check if .env file exists, if not copy from example
if not exist .env (
    echo Creating .env file from template...
    copy env.example .env
    echo Please edit .env file with your MQTT broker settings
    echo.
)

echo Starting all services with docker-compose...
docker-compose up --build
