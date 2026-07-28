from flask import Flask, render_template, request, jsonify, send_file, url_for, send_from_directory
import os
import uuid
import threading
import json
import logging
import shutil
from werkzeug.utils import secure_filename
from moviepy.editor import VideoFileClip
import moviepy.video.fx.all as vfx
import proglog
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['PROCESSED_FOLDER'] = os.path.join(BASE_DIR, 'processed')
app.config['FRAMES_FOLDER'] = os.path.join(BASE_DIR, 'frames')
app.config['SHORTS_FOLDER'] = os.path.join(BASE_DIR, 'shorts')
app.config['STORIES_FOLDER'] = os.path.join(BASE_DIR, 'stories')
app.config['STATE_FOLDER'] = os.path.join(BASE_DIR, 'state')
app.config['JOBS_FOLDER'] = os.path.join(BASE_DIR, 'jobs')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2 GB limit for large gameplay videos

# Create all directories
for folder in ['UPLOAD_FOLDER', 'PROCESSED_FOLDER', 'FRAMES_FOLDER',
               'SHORTS_FOLDER', 'STORIES_FOLDER', 'STATE_FOLDER', 'JOBS_FOLDER']:
    os.makedirs(app.config[folder], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

# Initialize State Manager (used by the legacy manual editor) and the Job Queue
# (used by the agent-in-the-loop AI shorts pipeline — no local ML models).
from services.state_manager import init_state_manager, get_state_manager
from services.job_queue import (
    init_job_queue, get_job_queue,
    STATUS_AWAITING_AGENT, STATUS_COMPLETED, STATUS_ERROR,
)
state_manager = init_state_manager(app.config['STATE_FOLDER'])
job_queue = init_job_queue(app.config['JOBS_FOLDER'])

# Source-video metadata store (agent-in-the-loop metadata for full gameplays).
from services.source_store import init_source_store, get_source_store
source_store = init_source_store(os.path.join(app.config['STATE_FOLDER'], 'sources'))

# Legacy task dictionary (for backward compatibility with existing code)
# Will be gradually migrated to state_manager
tasks = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _compute_video_id(filepath, fps):
    """
    Derive a stable identifier for a (video, fps) pair so extracted frames and
    contact sheets are cached and reused across jobs for the same source.
    """
    import hashlib
    h = hashlib.sha256()
    h.update(str(os.path.getsize(filepath)).encode())
    h.update(f"{fps:.1f}".encode())
    with open(filepath, 'rb') as f:
        h.update(f.read(1024 * 1024))   # first 1 MB fingerprint
    return h.hexdigest()[:20]           # 20 hex chars — collision-proof in practice


class CustomProgressBar(proglog.ProgressBarLogger):
    def __init__(self, task_id):
        super().__init__()
        self.task_id = task_id

    def callback(self, **changes):
        for (parameter, new_value) in changes.items():
            if parameter == 't':
                tasks[self.task_id]['current_t'] = new_value

    def bars_callback(self, bar, attr, value, old_value=None):
        if bar == 't':
            if attr == 'total':
                tasks[self.task_id]['total'] = value
            elif attr == 'index':
                tasks[self.task_id]['progress'] = value
                total = tasks[self.task_id].get('total', 0)
                if total > 0:
                    tasks[self.task_id]['percentage'] = int((value / total) * 100)


# ============================================================
# ROUTES - Pages
# ============================================================

@app.route('/')
def index():
    return render_template('index.html', video_input_path="")


@app.route('/gallery')
def gallery():
    """Standalone results gallery of every generated short across all jobs."""
    return render_template('gallery.html')


@app.route('/gallery/data')
def gallery_data():
    """
    Aggregate every completed job's shorts into a flat, gallery-friendly list:
    thumbnail, title, description, comma-separated hashtags, video + metadata URLs.
    Grouped by source video, sorted by virality within each group.
    """
    jq = get_job_queue()
    videos = []
    total_shorts = 0
    for job in jq.list_jobs(statuses=[STATUS_COMPLETED]):
        result = job.get('result', {})
        shorts = []
        for s in result.get('shorts', []):
            if not s.get('output_path'):
                continue
            moment = s.get('moment', {})
            meta = s.get('metadata', {})
            tags = meta.get('tags', [])
            tags_csv = meta.get('tags_csv') or ', '.join(
                (t if str(t).startswith('#') else '#' + str(t)) for t in tags
            )
            shorts.append({
                'index': s.get('index', 0),
                'job_id': job.get('job_id'),
                'title': meta.get('title', 'Untitled'),
                'description': meta.get('description', ''),
                'tags': tags,
                'tags_csv': tags_csv,
                'hook_text': meta.get('hook_text', ''),
                'category': moment.get('category', 'INTENSE'),
                'virality_score': moment.get('virality_score', 5),
                'duration': s.get('duration', 0),
                'fps': s.get('fps'),
                'video_url': s.get('web_video_path', ''),
                'thumbnail_url': s.get('web_thumbnail_path', ''),
                'metadata_url': s.get('web_metadata_path', ''),
                'youtube': s.get('youtube'),  # {video_id, url, privacy, uploaded_at} or None
            })
        if not shorts:
            continue
        shorts.sort(key=lambda x: x['virality_score'], reverse=True)
        total_shorts += len(shorts)
        videos.append({
            'job_id': job.get('job_id'),
            'filename': job.get('filename', ''),
            'game': result.get('game', ''),
            'summary': result.get('summary', ''),
            'short_count': len(shorts),
            'created_at': job.get('created_at', ''),
            'shorts': shorts,
        })

    videos.sort(key=lambda v: v.get('created_at', ''), reverse=True)
    return jsonify({
        'video_count': len(videos),
        'short_count': total_shorts,
        'videos': videos,
    })


# ============================================================
# ROUTES - YouTube upload
# ============================================================

@app.route('/youtube/status', methods=['GET'])
def youtube_status():
    """Report the YouTube integration state (deps/config/connection)."""
    from services import youtube_uploader
    return jsonify(youtube_uploader.status())


@app.route('/youtube/connect', methods=['POST'])
def youtube_connect():
    """
    Run the Google sign-in (OAuth) flow. Blocking; opens a browser on the server
    host (localhost). Stores the token securely (never returned to the client).
    """
    from services import youtube_uploader
    try:
        st = youtube_uploader.connect(open_browser=True)
        return jsonify({'status': 'success', 'youtube': st})
    except Exception as e:
        logger.error("YouTube connect failed: %s", e)
        return jsonify({'error': str(e)}), 400


@app.route('/youtube/disconnect', methods=['POST'])
def youtube_disconnect():
    from services import youtube_uploader
    try:
        youtube_uploader.disconnect()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/youtube/upload', methods=['POST'])
def youtube_upload():
    """
    Upload one generated short to YouTube. Body: {job_id, index, privacy?}.
    Idempotent: if the short was already uploaded, returns the existing link
    instead of uploading again.
    """
    from services import youtube_uploader
    data = request.json or {}
    job_id = data.get('job_id')
    index = data.get('index')
    privacy = data.get('privacy', youtube_uploader.DEFAULT_PRIVACY)
    if job_id is None or index is None:
        return jsonify({'error': 'job_id and index are required'}), 400
    try:
        index = int(index)
    except (ValueError, TypeError):
        return jsonify({'error': 'index must be an integer'}), 400

    jq = get_job_queue()

    # Duplicate guard — never upload the same short twice.
    existing = jq.get_short_youtube(job_id, index)
    if existing and existing.get('video_id'):
        return jsonify({'status': 'already_uploaded', 'youtube': existing})

    job = jq.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    short = next((s for s in job.get('result', {}).get('shorts', [])
                  if s.get('index') == index), None)
    if not short or not short.get('output_path'):
        return jsonify({'error': 'Short not found'}), 404

    meta = short.get('metadata', {})
    try:
        yt = youtube_uploader.upload(
            video_path=short['output_path'],
            title=meta.get('title', 'Gameplay Short'),
            description=meta.get('description', ''),
            tags=meta.get('tags', []),
            privacy=privacy,
            thumbnail_path=short.get('thumbnail_path'),
        )
    except youtube_uploader.QuotaExceededError as e:
        logger.warning("YouTube quota reached on %s#%s: %s", job_id, index, e)
        return jsonify({'error': str(e), 'reason': 'quota'}), 429
    except Exception as e:
        logger.error("YouTube upload failed for %s#%s: %s", job_id, index, e)
        return jsonify({'error': str(e)}), 400

    jq.set_short_youtube(job_id, index, yt)
    return jsonify({'status': 'success', 'youtube': yt})


@app.route('/youtube/archive', methods=['GET'])
def youtube_archive():
    """
    List every short that has been uploaded to YouTube (for the Archive tab),
    newest upload first, with a YouTube-style thumbnail + local fallback.
    """
    jq = get_job_queue()
    items = []
    for job in jq.list_jobs(statuses=[STATUS_COMPLETED]):
        result = job.get('result', {})
        for s in result.get('shorts', []):
            yt = s.get('youtube')
            if not yt or not yt.get('video_id'):
                continue
            meta = s.get('metadata', {})
            vid = yt['video_id']
            items.append({
                'job_id': job.get('job_id'),
                'index': s.get('index', 0),
                'game': result.get('game', ''),
                'title': meta.get('title', 'Untitled'),
                'description': meta.get('description', ''),
                'tags_csv': meta.get('tags_csv', ''),
                'category': s.get('moment', {}).get('category', 'INTENSE'),
                'duration': s.get('duration', 0),
                'video_url': s.get('web_video_path', ''),
                'local_thumbnail': s.get('web_thumbnail_path', ''),
                'youtube_url': yt.get('url', f'https://www.youtube.com/watch?v={vid}'),
                'youtube_thumbnail': f'https://img.youtube.com/vi/{vid}/hqdefault.jpg',
                'video_id': vid,
                'privacy': yt.get('privacy', ''),
                'uploaded_at': yt.get('uploaded_at', ''),
            })
    items.sort(key=lambda x: x.get('uploaded_at', ''), reverse=True)
    return jsonify({'count': len(items), 'items': items})


# ============================================================
# ROUTES - Source Gameplays (full-video AI metadata + direct upload)
# ============================================================

def _source_video_id(filepath):
    """Stable id for a source video (independent of fps) for its frames dir."""
    import hashlib
    h = hashlib.sha256()
    try:
        h.update(str(os.path.getsize(filepath)).encode())
        with open(filepath, 'rb') as f:
            h.update(f.read(1024 * 1024))
    except OSError:
        h.update(filepath.encode())
    return 'src_' + h.hexdigest()[:18]


def _source_meta_task(filename):
    """Background: extract frames + contact sheets for a source, then await agent."""
    with app.app_context():
        ss = get_source_store()
        try:
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if not os.path.exists(input_path):
                ss.mark_error(filename, 'Source video not found')
                return
            video_id = _source_video_id(input_path)
            frames_dir = os.path.join(app.config['FRAMES_FOLDER'], video_id)
            os.makedirs(frames_dir, exist_ok=True)
            ss.update(filename, status='pending_frames', percentage=5, video_id=video_id,
                      frames_dir=frames_dir, step_message='Extracting frames for analysis…')

            manifest_path = os.path.join(frames_dir, 'manifest.json')
            if os.path.exists(manifest_path):
                with open(manifest_path) as f:
                    manifest = json.load(f)
            else:
                from services.frame_extractor import extract_frames
                # Low fps sized to ~120 frames total — enough to understand the whole
                # video without extracting thousands of frames.
                dur = 0
                meta = _get_video_metadata_fast(input_path)
                if meta:
                    dur = meta.get('duration', 0) or 0
                fps = 1.0
                if dur > 0:
                    fps = max(0.2, min(1.0, 120.0 / dur))

                def prog(cur, total, msg):
                    pct = 5 + int((cur / total) * 30) if total else 5
                    ss.update(filename, percentage=pct, step_message=msg)

                manifest = extract_frames(input_path, frames_dir, fps=fps, progress_callback=prog)

            sheets_index = os.path.join(frames_dir, 'sheets', 'index.json')
            if not os.path.exists(sheets_index):
                from services.contact_sheet import build_contact_sheets
                ss.update(filename, percentage=38, step_message='Building contact sheets for the AI agent…')
                build_contact_sheets(frames_dir, manifest_path=manifest_path)

            ss.mark_awaiting_agent(filename, frames_dir, manifest)
            logger.info("Source %s awaiting agent metadata (%d frames)", filename, manifest.get('frame_count', 0))
        except Exception as e:
            logger.error("Source metadata task failed for %s: %s", filename, e, exc_info=True)
            ss.mark_error(filename, str(e))


@app.route('/sources/data')
def sources_data():
    """List uploaded source gameplays with AI metadata + shorts/upload status."""
    ss = get_source_store()
    jq = get_job_queue()
    upload_folder = app.config['UPLOAD_FOLDER']

    # filename -> latest shorts job (to show 'has shorts' / status)
    shorts_by_file = {}
    for job in jq.list_jobs():
        fn = job.get('filename')
        if fn:
            ex = shorts_by_file.get(fn)
            if not ex or job.get('created_at', '') > ex.get('created_at', ''):
                shorts_by_file[fn] = job

    items = []
    if os.path.exists(upload_folder):
        for filename in os.listdir(upload_folder):
            fp = os.path.join(upload_folder, filename)
            if not os.path.isfile(fp) or not allowed_file(filename):
                continue
            meta_info = _get_video_metadata_fast(fp) or {}
            rec = ss.get(filename) or {}
            sj = shorts_by_file.get(filename)
            items.append({
                'filename': filename,
                'size_mb': round(os.path.getsize(fp) / (1024 * 1024), 1),
                'modified': os.path.getmtime(fp),
                'duration': meta_info.get('duration'),
                'resolution': meta_info.get('resolution'),
                'fps': meta_info.get('fps'),
                'thumbnail_url': url_for('source_thumb', filename=filename),
                'video_url': url_for('serve_upload', filename=filename),
                'meta_status': rec.get('status', 'idle'),
                'meta_percentage': rec.get('percentage', 0),
                'meta_message': rec.get('step_message', ''),
                'meta': rec.get('meta'),
                'youtube': rec.get('youtube'),
                'shorts_job_id': sj.get('job_id') if sj else None,
                'shorts_status': sj.get('status') if sj else None,
            })
    items.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify({'count': len(items), 'items': items})


@app.route('/sources/thumb/<path:filename>')
def source_thumb(filename):
    """Serve (and cache) a mid-frame thumbnail for a source gameplay video."""
    import cv2
    safe = secure_filename(filename)
    src = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(src):
        return jsonify({'error': 'not found'}), 404
    thumb_dir = os.path.join(app.config['FRAMES_FOLDER'], '_source_thumbs')
    os.makedirs(thumb_dir, exist_ok=True)
    thumb = os.path.join(thumb_dir, safe + '.jpg')
    if not os.path.exists(thumb):
        try:
            cap = cv2.VideoCapture(src)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frames * 0.5))  # mid-video frame
            ok, frame = cap.read()
            cap.release()
            if ok:
                h, w = frame.shape[:2]
                scale = 480.0 / max(w, 1)
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
                cv2.imwrite(thumb, frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        except Exception as e:
            logger.debug("source thumb failed for %s: %s", filename, e)
    if os.path.exists(thumb):
        return send_file(thumb)
    return jsonify({'error': 'thumb unavailable'}), 404


@app.route('/sources/analyze', methods=['POST'])
def sources_analyze():
    """Trigger agent-in-the-loop metadata generation for a full source gameplay."""
    data = request.json or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({'error': 'filename required'}), 400
    if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        return jsonify({'error': 'source not found'}), 404
    ss = get_source_store()
    rec = ss.get(filename)
    if rec and rec.get('status') in ('pending_frames', 'awaiting_agent'):
        return jsonify({'status': 'already_running', 'source': rec})
    ss.update(filename, status='pending_frames', percentage=1,
              step_message='Queued for analysis…', error=None)
    threading.Thread(target=_source_meta_task, args=(filename,), daemon=True).start()
    return jsonify({'status': 'success', 'filename': filename})


@app.route('/sources/analyze-all', methods=['POST'])
def sources_analyze_all():
    """
    Kick off metadata analysis for every source gameplay that doesn't already have
    metadata (and isn't already running). Extraction runs in background threads;
    each ends parked as 'awaiting_agent' for the Copilot agent to pick up.
    """
    ss = get_source_store()
    upload_folder = app.config['UPLOAD_FOLDER']
    started, skipped = [], []
    if os.path.exists(upload_folder):
        for filename in sorted(os.listdir(upload_folder)):
            fp = os.path.join(upload_folder, filename)
            if not os.path.isfile(fp) or not allowed_file(filename):
                continue
            rec = ss.get(filename)
            status = rec.get('status') if rec else 'idle'
            has_meta = bool(rec and rec.get('meta'))
            if has_meta or status in ('pending_frames', 'awaiting_agent'):
                skipped.append(filename)
                continue
            ss.update(filename, status='pending_frames', percentage=1,
                      step_message='Queued for analysis…', error=None)
            threading.Thread(target=_source_meta_task, args=(filename,), daemon=True).start()
            started.append(filename)
    return jsonify({'status': 'success', 'started': started,
                    'started_count': len(started), 'skipped_count': len(skipped)})


@app.route('/sources/agent-status', methods=['GET'])
def sources_agent_status():
    """
    Summarize how many source gameplays are waiting for the AI agent vs. being
    extracted vs. done — so the gallery can show a clear 'agent needs to act' banner.
    """
    ss = get_source_store()
    recs = ss.all()
    awaiting = [r['filename'] for r in recs if r.get('status') == 'awaiting_agent']
    extracting = [r['filename'] for r in recs if r.get('status') == 'pending_frames']
    completed = sum(1 for r in recs if r.get('status') == 'completed')
    return jsonify({
        'awaiting_agent': awaiting,
        'awaiting_count': len(awaiting),
        'extracting_count': len(extracting),
        'completed_count': completed,
    })
    if not filename:
        return jsonify({'error': 'filename required'}), 400
    ss = get_source_store()
    if not ss.get(filename):
        return jsonify({'error': 'source metadata job not found'}), 404
    try:
        meta = ss.save_meta(filename, data)
    except Exception as e:
        return jsonify({'error': f'invalid metadata: {e}'}), 400
    return jsonify({'status': 'success', 'meta': meta})


@app.route('/sources/upload-youtube', methods=['POST'])
def sources_upload_youtube():
    """Upload the FULL source gameplay to YouTube using its AI metadata."""
    from services import youtube_uploader
    data = request.json or {}
    filename = data.get('filename')
    privacy = data.get('privacy', youtube_uploader.DEFAULT_PRIVACY)
    if not filename:
        return jsonify({'error': 'filename required'}), 400
    ss = get_source_store()
    rec = ss.get(filename)
    if not rec or not rec.get('meta'):
        return jsonify({'error': 'Generate AI metadata for this gameplay first.'}), 400
    if rec.get('youtube') and rec['youtube'].get('video_id'):
        return jsonify({'status': 'already_uploaded', 'youtube': rec['youtube']})

    src = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(src):
        return jsonify({'error': 'source not found'}), 404
    thumb = os.path.join(app.config['FRAMES_FOLDER'], '_source_thumbs', secure_filename(filename) + '.jpg')
    meta = rec['meta']
    try:
        yt = youtube_uploader.upload(
            video_path=src,
            title=meta.get('title', filename),
            description=meta.get('description', ''),
            tags=meta.get('tags', []),
            privacy=privacy,
            thumbnail_path=thumb if os.path.exists(thumb) else None,
        )
    except youtube_uploader.QuotaExceededError as e:
        return jsonify({'error': str(e), 'reason': 'quota'}), 429
    except Exception as e:
        logger.error("Source YouTube upload failed for %s: %s", filename, e)
        return jsonify({'error': str(e)}), 400
    ss.set_youtube(filename, yt)
    return jsonify({'status': 'success', 'youtube': yt})


# ============================================================
# ROUTES - File Serving
# ============================================================

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))


