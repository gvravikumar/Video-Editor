# Windows Setup Guide

## 🎯 Quick Setup on Windows

### Option A: Fresh Install (Downloads Models Again)

1. **Copy project to Windows machine**
   - Use USB drive, network share, or cloud storage
   - Copy entire `Video-Editor` folder

2. **Run the startup script**
   ```cmd
   cd Video-Editor
   start.bat
   ```

3. **Wait for setup** (~10-15 minutes)
   - Creates virtual environment
   - Installs dependencies
   - Downloads models (~3.2 GB)
   - Starts server

4. **Done!**
   - Browser opens automatically
   - Access: http://127.0.0.1:8000

---

### Option B: Transfer Models (Saves Time & Bandwidth) ⭐

Since you already downloaded models on Mac, you can transfer them to Windows to avoid re-downloading 3.2 GB!

#### Step 1: On Mac - Package Everything

```bash
cd /Users/ravikumar/CodeStudioProjects/Video-Editor

# Create a zip with code + models (skip venv)
zip -r Video-Editor-with-models.zip . -x "venv/*" "uploads/*" "processed/*" "frames/*" "shorts/*" "stories/*"
```

**This creates a ~3.2 GB zip file containing:**
- All Python code
- Both AI models (already downloaded)
- All configs and scripts

#### Step 2: Transfer to Windows

**Choose one method:**

1. **USB Drive**
   - Copy `Video-Editor-with-models.zip` to USB
   - Transfer to Windows machine

2. **Cloud Storage** (OneDrive, Google Drive, Dropbox)
   - Upload zip
   - Download on Windows

3. **Network Share**
   - Copy over local network

