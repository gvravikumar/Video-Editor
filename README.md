# VideoStudio AI - Gameplay Shorts Generator

AI-powered web application that automatically analyzes gameplay videos, detects epic moments, and generates viral YouTube Shorts and Instagram Reels with titles, descriptions, and tags.

## ✨ Features

- **🎮 Gameplay Analysis**: AI analyzes your gameplay video frame-by-frame (configurable FPS)
- **📖 Story Generation**: Creates a complete narrative of your gameplay session with timestamps
- **🎯 Moment Detection**: Automatically identifies:
  - Epic wins and victories
  - Crushing defeats
  - Satisfying moments
  - Intense gameplay
  - Funny glitches
- **📱 Short Video Generation**: Creates 9:16 vertical shorts (YouTube Shorts / Instagram Reels format)
  - Hook-first structure: First 7 seconds show the climax/result
  - Then shows the build-up gameplay
  - Optimized for mobile viewing
- **✍️ Metadata Generation**: Auto-generates for each short:
  - Catchy titles with emojis
  - Engaging descriptions
  - Relevant hashtags/tags
- **🎬 Preview System**: Hover to preview shorts before downloading
- **💻 Cross-Platform**: Works on Windows, macOS, and Linux
- **🔌 Offline Mode**: Download models once, run without internet

## 🏗️ Architecture

### AI Models Used (All Free & Open Source)

1. **BLIP Image Captioning** (Salesforce/blip-image-captioning-base)
   - Size: ~990 MB
   - Purpose: Analyzes each video frame and generates descriptive captions
   - Hardware: Auto-detects MPS (Apple Silicon) / CUDA (NVIDIA) / CPU

2. **TinyLlama 1.1B Chat** (TinyLlama/TinyLlama-1.1B-Chat-v1.0)
   - Size: ~2.2 GB
   - Purpose: Generates stories, detects moments, creates metadata
   - Hardware: Auto-detects MPS / CUDA / CPU

### Technology Stack

- **Backend**: Python, Flask
- **Video Processing**: MoviePy, OpenCV
- **AI/ML**: PyTorch, Transformers (HuggingFace)
- **Frontend**: HTML5, Bootstrap 5, Vanilla JavaScript

## 📋 Requirements

- **Python**: 3.8 or higher
- **RAM**: Minimum 8 GB (16 GB recommended for large videos)
- **Storage**: ~5 GB for AI models + space for videos
- **GPU** (optional but recommended):
  - Apple Silicon Mac (M1/M2/M3) - uses MPS backend
  - NVIDIA GPU with CUDA support
  - Falls back to CPU if no GPU available

## 🚀 Quick Start

### Option 1: Easy Start (Recommended)

#### On macOS/Linux:
```bash
chmod +x start.sh
./start.sh
```

#### On Windows:
```cmd
start.bat
```

The script will:
1. Check for Python installation
2. Create a virtual environment
3. Install dependencies
4. Check for AI models (prompt to download if missing)
5. Start the server
6. Open your browser automatically

### Option 2: Manual Setup

1. **Clone or download this repository**

2. **Create virtual environment**:
```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Download AI models** (required for offline use):
```bash
python download_models.py
```
This will download ~3.2 GB of models. First-time download takes 5-15 minutes depending on internet speed.

5. **Start the server**:
```bash
python app.py
```

6. **Open browser** to `http://127.0.0.1:8000`

## 📖 How to Use

### 🎯 **Quick Start Guide**

**See detailed step-by-step guide**: [USER_GUIDE.md](USER_GUIDE.md) 📘

### **Basic Workflow** (5 minutes to get started)

#### **Step 1: Start the App**
```bash
./start.sh        # macOS/Linux
start.bat         # Windows
```
Browser opens to `http://127.0.0.1:8000`

#### **Step 2: Upload Video**
- **Drag & drop** your gameplay video OR
- Click **"Browse Files"** OR
- Select from **"Previously Uploaded Videos"** (if available)

**Supported**: MP4, AVI, MOV, MKV, WebM | **Max**: 2 GB

#### **Step 3: Choose AI Shorts Generator**
1. **Set FPS** (frames per second):
   - Move slider to **2 FPS** (recommended)
   - Higher FPS = more detailed but slower

2. Click **"Generate AI Shorts"** button

#### **Step 4: Wait for AI Processing** ⏳

The AI will automatically:
1. **Extract frames** (~2 min)
2. **Analyze with BLIP AI** (~15 min on M1 Mac, ~30-45 min on CPU)
3. **Generate story** (~5 min)
4. **Detect moments** (~3 min) - finds wins/losses/satisfying/intense moments
5. **Create shorts** (~10 min) - makes 9:16 vertical videos
6. **Generate metadata** (~2 min) - creates titles/descriptions/tags

**Total Time**: ~35-40 minutes for 2-hour video (Apple M1), ~70-90 min (CPU)

#### **Step 5: Download Your Shorts** 🎉

After processing:
- **Browse** all generated shorts (sorted by virality score)
- **Hover** to preview any short
- **Click** to view details (title, description, tags)
- **Copy metadata** with one click
- **Download** individual shorts or all at once