def _get_video_metadata_fast(filepath):
    """
    Extract video metadata quickly. Prefer ffprobe (fast); if it's not available
    (common on Windows without a full FFmpeg install), fall back to OpenCV, which
    is always installed. Returns None only if both fail.
    """
    import subprocess
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams', '-show_format',
                filepath
            ],
            capture_output=True, text=True, timeout=8
        )
        info = json.loads(result.stdout)
        duration = float(info.get('format', {}).get('duration', 0))
        video_stream = next(
            (s for s in info.get('streams', []) if s.get('codec_type') == 'video'),
            None
        )
        if video_stream:
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            fps_str = video_stream.get('r_frame_rate', '30/1')
            num, den = fps_str.split('/') if '/' in fps_str else (fps_str, '1')
            fps = round(float(num) / float(den), 2)
            return {'duration': duration, 'resolution': [width, height], 'fps': fps}
    except Exception as e:
        logger.debug(f"ffprobe metadata failed for {filepath}: {e}")

    # Fallback: OpenCV (no external binary needed) — works everywhere.
    try:
        import cv2
        cap = cv2.VideoCapture(filepath)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            cap.release()
            duration = round(frames / fps, 2) if fps else 0
            return {'duration': duration, 'resolution': [width, height], 'fps': round(fps, 2)}
    except Exception as e:
        logger.debug(f"OpenCV metadata failed for {filepath}: {e}")
    return None


