from flask import Flask, render_template, request, jsonify, send_file, url_for
import os
import sys
import uuid
import threading
from werkzeug.utils import secure_filename
import cv2
import numpy as np
import tensorflow as tf
from transformers import pipeline, BlipProcessor, BlipForConditionalGeneration
import torch
import nltk
from nltk.tokenize import sent_tokenize
import moviepy.video.fx.all as vfx
import proglog
import time
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

# Fix Windows console encoding so Unicode chars in print() don't crash the app
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

app = Flask(__name__)
# Configurations
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024 # 2 GB limit

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

tasks = {}

# AI Analysis Configuration
# ---- GPU Detection (NVIDIA CUDA or AMD DirectML) --------------------------
GPU_AVAILABLE = False
DEVICE     = torch.device('cpu')
GPU_NAME   = 'CPU'
DEVICE_TAG = 'cpu'   # 'cuda' | 'dml' | 'cpu'

if torch.cuda.is_available():
    # NVIDIA GPU - use CUDA
    GPU_AVAILABLE = True
    DEVICE     = torch.device('cuda')
    GPU_NAME   = torch.cuda.get_device_name(0)
    DEVICE_TAG = 'cuda'
    print(f"[AI] NVIDIA GPU detected: {GPU_NAME} -- using CUDA.")
else:
    # AMD / Intel GPU on Windows - try DirectML
    try:
        import torch_directml
        DEVICE     = torch_directml.device()
        GPU_AVAILABLE = True
        GPU_NAME   = 'AMD/Intel GPU (DirectML)'
        DEVICE_TAG = 'dml'
        print("[AI] AMD GPU detected via DirectML -- BLIP will run on GPU.")
    except ImportError:
        print("[AI] No GPU acceleration found -- running on CPU.")
        print("[AI] For AMD GPU support: pip install torch-directml")

# Pipeline device: HuggingFace accepts 0 (CUDA), torch.device (DML), or -1 (CPU)
if DEVICE_TAG == 'cuda':
    _pipeline_device = 0
elif DEVICE_TAG == 'dml':
    _pipeline_device = DEVICE   # DirectML device object
else:
    _pipeline_device = -1

nlp = pipeline(
    'zero-shot-classification',
    model='facebook/bart-large-mnli',
    device=_pipeline_device
)
sentiment_analyzer = pipeline(
    'sentiment-analysis',
    device=_pipeline_device
)
object_detector = tf.keras.applications.MobileNetV2(weights='imagenet')
nltk.download('punkt')
nltk.download('punkt_tab')

# BLIP Image Captioning Model
print("[AI] Loading BLIP image captioning model...")
try:
    blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = blip_model.to(DEVICE)   # GPU (CUDA or DirectML) or CPU
    blip_model.eval()
    BLIP_AVAILABLE = True
    print(f"[AI] BLIP model ready on {DEVICE_TAG.upper()}  ({GPU_NAME}).")
except Exception as e:
    BLIP_AVAILABLE = False
    blip_processor = None
    blip_model = None
    print(f"[AI] BLIP not available (visual-only fallback): {e}")

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

@app.route('/')
def index():
    return render_template('index.html', video_input_path="")

@app.route('/api/uploads', methods=['GET'])
def list_uploads():
    files = []
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for f in os.listdir(app.config['UPLOAD_FOLDER']):
            if allowed_file(f):
                stat = os.stat(os.path.join(app.config['UPLOAD_FOLDER'], f))
                files.append({
                    'filename': f,
                    'size': stat.st_size,
                    'time': stat.st_mtime
                })
        # Sort by latest first
        files.sort(key=lambda x: x['time'], reverse=True)
    return jsonify({'files': files})

@app.route('/api/load_upload/<filename>', methods=['GET'])
def load_upload(filename):
    if not allowed_file(filename):
        return jsonify({'error': 'Invalid file'}), 400

filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    try:
        clip = VideoFileClip(filepath)
        metadata = {
            'duration': clip.duration,
            'resolution': clip.size,
            'format': filename.rsplit('.', 1)[1].lower()
        }
        clip.close()
        video_input_path = url_for('serve_upload', filename=filename)
        return jsonify({
            'filepath': filename,
            'video_input_path': video_input_path,
            'metadata': metadata,
            'status': 'success'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
                'format': filename.rsplit('.', 1)[1].lower()
            }
            clip.close()
            # Fulfilling the requirement for {{video_input_path}} use
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

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/processed/<path:filename>')
def serve_processed(filename):
    return send_file(os.path.join(app.config['PROCESSED_FOLDER'], filename))

def cleanup_files(input_filename):
    time.sleep(3600)
    try:
        ipath = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        if os.path.exists(ipath):
            os.remove(ipath)
    except:
        pass

# ---------------------------------------------------------------------------
# GPU-ACCELERATED VIDEO PROCESSING HELPERS
# ---------------------------------------------------------------------------

def gpu_analyze_frame_quick(frame):
    """GPU-accelerated visual feature extraction using OpenCV."""
    if len(frame.shape) == 3 and frame.shape[2] == 4:
        frame = frame[:, :, :3]
    rgb = frame.astype(float)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    brightness = (np.mean(r) + np.mean(g) + np.mean(b)) / 3.0
    saturation = np.mean(np.max(rgb, axis=2) - np.min(rgb, axis=2))
    gray = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.uint8)
    edge_density = cv2.Laplacian(gray, cv2.CV_64F).var()
    return {
        'brightness': brightness,
        'saturation': saturation,
        'edge_density': edge_density,
        'mean_color': np.array([np.mean(r), np.mean(g), np.mean(b)]),
    }

def gpu_caption_frame_blip(frame_rgb):
    """
    GPU-accelerated BLIP image captioning.
    Uses DirectML/CUDA for faster inference.
    """
    if not BLIP_AVAILABLE:
        return ""
    try:
        pil_img = Image.fromarray(frame_rgb.astype(np.uint8)).resize((384, 216), Image.LANCZOS)
        inputs = blip_processor(images=pil_img, return_tensors="pt")
        # Move inputs to same device as model
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        with torch.no_grad():
            out = blip_model.generate(
                **inputs,
                max_new_tokens=40,
                num_beams=3,
                early_stopping=True
            )
        return blip_processor.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        print(f"[BLIP] Caption error: {e}")
        return ""