Each short includes:
- ✅ 9:16 vertical video (1080x1920) for YouTube Shorts/Instagram Reels
- ✅ Hook-first structure (first 7 sec = climax/result)
- ✅ AI-generated catchy title with emojis
- ✅ Engaging description
- ✅ 10-15 relevant hashtags

---

### **📚 Detailed Guides**

- **Complete Tutorial**: [USER_GUIDE.md](USER_GUIDE.md) - Full step-by-step with screenshots
- **Setup Instructions**: [SETUP.md](SETUP.md) - Installation troubleshooting
- **Windows Setup**: [WINDOWS_SETUP.md](WINDOWS_SETUP.md) - Windows-specific guide
- **Implementation Details**: [AUDIT_REPORT.md](AUDIT_REPORT.md) - Technical audit
- **Model Structure**: [MODEL_STRUCTURE.md](MODEL_STRUCTURE.md) - How AI models work

---

### **Example Workflow**

```
1. Upload 2-hour Valorant gameplay
   ↓
2. Set FPS to 2 (extracts 14,400 frames)
   ↓
3. Click "Generate AI Shorts"
   ↓ (35-40 min on M1 Mac)
4. AI finds 15 epic moments:
   • 5 WINNING (clutches, aces)
   • 3 LOSING (funny deaths)
   • 4 SATISFYING (perfect shots)
   • 2 INTENSE (battles)
   • 1 FUNNY (glitch)
   ↓
5. Get 15 ready-to-post shorts:
   • Each 30-60 seconds
   • 9:16 vertical format
   • With titles like:
     "🔥 INSANE 1v5 Clutch! 🎯"
   • And descriptions:
     "Watch this incredible comeback..."
   • And hashtags:
     #valorant #clutch #gaming #shorts
   ↓
6. Upload to YouTube/Instagram/TikTok
   ✅ Done!
```

**Time saved vs manual editing**: ~6-7 hours! 🚀

---

### **Alternative: Manual Editor** (Quick Trim)

If you just want to trim a video without AI:

1. Upload video
2. Set start/end times
3. Toggle 2x speed (optional)
4. Click "Process Video"
5. Download trimmed video

Fast and simple! ⚡

---

## 🎮 **What Makes a Good Gaming Short?**

### **The Hook-First Formula** (Implemented by AI):

```
[0-7 sec]    = RESULT/CLIMAX     (Grabs attention!)
               "TRIPLE KILL!"
               "VICTORY!"
               "CLUTCH WON!"
[7-8 sec]    = Brief transition
[8-end]      = BUILD-UP          (Shows how it happened)
               The gameplay leading to the climax
```

**Why this works**:
- Viewer sees exciting result immediately
- Curiosity: "How did that happen?"
- Watches full video to see the build-up
- Higher retention = Algorithm boost 📈

---

## 📊 **Expected Processing Times**

| Hardware | Video Length | FPS | Processing Time |
|----------|--------------|-----|-----------------|
| Apple M1/M2 | 2 hours | 2 | ~35-40 min |
| Apple M1/M2 | 30 min | 2 | ~10-12 min |
| NVIDIA RTX 3060 | 2 hours | 2 | ~30-35 min |
| NVIDIA RTX 3060 | 30 min | 2 | ~8-10 min |
| Intel i7 (CPU) | 2 hours | 2 | ~70-90 min |
| Intel i7 (CPU) | 2 hours | 1 | ~35-45 min |
| Intel i7 (CPU) | 30 min | 2 | ~20-25 min |

**💡 Tip**: Use 1 FPS on CPU-only systems for 2x faster processing!

---

## 🎯 **AI Processing Details**

When you click "Generate AI Shorts", here's what happens:

### **Step 1: Frame Extraction**
    2. AI frame analysis
    3. Story generation
    4. Moment detection
    5. Short video creation
    6. Metadata generation

- **Manual Editor** (Optional):
  - Trim video to specific time range
  - Apply 2x speed up
  - Export manually

### Step 3: Review & Download
- Browse generated shorts (sorted by virality score)
- Hover to preview
- Click to view full details
- Download individual shorts with metadata
- Copy titles, descriptions, and tags

## 🎯 AI Pipeline Details

### Frame Extraction
- Extracts frames at configurable FPS (default: 2 FPS)
- For a 2-hour video at 2 FPS = 14,400 frames
- Saves as JPEG with metadata JSON

### Frame Analysis
- BLIP model analyzes each frame
- Generates gameplay-specific captions
- Batch processing for efficiency
- Progress tracking

### Story Generation
- TinyLlama processes captions in chunks
- Creates narrative with timestamps
- Understands gameplay context
- Maps key events

### Moment Detection
- AI identifies categories:
  - WINNING: Victories, eliminations, captures
  - LOSING: Defeats, deaths, failures
  - SATISFYING: Perfect combos, builds, achievements
  - INTENSE: Battles, sieges, action
  - FUNNY: Glitches, bugs, humor
- Assigns virality scores (1-10)
- Ranks by viral potential

### Short Generation
- **Hook-First Structure**:
  - First 7 seconds: The result/climax
  - Brief transition
  - Remaining: Build-up gameplay
