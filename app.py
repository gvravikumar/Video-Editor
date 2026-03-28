from flask import Flask, render_template, request, jsonify, send_file, url_for
import os
import uuid
import threading
from werkzeug.utils import secure_filename
from moviepy.editor import VideoFileClip
import moviepy.video.fx.all as vfx
import proglog
import time

app = Flask(__name__)
# Configurations
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 # 500 MB limit

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

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

@app.route('/')
def index():
    return render_template('index.html', video_input_path="")

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

@app.route('/processed/<filename>')
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
    
    thread = threading.Thread(target=process_video_task, args=(task_id, filename, operations))
    thread.start()
    
    return jsonify({'task_id': task_id, 'status': 'success'})

@app.route('/status/<task_id>')
def task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)

if __name__ == '__main__':
    app.run(debug=True, port=8000)
