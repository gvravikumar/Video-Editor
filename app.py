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
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2 GB limit for large gameplay videos

# Create all directories
for folder in ['UPLOAD_FOLDER', 'PROCESSED_FOLDER', 'FRAMES_FOLDER',
               'SHORTS_FOLDER', 'STORIES_FOLDER', 'MODELS_FOLDER']:
    os.makedirs(app.config[folder], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

# Task tracking for all operations
tasks = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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


@app.route('/uploads/list')
def list_uploads():
    """List all previously uploaded videos."""
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            return jsonify({'files': []})

        files = []
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            if os.path.isfile(filepath) and allowed_file(filename):
                # Get file info
                stat = os.stat(filepath)
                size_mb = stat.st_size / (1024 * 1024)
                modified = stat.st_mtime

                # Try to get video metadata
                try:
                    clip = VideoFileClip(filepath)
                    metadata = {
                        'duration': clip.duration,
                        'resolution': clip.size,
                        'fps': clip.fps
                    }
                    clip.close()
                except:
                    metadata = None

                files.append({
                    'filename': filename,
                    'size_mb': round(size_mb, 2),
                    'modified': modified,
                    'metadata': metadata,
                    'url': url_for('serve_upload', filename=filename)
                })

        # Sort by modified time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)

        return jsonify({'files': files})
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

    task_id = uuid.uuid4().hex
    tasks[task_id] = {
        'status': 'queued',
        'percentage': 0,
        'step': 'initializing',
        'step_message': 'Initializing AI pipeline...'
    }

    # Start AI pipeline in background thread
    thread = threading.Thread(target=ai_pipeline_task, args=(task_id, filename, fps))
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'success'})


