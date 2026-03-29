# Changelog

## 2026-03-29 - Previous Uploads Feature

### Added ✅

**Feature**: Show previously uploaded videos to avoid re-uploading

#### Backend (app.py)
- **New Endpoint**: `/uploads/list`
  - Lists all videos in `uploads/` folder
  - Returns file metadata (size, duration, resolution, modified date)
  - Sorted by most recent first
  - Auto-detects video metadata using MoviePy

#### Frontend (templates/index.html)
- **New Section**: "Previously Uploaded Videos"
  - Displays below the upload area
  - Shows only when files exist
  - Clean, card-based layout with file details

#### JavaScript (static/js/script.js)
- **New Functions**:
  - `loadPreviousUploads()` - Fetches file list on page load
  - `displayPreviousFiles(files)` - Renders file list
  - `createFileListItem(file)` - Creates individual file card
  - `selectPreviousFile(file)` - Loads selected file into editor

#### Styling (static/css/style.css)
- **New Styles**:
  - `.hover-highlight` - Smooth hover effect
  - File list item styling with rounded corners
  - Slide animation on hover

### How It Works

1. **On Page Load**:
   - JavaScript calls `/uploads/list` endpoint
   - Server scans `uploads/` directory
   - Returns array of video files with metadata

2. **Display**:
   - Files shown in a list below upload area
   - Each file shows:
     - Filename
     - Duration (HH:MM:SS)
     - Resolution (WxH)
     - File size (MB)
     - Upload date & time
     - "Click to use" badge

3. **Selection**:
   - User clicks on a file
   - File loads directly into editor (no re-upload)
   - Video player shows the selected file
   - Ready for processing or AI shorts generation

### User Benefits

- ✅ **No Re-uploads**: Select previously uploaded videos instantly
- ✅ **Fast Loading**: Skips upload step entirely
- ✅ **Bandwidth Saving**: No need to transfer large files again
- ✅ **Time Saving**: Immediate access to past uploads
- ✅ **Clear Overview**: See all uploaded videos at a glance

### Example

```
┌─────────────────────────────────────────────────────────┐
│  Previously Uploaded Videos                             │
│  Select a video to avoid re-uploading                   │
├─────────────────────────────────────────────────────────┤
│  🎮 gameplay_valorant_2024.mp4        📅 Mar 29, 12:34 │
│     ⏱ 02:15:30  📐 1920x1080  💾 850 MB  [Click to use] │
├─────────────────────────────────────────────────────────┤
│  🎮 fortnite_highlights.mp4           📅 Mar 28, 18:20 │
│     ⏱ 01:45:12  📐 1920x1080  💾 720 MB  [Click to use] │
└─────────────────────────────────────────────────────────┘
```

### Technical Details

**Backend Logic**:
```python
# Scans uploads/ folder
# For each video file:
#   - Get file size
#   - Get modified timestamp
#   - Extract video metadata (duration, resolution, fps)
#   - Return as JSON array
```

**Frontend Logic**:
```javascript
// On page load:
fetch('/uploads/list')
  → Get file list
  → Display if files exist
  → User clicks file
  → Load into editor (skip upload)
```

### Files Modified

1. `app.py` - Added `/uploads/list` endpoint
2. `templates/index.html` - Added previous files section
3. `static/js/script.js` - Added file listing functionality
4. `static/css/style.css` - Added styling

### Compatibility

- ✅ Windows - Works
- ✅ macOS - Works
- ✅ Linux - Works
- ✅ All browsers with JavaScript enabled

---

## Previous Updates

### 2026-03-29 - Initial Implementation

- ✅ AI-powered frame extraction
- ✅ BLIP image captioning
- ✅ TinyLlama story generation
- ✅ Moment detection (wins/losses/satisfying/intense/funny)
- ✅ 9:16 vertical shorts generation
- ✅ Hook-first video structure
- ✅ Metadata generation (titles/descriptions/tags)
- ✅ Cross-platform support
- ✅ Offline mode with model caching
- ✅ Model download script
- ✅ System verification script
- ✅ Comprehensive documentation

---

*Last Updated: 2026-03-29*
