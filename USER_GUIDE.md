# Step-by-Step User Guide
## How to Use VideoStudio AI - Gameplay Shorts Generator

---

## 📺 **Quick Demo Video Script**

**Total Time**: 5-10 minutes for a test video

---

## 🚀 **Step 1: Start the Application**

### On macOS:
```bash
cd Video-Editor
./start.sh
```

### On Windows:
```cmd
cd Video-Editor
start.bat
```

### What happens:
- Browser opens automatically
- Shows: `http://127.0.0.1:8000`
- You see the upload screen

**✅ Success**: You see "AI-Powered Gameplay Shorts Generator" page

---

## 📤 **Step 2: Upload Your Gameplay Video**

### Method A: Drag & Drop
1. Open your file explorer
2. Find your gameplay video (MP4, AVI, MOV, MKV, WebM)
3. **Drag the file** onto the upload area
4. **Drop it**

### Method B: Browse Files
1. Click **"Browse Files"** button
2. Select your video file
3. Click **"Open"**

### Method C: Use Previous Upload (if available)
1. Scroll down to **"Previously Uploaded Videos"** section
2. Click on any file to reuse it (skips upload)

### What you'll see:
```
Uploading... 45%
[████████████░░░░░░░]
```

**⏱ Upload Time**:
- Small video (100 MB): ~30 seconds
- Large video (1 GB): ~2-5 minutes

**✅ Success**: Video player appears with your video loaded

---

## 🎬 **Step 3: Choose Your Processing Mode**

You'll see **TWO options**:

### **Option A: AI Shorts Generator** ⭐ (Recommended)

This is the **MAIN FEATURE** - fully automated AI processing!

**What it does**:
- Extracts frames from your video
- AI analyzes each frame
- Generates a story with timestamps
- Detects epic moments (wins/losses/satisfying/intense)
- Creates 9:16 vertical shorts
- Generates titles, descriptions, and tags

**Skip to Step 4** for AI Shorts Generator

---

### **Option B: Manual Editor** (Quick Trim & Export)

Simple video editing without AI.

**What it does**:
- Trim video to specific time range
- Optional 2x speed up
- Export manually

**How to use Manual Editor**:

1. **Set Start Time**:
   - Play video to desired start point
   - Click **"Set as Start"**
   - OR manually enter time (e.g., `120.5` = 2 min 0.5 sec)

2. **Set End Time**:
   - Play video to desired end point
   - Click **"Set as End"**
   - OR manually enter time

3. **Speed Up** (optional):
   - Toggle **"2x Speed Up"** switch

4. **Process**:
   - Click **"Process Video"** button
   - Wait for processing (progress bar shows status)
   - Download when complete

**✅ Done with Manual Editor!** You can download your processed video.

---

## 🤖 **Step 4: Use AI Shorts Generator** (Main Feature)

### **4.1 Configure FPS (Frames Per Second)**

You'll see an **FPS slider**:

```
┌─────────────────────────────────────┐
│  AI Analysis FPS: 2                 │
│  [1]─────●─────[3]─────[5]         │
│                                      │
│  2 FPS = 14,400 frames for 2 hours │
└─────────────────────────────────────┘
```

**What is FPS?**
- FPS = How many frames to extract per second
- Higher FPS = More detailed analysis, but slower
- Lower FPS = Faster processing, less detail

**Recommendations**:

| Video Length | Recommended FPS | Why? |
|--------------|-----------------|------|
| 0-30 min | 3-4 FPS | Short video, can afford detail |
| 30-60 min | 2-3 FPS | Balanced |
| 1-2 hours | 2 FPS | Standard (14,400 frames for 2hr) |
| 2+ hours | 1 FPS | Faster, still effective |

**💡 For First Test**: Use **2 FPS** (default)

---

### **4.2 Click "Generate AI Shorts"**

Click the big **"Generate AI Shorts"** button.

**What happens now**:
The AI pipeline starts! You'll see **5 stages**:

---

### **STAGE 1: Frame Extraction** 🎞️

```
┌─────────────────────────────────────────┐
│ 🎞️  Extracting Frames...              │
│                                         │
│ [████████████░░░░░░] 65%               │
│                                         │
│ Extracted 9,360 / 14,400 frames        │
└─────────────────────────────────────────┘
```

**What's happening**:
- Extracting frames from video at your chosen FPS
- For 2-hour video at 2 FPS = 14,400 frames

**⏱ Time**: ~1-3 minutes

---

### **STAGE 2: AI Frame Analysis** 🧠

```
┌─────────────────────────────────────────┐
│ 🧠  AI Analyzing Frames...             │
│                                         │
│ [████████░░░░░░░░░░] 45%               │
│                                         │
│ Analyzed 6,480 / 14,400 frames         │
│                                         │
│ Using: BLIP Image Captioning           │
└─────────────────────────────────────────┘
```