def gpu_analyze_video_for_moments(input_path, task_id=None):
    """
    GPU-accelerated 3-pass pipeline:
      PASS 1 — Fast visual feature extraction at 2fps (GPU-accelerated)
      PASS 2 — BLIP image captioning at 1 frame/5s (GPU-accelerated)
      PASS 3 — Zero-shot NLP excitement scoring on all captions
    """
    def _update(status_text, pct):
        if task_id and task_id in tasks:
            tasks[task_id]['status_text'] = status_text
            tasks[task_id]['percentage'] = pct
            print(f"[AI][{pct}%] {status_text}")

    # Use OpenCV for GPU-accelerated video processing
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise Exception("Error opening video file")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    frame_interval   = 0.5   # 2fps for visual
    caption_interval = 5.0   # 1 caption per 5 seconds

    # =========== PASS 1: GPU-Accelerated Visual Feature Extraction ===========
    _update(f"Pass 1/3: Scanning {duration/60:.1f} min video for visual signals...", 2)
    frames_data, frame_times = [], []
    prev_gray = None
    prev_edge = 0.0
    prev_bright = None
    t = 0.0
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Process every 0.5 seconds
        current_time = frame_idx / fps
        if current_time >= t:
            try:
                feat = gpu_analyze_frame_quick(frame)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                motion = float(np.mean(np.abs(gray.astype(float) - prev_gray.astype(float)))) if prev_gray is not None else 0.0
                prev_gray = gray
                bright_spike = max(0.0, feat['brightness'] - prev_bright) if prev_bright is not None else 0.0
                prev_bright = feat['brightness']
                edge_delta = abs(feat['edge_density'] - prev_edge)
                prev_edge  = feat['edge_density']
                feat.update({'motion': motion, 'bright_spike': bright_spike, 'edge_delta': edge_delta})
                frames_data.append(feat)
                frame_times.append(current_time)
                t += frame_interval
            except Exception as e:
                print(f"[AI] Skip @{current_time:.1f}s: {e}")

        frame_idx += 1

    cap.release()
    n = len(frames_data)
    print(f"[AI] Pass 1 done: {n} frames ({duration:.1f}s video)")

    # =========== PASS 2: GPU-Accelerated BLIP Captioning ======================
    captioned_frames = []   # [(time, caption), ...]
    story_text = None

    if BLIP_AVAILABLE:
        caption_times = list(np.arange(0.0, duration, caption_interval))
        total = len(caption_times)
        _update(f"Pass 2/3: Generating {total} frame captions with BLIP AI...", 5)

        # Use ThreadPoolExecutor for parallel caption generation
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for ci, ct in enumerate(caption_times):
                futures.append(executor.submit(gpu_caption_frame, input_path, ct, width, height))

            for ci, future in enumerate(futures):
                try:
                    result = future.result()
                    if result:
                        captioned_frames.append(result)
                    pct = 5 + int((ci / total) * 50)   # 5% → 55%
                    if ci % 5 == 0 or ci == total - 1:
                        preview = result[1][:70] if result else "(no caption)"
                        _update(f"Captioning [{ci+1}/{total}] @{result[0]:.0f}s: {preview}", pct)
                except Exception as e:
                    print(f"[AI] Caption error: {e}")

        story_text = build_gameplay_story(captioned_frames)
        print(f"[AI] Pass 2 done: {len(captioned_frames)} captions → story built.")
        print("[AI] === GAMEPLAY STORY EXCERPT ===")
        for line in story_text.split('\n')[:10]:
            print(f"  {line}")
    else:
        _update("BLIP not available — using visual-only analysis", 55)

    # =========== PASS 3: GPU-Accelerated NLP Excitement Scoring ===============
    nlp_frame_scores = np.zeros(n)

    if captioned_frames:
        _update(f"Pass 3/3: Scoring {len(captioned_frames)} captions for excitement...", 57)
        nlp_scores = score_captions_for_excitement([cap for _, cap in captioned_frames])
        nlp_times  = [t_ for t_, _ in captioned_frames]

        # Interpolate NLP scores back to the 2fps frame timeline
        for i, ft in enumerate(frame_times):
            idx = np.searchsorted(nlp_times, ft)
            if idx == 0:
                nlp_frame_scores[i] = nlp_scores[0] if nlp_scores else 0.0
            elif idx >= len(nlp_times):
                nlp_frame_scores[i] = nlp_scores[-1] if nlp_scores else 0.0
            else:
                t0, t1 = nlp_times[idx-1], nlp_times[idx]
                s0, s1 = nlp_scores[idx-1], nlp_scores[idx]
                alpha = (ft - t0) / (t1 - t0) if t1 != t0 else 0.5
                nlp_frame_scores[i] = s0 + alpha * (s1 - s0)

        _update("NLP scoring done. Finding excitement peaks...", 70)

    if n < 4:
        return [], frame_times, frames_data, captioned_frames, story_text

    # =========== COMBINE SIGNALS & FIND PEAKS ================
    def norm(arr):
        mx = arr.max()
        return arr / mx if mx > 0 else arr

    visual_score = (
        0.45 * norm(np.array([f['motion']       for f in frames_data])) +
        0.25 * norm(np.array([f['bright_spike'] for f in frames_data])) +
        0.15 * norm(np.array([f['saturation']   for f in frames_data])) +
        0.15 * norm(np.array([f['edge_delta']   for f in frames_data]))
    )

    # Blend: 60% NLP text understanding + 40% visual signals
    if captioned_frames and nlp_frame_scores.max() > 0:
        excitement = 0.40 * visual_score + 0.60 * nlp_frame_scores
        print("[AI] Blending: 60% NLP + 40% visual.")
    else:
        excitement = visual_score
        print("[AI] Using visual-only score (BLIP unavailable).")

    # Gaussian smoothing
    win    = 10
    kernel = np.exp(-0.5 * np.linspace(-2, 2, win) ** 2)
    kernel /= kernel.sum()
    smoothed  = np.convolve(excitement, kernel, mode='same')
    threshold = smoothed.mean() + 0.6 * smoothed.std()
    print(f"[AI] threshold={threshold:.3f}  mean={smoothed.mean():.3f}  std={smoothed.std():.3f}")

    # Clip window parameters
    clip_pre     = 8    # seconds of context before peak (build-up)
    clip_post    = 20   # seconds after peak (payoff)
    min_clip_dur = 20   # minimum short-video length in seconds

    # Find contiguous above-threshold regions → pick highest frame as peak
    in_region = False
    rs_idx    = 0
    regions   = []
    for i in range(n):
        if smoothed[i] >= threshold:
            if not in_region:
                in_region = True
                rs_idx = i
        else:
            if in_region:
                seg = smoothed[rs_idx:i]
                pk  = rs_idx + int(np.argmax(seg))
                regions.append((rs_idx, i-1, float(smoothed[pk]), pk))
                in_region = False
    if in_region:
        seg = smoothed[rs_idx:]
        pk  = rs_idx + int(np.argmax(seg))
        regions.append((rs_idx, n-1, float(smoothed[pk]), pk))

    # Highest excitement first
    regions.sort(key=lambda x: x[2], reverse=True)

    satisfying_moments = []
    used_ranges = []

    for (rs, re, peak_score, pk_idx) in regions:
        t_peak  = frame_times[pk_idx]
        t_start = max(0.0, t_peak - clip_pre)
        t_end   = min(duration, t_peak + clip_post)

        # Pad to minimum duration
        if (t_end - t_start) < min_clip_dur:
            deficit = min_clip_dur - (t_end - t_start)
            t_start = max(0.0, t_start - deficit / 2)
            t_end   = min(duration, t_start + min_clip_dur)

        # Skip overlapping moments
        if any(not (t_end <= us or t_start >= ue) for us, ue in used_ranges):
            continue

        # Build moment description from captions in this window (ASCII-safe)
        moment_captions = [cap for (ct, cap) in captioned_frames if t_start <= ct <= t_end]
        description = " | ".join(dict.fromkeys(moment_captions[:6])) if moment_captions \
                      else "High-intensity action sequence detected."

        moment = {
            'start':         t_start,
            'end':           t_end,
            'peak_time':     t_peak,
            'avg_intensity': peak_score,
            'avg_motion':    peak_score,
            'frames':        list(range(rs, re+1)),
            'description':   description,
        }
        satisfying_moments.append(moment)
        used_ranges.append((t_start, t_end))
        print(f"[AI] Moment {len(satisfying_moments)}: {t_start:.1f}s-{t_end:.1f}s "
              f"(peak@{t_peak:.1f}s score={peak_score:.3f})")
        desc_preview = description[:100].encode('ascii', errors='replace').decode('ascii')
        print(f"      Story: {desc_preview}")

    satisfying_moments.sort(key=lambda x: x['start'])
    print(f"[AI] Pipeline complete -> {len(satisfying_moments)} moments found.")
    return satisfying_moments, frame_times, frames_data, captioned_frames, story_text

