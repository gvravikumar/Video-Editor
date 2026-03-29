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
echo Windows detected - PyTorch with CPU support will be used.
echo (CUDA will be auto-detected if NVIDIA GPU is available)

REM Check if AI models are downloaded
echo.
echo Checking AI models...
if not exist "models\blip-captioning-base\config.json" (
    echo WARNING: AI models not found locally.
    echo.
    echo To enable offline operation, please download models first:
    echo     python download_models.py
    echo.
    echo Models will be automatically downloaded on first use (requires internet^).
    echo Total download size: ~3.2 GB
    echo.
    set /p CONTINUE="Continue anyway? (Y/N): "
    if /i not "%CONTINUE%"=="Y" (
        echo Cancelled. Please run: python download_models.py
        pause
        exit /b 1
    )
) else (
    echo OK - AI models found locally (offline mode ready^)
)

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
