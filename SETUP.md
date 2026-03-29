# Setup Guide - VideoStudio AI

Complete setup instructions for all platforms.

## 🎯 Prerequisites

Before you begin, ensure you have:

1. **Python 3.8 or higher** installed
   - Check: `python3 --version` or `python --version`
   - Download from: https://www.python.org/downloads/

2. **At least 8 GB RAM** (16 GB recommended)

3. **~5 GB free disk space** (for models and temporary files)

4. **Internet connection** (only for initial setup)

## 📦 Installation Methods

### Method 1: Automatic Setup (Easiest)

This is the recommended method for most users.

#### On macOS:
```bash
cd Video-Editor
./start.sh
```

The script will:
- ✓ Create virtual environment
- ✓ Install all dependencies
- ✓ Check for AI models
- ✓ Start the server
- ✓ Open browser

#### On Windows:
1. Navigate to the `Video-Editor` folder
2. Double-click `start.bat`

### Method 2: Manual Setup

#### Step 1: Create Virtual Environment

**macOS/Linux:**
```bash
cd Video-Editor
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
cd Video-Editor
python -m venv venv
venv\Scripts\activate
```

#### Step 2: Upgrade pip
```bash
pip install --upgrade pip
```

#### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- Flask (web framework)
- MoviePy (video processing)
- OpenCV (frame extraction)
- PyTorch (AI backend)
- Transformers (HuggingFace models)
- Pillow (image processing)
- And other dependencies...

**Note for macOS (Apple Silicon):**
PyTorch will automatically use MPS (Metal Performance Shaders) for GPU acceleration.

**Note for NVIDIA GPU users:**
PyTorch will automatically detect and use CUDA if available.

#### Step 4: Download AI Models

**Option A - Using the download script (Recommended):**
```bash
python download_models.py
```

This will download:
- BLIP Image Captioning model (~990 MB)
- TinyLlama Chat model (~2.2 GB)

Total: ~3.2 GB

**Option B - Models will auto-download on first use:**
If you skip this step, models will be downloaded automatically when you first run the AI pipeline. However, this is not recommended for production environments.

#### Step 5: Verify Installation

```bash
python -c "import torch; import transformers; import cv2; import flask; print('✓ All dependencies installed successfully')"
```

#### Step 6: Start the Server

```bash
python app.py
```

Open browser to: http://127.0.0.1:8000

## 🔧 Platform-Specific Notes

### macOS

**Apple Silicon (M1/M2/M3):**
- PyTorch will use MPS backend for GPU acceleration
- Significantly faster than CPU-only processing
- No additional setup required

**Intel Mac:**
- Will use CPU backend
- Processing will be slower
- Consider using a smaller FPS setting (1 FPS)

**Permissions:**
If you get "Permission Denied" errors:
```bash
chmod +x start.sh
chmod +x download_models.py
```

### Windows

**NVIDIA GPU:**
- PyTorch will auto-detect CUDA if drivers are installed
- Install NVIDIA GPU drivers from: https://www.nvidia.com/download/index.aspx

**No GPU:**
- Will use CPU backend
- Processing will be slower

**Antivirus/Firewall:**
- May need to allow Python through firewall
- May need to allow Flask server (port 8000)

### Linux

**NVIDIA GPU:**
```bash
# Verify CUDA is available
python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

**CPU Only:**
- Works fine, just slower
- Use lower FPS settings

## 🐛 Common Issues

### Issue: "Python not found"

**Solution:**
- Install Python from https://www.python.org/downloads/
- Ensure it's in your PATH
- On macOS: `brew install python3`
- On Ubuntu/Debian: `sudo apt install python3 python3-pip python3-venv`

### Issue: "pip install fails"

**Solution:**
```bash
# Upgrade pip first
pip install --upgrade pip

# Try installing with verbose output
pip install -r requirements.txt --verbose
```

### Issue: "Out of memory during model download"

**Solution:**
- Free up disk space (need at least 5 GB)
- Download models one at a time:
  ```bash
  python -c "from transformers import BlipProcessor; BlipProcessor.from_pretrained('Salesforce/blip-image-captioning-base')"
  ```

### Issue: "torch not available" or "MPS not available"

**Solution:**
```bash
# Reinstall PyTorch
pip uninstall torch torchvision
pip install torch torchvision
```

### Issue: "ModuleNotFoundError"

**Solution:**
Make sure virtual environment is activated:
```bash
# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

# Then reinstall
pip install -r requirements.txt
```

### Issue: "Port 8000 already in use"

**Solution:**
```bash
# Find and kill process using port 8000
# macOS/Linux:
lsof -ti:8000 | xargs kill -9

# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Or use a different port in app.py:
# app.run(debug=True, port=8001)
```

## 🔍 Verification Checklist

After setup, verify everything works:

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] All dependencies installed (run: `pip list`)
- [ ] PyTorch installed and detects correct device
  ```bash
  python -c "import torch; print('Device:', 'mps' if torch.backends.mps.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu')"
  ```
- [ ] AI models downloaded (check `models/` directory)
- [ ] Flask server starts without errors
- [ ] Can access web UI at http://127.0.0.1:8000

## 📊 System Requirements Summary

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.8 | 3.10+ |
| RAM | 8 GB | 16 GB |
| Storage | 5 GB free | 20 GB free |
| GPU | None (CPU works) | Apple Silicon / NVIDIA |
| OS | Windows 10, macOS 10.15, Ubuntu 18.04 | Windows 11, macOS 13+, Ubuntu 22.04 |

## 🚀 Next Steps

Once setup is complete:

1. Read the main [README.md](README.md) for usage instructions
2. Start with a short test video (< 5 minutes)
3. Use 1-2 FPS for first test
4. Review the generated shorts
5. Adjust settings as needed

## 💡 Tips for Best Performance

1. **Start small**: Test with a 5-10 minute video first
2. **Use appropriate FPS**:
   - 1 FPS: Fast, good for long videos
   - 2 FPS: Balanced (default)
   - 3-5 FPS: Detailed, but slower
3. **GPU acceleration**:
   - Apple Silicon Macs: Use MPS automatically
   - NVIDIA GPUs: Ensure CUDA drivers installed
   - CPU-only: Use 1 FPS
4. **Close other apps**: Free up RAM during processing
5. **SSD storage**: Faster I/O for frame extraction

## 🔄 Updating

To update the application:

```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Update dependencies
pip install -r requirements.txt --upgrade

# Re-download models if needed
python download_models.py
```

## 🆘 Still Having Issues?

1. Check this guide again carefully
2. Review error messages
3. Check available disk space and RAM
4. Try with a smaller test video
5. Check Python and pip versions
6. Reinstall virtual environment from scratch:
   ```bash
   rm -rf venv  # macOS/Linux
   # or
   rmdir /s venv  # Windows

   # Then follow setup steps again
   ```

---

**Ready to generate viral gaming content!** 🎮✨