@app.route('/uploads/list')
def list_uploads():
    """List all previously uploaded videos with their latest task state."""
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            return jsonify({'files': []})

        # Build filename → most-recent job map from the job queue
        jq = get_job_queue()
        all_jobs = jq.list_jobs()
        filename_task_map = {}
        for job in all_jobs:
            fname = job.get('filename')
            if fname:
                existing = filename_task_map.get(fname)
                if not existing or job.get('created_at', '') > existing.get('created_at', ''):
                    filename_task_map[fname] = job

        files = []
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            if not os.path.isfile(filepath) or not allowed_file(filename):
                continue

            stat = os.stat(filepath)
            size_mb = stat.st_size / (1024 * 1024)
            modified = stat.st_mtime

            # Fast metadata via ffprobe — no video decoding required
            metadata = _get_video_metadata_fast(filepath)

            task_info = filename_task_map.get(filename)
            files.append({
                'filename': filename,
                'size_mb': round(size_mb, 2),
                'modified': modified,
                'metadata': metadata,
                'url': url_for('serve_upload', filename=filename),
                'task_id': task_info.get('job_id') if task_info else None,
                'task_status': task_info.get('status') if task_info else None,
                'task_percentage': task_info.get('percentage', 0) if task_info else 0,
            })

        files.sort(key=lambda x: x['modified'], reverse=True)
        return jsonify({'files': files, 'total': len(files)})
    except Exception as e:
        logger.error(f"Error listing uploads: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/processed/<filename>')
def serve_processed(filename):
    return send_file(os.path.join(app.config['PROCESSED_FOLDER'], filename))


@app.route('/shorts/<path:filepath>')
def serve_short(filepath):
    """Serve generated short videos and thumbnails."""
    full_path = os.path.join(app.config['SHORTS_FOLDER'], filepath)
    if os.path.exists(full_path):
        return send_file(full_path)
    return jsonify({'error': 'File not found'}), 404


@app.route('/frames/<path:filepath>')
def serve_frame(filepath):
    """Serve extracted frames."""
    full_path = os.path.join(app.config['FRAMES_FOLDER'], filepath)
    if os.path.exists(full_path):
        return send_file(full_path)
    return jsonify({'error': 'File not found'}), 404


# ============================================================
# ROUTES - Upload
# ============================================================

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file part'}), 400
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)

        try:
            clip = VideoFileClip(filepath)
            metadata = {
                'duration': clip.duration,
                'resolution': clip.size,
                'fps': clip.fps,
                'format': filename.rsplit('.', 1)[1].lower()
            }
            clip.close()
            video_input_path = url_for('serve_upload', filename=unique_filename)
            return jsonify({
                'filepath': unique_filename,
                'video_input_path': video_input_path,
                'metadata': metadata,
                'status': 'success'
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Invalid file type'}), 400


# ============================================================
# ROUTES - Basic Video Processing (existing feature)
# ============================================================

def cleanup_files(input_filename):
    time.sleep(3600)
    try:
        ipath = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        if os.path.exists(ipath):
            os.remove(ipath)
    except:
        pass


def process_video_task(task_id, input_filename, operations):
    with app.app_context():
        try:
            tasks[task_id]['status'] = 'processing'
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
            output_filename = f"processed_{task_id}.mp4"
            output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)

            clip = VideoFileClip(input_path)

            if 'clip' in operations:
                start_time = float(operations['clip'].get('start', 0))
                end_time = float(operations['clip'].get('end', clip.duration))
                end_time = min(end_time, clip.duration)
                clip = clip.subclip(start_time, end_time)

            if operations.get('speed_up', False):
                speed_factor = float(operations.get('speed_factor', 2.0))
                clip = clip.fx(vfx.speedx, speed_factor)

            logger_bar = CustomProgressBar(task_id)
            clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                logger=logger_bar,
                preset='ultrafast'
            )
            clip.close()

            threading.Thread(target=cleanup_files, args=(input_filename,), daemon=True).start()

            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['percentage'] = 100
            tasks[task_id]['result_path'] = f"/processed/{output_filename}"
            tasks[task_id]['result_filename'] = output_filename
        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)


