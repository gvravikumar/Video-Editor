# Quick Reference Card

## 🚀 **5-Minute Quick Start**

```bash
# 1. Start the app
./start.sh          # Mac/Linux
start.bat           # Windows

# 2. Open browser (auto-opens)
http://127.0.0.1:8000

# 3. Upload video (drag & drop)

# 4. Set FPS to 2

# 5. Click "Generate AI Shorts"

# 6. Wait ~35-40 min (M1 Mac) or ~70-90 min (CPU)

# 7. Download shorts!
```

---

## 📋 **Command Cheat Sheet**

### **Setup (One-Time)**
```bash
# Download models (~3.2 GB)
python download_models.py

# Verify installation
python verify_setup.py
```

### **Daily Use**
```bash
# Start server
./start.sh          # Mac/Linux
start.bat           # Windows

# Or manually
python app.py
```

---

## ⚙️ **FPS Settings Guide**

| FPS | Frames (2hr) | Processing Time | Use When |
|-----|--------------|-----------------|----------|
| **1** | 7,200 | ⚡ Fast (CPU: 35-45min) | Long videos, CPU-only |
| **2** | 14,400 | ⚖️ Balanced (CPU: 70-90min) | **Recommended default** |
| **3** | 21,600 | 🎯 Detailed (CPU: 90-120min) | Short videos, has GPU |
| **4-5** | 28k-36k | 🐌 Slow | Testing only |

**💡 Rule of thumb**: More FPS = Better detection but slower processing

---

## 🎬 **Output Specifications**

### **Short Videos**
- **Format**: MP4
- **Resolution**: 1080x1920 (9:16 vertical)
- **Frame Rate**: 30 FPS
- **Audio**: Included
- **Codec**: H.264 (libx264)
- **Size**: ~20-50 MB per short
- **Duration**: 15-60 seconds each

### **Platforms**
- ✅ YouTube Shorts
- ✅ Instagram Reels
- ✅ TikTok
- ✅ Facebook Reels

---

## 🔍 **Moment Categories**

| Category | What AI Looks For | Examples |
|----------|-------------------|----------|
| **WINNING** 🏆 | Victories, eliminations, captures | Clutches, aces, final kills |
| **LOSING** 💀 | Defeats, deaths, failures | Funny deaths, epic fails |
| **SATISFYING** ✨ | Perfect execution, achievements | Headshots, combos, builds |
| **INTENSE** ⚔️ | Action-packed sequences | Battles, chases, sieges |
| **FUNNY** 😂 | Glitches, bugs, humor | Ragdolls, physics fails |

---

## 📊 **Processing Pipeline**

```
Upload → Extract → Analyze → Story → Moments → Shorts → Metadata → Done!
         (2min)    (15min)   (5min)  (3min)    (10min)  (2min)

Total: ~35-40 min (M1 Mac) | ~70-90 min (CPU)
```

---

## 💾 **File Locations**

```
Video-Editor/
├── uploads/          ← Your uploaded videos
├── frames/           ← Extracted frames (temp)
├── stories/          ← Generated stories + moments
├── shorts/           ← Generated short videos ⭐
│   └── task_xxx/
│       ├── short_001_winning.mp4
│       ├── short_002_satisfying.mp4
│       └── shorts_with_metadata.json
└── models/           ← AI models (offline cache)
```

---

## 🎯 **Virality Score Guide**

| Score | Meaning | Action |
|-------|---------|--------|
| **9-10** | 🔥 Extremely viral | Upload immediately! |
| **7-8** | ⭐ High potential | Great content |
| **5-6** | 👍 Good | Worth posting |
| **3-4** | 😐 Average | Consider editing |
| **1-2** | ⏭️ Skip | Not recommended |

**Shorts are auto-sorted by virality score (highest first)**

---

## 🛠️ **Common Tasks**

### **Re-process with Different FPS**
1. Select from "Previously Uploaded Videos"
2. Change FPS
3. Click "Generate AI Shorts" again

### **Copy Metadata**
1. Click on any short card
2. Click "📋 Copy Title" / "📋 Copy Description" / "📋 Copy Tags"
3. Paste to YouTube/Instagram/TikTok

### **Download All Shorts**
1. Click "Download All Shorts" button
2. Extract ZIP file
3. Get all MP4 files + metadata.json

---

## ⚡ **Performance Tips**

### **Faster Processing**
- ✅ Use 1 FPS instead of 2-3
- ✅ Process shorter videos (< 1 hour)
- ✅ Close other apps (free up RAM)
- ✅ Use GPU if available

### **Better Results**
- ✅ Use 2-3 FPS for more frames
- ✅ Videos with varied action work best
- ✅ Good lighting and clear gameplay
- ✅ Multiple match types (not one long match)

---

## 🐛 **Quick Troubleshooting**

| Problem | Solution |
|---------|----------|
| Python not found | Install Python 3.8+, add to PATH |
| Models not downloading | Run: `python download_models.py` |
| Out of memory | Use 1 FPS, close other apps |
| Processing stuck | Normal! Check terminal for progress |
| No moments detected | Lower FPS, check video has action |
| Port 8000 busy | Kill process or use different port |

---

## 📱 **Upload to Social Media**

### **YouTube Shorts**
```
1. YouTube Studio → Create → Upload
2. Select short.mp4
3. Paste title ✍️
4. Paste description ✍️
5. Add tags ✍️
6. Set aspect ratio: Vertical
7. Publish!
```

### **Instagram Reels**
```
1. Instagram app → + → Reel
2. Select short.mp4
3. Paste caption ✍️
4. Add hashtags ✍️
5. Post!
```

### **TikTok**
```
1. TikTok app → +
2. Upload short.mp4
3. Paste description + tags ✍️
4. Post!
```

---

## 📞 **Quick Help**

```bash
# Verify setup
python verify_setup.py

# Check models
ls -lh models/

# View logs
# Check terminal/console for errors
```

**Documentation**:
- Full Tutorial: [USER_GUIDE.md](USER_GUIDE.md)
- Setup Help: [SETUP.md](SETUP.md)
- Windows Guide: [WINDOWS_SETUP.md](WINDOWS_SETUP.md)

---

## 🎮 **Supported Games**

**Works best with**:
- FPS games (CS:GO, Valorant, COD, Apex)
- MOBA games (League, Dota 2)
- Battle Royale (Fortnite, PUBG, Warzone)
- Sports games (FIFA, NBA 2K)
- Any game with clear action/events!

---

## ⏱️ **Time Comparison**

### **Manual Editing**:
```
Watch 2hr video:         2 hours
Note moments:           30 min
Edit 10 shorts:        3-4 hours
Create thumbnails:      1 hour
Write metadata:         1 hour
─────────────────────────────────
TOTAL:                  ~7 hours
```

### **With AI**:
```
Upload:                  3 min
Configure:              30 sec
AI processing:         35-40 min
Review & download:      5 min
─────────────────────────────────
TOTAL:                 ~45 min
```

**⚡ 9x faster!** Time saved: ~6 hours

---

**Print this card and keep it handy!** 📄✨
