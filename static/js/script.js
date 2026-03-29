// ============================================================
// State
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const videoInput = document.getElementById('video-input');
    
    // Drag & Drop Handlers
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFiles(files[0]);
        }
    });

    videoInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            handleFiles(this.files[0]);
        }
    });

    document.getElementById('process-btn').addEventListener('click', processVideo);
    document.getElementById('restart-btn').addEventListener('click', () => {
        window.location.reload();
    });

    // Sync speed playback switch with video player for live preview
    document.getElementById('speed-up-switch').addEventListener('change', function() {
        const player = document.getElementById('video-player');
        if (this.checked) {
            player.playbackRate = 2.0;
        } else {
            player.playbackRate = 1.0;
        }
    });
});

function handleFiles(file) {
    if (!file.type.match('video.*')) {
        alert("Please upload a supported video file.");
        return;
    }
    
    // UI Updates for upload
    document.getElementById('upload-progress-container').classList.remove('d-none');
    
    const formData = new FormData();
    formData.append('video', file);
    
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload', true);
    
    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
            const percentComplete = Math.round((e.loaded / e.total) * 100);
            document.getElementById('upload-progress').style.width = percentComplete + '%';
            document.getElementById('upload-percent').innerText = percentComplete + '%';
            document.getElementById('upload-progress').setAttribute('aria-valuenow', percentComplete);
        }
    };
    
    xhr.onload = function() {
        if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            currentFilename = response.filepath;
            
            // Setup Editor
            setupEditor(response.video_input_path, response.metadata);
        } else {
            const response = JSON.parse(xhr.responseText);
            alert("Upload failed: " + (response.error || "Unknown error"));
            document.getElementById('upload-progress-container').classList.add('d-none');
        }
    };
    
    xhr.onerror = function() {
        alert("Upload failed. Please check your connection.");
        document.getElementById('upload-progress-container').classList.add('d-none');
    };
    
    xhr.send(formData);
}

function setupEditor(videoPath, metadata) {
    document.getElementById('upload-section').classList.add('d-none');
    document.getElementById('editor-section').classList.remove('d-none');
    
    const videoSource = document.getElementById('video-source');
    const player = document.getElementById('video-player');
    
    videoSource.src = videoPath;
    player.load();
    
    videoDuration = metadata.duration;
    
    // Formatting metadata
    const res = metadata.resolution;
    const durStr = new Date(metadata.duration * 1000).toISOString().substr(11, 8);
    const metaHtml = `
        <span class="badge bg-dark rounded-pill shadow-sm"><i class="bi bi-clock-history me-1"></i> ${durStr}</span> 
        <span class="badge bg-dark rounded-pill shadow-sm"><i class="bi bi-aspect-ratio me-1"></i> ${res[0]}x${res[1]}</span> 
        <span class="badge bg-dark rounded-pill shadow-sm text-uppercase"><i class="bi bi-file-play me-1"></i> ${metadata.format}</span>
    `;
    document.getElementById('video-metadata').innerHTML = metaHtml;
    
    // Initialize Inputs
    document.getElementById('start-time').max = metadata.duration;
    document.getElementById('start-time').value = 0;
    
    document.getElementById('end-time').max = metadata.duration;
    document.getElementById('end-time').value = metadata.duration.toFixed(2);
    
    // Player events integration
    player.addEventListener('play', () => updatePlayPauseBtn(true));
    player.addEventListener('pause', () => updatePlayPauseBtn(false));
}

function updatePlayPauseBtn(isPlaying) {
    const btn = document.getElementById('play-pause-btn');
    if(isPlaying) {
        btn.innerHTML = '<i class="bi bi-pause-fill fs-5"></i>';
    } else {
        btn.innerHTML = '<i class="bi bi-play-fill fs-5"></i>';
    }
}

function togglePlayPause() {
    const player = document.getElementById('video-player');
    if (player.paused) {
        player.play();
    } else {
        player.pause();
    }
}

function scrubVideo(seconds) {
    const player = document.getElementById('video-player');
    let newTime = player.currentTime + seconds;
    if (newTime < 0) newTime = 0;
    if (newTime > player.duration) newTime = player.duration;
    player.currentTime = newTime;
}