def ai_pipeline_task(task_id, input_filename, fps):
    """
    Full AI pipeline:
    1. Extract frames
    2. Analyze frames (BLIP captioning)
    3. Generate story + detect moments
    4. Generate short videos
    5. Generate metadata for shorts
    """
    with app.app_context():
        try:
            tasks[task_id]['status'] = 'extracting_frames'
            tasks[task_id]['percentage'] = 0

            input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)

            # Create task-specific directories
            task_frames_dir = os.path.join(app.config['FRAMES_FOLDER'], task_id)
            task_shorts_dir = os.path.join(app.config['SHORTS_FOLDER'], task_id)
            task_stories_dir = os.path.join(app.config['STORIES_FOLDER'], task_id)

            os.makedirs(task_frames_dir, exist_ok=True)
            os.makedirs(task_shorts_dir, exist_ok=True)
            os.makedirs(task_stories_dir, exist_ok=True)

            # ---- Step 1: Extract Frames ----
            from services.frame_extractor import extract_frames

            def frame_progress(current, total, msg):
                if total > 0:
                    step_pct = int((current / total) * 20)  # 0-20%
                else:
                    step_pct = 0
                tasks[task_id]['percentage'] = step_pct
                tasks[task_id]['step_message'] = msg
                tasks[task_id]['step'] = 'extracting_frames'

            manifest = extract_frames(
                input_path, task_frames_dir, fps=fps,
                progress_callback=frame_progress
            )

            tasks[task_id]['frame_count'] = manifest['frame_count']
            tasks[task_id]['percentage'] = 20
            tasks[task_id]['status'] = 'analyzing_frames'

            # ---- Step 2: Analyze Frames (BLIP) ----
            from services.frame_analyzer import analyze_frames

            def analyze_progress(current, total, msg):
                if total > 0:
                    step_pct = 20 + int((current / total) * 40)  # 20-60%
                else:
                    step_pct = 20
                tasks[task_id]['percentage'] = step_pct
                tasks[task_id]['step_message'] = msg
                tasks[task_id]['step'] = 'analyzing_frames'

            captions_data = analyze_frames(
                task_frames_dir,
                progress_callback=analyze_progress
            )

            tasks[task_id]['percentage'] = 60
            tasks[task_id]['status'] = 'generating_story'

            # ---- Step 3: Generate Story + Detect Moments ----
            from services.story_generator import generate_full_analysis

            captions_path = os.path.join(task_frames_dir, "captions.json")

            def story_progress(current, total, msg):
                if total > 0:
                    step_pct = 60 + int((current / total) * 15)  # 60-75%
                else:
                    step_pct = 60
                tasks[task_id]['percentage'] = step_pct
                tasks[task_id]['step_message'] = msg
                tasks[task_id]['step'] = 'generating_story'

            analysis = generate_full_analysis(
                captions_path, task_stories_dir,
                progress_callback=story_progress
            )

            tasks[task_id]['moment_count'] = len(analysis['moments'])
            tasks[task_id]['percentage'] = 75
            tasks[task_id]['status'] = 'generating_shorts'

            # ---- Step 4: Generate Short Videos ----
            from services.short_generator import generate_all_shorts

            def shorts_progress(current, total, msg):
                if total > 0:
                    step_pct = 75 + int((current / total) * 15)  # 75-90%
                else:
                    step_pct = 75
                tasks[task_id]['percentage'] = step_pct
                tasks[task_id]['step_message'] = msg
                tasks[task_id]['step'] = 'generating_shorts'

            shorts = generate_all_shorts(
                input_path, analysis['moments'], task_shorts_dir,
                progress_callback=shorts_progress
            )

            tasks[task_id]['percentage'] = 90
            tasks[task_id]['status'] = 'generating_metadata'

            # ---- Step 5: Generate Metadata ----
            from services.metadata_generator import generate_all_metadata

            def metadata_progress(current, total, msg):
                if total > 0:
                    step_pct = 90 + int((current / total) * 10)  # 90-100%
                else:
                    step_pct = 90
                tasks[task_id]['percentage'] = step_pct
                tasks[task_id]['step_message'] = msg
                tasks[task_id]['step'] = 'generating_metadata'

            enriched_shorts = generate_all_metadata(
                shorts, task_stories_dir,
                progress_callback=metadata_progress
            )

            # ---- Complete ----
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['percentage'] = 100
            tasks[task_id]['step_message'] = 'AI pipeline complete!'
            tasks[task_id]['step'] = 'done'
            tasks[task_id]['result'] = {
                'story': analysis['story'],
                'moments': analysis['moments'],
                'shorts': enriched_shorts,
                'shorts_dir': task_id,
                'story_dir': task_id,
                'frame_count': manifest['frame_count'],
                'moment_count': len(analysis['moments']),
                'short_count': sum(1 for s in enriched_shorts if s.get('output_path'))
            }

            logger.info(f"AI pipeline complete for task {task_id}: "
                        f"{manifest['frame_count']} frames, "
                        f"{len(analysis['moments'])} moments, "
                        f"{len(enriched_shorts)} shorts")

        except Exception as e:
            logger.error(f"AI pipeline error for task {task_id}: {e}", exc_info=True)
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)


@app.route('/ai/start', methods=['POST'])
def start_ai_pipeline():
    """Start the full AI analysis pipeline."""
    data = request.json
    filename = data.get('filename')
    fps = data.get('fps', 2)

    if not filename:
        return jsonify({'error': 'Filename is required'}), 400

    # Validate FPS
    try:
        fps = float(fps)
        fps = max(0.5, min(5, fps))  # Clamp between 0.5 and 5
    except (ValueError, TypeError):
        fps = 2

    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(input_path):
        return jsonify({'error': 'Video file not found'}), 404

    task_id = uuid.uuid4().hex
    tasks[task_id] = {
        'status': 'queued',
        'percentage': 0,
        'step': 'initializing',
        'step_message': 'Starting AI pipeline...',
        'type': 'ai_pipeline',
        'fps': fps,
        'filename': filename
    }

    thread = threading.Thread(
        target=ai_pipeline_task,
        args=(task_id, filename, fps),
        daemon=True
    )
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'success', 'fps': fps})


@app.route('/ai/status/<task_id>')
def ai_task_status(task_id):
    """Get status of an AI pipeline task."""
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
        'moment_count': task.get('moment_count')
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

    return jsonify(response)


@app.route('/ai/results/<task_id>')
def ai_results(task_id):
    """Get full results of a completed AI pipeline task."""
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