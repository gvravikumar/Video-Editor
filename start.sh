#!/bin/bash
echo "========================================="
echo "     Starting Video Editor Web App"
echo "========================================="

# Detect OS
OS="$(uname -s)"
echo "Detected OS: $OS"

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "ERROR: Python not found. Please install Python 3.8+."
    exit 1
fi

echo "Using Python: $($PYTHON --version)"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Setting it up..."
    $PYTHON -m venv venv
fi

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "ERROR: Could not activate virtual environment."
    exit 1
fi

# Install/upgrade dependencies
echo "Checking dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt --quiet

# Handle PyTorch for different platforms
if [ "$OS" = "Darwin" ]; then
    echo "macOS detected — PyTorch with MPS (Apple Silicon) support will be used."
else
    echo "Linux detected — PyTorch with CPU/CUDA support will be used."
fi

# Check if AI models are downloaded
echo ""
echo "Checking AI models..."
if [ ! -d "models/blip-captioning-base" ] || [ ! -d "models/tinyllama-chat" ]; then
    echo "⚠️  AI models not found locally."
    echo ""
    echo "To enable offline operation, please download models first:"
    echo "    python download_models.py"
    echo ""
    echo "Models will be automatically downloaded on first use (requires internet)."
    echo "Total download size: ~3.2 GB"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled. Please run: python download_models.py"
        exit 1
    fi
else
    echo "✓ AI models found locally (offline mode ready)"
fi

echo ""
echo "Starting the Flask server..."
echo "Access the app at: http://127.0.0.1:8000"
echo ""

# Trap Ctrl+C to cleanup
trap ctrl_c INT

function ctrl_c() {
    echo ""
    echo "Shutting down server..."
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null
    fi
    exit 0
}

# Start the server
$PYTHON app.py &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Open browser
if [ "$OS" = "Darwin" ]; then
    open http://127.0.0.1:8000 2>/dev/null
elif command -v xdg-open &> /dev/null; then
    xdg-open http://127.0.0.1:8000 2>/dev/null
fi

echo ""
echo "✓ Server is running (PID: $SERVER_PID)"
echo "Press Ctrl+C to stop the server."
echo ""

# Wait for server process
wait $SERVER_PID