function setStartTime() {
    const player = document.getElementById('video-player');
    document.getElementById('start-time').value = player.currentTime.toFixed(2);
    // Visual feedback
    const btn = document.querySelector('button[onclick="setStartTime()"]');
    flashButtonFeedback(btn);
}

function setEndTime() {
    const player = document.getElementById('video-player');
    document.getElementById('end-time').value = player.currentTime.toFixed(2);
    // Visual feedback
    const btn = document.querySelector('button[onclick="setEndTime()"]');
    flashButtonFeedback(btn);
}

function flashButtonFeedback(btn) {
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-check2"></i> Done';
    btn.classList.add('btn-info');
    btn.classList.remove('btn-outline-info');
    setTimeout(() => {
        btn.innerHTML = originalText;
        btn.classList.remove('btn-info');
        btn.classList.add('btn-outline-info');
    }, 1000);
}

function processVideo() {
    if (!currentFilename) return;
    
    const startTime = parseFloat(document.getElementById('start-time').value);
    const endTime = parseFloat(document.getElementById('end-time').value);
    const speedUp = document.getElementById('speed-up-switch').checked;
    
    // Basic validation
    if (startTime >= endTime) {
        alert("Ops! Start time must be less than end time.");
        return;
    }
    
    const operations = {
        clip: {
            start: startTime,
            end: endTime
        },
        speed_up: speedUp,
        speed_factor: 2.0
    };
    
    // UI Update
    document.getElementById('process-btn').disabled = true;
    document.getElementById('process-progress-container').classList.remove('d-none');
    document.getElementById('download-container').classList.add('d-none');
    
    // Hide process success/error icons
    document.getElementById('process-spinner').classList.remove('d-none');
    document.getElementById('process-success-icon').classList.add('d-none');
    document.getElementById('process-percentage').classList.remove('text-success');
    document.getElementById('process-percentage').classList.add('text-primary');
    document.getElementById('process-progress').classList.remove('bg-gradient-success');
    document.getElementById('process-progress').classList.add('bg-gradient-primary');
    
    document.getElementById('process-progress').style.width = '0%';
    document.getElementById('process-percentage').innerText = '0%';
    document.getElementById('process-status-text').innerText = "Initializing process...";
    
    fetch('/process', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            filename: currentFilename,
            operations: operations
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showErrorStatus(data.error);
        } else {
            pollTaskStatus(data.task_id);
        }
    })
    .catch(error => {
        showErrorStatus("Error starting process.");
    });
}

function showErrorStatus(msg) {
    document.getElementById('process-status-text').innerText = "Error!";
    document.getElementById('process-spinner').classList.add('d-none');
    alert(msg);
    document.getElementById('process-btn').disabled = false;
}

function pollTaskStatus(taskId) {
    const interval = setInterval(() => {
        fetch('/status/' + taskId)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                clearInterval(interval);
                showErrorStatus(data.error);
                return;
            }
            
            const progress = document.getElementById('process-progress');
            const pctText = document.getElementById('process-percentage');
            const statusText = document.getElementById('process-status-text');
            
            if (data.percentage) {
                progress.style.width = data.percentage + '%';
                pctText.innerText = data.percentage + '%';
            }
            
            if (data.status === 'processing') {
                statusText.innerText = "Rendering Video... this. might take a while.";
            } else if (data.status === 'completed') {
                clearInterval(interval);
                
                // Success styling
                progress.style.width = '100%';
                pctText.innerText = '100%';
                statusText.innerText = "Processing Complete!";
                
                progress.classList.remove('progress-bar-animated', 'bg-gradient-primary');
                progress.classList.add('bg-success');
                pctText.classList.remove('text-primary');
                pctText.classList.add('text-success');
                
                document.getElementById('process-spinner').classList.add('d-none');
                document.getElementById('process-success-icon').classList.remove('d-none');
                
                document.getElementById('download-container').classList.remove('d-none');
                document.getElementById('download-btn').href = data.result_path;
                
                // Allow processing again maybe? Or force to download
                document.getElementById('process-btn').disabled = false;
                document.getElementById('process-btn').innerHTML = '<i class="bi bi-arrow-clockwise me-2 fs-5"></i> Process Again';
            } else if (data.status === 'error') {
                clearInterval(interval);
                showErrorStatus(data.error);
            }
        })
        .catch(error => {
            console.error(error);
        });
    }, 1500);
}