@app.route('/process', methods=['POST'])
def process_video():
    data = request.json
    filename = data.get('filename')
    operations = data.get('operations', {})

    if not filename:
        return jsonify({'error': 'Filename is required'}), 400

    task_id = uuid.uuid4().hex
    tasks[task_id] = {
        'status': 'queued',
        'percentage': 0
    }

    thread = threading.Thread(target=process_video_task, args=(task_id, filename, operations))
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'success'})


# ============================================================
# ROUTES - AI Shorts (agent-in-the-loop, no local ML models)
# ============================================================
#
# Flow:
#   1. /ai/start  -> create a job, extract frames, build contact sheets,
#                    then park the job as 'awaiting_agent'.
#   2. The AGENT (Copilot, via the shorts-generator skill) reads the frames /
#      contact sheets, decides the epic hook-worthy moments, and writes a plan
#      (services.plan_schema) using agent_worker.py -> job flips to 'plan_ready'.
#   3. The background thread wakes, renders 9:16 hook-first shorts + thumbnails
#      deterministically (services.renderer), and marks the job 'completed'.
#
# The frontend keeps polling /ai/status/<job_id> and /ai/results/<job_id>.

AGENT_PLAN_TIMEOUT = int(os.environ.get('AGENT_PLAN_TIMEOUT', '3600'))  # seconds


