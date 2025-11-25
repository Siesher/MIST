@echo off
REM MITS Quick Start Script for Windows

echo.
echo ========================================
echo   MITS - Mathematics Tutoring System
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.10+
    pause
    exit /b 1
)

REM Check if venv exists
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

REM Activate venv
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies if needed
if not exist "venv\Lib\site-packages\gradio" (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
)

REM Check Ollama
echo.
echo [INFO] Checking Ollama...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama not found in PATH
    echo Please install from: https://ollama.com/
    echo.
)

REM Create .env if not exists
if not exist ".env" (
    echo [INFO] Creating .env from example...
    copy .env.example .env
)

echo.
echo [INFO] Starting MITS...
echo.
python -m src.main --check

echo.
set /p START="Start Gradio interface? (y/n): "
if /i "%START%"=="y" (
    python -m interface.gradio_app
)

pause
