@echo off
REM Quick Launch MITS Gradio Interface

echo.
echo ========================================
echo   MITS - Socratic Math Tutor
echo ========================================
echo.

REM Activate venv if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo Starting Gradio interface...
echo.
echo Open in browser: http://localhost:7860
echo.

python -m interface.gradio_app

pause