def run_job_task(job_id, input_filename, fps, video_id=None, smooth=False):
    """Background worker: extract frames -> await agent plan -> render shorts."""
    with app.app_context():
        jq = get_job_queue()
        try:
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
            if not os.path.exists(input_path):
                jq.mark_error(job_id, 'Uploaded video not found')
                return

            if not video_id:
                video_id = _compute_video_id(input_path, fps)

            frames_dir = os.path.join(app.config['FRAMES_FOLDER'], video_id)
            shorts_dir = os.path.join(app.config['SHORTS_FOLDER'], job_id)
            os.makedirs(frames_dir, exist_ok=True)
            os.makedirs(shorts_dir, exist_ok=True)

            jq.update_job(job_id, video_id=video_id, frames_dir=frames_dir,
                          shorts_dir=shorts_dir)

            # ---- Step 1: Extract frames (cached per video_id) ----
            manifest_path = os.path.join(frames_dir, 'manifest.json')
            if os.path.exists(manifest_path):
                with open(manifest_path) as f:
                    manifest = json.load(f)
                logger.info("Job %s: reusing cached frames (%d)", job_id, manifest.get('frame_count', 0))
            else:
                from services.frame_extractor import extract_frames

                jq.update_job(job_id, status='pending_frames', percentage=2,
                              step_message='Extracting frames from gameplay…')

                def frame_progress(current, total, msg):
                    pct = 2 + int((current / total) * 18) if total else 2
                    jq.update_job(job_id, percentage=pct, step_message=msg)

                manifest = extract_frames(input_path, frames_dir, fps=fps,
                                          progress_callback=frame_progress)

            # ---- Step 2: Build contact sheets for the agent ----
            sheets_index = os.path.join(frames_dir, 'sheets', 'index.json')
            if not os.path.exists(sheets_index):
                from services.contact_sheet import build_contact_sheets
                jq.update_job(job_id, percentage=22,
                              step_message='Building contact sheets for the AI agent…')
                build_contact_sheets(frames_dir, manifest_path=manifest_path)

            # ---- Step 3: Hand off to the agent ----
            jq.mark_awaiting_agent(job_id, frames_dir, manifest)
            logger.info("Job %s: awaiting agent analysis (%d frames)", job_id, manifest.get('frame_count', 0))

            plan = jq.wait_for_plan(job_id, timeout=AGENT_PLAN_TIMEOUT)
            if plan is None:
                job = jq.get_job(job_id)
                if job and job.get('status') == STATUS_ERROR:
                    return
                jq.mark_error(job_id, 'Timed out waiting for the AI agent to analyze the gameplay')
                return

            # ---- Step 4: Render shorts from the agent's plan ----
            from services.renderer import render_shorts
            jq.update_job(job_id, status='rendering', percentage=60,
                          step_message=f"Rendering {len(plan['moments'])} shorts…")

            def render_progress(current, total, msg):
                pct = 60 + int((current / total) * 38) if total else 60
                jq.update_job(job_id, percentage=pct, step_message=msg)

            shorts = render_shorts(input_path, plan, shorts_dir,
                                   progress_callback=render_progress,
                                   smooth=smooth,
                                   smooth_cache_dir=os.path.join(app.config['FRAMES_FOLDER'], '_smoothed'))

            result = {
                'shorts_dir': job_id,
                'video_id': video_id,
                'frame_count': manifest.get('frame_count', 0),
                'moment_count': len(plan['moments']),
                'short_count': sum(1 for s in shorts if s.get('output_path')),
                'game': plan.get('game', ''),
                'summary': plan.get('summary', ''),
                'shorts': shorts,
            }
            jq.mark_completed(job_id, result)
            logger.info("Job %s complete: %d shorts", job_id, result['short_count'])

        except Exception as e:
            logger.error("Job %s failed: %s", job_id, e, exc_info=True)
            jq.mark_error(job_id, str(e))


