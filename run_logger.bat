@echo off
REM OptiMetrics Hardware Logger Launcher
REM This script starts the hardware metrics collection

cd /d "%~dp0"

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the logger
python src\hardware_logger.py %*

pause