**What's happening**:
- BLIP AI model analyzes each frame
- Generates gameplay descriptions
- Example: "a player aiming at enemy in first person shooter"

**⏱ Time**:
- **Apple M1/M2**: ~10-15 minutes
- **NVIDIA GPU**: ~8-12 minutes
- **CPU only**: ~30-45 minutes

**💡 Tip**: This is the slowest part - be patient!

---

### **STAGE 3: Story Generation** 📖

```
┌─────────────────────────────────────────┐
│ 📖  Generating Story...                │
│                                         │
│ [████████████████░░] 80%               │
│                                         │
│ Using: TinyLlama AI                    │
└─────────────────────────────────────────┘
```

**What's happening**:
- TinyLlama AI reads all frame descriptions
- Generates a narrative story of your gameplay
- Maps story to timestamps

**⏱ Time**: ~5-8 minutes

---

### **STAGE 4: Moment Detection** 🎯

```
┌─────────────────────────────────────────┐
│ 🎯  Detecting Key Moments...           │
│                                         │
│ [██████████████████] 100%              │
│                                         │
│ Found 15 moments!                      │
│ • 5 WINNING moments                    │
│ • 3 LOSING moments                     │
│ • 4 SATISFYING moments                 │
│ • 2 INTENSE moments                    │
│ • 1 FUNNY moment                       │
└─────────────────────────────────────────┘
```

**What's happening**:
- AI identifies epic moments
- Assigns categories:
  - **WINNING**: Victories, eliminations, captures
  - **LOSING**: Defeats, deaths, game overs
  - **SATISFYING**: Perfect combos, builds, achievements
  - **INTENSE**: Battles, sieges, action sequences
  - **FUNNY**: Glitches, bugs, hilarious fails
- Assigns virality score (1-10) to each moment

**⏱ Time**: ~3-5 minutes

---

### **STAGE 5: Generating Short Videos** 🎬

```
┌─────────────────────────────────────────┐
│ 🎬  Creating Short Videos...           │
│                                         │
│ [████████████░░░░░░] 60%               │
│                                         │
│ Generated 9 / 15 shorts                │
│                                         │
│ • Creating 9:16 vertical format        │
│ • Hook-first structure                 │
│ • Generating thumbnails                │
└─────────────────────────────────────────┘
```

**What's happening**:
- Creates 9:16 vertical shorts (YouTube Shorts / Instagram Reels)
- **Hook-first structure**:
  - First 7 seconds = Result/Climax (grabs attention)
  - Then shows the build-up gameplay
- Generates thumbnail for each short

**⏱ Time**: ~8-12 minutes (depends on number of moments)

---

### **STAGE 6: Generating Metadata** ✍️

```
┌─────────────────────────────────────────┐
│ ✍️  Generating Titles & Tags...        │
│                                         │
│ [██████████████████] 100%              │
│                                         │
│ Created metadata for 15 shorts         │
└─────────────────────────────────────────┘
```

**What's happening**:
- AI generates for each short:
  - Catchy title with emojis (< 60 chars)
  - Engaging description (2-3 sentences)
  - 10-15 relevant hashtags

**Example**:
- **Title**: "🔥 INSANE Clutch Victory in Valorant! 🎮"
- **Description**: "Watch this incredible 1v5 comeback that had everyone speechless. The final headshot was pure perfection!"
- **Tags**: #valorant #clutch #gaming #shorts #viral #fps #esports #gaming #gameplay

**⏱ Time**: ~2-3 minutes

---

## 🎉 **Step 5: View Your AI-Generated Shorts**

### **Results Page** 🎊

After all stages complete, you'll see:

```
┌────────────────────────────────────────────────────────────┐
│  ✅ AI Processing Complete!                                │
│                                                             │
│  📊 Results:                                                │
│  • Total Frames Analyzed: 14,400                          │
│  • Story Generated: Yes                                    │
│  • Moments Detected: 15                                    │
│  • Shorts Created: 15                                      │
│                                                             │
│  [View Story] [Download All Shorts]                       │
└────────────────────────────────────────────────────────────┘
```

---

### **5.1 View the Generated Story**

Click **"View Story"** to see the AI-generated narrative:

```
┌────────────────────────────────────────────────────────────┐
│  📖 Gameplay Story                                          │
├────────────────────────────────────────────────────────────┤
│  [00:00 - 02:30]                                           │
│  The match begins with the player selecting Jett as their │
│  agent. Initial round shows careful positioning and team  │
│  coordination. The player secures two early kills with    │
│  precise headshots.                                        │
│                                                             │
│  [02:30 - 05:45]                                           │
│  Intense battle at B site. The player executes a perfect  │
│  smoke and dash combo, catching enemies off guard. Three  │
│  consecutive eliminations lead to site capture.           │
│                                                             │
│  [05:45 - 08:20]                                           │
│  Critical clutch moment: 1v5 situation. Player uses map   │
│  knowledge and timing to isolate duels. Final headshot    │
│  wins the round, triggering team celebration.             │
│                                                             │
│  ... (continues for full video) ...                        │
└────────────────────────────────────────────────────────────┘
```

