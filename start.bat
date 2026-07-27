@echo off
echo =========================================
echo      Starting Video Editor Web App
echo =========================================

REM Check if Python is available
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found. Please install Python 3.8+.
    pause
    exit /b 1
)

echo Using Python:
python --version

REM Check if virtual environment exists, if not create and install requirements
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Setting it up...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
    echo Checking dependencies...
    pip install -r requirements.txt --quiet
)

echo.
echo AI engine: agent-in-the-loop (Copilot) - no local models to download.
echo Make sure FFmpeg is installed and on PATH.

echo.
echo Starting the Flask server...
echo Access the app at: http://127.0.0.1:8000
echo.

REM Start the python server in a new window
start "VideoStudio AI Server - Press Ctrl+C to stop" cmd /c "venv\Scripts\python app.py"

echo Waiting for the server to start...
timeout /t 3 /nobreak > NUL

echo Opening the application in your default browser...
start http://127.0.0.1:8000

echo.
echo Done! Please check your web browser.
echo The server is running in the separate window.
echo To stop the server, press Ctrl+C in the server window.
echo.
pause
