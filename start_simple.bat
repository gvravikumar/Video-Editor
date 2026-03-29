@echo off
echo =========================================
echo      Starting Video Editor Web App
echo =========================================

REM Check Python
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

REM Create venv if needed
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate and install
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet

REM Start server
echo Starting server...
start "VideoStudio AI Server" cmd /c "python app.py"

timeout /t 3 /nobreak > NUL
start http://127.0.0.1:8000

echo.
echo Server started! Check your browser.
pause