**💡 Use this story to**:
- Understand what AI detected
- Find specific moments by timestamp
- Create longer video descriptions

---

### **5.2 Browse Generated Shorts**

You'll see a **grid of short videos**, sorted by **virality score** (highest first):

```
┌────────────┐ ┌────────────┐ ┌────────────┐
│ 🔥 10/10   │ │ ⭐ 9/10    │ │ 💪 8/10    │
│            │ │            │ │            │
│ [THUMB]    │ │ [THUMB]    │ │ [THUMB]    │
│            │ │            │ │            │
│ WINNING    │ │ SATISFYING │ │ INTENSE    │
│ 45s        │ │ 38s        │ │ 52s        │
│            │ │            │ │            │
│ Insane     │ │ Perfect    │ │ Epic       │
│ Clutch! 🎯 │ │ Build! 🏗️  │ │ Battle! ⚔️ │
└────────────┘ └────────────┘ └────────────┘
```

Each card shows:
- **Virality Score**: 1-10 (10 = most viral potential)
- **Thumbnail**: Preview image
- **Category**: WINNING / LOSING / SATISFYING / INTENSE / FUNNY
- **Duration**: Length of the short
- **Title**: AI-generated catchy title

---

### **5.3 Preview a Short** (Hover)

**Hover your mouse** over any short card:

```
┌────────────┐
│ ▶️ PLAYING │  ← Video plays automatically
│            │
│ [VIDEO]    │
│            │
│ WINNING    │
│ 45s        │
└────────────┘
```

**What happens**:
- Video plays automatically
- Shows you the content
- Pauses when you move mouse away

**💡 Use this to**: Quickly scan all shorts without opening each one

---

### **5.4 View Short Details** (Click)

**Click on any short card** to see full details:

```
┌─────────────────────────────────────────────────────────┐
│  Short #1 - WINNING Moment                     [✕ Close]│
├─────────────────────────────────────────────────────────┤
│  ┌────────────────┐  Title:                            │
│  │                │  🔥 INSANE 1v5 Clutch in Valorant! │
│  │   [VIDEO]      │                                     │
│  │   9:16 ratio   │  Description:                       │
│  │   Plays here   │  Watch this incredible comeback    │
│  │                │  that had everyone speechless. The  │
│  │                │  final headshot was pure perfection!│
│  └────────────────┘                                     │
│                     Tags:                               │
│  Details:          #valorant #clutch #gaming #shorts    │
│  • Duration: 45s   #viral #fps #esports #1v5 #ace      │
│  • Category: WIN   #gameplay #headshot #insane          │
│  • Virality: 10/10                                      │
│  • Start: 05:45    [📋 Copy Title]                      │
│  • End: 06:30      [📋 Copy Description]                │
│                     [📋 Copy Tags]                       │
│  [⬇️ Download]     [🎬 Download All]                    │
└─────────────────────────────────────────────────────────┘
```

**What you can do**:
- ✅ **Watch the video** in high quality
- ✅ **Copy metadata** (title, description, tags) with one click
- ✅ **Download individual short** (MP4, 1080x1920, 30fps)
- ✅ **See exact timestamps** from original video

---

## 📥 **Step 6: Download Your Shorts**

### **Option A: Download Individual Short**

1. Open short details (click card)
2. Click **"Download"** button
3. Save the MP4 file

**File details**:
- Format: MP4
- Resolution: 1080x1920 (9:16 vertical)
- Frame rate: 30 FPS
- Audio: Included
- Size: ~20-50 MB per short

---

### **Option B: Download All Shorts**

1. Click **"Download All Shorts"** button
2. ZIP file downloads with all shorts
3. Extract the ZIP file

**Folder structure**:
```
gameplay-shorts-2024-03-29/
├── short_001_winning.mp4
├── short_002_satisfying.mp4
├── short_003_intense.mp4
├── ... (all shorts)
└── metadata.json (all titles/descriptions/tags)
```

---

## 📤 **Step 7: Upload to Social Media**

### **For YouTube Shorts**:

1. Open YouTube Studio
2. Click **"Create"** → **"Upload videos"**
3. Select your short video (MP4)
4. **Copy & paste** the AI-generated:
   - Title → YouTube title field
   - Description → YouTube description
   - Tags → YouTube tags field
5. **Important**: Select aspect ratio as **"Vertical"**
6. Publish!

---

### **For Instagram Reels**:

