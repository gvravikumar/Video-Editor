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
app.config['MODELS_FOLDER'] = os.path.join(BASE_DIR, 'models')
app.config['STATE_FOLDER'] = os.path.join(BASE_DIR, 'state')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2 GB limit for large gameplay videos

# Create all directories
for folder in ['UPLOAD_FOLDER', 'PROCESSED_FOLDER', 'FRAMES_FOLDER',
               'SHORTS_FOLDER', 'STORIES_FOLDER', 'MODELS_FOLDER', 'STATE_FOLDER']:
    os.makedirs(app.config[folder], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

# Initialize State Manager for persistent task tracking
from services.state_manager import init_state_manager, get_state_manager
state_manager = init_state_manager(app.config['STATE_FOLDER'])

# Legacy task dictionary (for backward compatibility with existing code)
# Will be gradually migrated to state_manager
tasks = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _compute_video_id(filepath, fps, vision_model="blip-base"):
    """
    Derive a stable identifier for a (video, fps, vision_model) triple.
    Changing any of fps or vision_model produces a new ID so cached captions
    from a different model are never reused.
    """
    import hashlib
    h = hashlib.sha256()
    h.update(str(os.path.getsize(filepath)).encode())
    h.update(f"{fps:.1f}".encode())
    h.update(vision_model.encode())
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


# ============================================================
# ROUTES - File Serving
# ============================================================

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))