- **Vertical Format**: 9:16 aspect ratio (1080x1920)
- Center-crops horizontal gameplay
- 30 FPS output, optimized bitrate
- Generates thumbnail from hook

### Metadata Generation
- AI creates for each short:
  - Catchy title (< 60 chars with emojis)
  - Engaging description (2-3 sentences)
  - 10-15 relevant hashtags
- Optimized for social media algorithms

## 📁 Project Structure

```
Video-Editor/
├── app.py                  # Flask application & routes
├── download_models.py      # Model download script
├── requirements.txt        # Python dependencies
├── start.sh               # Unix/Mac startup script
├── start.bat              # Windows startup script
├── .gitignore             # Git ignore rules
│
├── services/              # AI pipeline services
│   ├── frame_extractor.py     # Video → frames
│   ├── frame_analyzer.py      # Frames → captions (BLIP)
│   ├── story_generator.py     # Captions → story + moments (TinyLlama)
│   ├── short_generator.py     # Moments → vertical shorts
│   └── metadata_generator.py  # Shorts → titles/descriptions/tags
│
├── templates/
│   └── index.html         # Web UI
│
├── static/
│   ├── css/
│   │   └── style.css      # Styling
│   └── js/
│       └── script.js      # Frontend logic
│
├── models/                # AI models (downloaded on first run)
│   ├── blip-captioning-base/
│   └── tinyllama-chat/
│
├── uploads/               # Uploaded videos (auto-created)
├── frames/                # Extracted frames (auto-created)
├── stories/               # Generated stories (auto-created)
├── shorts/                # Generated short videos (auto-created)
└── processed/             # Manually processed videos (auto-created)
```

## 🔧 Configuration

### AI Model Settings
Edit service files to customize:
- `services/frame_analyzer.py` - BLIP model settings
- `services/story_generator.py` - TinyLlama prompts and generation params

### Video Processing
Edit `services/short_generator.py`:
```python
TARGET_WIDTH = 1080          # Output width
TARGET_HEIGHT = 1920         # Output height (9:16)
HOOK_DURATION = 7            # Hook length in seconds
MIN_SHORT_DURATION = 15      # Minimum short length
MAX_SHORT_DURATION = 60      # Maximum short length
```

### Server Settings
Edit `app.py`:
```python
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2 GB upload limit
```

## 🐛 Troubleshooting

### Models Not Downloading
```bash
# Manually download models
python download_models.py

# Check internet connection
# Verify ~5 GB free disk space
```

### Out of Memory Errors
- Reduce FPS (use 1 FPS instead of 2+)
- Close other applications
- Use shorter video segments
- Upgrade RAM if possible

### Slow Processing
- **On CPU**: Processing is slower. Consider:
  - Using lower FPS (1 FPS)
  - Shorter videos
  - Running on GPU-enabled machine
- **On Apple Silicon**: MPS backend is fast
- **On NVIDIA GPU**: CUDA backend is fastest

### Video Format Not Supported
```bash
# Convert video to MP4 using ffmpeg
ffmpeg -i input.avi -c:v libx264 -c:a aac output.mp4
```

### Permission Errors on macOS/Linux
```bash
chmod +x start.sh
chmod +x download_models.py
```

## 📊 Performance Benchmarks

Approximate processing times (2-hour gameplay video, 2 FPS):

| Hardware | Frame Extraction | AI Analysis | Story+Moments | Shorts Gen | Total |
|----------|-----------------|-------------|---------------|------------|--------|
| Apple M1 | ~2 min | ~15 min | ~8 min | ~10 min | ~35 min |
| NVIDIA RTX 3060 | ~2 min | ~12 min | ~7 min | ~10 min | ~31 min |
| Intel i7 CPU | ~3 min | ~45 min | ~20 min | ~12 min | ~80 min |

*Times vary based on video complexity and moment count

## 🔒 Privacy & Security

- **Local Processing**: All AI processing happens locally on your machine
- **No Cloud**: Videos never leave your computer
- **No API Keys**: Uses open-source models, no external API calls
- **Offline Ready**: Works completely offline after model download

## 📜 License

This project uses the following open-source components:

- **BLIP**: BSD-3-Clause License (Salesforce)
- **TinyLlama**: Apache 2.0 License
- **PyTorch**: BSD License
- **Flask**: BSD-3-Clause License
- **MoviePy**: MIT License

See individual licenses in respective model/library repositories.

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- Support for more languages (non-English gameplay)
- Additional moment categories
- Custom model fine-tuning
- Batch video processing
- Advanced editing features
- Cloud/GPU acceleration options

## 🙏 Acknowledgments

- **Salesforce** for BLIP image captioning model
- **TinyLlama Team** for the lightweight language model
- **HuggingFace** for the Transformers library
- **OpenAI** for inspiration

## 📞 Support

For issues, questions, or feature requests:
1. Check the Troubleshooting section above
2. Review closed issues on GitHub
3. Open a new issue with:
   - Operating system
   - Python version
   - Error messages
   - Steps to reproduce

---

**Made with ❤️ for gamers and content creators**

*Generate viral gaming content with the power of AI* 🎮🚀