1. Open Instagram app
2. Tap **"+"** → **"Reel"**
3. Select your short video
4. **Copy & paste** the AI-generated:
   - First line of description as caption
   - Tags as hashtags
5. Post!

---

### **For TikTok**:

1. Open TikTok app
2. Tap **"+"**
3. Upload video
4. **Copy & paste** description and tags
5. Post!

---

## 🎯 **Complete Workflow Example**

**Let's say you have a 2-hour Valorant gameplay**:

### **Time Investment**:
1. Upload: 3 min
2. Set FPS to 2: 10 seconds
3. Click "Generate": 10 seconds
4. **Wait for AI** (total): ~35-40 minutes
   - Frame extraction: 2 min
   - AI analysis: 15 min (on Apple M1)
   - Story generation: 5 min
   - Moment detection: 3 min
   - Short generation: 10 min
   - Metadata: 2 min
5. Review & download: 5 min

**Total**: ~45 minutes (most of it automated!)

### **What You Get**:
- 📖 Full gameplay story with timestamps
- 🎬 10-20 ready-to-post vertical shorts (9:16)
- ✍️ Titles, descriptions, and tags for each short
- 🏆 Sorted by virality potential

### **What You'd Do Manually** (without AI):
- Watch entire 2-hour video: 2 hours
- Take notes on moments: 30 min
- Edit 10-20 shorts: 3-4 hours
- Create thumbnails: 1 hour
- Write titles/descriptions: 1 hour

**Time saved**: ~6-7 hours! 🚀

---

## 💡 **Pro Tips**

### **Tip 1: Start with a Short Test Video**
- Use a 5-10 minute clip for your first test
- Verify everything works
- Then try longer videos

### **Tip 2: FPS Selection**
- Testing/short videos: Use 3-4 FPS
- 1-2 hour videos: Use 2 FPS
- Very long videos (3+ hours): Use 1 FPS

### **Tip 3: Best Moments are Ranked**
- Shorts are sorted by virality score
- Top shorts = highest viral potential
- Start uploading from the top!

### **Tip 4: Customize Metadata**
- AI-generated text is a great starting point
- Feel free to edit titles/descriptions
- Add your personal touch!

### **Tip 5: Batch Processing**
- Process multiple gameplay sessions
- Build a library of shorts
- Schedule uploads over time

### **Tip 6: Hook-First Structure**
- First 7 seconds show the climax
- This grabs viewer attention immediately
- Perfect for social media algorithms!

### **Tip 7: Use Previous Uploads**
- Re-process videos with different FPS
- Try different settings
- No need to re-upload!

---

## ❓ **Common Questions**

### **Q: How long does processing take?**

**A**: Depends on hardware and video length:

| Hardware | 2-hour video | 30-min video |
|----------|--------------|--------------|
| Apple M1/M2 | ~35-40 min | ~10-12 min |
| NVIDIA RTX 3060 | ~30-35 min | ~8-10 min |
| CPU only | ~70-90 min | ~20-25 min |

### **Q: Can I process while it's running?**
**A**: Yes, but it will slow down. Best to let it run uninterrupted.

### **Q: What if I close the browser?**
**A**: Processing continues! Refresh the page to see progress.

### **Q: Can I process multiple videos at once?**
**A**: Not recommended. Process one at a time for best performance.

### **Q: What if no moments are detected?**
**A**: Try:
- Lower FPS (more frames analyzed)
- Different game (some games work better)
- Check if gameplay has varied action

### **Q: Can I customize the AI prompts?**
**A**: Yes! Edit the service files (`services/*.py`) to change prompts.

### **Q: How do I delete old videos?**
**A**: Manually delete files from `uploads/` folder.

### **Q: Can I export to different resolutions?**
**A**: Currently 1080x1920 only. Edit `services/short_generator.py` to change.

---

## 🐛 **Troubleshooting**

### **Problem**: "No moments detected"
**Solution**:
- Use lower FPS (more frames = better detection)
- Ensure video has action/variety
- Check AI logs in terminal

### **Problem**: Processing stuck at "Analyzing frames"
**Solution**:
- This is normal - it's the slowest part
- On CPU, can take 30-45 minutes
- Check terminal for progress logs

### **Problem**: "Out of memory"
**Solution**:
- Use 1 FPS instead of 2-3
- Close other applications
- Process shorter video segments

### **Problem**: Videos play but shorts aren't generated
**Solution**:
- Check terminal for error messages
- Verify MoviePy is installed: `pip install moviepy`
- Check disk space (need ~2x video size)

---

## 📞 **Need Help?**

1. Check terminal/console for error messages
2. Read `TROUBLESHOOTING.md` (if available)
3. Check `AUDIT_REPORT.md` for system verification
4. Run `python verify_setup.py` to check installation

---

**Enjoy creating viral gaming content with AI!** 🎮🤖✨