def _get_video_metadata_fast(filepath):
    """
    Extract video metadata using ffprobe (bundled with FFmpeg/MoviePy).
    ~50ms per file vs 2-5s with VideoFileClip — critical for listing many videos.
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
    return None


@app.route('/uploads/list')
def list_uploads():
    """List all previously uploaded videos with their latest task state."""
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            return jsonify({'files': []})

        # Build filename → most-recent task map from state manager
        sm = get_state_manager()
        all_tasks = sm.get_all_tasks()
        filename_task_map = {}
        for task in all_tasks.values():
            fname = task.get('filename')
            if fname:
                existing = filename_task_map.get(fname)
                if not existing or task.get('created_at', '') > existing.get('created_at', ''):
                    filename_task_map[fname] = task

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
                'task_id': task_info.get('task_id') if task_info else None,
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
# ROUTES - AI Pipeline
# ============================================================

@app.route('/generate_ai_shorts', methods=['POST'])
def generate_ai_shorts():
    """Start AI shorts generation pipeline."""
    data = request.json
    filename = data.get('filename')
    fps = data.get('fps', 2)

    if not filename:
        return jsonify({'error': 'Filename is required'}), 400

    # Validate FPS
    try:
        fps = int(fps)
        if fps < 1 or fps > 5:
            fps = 2
    except:
        fps = 2

    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    task_id  = uuid.uuid4().hex
    video_id = _compute_video_id(input_path, fps) if os.path.exists(input_path) else None
    tasks[task_id] = {
        'status': 'queued',
        'percentage': 0,
        'step': 'initializing',
        'step_message': 'Initializing AI pipeline...',
        'video_id': video_id,
    }

    # Start AI pipeline in background thread
    thread = threading.Thread(target=ai_pipeline_task, args=(task_id, filename, fps, video_id))
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'success'})


def _auto_detect_checkpoints(sm, task_id, frames_dir, stories_dir):
    """
    Inspect the video_id-based directories and pre-set checkpoints for any
    steps whose output already exists on disk.  Called at the start of every
    pipeline run so new tasks transparently reuse previous work.
    """
    # Step 1 — frames extracted
    if not sm.has_checkpoint(task_id, 'frames_extracted'):
        manifest_path = os.path.join(frames_dir, 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                m = json.load(f)
            sm.add_checkpoint(task_id, 'frames_extracted', {
                'frame_count': m.get('frame_count', 0),
                'manifest_path': manifest_path
            })
            sm.update_task(task_id, frame_count=m.get('frame_count', 0), percentage=20)
            logger.info(f"Task {task_id}: reusing existing frames ({m.get('frame_count')} frames)")

    # Step 2 — frames analyzed
    if not sm.has_checkpoint(task_id, 'frames_analyzed'):
        captions_path = os.path.join(frames_dir, 'captions.json')
        if os.path.exists(captions_path):
            with open(captions_path, 'r') as f:
                c = json.load(f)
            sm.add_checkpoint(task_id, 'frames_analyzed', {
                'captions_count': len(c.get('captions', [])),
                'captions_path': captions_path
            })
            sm.update_task(task_id, percentage=60)
            logger.info(f"Task {task_id}: reusing existing captions ({len(c.get('captions', []))} captions)")

    # Step 3 — story + moments generated
    if not sm.has_checkpoint(task_id, 'story_generated'):
        story_path   = os.path.join(stories_dir, 'story.json')
        moments_path = os.path.join(stories_dir, 'moments.json')
        if os.path.exists(story_path) and os.path.exists(moments_path):
            with open(moments_path, 'r') as f:
                mo = json.load(f)
            moment_count = len(mo.get('moments', []))
            sm.add_checkpoint(task_id, 'story_generated', {
                'moment_count': moment_count,
                'story_path': story_path,
                'moments_path': moments_path
            })
            sm.update_task(task_id, moment_count=moment_count, percentage=75)
            logger.info(f"Task {task_id}: reusing existing story/moments ({moment_count} moments)")

    # Steps 4 & 5 (shorts + metadata) are NOT auto-detected: shorts belong to
    # a specific task_id directory, so a new task always generates fresh clips.


def ai_pipeline_task(task_id, input_filename, fps, video_id=None, vision_model=None):
    """
    Full AI pipeline with checkpoint-based resumption:
    1. Extract frames
    2. Analyze frames (BLIP captioning)
    3. Generate story + detect moments
    4. Generate short videos
    5. Generate metadata for shorts

    Frames and story/moments are stored under video_id (stable per video+fps),
    so the same video never re-extracts or re-analyzes frames across runs.
    Shorts are stored under task_id so each run can produce its own clips.
    """
    with app.app_context():
        try:
            sm = get_state_manager()
            task = sm.get_task(task_id)

            if not task:
                logger.error(f"Task {task_id} not found in state manager")
                return

            input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)

            # vision_model / video_id may come from state (resume) or parameter (fresh start)
            if not vision_model:
                vision_model = task.get('vision_model', 'blip-base')
            if not video_id:
                video_id = task.get('video_id') or _compute_video_id(input_path, fps, vision_model)

            # Frames + stories: shared per (video, fps) — reused across all runs
            # Shorts: per task_id — each run may produce different clips
            task_frames_dir  = os.path.join(app.config['FRAMES_FOLDER'],  video_id)
            task_stories_dir = os.path.join(app.config['STORIES_FOLDER'], video_id)
            task_shorts_dir  = os.path.join(app.config['SHORTS_FOLDER'],  task_id)

            os.makedirs(task_frames_dir,  exist_ok=True)
            os.makedirs(task_shorts_dir,  exist_ok=True)
            os.makedirs(task_stories_dir, exist_ok=True)

            # Store directory paths + video_id in state
            sm.update_task(task_id,
                           video_id=video_id,
                           task_frames_dir=task_frames_dir,
                           task_shorts_dir=task_shorts_dir,
                           task_stories_dir=task_stories_dir)

            # ------------------------------------------------------------------
            # Pre-flight: auto-detect already-completed steps from disk.
            # This lets a brand-new task reuse work done by any previous run
            # for the same video without requiring an explicit "resume".
            # ------------------------------------------------------------------
            _auto_detect_checkpoints(sm, task_id, task_frames_dir, task_stories_dir)
            logger.info(f"Task {task_id}: video_id={video_id}, "
                        f"last_checkpoint={sm.get_last_checkpoint(task_id)}")

            # ---- Step 1: Extract Frames ----
            manifest = None
            if not sm.has_checkpoint(task_id, 'frames_extracted'):
                from services.frame_extractor import extract_frames
                
                sm.update_task(task_id, status='extracting_frames', percentage=0, step='extracting_frames')
                tasks[task_id] = sm.get_task(task_id)  # Sync legacy dict

                def frame_progress(current, total, msg):
                    if total > 0:
                        step_pct = int((current / total) * 20)  # 0-20%
                    else:
                        step_pct = 0
                    sm.update_task(task_id, percentage=step_pct, step_message=msg, step='extracting_frames')
                    tasks[task_id] = sm.get_task(task_id)

                logger.info(f"Task {task_id}: Starting frame extraction...")
                manifest = extract_frames(
                    input_path, task_frames_dir, fps=fps,
                    progress_callback=frame_progress
                )

                sm.add_checkpoint(task_id, 'frames_extracted', {
                    'frame_count': manifest['frame_count'],
                    'manifest_path': os.path.join(task_frames_dir, 'manifest.json')
                })
                sm.update_task(task_id, frame_count=manifest['frame_count'], percentage=20)
                tasks[task_id] = sm.get_task(task_id)
                logger.info(f"Task {task_id}: Frame extraction complete ({manifest['frame_count']} frames)")
            else:
                # Resume: Load existing manifest
                logger.info(f"Task {task_id}: Resuming - frames already extracted")
                manifest_path = os.path.join(task_frames_dir, 'manifest.json')
                if os.path.exists(manifest_path):
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    sm.update_task(task_id, frame_count=manifest['frame_count'], percentage=20)
                    tasks[task_id] = sm.get_task(task_id)

            # ---- Step 2: Analyze Frames (BLIP) ----
            captions_data = None
            if not sm.has_checkpoint(task_id, 'frames_analyzed'):
                from services.frame_analyzer import analyze_frames
                
                sm.update_task(task_id, status='analyzing_frames', step='analyzing_frames')
                tasks[task_id] = sm.get_task(task_id)

                def analyze_progress(current, total, msg):
                    if total > 0:
                        step_pct = 20 + int((current / total) * 40)  # 20-60%
                    else:
                        step_pct = 20
                    sm.update_task(task_id, percentage=step_pct, step_message=msg, step='analyzing_frames')
                    tasks[task_id] = sm.get_task(task_id)

                logger.info(f"Task {task_id}: Starting frame analysis with model={vision_model}...")
                captions_data = analyze_frames(
                    task_frames_dir,
                    progress_callback=analyze_progress,
                    vision_model=vision_model
                )

                sm.add_checkpoint(task_id, 'frames_analyzed', {
                    'captions_count': len(captions_data.get('captions', [])),
                    'captions_path': os.path.join(task_frames_dir, 'captions.json')
                })
                sm.update_task(task_id, percentage=60)
                tasks[task_id] = sm.get_task(task_id)
                logger.info(f"Task {task_id}: Frame analysis complete")
            else:
                # Resume: Load existing captions
                logger.info(f"Task {task_id}: Resuming - frames already analyzed")
                sm.update_task(task_id, percentage=60)
                tasks[task_id] = sm.get_task(task_id)

            # ---- Step 3: Generate Story + Detect Moments ----
            analysis = None
            if not sm.has_checkpoint(task_id, 'story_generated'):
                from services.story_generator import generate_full_analysis

                sm.update_task(task_id, status='generating_story', step='generating_story')
                tasks[task_id] = sm.get_task(task_id)

                captions_path = os.path.join(task_frames_dir, "captions.json")

                def story_progress(current, total, msg):
                    if total > 0:
                        step_pct = 60 + int((current / total) * 15)  # 60-75%
                    else:
                        step_pct = 60
                    sm.update_task(task_id, percentage=step_pct, step_message=msg, step='generating_story')
                    tasks[task_id] = sm.get_task(task_id)

                logger.info(f"Task {task_id}: Starting story generation...")
                analysis = generate_full_analysis(
                    captions_path, task_stories_dir,
                    progress_callback=story_progress
                )

                sm.add_checkpoint(task_id, 'story_generated', {
                    'moment_count': len(analysis['moments']),
                    'story_path': os.path.join(task_stories_dir, 'story.json'),
                    'moments_path': os.path.join(task_stories_dir, 'moments.json')
                })
                sm.update_task(task_id, moment_count=len(analysis['moments']), percentage=75)
                tasks[task_id] = sm.get_task(task_id)
                logger.info(f"Task {task_id}: Story generation complete ({len(analysis['moments'])} moments)")
            else:
                # Resume: reconstruct analysis from story.json + moments.json
                logger.info(f"Task {task_id}: Resuming - story already generated")
                story_path = os.path.join(task_stories_dir, 'story.json')
                moments_path = os.path.join(task_stories_dir, 'moments.json')
                analysis = None
                if os.path.exists(story_path) and os.path.exists(moments_path):
                    with open(story_path, 'r') as f:
                        story_data = json.load(f)
                    with open(moments_path, 'r') as f:
                        moments_data = json.load(f)
                    analysis = {
                        'story': story_data,
                        'moments': moments_data.get('moments', [])
                    }
                if analysis:
                    sm.update_task(task_id, moment_count=len(analysis['moments']), percentage=75)
                    tasks[task_id] = sm.get_task(task_id)
                else:
                    # Files missing — clear checkpoint so this stage re-runs on next attempt
                    logger.warning(f"Task {task_id}: story/moments files missing, clearing checkpoint to re-run")
                    sm.remove_checkpoint(task_id, 'story_generated')

            # Guard: analysis must be populated before Step 4
            if analysis is None:
                raise RuntimeError(
                    "Story/moments data could not be loaded. "
                    "The checkpoint has been cleared — resume the task to re-run story generation."
                )

            # ---- Step 4: Generate Short Videos ----
            shorts = None
            if not sm.has_checkpoint(task_id, 'shorts_generated'):
                from services.short_generator import generate_all_shorts

                sm.update_task(task_id, status='generating_shorts', step='generating_shorts')
                tasks[task_id] = sm.get_task(task_id)
                
                def shorts_progress(current, total, msg):
                    if total > 0:
                        step_pct = 75 + int((current / total) * 15)  # 75-90%
                    else:
                        step_pct = 75
                    sm.update_task(task_id, percentage=step_pct, step_message=msg, step='generating_shorts')
                    tasks[task_id] = sm.get_task(task_id)

                logger.info(f"Task {task_id}: Starting shorts generation...")
                shorts = generate_all_shorts(
                    input_path, analysis['moments'], task_shorts_dir,
                    progress_callback=shorts_progress
                )

                sm.add_checkpoint(task_id, 'shorts_generated', {
                    'shorts_count': len(shorts)
                })
                sm.update_task(task_id, percentage=90)
                tasks[task_id] = sm.get_task(task_id)
                logger.info(f"Task {task_id}: Shorts generation complete")
            else:
                # Resume: Load existing shorts
                logger.info(f"Task {task_id}: Resuming - shorts already generated")
                shorts_manifest_path = os.path.join(task_shorts_dir, 'shorts_manifest.json')
                if os.path.exists(shorts_manifest_path):
                    with open(shorts_manifest_path, 'r') as f:
                        shorts = json.load(f)
                sm.update_task(task_id, percentage=90)
                tasks[task_id] = sm.get_task(task_id)

            # ---- Step 5: Generate Metadata ----
            enriched_shorts = None
            if not sm.has_checkpoint(task_id, 'metadata_generated'):
                from services.metadata_generator import generate_all_metadata

                sm.update_task(task_id, status='generating_metadata', step='generating_metadata')
                tasks[task_id] = sm.get_task(task_id)

                def metadata_progress(current, total, msg):
                    if total > 0:
                        step_pct = 90 + int((current / total) * 10)  # 90-100%
                    else:
                        step_pct = 90
                    sm.update_task(task_id, percentage=step_pct, step_message=msg, step='generating_metadata')
                    tasks[task_id] = sm.get_task(task_id)

                logger.info(f"Task {task_id}: Starting metadata generation...")
                enriched_shorts = generate_all_metadata(
                    shorts, task_stories_dir,
                    progress_callback=metadata_progress
                )

                sm.add_checkpoint(task_id, 'metadata_generated', {
                    'enriched_shorts_count': len(enriched_shorts)
                })
                logger.info(f"Task {task_id}: Metadata generation complete")
            else:
                # Resume: Load existing enriched shorts
                logger.info(f"Task {task_id}: Resuming - metadata already generated")
                metadata_path = os.path.join(task_stories_dir, 'enriched_shorts.json')
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        enriched_shorts = json.load(f)

            # ---- Complete ----
            result = {
                'story': analysis['story'],
                'moments': analysis['moments'],
                'shorts': enriched_shorts,
                'shorts_dir': task_id,
                'story_dir': task_id,
                'frame_count': manifest['frame_count'],
                'moment_count': len(analysis['moments']),
                'short_count': sum(1 for s in enriched_shorts if s.get('output_path'))
            }
            
            sm.mark_completed(task_id, result)
            tasks[task_id] = sm.get_task(task_id)

            logger.info(f"AI pipeline complete for task {task_id}: "
                        f"{manifest['frame_count']} frames, "
                        f"{len(analysis['moments'])} moments, "
                        f"{len(enriched_shorts)} shorts")

        except Exception as e:
            logger.error(f"AI pipeline error for task {task_id}: {e}", exc_info=True)
            sm = get_state_manager()
            sm.mark_error(task_id, str(e))
            tasks[task_id] = sm.get_task(task_id)


@app.route('/ai/start', methods=['POST'])
def start_ai_pipeline():
    """Start the full AI analysis pipeline with persistent state."""
    from services.frame_analyzer import AVAILABLE_MODELS, DEFAULT_MODEL

    data = request.json
    filename = data.get('filename')
    fps = data.get('fps', 2)
    vision_model = data.get('vision_model', DEFAULT_MODEL)

    if not filename:
        return jsonify({'error': 'Filename is required'}), 400

    # Validate FPS
    try:
        fps = float(fps)
        fps = max(0.5, min(5, fps))  # Clamp between 0.5 and 5
    except (ValueError, TypeError):
        fps = 2

    # Validate model key
    if vision_model not in AVAILABLE_MODELS:
        vision_model = DEFAULT_MODEL

    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(input_path):
        return jsonify({'error': 'Video file not found'}), 404

    task_id = uuid.uuid4().hex
    video_id = _compute_video_id(input_path, fps, vision_model)

    # Create task in state manager
    sm = get_state_manager()
    sm.create_task(
        task_id,
        task_type='ai_pipeline',
        fps=fps,
        filename=filename,
        video_id=video_id,
        vision_model=vision_model,
        step_message='Starting AI pipeline...'
    )

    # Sync to legacy tasks dict
    tasks[task_id] = sm.get_task(task_id)

    thread = threading.Thread(
        target=ai_pipeline_task,
        args=(task_id, filename, fps, video_id, vision_model),
        daemon=True
    )
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'success', 'fps': fps, 'video_id': video_id, 'vision_model': vision_model})


@app.route('/ai/tasks', methods=['GET'])
def list_all_tasks():
    """List all tasks (active, completed, interrupted, etc.)."""
    sm = get_state_manager()
    all_tasks = sm.get_all_tasks()
    
    # Format for response
    tasks_list = []
    for task_id, task in all_tasks.items():
        tasks_list.append({
            'task_id': task_id,
            'status': task.get('status'),
            'type': task.get('type'),
            'filename': task.get('filename'),
            'percentage': task.get('percentage', 0),
            'step': task.get('step', ''),
            'created_at': task.get('created_at'),
            'updated_at': task.get('updated_at'),
            'resumable': task.get('resumable', False),
            'last_checkpoint': task.get('last_checkpoint')
        })
    
    # Sort by updated_at (newest first)
    tasks_list.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
    
    return jsonify({'tasks': tasks_list, 'total': len(tasks_list)})


@app.route('/ai/tasks/resumable', methods=['GET'])
def list_resumable_tasks():
    """List all tasks that can be resumed."""
    sm = get_state_manager()
    resumable = sm.get_resumable_tasks()
    
    # Format for response
    tasks_list = []
    for task in resumable:
        tasks_list.append({
            'task_id': task.get('task_id'),
            'status': task.get('status'),
            'type': task.get('type'),
            'filename': task.get('filename'),
            'percentage': task.get('percentage', 0),
            'step': task.get('step', ''),
            'last_checkpoint': task.get('last_checkpoint'),
            'interrupted_at': task.get('interrupted_at'),
            'created_at': task.get('created_at')
        })
    
    return jsonify({'tasks': tasks_list, 'total': len(tasks_list)})


@app.route('/ai/task-for-file', methods=['GET'])
def task_for_file():
    """Return the most recent task for a given filename (used by frontend state restore)."""
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'filename required'}), 400

    sm = get_state_manager()
    matching = [t for t in sm.get_all_tasks().values() if t.get('filename') == filename]
    if not matching:
        return jsonify({'task': None})

    matching.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    task = matching[0]
    return jsonify({
        'task': {
            'task_id': task.get('task_id'),
            'status': task.get('status'),
            'percentage': task.get('percentage', 0),
            'step': task.get('step', ''),
            'last_checkpoint': task.get('last_checkpoint'),
            'resumable': task.get('resumable', False)
        }
    })


@app.route('/ai/resume/<task_id>', methods=['POST'])
def resume_task(task_id):
    """Resume an interrupted task from its last checkpoint."""
    sm = get_state_manager()
    task = sm.get_task(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    if task.get('status') not in ['interrupted', 'error']:
        return jsonify({'error': 'Task is not resumable', 'status': task.get('status')}), 400
    
    # Get task details — vision_model preserved from the original run
    filename     = task.get('filename')
    fps          = task.get('fps', 2)
    video_id     = task.get('video_id')
    vision_model = task.get('vision_model', 'blip-base')

    if not filename:
        return jsonify({'error': 'Task missing filename metadata'}), 400

    # Reset status to queued for resumption
    sm.update_task(task_id,
                   status='queued',
                   step='resuming',
                   step_message=f'Resuming from {task.get("last_checkpoint", "last checkpoint")}...',
                   resumable=False)

    # Sync to legacy dict
    tasks[task_id] = sm.get_task(task_id)

    # Start the pipeline thread (it will detect checkpoints and resume)
    thread = threading.Thread(
        target=ai_pipeline_task,
        args=(task_id, filename, fps, video_id, vision_model),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'status': 'success',
        'message': 'Task resumed',
        'last_checkpoint': task.get('last_checkpoint')
    })


@app.route('/ai/status/<task_id>')
def ai_task_status(task_id):
    """Get status of an AI pipeline task from persistent state."""
    sm = get_state_manager()
    task = sm.get_task(task_id)
    
    if not task:
        # Fallback to legacy tasks dict
        task = tasks.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

    # Build response (exclude large data from status polling)
    response = {
        'status': task.get('status'),
        'percentage': task.get('percentage', 0),
        'step': task.get('step', ''),
        'step_message': task.get('step_message', ''),
        'frame_count': task.get('frame_count'),
        'moment_count': task.get('moment_count'),
        'resumable': task.get('resumable', False),
        'last_checkpoint': task.get('last_checkpoint')
    }

    if task.get('status') == 'completed' and 'result' in task:
        result = task['result']
        response['result'] = {
            'frame_count': result.get('frame_count', 0),
            'moment_count': result.get('moment_count', 0),
            'short_count': result.get('short_count', 0),
            'shorts_dir': result.get('shorts_dir', ''),
            'story_dir': result.get('story_dir', '')
        }

    if task.get('status') == 'error':
        response['error'] = task.get('error', 'Unknown error')
    
    if task.get('status') == 'interrupted':
        response['message'] = 'Task was interrupted. You can resume it.'

    return jsonify(response)


# Update the existing route to also use state manager
@app.route('/ai/results/<task_id>')
def ai_results(task_id):
    """Get full results of a completed AI pipeline task."""
    sm = get_state_manager()
    task = sm.get_task(task_id)
    
    if not task:
        # Fallback to legacy
        task = tasks.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

    if task.get('status') != 'completed':
        return jsonify({'error': 'Task not yet completed', 'status': task.get('status')}), 400

    result = task.get('result', {})

    # Build shorts data with web paths
    shorts_data = []
    for short_info in result.get('shorts', []):
        if short_info.get('output_path'):
            moment = short_info.get('moment', {})
            metadata = short_info.get('metadata', {})
            shorts_data.append({
                'index': short_info.get('index', 0),
                'video_url': short_info.get('web_video_path', ''),
                'thumbnail_url': short_info.get('web_thumbnail_path', ''),
                'duration': short_info.get('duration', 0),
                'hook_structure': short_info.get('hook_structure', 'linear'),
                'category': moment.get('category', 'INTENSE'),
                'virality_score': moment.get('virality_score', 5),
                'moment_description': moment.get('description', ''),
                'start_time': moment.get('start_time', 0),
                'end_time': moment.get('end_time', 0),
                'title': metadata.get('title', 'Gameplay Moment'),
                'description': metadata.get('description', ''),
                'tags': metadata.get('tags', [])
            })

    # Sort by virality score
    shorts_data.sort(key=lambda s: s['virality_score'], reverse=True)

    # Get story
    story = result.get('story', {})

    return jsonify({
        'task_id': task_id,
        'frame_count': result.get('frame_count', 0),
        'moment_count': result.get('moment_count', 0),
        'short_count': result.get('short_count', 0),
        'story': story.get('full_story', ''),
        'story_parts': story.get('parts', []),
        'shorts': shorts_data
    })


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

    # Clear all task state so the sidebar shows no stale tasks
    sm = get_state_manager()
    sm.clear_all_tasks()

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
# ROUTES - Model Status
# ============================================================

@app.route('/ai/models', methods=['GET'])
def ai_models():
    """Return available vision models and whether each is already downloaded."""
    from services.frame_analyzer import AVAILABLE_MODELS
    result = []
    for key, cfg in AVAILABLE_MODELS.items():
        local_path = os.path.join(app.config['MODELS_FOLDER'], cfg['local_dir'])
        downloaded = os.path.exists(os.path.join(local_path, 'config.json'))
        result.append({
            'key': key,
            'display_name': cfg['display_name'],
            'size_label': cfg['size_label'],
            'speed_label': cfg['speed_label'],
            'quality_label': cfg['quality_label'],
            'downloaded': downloaded,
        })
    return jsonify({'models': result})


# ============================================================
# ROUTES - System Info
# ============================================================

@app.route('/system/info')
def system_info():
    """Return system capabilities for the frontend."""
    import platform
    import torch

    device = "cpu"
    device_name = "CPU"

    if torch.backends.mps.is_available():
        device = "mps"
        device_name = "Apple Silicon (MPS)"
    elif torch.cuda.is_available():
        device = "cuda"
        device_name = torch.cuda.get_device_name(0)

    return jsonify({
        'platform': platform.system(),
        'python_version': platform.python_version(),
        'device': device,
        'device_name': device_name,
        'torch_version': torch.__version__,
        'max_upload_mb': app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    })


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    app.run(debug=True, port=8000)