def _start_job(filename, fps, smooth=False):
    """Create a job + spawn its background worker. Returns (job_id, video_id)."""
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    job_id = uuid.uuid4().hex
    video_id = _compute_video_id(input_path, fps) if os.path.exists(input_path) else None

    jq = get_job_queue()
    jq.create_job(job_id, filename=filename, fps=fps, video_id=video_id, smooth=smooth)

    thread = threading.Thread(
        target=run_job_task, args=(job_id, filename, fps, video_id, smooth), daemon=True
    )
    thread.start()
    return job_id, video_id


@app.route('/generate_ai_shorts', methods=['POST'])
def generate_ai_shorts():
    """Legacy entry point — kept for compatibility. Starts an agent-in-the-loop job."""
    data = request.json or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({'error': 'Filename is required'}), 400
    try:
        fps = float(data.get('fps', 2))
        fps = max(0.5, min(5, fps))
    except (ValueError, TypeError):
        fps = 2
    smooth = bool(data.get('smooth', False))
    job_id, video_id = _start_job(filename, fps, smooth)
    return jsonify({'task_id': job_id, 'status': 'success', 'video_id': video_id})


@app.route('/ai/start', methods=['POST'])
def start_ai_pipeline():
    """Start an agent-in-the-loop AI shorts job (no local models)."""
    data = request.json or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({'error': 'Filename is required'}), 400

    try:
        fps = float(data.get('fps', 2))
        fps = max(0.5, min(5, fps))
    except (ValueError, TypeError):
        fps = 2

    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(input_path):
        return jsonify({'error': 'Video file not found'}), 404

    smooth = bool(data.get('smooth', False))
    job_id, video_id = _start_job(filename, fps, smooth)
    return jsonify({'task_id': job_id, 'status': 'success', 'fps': fps, 'video_id': video_id, 'smooth': smooth})


