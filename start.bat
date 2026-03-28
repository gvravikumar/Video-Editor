@echo off
echo =========================================
echo      Starting Video Editor Web App
echo =========================================

REM Check if virtual environment exists, if not create and install requirements
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Setting it up...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Starting the Flask server...
REM Start the python server in a new window
start "Video Editor Server" cmd /c "venv\Scripts\python app.py"

echo Waiting for the server to start...
timeout /t 3 /nobreak > NUL

echo Opening the application in your default browser...
start http://127.0.0.1:8000

echo.
echo Done! Please check your web browser.
echo You can close this window now. The server is running in the other window.
echo.
pause