def gpu_caption_frame(input_path, time, width, height):
    """Helper function to caption a specific frame using GPU."""
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    # Resize to match BLIP input size
    frame_rgb = cv2.resize(frame, (384, 216))
    caption = gpu_caption_frame_blip(frame_rgb)
    return (time, caption)

def process_video_task_gpu(task_id, input_filename, operations):
    with app.app_context():
        try:
            tasks[task_id]['status'] = 'processing'
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
            output_dir = os.path.join(app.config['PROCESSED_FOLDER'], task_id)
            os.makedirs(output_dir, exist_ok=True)

            if operations.get('ai_analysis', False):
                tasks[task_id]['status'] = 'analyzing'
                tasks[task_id]['status_text'] = 'Starting GPU-accelerated AI analysis pipeline...'
                tasks[task_id]['percentage'] = 1

                satisfying_moments, frame_times, frames_data, captioned_frames, story_text = \
                    gpu_analyze_video_for_moments(input_path, task_id=task_id)

                if not satisfying_moments:
                    tasks[task_id]['status'] = 'error'
                    tasks[task_id]['error'] = 'No satisfying moments found. Try a different video or lower the threshold.'
                    return

                game_type = operations.get('game_type', 'unknown')
                metadata  = generate_metadata_from_moments(satisfying_moments, story_text, game_type)

                tasks[task_id]['status'] = 'generating'
                tasks[task_id]['status_text'] = f'Rendering {len(satisfying_moments)} short clips with GPU acceleration...'
                tasks[task_id]['percentage'] = 80
                clips = generate_short_clips_gpu(input_path, satisfying_moments, output_dir)

                rel_clips = [f"/processed/{task_id}/moment_{i+1}.mp4" for i in range(len(clips))]
                tasks[task_id]['status']              = 'completed'
                tasks[task_id]['percentage']          = 100
                tasks[task_id]['result_path']         = f"/processed/{task_id}/"
                tasks[task_id]['result_files']        = rel_clips
                tasks[task_id]['metadata']            = metadata
                tasks[task_id]['satisfying_moments']  = satisfying_moments
                tasks[task_id]['story']               = story_text
                tasks[task_id]['ai_analysis']         = True
            else:
                # Original processing logic
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

                logger = CustomProgressBar(task_id)
                clip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    logger=logger,
                    preset='ultrafast'
                )
                clip.close()

                threading.Thread(target=cleanup_files, args=(input_filename,)).start()

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

    thread = threading.Thread(target=process_video_task_gpu, args=(task_id, filename, operations))
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'success', 'ai_analysis': operations.get('ai_analysis', False)})

@app.route('/status/<task_id>')
def task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.get('status') == 'analyzing':
        # Return the live status_text set by the analysis pipeline for detailed progress
        pass
    elif task.get('status') == 'generating':
        if not task.get('status_text'):
            task['status_text'] = 'Rendering short video clips...'
    elif task.get('status') == 'completed':
        task['status_text'] = 'All done! Your AI-curated shorts are ready.'

    return jsonify(task)

if __name__ == '__main__':
    app.run(debug=True, port=8000)