# ------------------------------------------------------------------ Agent API
# These endpoints let the agent (via the shorts-generator skill) discover jobs
# that need analysis and submit the plan. The skill can also use agent_worker.py
# to talk to the job queue directly on the filesystem.

@app.route('/agent/jobs', methods=['GET'])
def agent_list_jobs():
    """List jobs awaiting agent analysis (frames + contact sheets ready)."""
    jq = get_job_queue()
    jobs = []
    for job in jq.awaiting_agent_jobs():
        jobs.append({
            'job_id': job.get('job_id'),
            'filename': job.get('filename'),
            'frames_dir': job.get('frames_dir'),
            'frame_count': job.get('frame_count'),
            'duration': job.get('duration'),
            'created_at': job.get('created_at'),
        })
    return jsonify({'jobs': jobs, 'total': len(jobs)})


@app.route('/agent/jobs/<job_id>', methods=['GET'])
def agent_job_detail(job_id):
    """Full detail for a job, including the contact-sheet index for analysis."""
    jq = get_job_queue()
    job = jq.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    sheets = None
    frames_dir = job.get('frames_dir')
    if frames_dir:
        idx = os.path.join(frames_dir, 'sheets', 'index.json')
        if os.path.exists(idx):
            with open(idx) as f:
                sheets = json.load(f)
    return jsonify({'job': job, 'sheets': sheets})


@app.route('/agent/jobs/<job_id>/plan', methods=['POST'])
def agent_submit_plan(job_id):
    """Agent submits its analysis plan; job flips to plan_ready and rendering starts."""
    jq = get_job_queue()
    job = jq.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    plan = request.json
    if not isinstance(plan, dict):
        return jsonify({'error': 'Plan must be a JSON object'}), 400
    try:
        normalized = jq.save_plan(job_id, plan)
    except Exception as e:
        return jsonify({'error': f'Invalid plan: {e}'}), 400
    return jsonify({'status': 'success', 'moment_count': len(normalized['moments'])})


@app.route('/ai/status/<task_id>')
def ai_task_status(task_id):
    """Status of an AI shorts job (polled by the frontend)."""
    jq = get_job_queue()
    job = jq.get_job(task_id)
    if not job:
        return jsonify({'error': 'Task not found'}), 404

    response = {
        'status': job.get('status'),
        'percentage': job.get('percentage', 0),
        'step': job.get('status', ''),
        'step_message': job.get('step_message', ''),
        'frame_count': job.get('frame_count'),
        'moment_count': job.get('moment_count'),
    }

    if job.get('status') == STATUS_COMPLETED and 'result' in job:
        result = job['result']
        response['result'] = {
            'frame_count': result.get('frame_count', 0),
            'moment_count': result.get('moment_count', 0),
            'short_count': result.get('short_count', 0),
            'shorts_dir': result.get('shorts_dir', ''),
            'story_dir': result.get('shorts_dir', ''),
        }

    if job.get('status') == STATUS_ERROR:
        response['error'] = job.get('error', 'Unknown error')
    if job.get('status') == STATUS_AWAITING_AGENT:
        response['message'] = 'Waiting for the AI agent to analyze the gameplay.'

    return jsonify(response)