4. **Email/WeTransfer** (if < 2 GB, won't work for this)
   - Too large for this method

#### Step 3: On Windows - Extract and Run

1. **Extract the zip**
   ```cmd
   REM Extract to C:\Video-Editor (or any location)
   ```

2. **Verify models are present**
   ```cmd
   cd C:\Video-Editor
   dir models\blip-captioning-base
   dir models\tinyllama-chat
   ```

   Should see:
   ```
   models\blip-captioning-base\model.safetensors (854 MB)
   models\tinyllama-chat\model.safetensors (2.0 GB)
   ```

3. **Run setup**
   ```cmd
   start.bat
   ```

   This will:
   - ✅ Create virtual environment (fresh for Windows)
   - ✅ Install dependencies
   - ✅ **Skip model download** (already present!)
   - ✅ Start server

4. **Done!** Total time: ~5 minutes instead of 15-20 minutes

---

## 🔧 Windows-Specific Considerations

### **GPU Acceleration**

#### **If you have NVIDIA GPU:**

1. **Install NVIDIA drivers**
   - Download from: https://www.nvidia.com/download/index.aspx
   - Select your GPU model
   - Install latest Game Ready or Studio drivers

2. **Check CUDA detection**
   ```cmd
   python -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
   ```

   Should show:
   ```
   CUDA: True GeForce RTX 3060
   ```

3. **Performance with GPU:**
   - 2-hour video at 2 FPS: ~25-35 minutes
   - Much faster than CPU!

#### **If you have CPU only:**

- Still works perfectly!
- Just slower: ~60-90 minutes for 2-hour video
- Use lower FPS (1 FPS) for faster processing

---

## 🐛 Common Windows Issues

### Issue 1: "Python not found"

**Solution:**
```cmd
REM Download Python from python.org
REM During installation, CHECK "Add Python to PATH"
```

### Issue 2: "Permission denied" or "Access denied"

**Solution:**
- Run `start.bat` as Administrator
- Right-click → Run as administrator

### Issue 3: Antivirus blocks Python/pip

**Solution:**
- Add Python folder to antivirus exceptions
- Temporarily disable antivirus during setup

### Issue 4: Port 8000 already in use

**Solution:**
```cmd
REM Find and kill process using port 8000
netstat -ano | findstr :8000
taskkill /PID <PID_NUMBER> /F

REM Or edit app.py to use different port
```

### Issue 5: "No module named 'torch'"

**Solution:**
```cmd
REM Activate virtual environment first
venv\Scripts\activate
pip install -r requirements.txt
```

---

## 📊 Windows Performance Estimates

| Hardware | Processing Time (2-hour video, 2 FPS) |
|----------|--------------------------------------|
| Intel i7 + RTX 3060 | ~30-35 minutes ⚡ |
| Intel i7 + RTX 2060 | ~35-45 minutes |
| Intel i5 + CPU only | ~70-90 minutes |
| Intel i3 + CPU only | ~90-120 minutes |

---

## ✅ Verification on Windows

After setup, verify everything works:

```cmd
REM Activate virtual environment
venv\Scripts\activate

REM Run verification
python verify_setup.py
```

Should show:
```
✅ All checks passed! System is ready.
✓ PyTorch version: 2.11.0
✓ Compute device: CUDA - GeForce RTX 3060  (or CPU)
✓ BLIP Image Captioning - 855.1 MB
✓ TinyLlama Chat - 2101.7 MB
```

---

## 🔄 Transferring Between Mac and Windows

### **What Transfers:**
- ✅ All Python code
- ✅ AI models (platform-independent)
- ✅ Configuration files
- ✅ Scripts

### **What Doesn't Transfer:**
- ❌ Virtual environment (`venv/`) - Must recreate on each OS
- ❌ Compiled binaries (.so, .dylib, .dll)
- ❌ OS-specific cache files

### **Best Practice:**

**On Mac:**
```bash
# Package code + models (exclude venv and data)
zip -r project.zip . -x "venv/*" "uploads/*" "processed/*" "frames/*" "shorts/*" "stories/*" "__pycache__/*" "*.pyc"
```

**On Windows:**
```cmd
REM Extract zip
REM Run start.bat (recreates venv automatically)
```

---

## 🌐 Network/Cloud Alternative

If you want to use the Mac as a server and access from Windows:

### **On Mac:**

1. **Find Mac IP address**
   ```bash
   ipconfig getifaddr en0
   # Example: 192.168.1.100
   ```

2. **Start server on all interfaces**
   ```bash
   # Edit app.py, change last line:
   app.run(debug=True, host='0.0.0.0', port=8000)
   ```

3. **Start server**
   ```bash
   ./start.sh
   ```

### **On Windows:**

1. **Open browser**
   ```
   http://192.168.1.100:8000
   ```

2. **Upload and process videos remotely!**

**Note:** Both machines must be on same network.

---

## 📦 File Sizes

When transferring:

| Item | Size |
|------|------|
| Python code + configs | ~5 MB |
| BLIP model | 855 MB |
| TinyLlama model | 2.1 GB |
| **Total (with models)** | **~3 GB** |
| **Total (without models)** | **~5 MB** |

---

## 🎯 Recommended Transfer Method

**Best Option: Transfer with Models**

1. ✅ Saves 3.2 GB download on Windows
2. ✅ Faster setup (5 min vs 15-20 min)
3. ✅ Works offline immediately
4. ✅ One-time 3 GB transfer

**Steps:**
1. Zip project with models on Mac
2. Transfer via USB drive (fastest) or cloud
3. Extract on Windows
4. Run `start.bat`
5. Done!

---

## 🚀 Quick Start Checklist (Windows)

- [ ] Python 3.8+ installed (with PATH)
- [ ] Project folder copied/extracted
- [ ] Models present in `models/` folder
- [ ] Double-click `start.bat`
- [ ] Browser opens to http://127.0.0.1:8000
- [ ] Upload test video (5-10 min)
- [ ] Click "Generate AI Shorts"
- [ ] Wait for results
- [ ] Download shorts!

---

## 💡 Pro Tips

1. **First Run**: Use a short test video (5-10 minutes)
2. **GPU Users**: Install NVIDIA drivers first
3. **CPU Users**: Use 1 FPS for faster processing
4. **Transfer**: Include models to save time
5. **Firewall**: Allow Python through Windows Firewall when prompted

---

**The app will work identically on Windows!** 🎮🖥️