@app.route('/ai/results/<task_id>')
def ai_results(task_id):
    """Full results of a completed AI shorts job."""
    jq = get_job_queue()
    job = jq.get_job(task_id)
    if not job:
        return jsonify({'error': 'Task not found'}), 404
    if job.get('status') != STATUS_COMPLETED:
        return jsonify({'error': 'Task not yet completed', 'status': job.get('status')}), 400

    result = job.get('result', {})
    shorts_data = []
    for short_info in result.get('shorts', []):
        if short_info.get('output_path'):
            moment = short_info.get('moment', {})
            metadata = short_info.get('metadata', {})
            shorts_data.append({
                'index': short_info.get('index', 0),
                'video_url': short_info.get('web_video_path', ''),
                'thumbnail_url': short_info.get('web_thumbnail_path', ''),
                'metadata_url': short_info.get('web_metadata_path', ''),
                'duration': short_info.get('duration', 0),
                'fps': short_info.get('fps'),
                'smoothed': short_info.get('smoothed', False),
                'hook_structure': short_info.get('hook_structure', 'linear'),
                'category': moment.get('category', 'INTENSE'),
                'virality_score': moment.get('virality_score', 5),
                'moment_description': moment.get('reason', moment.get('description', '')),
                'start_time': moment.get('start_time', 0),
                'end_time': moment.get('end_time', 0),
                'title': metadata.get('title', 'Gameplay Moment'),
                'description': metadata.get('description', ''),
                'tags': metadata.get('tags', []),
                'tags_csv': metadata.get('tags_csv', ', '.join(metadata.get('tags', []))),
            })

    shorts_data.sort(key=lambda s: s['virality_score'], reverse=True)

    return jsonify({
        'task_id': task_id,
        'frame_count': result.get('frame_count', 0),
        'moment_count': result.get('moment_count', 0),
        'short_count': result.get('short_count', 0),
        'game': result.get('game', ''),
        'story': result.get('summary', ''),
        'story_parts': [],
        'shorts': shorts_data,
    })


@app.route('/ai/tasks', methods=['GET'])
def list_all_tasks():
    """List all AI jobs (for the sidebar)."""
    jq = get_job_queue()
    tasks_list = []
    for job in jq.list_jobs():
        tasks_list.append({
            'task_id': job.get('job_id'),
            'status': job.get('status'),
            'type': 'ai_shorts',
            'filename': job.get('filename'),
            'percentage': job.get('percentage', 0),
            'step': job.get('status', ''),
            'created_at': job.get('created_at'),
            'updated_at': job.get('updated_at'),
        })
    return jsonify({'tasks': tasks_list, 'total': len(tasks_list)})


@app.route('/ai/task-for-file', methods=['GET'])
def task_for_file():
    """Return the most recent job for a given filename (frontend state restore)."""
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'filename required'}), 400
    jq = get_job_queue()
    matching = [j for j in jq.list_jobs() if j.get('filename') == filename]
    if not matching:
        return jsonify({'task': None})
    job = matching[0]
    return jsonify({'task': {
        'task_id': job.get('job_id'),
        'status': job.get('status'),
        'percentage': job.get('percentage', 0),
        'step': job.get('status', ''),
    }})





# ============================================================
# ROUTES - Cache Management
# ============================================================

def _folder_size_mb(folder):
    """Return total size of a folder in MB."""
    total = 0
    if os.path.exists(folder):
        for dirpath, _, filenames in os.walk(folder):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    return round(total / (1024 * 1024), 1)


@app.route('/cache/info', methods=['GET'])
def cache_info():
    """Return size of each cache folder so the UI can show what will be cleared."""
    folders = {
        'frames': app.config['FRAMES_FOLDER'],
        'shorts': app.config['SHORTS_FOLDER'],
        'stories': app.config['STORIES_FOLDER'],
    }
    info = {}
    total_mb = 0.0
    for name, path in folders.items():
        mb = _folder_size_mb(path)
        info[name] = {'path': path, 'size_mb': mb}
        total_mb += mb
    return jsonify({'folders': info, 'total_mb': round(total_mb, 1)})


@app.route('/cache/clear', methods=['POST'])
def cache_clear():
    """
    Move generated cache folders (frames, shorts, stories) to the OS trash/bin.
    State tasks are also cleared so the UI starts fresh.
    The original uploads folder is left untouched.
    """
    from send2trash import send2trash

    folders = {
        'frames': app.config['FRAMES_FOLDER'],
        'shorts': app.config['SHORTS_FOLDER'],
        'stories': app.config['STORIES_FOLDER'],
    }

    moved = []
    errors = []

    for name, folder_path in folders.items():
        if not os.path.exists(folder_path):
            continue
        # Only trash if there is something inside
        contents = os.listdir(folder_path)
        if not contents:
            continue
        try:
            # Move the *contents* to trash so the empty folder remains
            # (app expects the folder to exist on next run)
            for item in contents:
                item_path = os.path.join(folder_path, item)
                send2trash(item_path)
            moved.append(name)
            logger.info(f"Cache clear: moved {name} contents to trash")
        except Exception as e:
            errors.append({'folder': name, 'error': str(e)})
            logger.error(f"Cache clear: failed to move {name}: {e}")

    # Clear all job + task state so the sidebar shows no stale tasks
    get_job_queue().clear_all()
    get_state_manager().clear_all_tasks()

    if errors:
        return jsonify({
            'status': 'partial',
            'moved': moved,
            'errors': errors,
            'message': f"Moved {len(moved)} folder(s) to trash. {len(errors)} error(s)."
        }), 207

    return jsonify({
        'status': 'success',
        'moved': moved,
        'message': f"Moved to trash: {', '.join(moved) if moved else 'nothing to clear'}."
    })


# ============================================================
# ROUTES - Task Status (existing)
# ============================================================

@app.route('/status/<task_id>')
def task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)


# ============================================================
# ROUTES - System Info
# ============================================================

@app.route('/system/info')
def system_info():
    """Return system capabilities for the frontend."""
    import platform

    return jsonify({
        'platform': platform.system(),
        'python_version': platform.python_version(),
        'engine': 'agent-in-the-loop',
        'device_name': 'AI agent (no local models)',
        'max_upload_mb': app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    })


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    app.run(debug=True, port=8000, threaded=True)