// ============================================================
// State
// ============================================================
let currentFilename = null;
let videoDuration = 0;

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const videoInput = document.getElementById('video-input');

    // Load previously uploaded files
    loadPreviousUploads();
    
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
    document.getElementById('ai-generate-btn').addEventListener('click', generateAIShorts);
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

    // Update FPS display when slider changes
    const fpsSlider = document.getElementById('ai-fps-slider');
    const fpsDisplay = document.getElementById('ai-fps-display');
    if (fpsSlider && fpsDisplay) {
        fpsSlider.addEventListener('input', function() {
            const fpsValue = parseFloat(this.value);
            fpsDisplay.textContent = fpsValue + ' FPS';

            // Show frame count estimate if video is loaded
            if (videoDuration > 0) {
                const estimatedFrames = Math.round(videoDuration * fpsValue);
                const helpText = document.getElementById('ai-fps-help');
                if (helpText) {
                    helpText.textContent = `~${estimatedFrames.toLocaleString()} frames for this video`;
                }
            }
        });
    }
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

// ============================================================
// Previously Uploaded Files
// ============================================================

function loadPreviousUploads() {
    fetch('/uploads/list')
        .then(response => response.json())
        .then(data => {
            if (data.files && data.files.length > 0) {
                displayPreviousFiles(data.files);
            }
        })
        .catch(error => {
            console.error('Error loading previous uploads:', error);
        });
}

function displayPreviousFiles(files) {
    const container = document.getElementById('previous-files-container');
    const listElement = document.getElementById('previous-files-list');

    listElement.innerHTML = '';

    files.forEach(file => {
        const fileItem = createFileListItem(file);
        listElement.appendChild(fileItem);
    });

    container.classList.remove('d-none');
}

function createFileListItem(file) {
    const item = document.createElement('a');
    item.href = '#';
    item.className = 'list-group-item list-group-item-action bg-surface border-darker text-white hover-highlight';
    item.onclick = (e) => {
        e.preventDefault();
        selectPreviousFile(file);
    };

    // Format duration
    let durationStr = 'Unknown';
    let resolutionStr = 'Unknown';
    if (file.metadata) {
        const dur = file.metadata.duration;
        durationStr = new Date(dur * 1000).toISOString().substr(11, 8);
        resolutionStr = `${file.metadata.resolution[0]}x${file.metadata.resolution[1]}`;
    }

    // Format modified date
    const modDate = new Date(file.modified * 1000);
    const dateStr = modDate.toLocaleDateString() + ' ' + modDate.toLocaleTimeString();

    item.innerHTML = `
        <div class="d-flex justify-content-between align-items-start">
            <div class="flex-grow-1">
                <div class="d-flex align-items-center mb-2">
                    <i class="bi bi-file-play-fill text-primary me-2 fs-5"></i>
                    <h6 class="mb-0 fw-semibold">${file.filename}</h6>
                </div>
                <div class="d-flex gap-3 small text-muted">
                    <span><i class="bi bi-clock me-1"></i> ${durationStr}</span>
                    <span><i class="bi bi-aspect-ratio me-1"></i> ${resolutionStr}</span>
                    <span><i class="bi bi-hdd me-1"></i> ${file.size_mb} MB</span>
                </div>
            </div>
            <div class="text-end text-muted small">
                <div><i class="bi bi-calendar3 me-1"></i> ${dateStr}</div>
                <div class="mt-1">
                    <span class="badge bg-primary">Click to use</span>
                </div>
            </div>
        </div>
    `;

    return item;
}

function selectPreviousFile(file) {
    // Set current filename
    currentFilename = file.filename;

    // Create metadata object
    const metadata = {
        duration: file.metadata ? file.metadata.duration : 0,
        resolution: file.metadata ? file.metadata.resolution : [0, 0],
        fps: file.metadata ? file.metadata.fps : 0,
        format: file.filename.split('.').pop().toUpperCase()
    };

    // Setup editor with the selected file
    setupEditor(file.url, metadata);
}

// ============================================================
// AI Shorts Generator
// ============================================================

function generateAIShorts() {
    if (!currentFilename) {
        alert('No video file loaded!');
        return;
    }

    // Get FPS value from slider
    const fps = parseInt(document.getElementById('ai-fps-slider').value) || 2;

    // Disable button
    const btn = document.getElementById('ai-generate-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Starting AI Pipeline...';

    // Hide editor, show AI progress
    document.getElementById('editor-section').classList.add('d-none');
    document.getElementById('ai-progress-section').classList.remove('d-none');

    // Reset AI progress
    resetAIProgress();

    // Start AI pipeline
    fetch('/generate_ai_shorts', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            filename: currentFilename,
            fps: fps
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-stars me-2"></i> Generate AI Shorts';
            document.getElementById('editor-section').classList.remove('d-none');
            document.getElementById('ai-progress-section').classList.add('d-none');
        } else {
            // Start polling for progress
            pollAIProgress(data.task_id);
        }
    })
    .catch(error => {
        alert('Error starting AI pipeline: ' + error);
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-stars me-2"></i> Generate AI Shorts';
        document.getElementById('editor-section').classList.remove('d-none');
        document.getElementById('ai-progress-section').classList.add('d-none');
    });
}

function resetAIProgress() {
    // Reset all progress indicators
    updateAIStep('extracting_frames', 0, 'Initializing...');
}

function pollAIProgress(taskId) {
    const interval = setInterval(() => {
        fetch('/status/' + taskId)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                clearInterval(interval);
                alert('Error: ' + data.error);
                document.getElementById('ai-generate-btn').disabled = false;
                document.getElementById('ai-generate-btn').innerHTML = '<i class="bi bi-stars me-2"></i> Generate AI Shorts';
                return;
            }

            // Update progress based on current step
            const step = data.step || data.status;
            const percentage = data.percentage || 0;
            const message = data.step_message || data.status;

            updateAIStep(step, percentage, message);

            // Check if completed
            if (data.status === 'completed') {
                clearInterval(interval);
                showAIResults(data);
            } else if (data.status === 'error') {
                clearInterval(interval);
                alert('AI processing failed: ' + (data.error || 'Unknown error'));
                document.getElementById('ai-generate-btn').disabled = false;
                document.getElementById('ai-generate-btn').innerHTML = '<i class="bi bi-stars me-2"></i> Generate AI Shorts';
            }
        })
        .catch(error => {
            console.error('Error polling status:', error);
        });
    }, 2000); // Poll every 2 seconds
}

function updateAIStep(step, percentage, message) {
    // Update step indicators based on current step
    const steps = ['extracting_frames', 'analyzing_frames', 'generating_story', 'detecting_moments', 'generating_shorts', 'generating_metadata'];

    // Update progress bar
    document.getElementById('ai-overall-progress').style.width = percentage + '%';
    document.getElementById('ai-overall-percentage').innerText = percentage + '%';

    // Update status message
    const statusText = document.getElementById('ai-status-text');
    if (statusText) {
        statusText.innerText = message || 'Processing...';
    }

    // Update step-specific UI elements (if you have them in HTML)
    // This is a placeholder - you can enhance based on your HTML structure
}

function showAIResults(data) {
    // Hide progress section
    document.getElementById('ai-progress-section').classList.add('d-none');

    // Show results section
    document.getElementById('ai-results-section').classList.remove('d-none');

    // Load and display shorts
    if (data.shorts && data.shorts.length > 0) {
        displayShorts(data.shorts);
    }

    // Show story if available
    if (data.story_path) {
        loadStory(data.story_path);
    }

    // Update stats
    if (data.stats) {
        updateStats(data.stats);
    }
}

function displayShorts(shorts) {
    const grid = document.getElementById('shorts-grid');
    if (!grid) return;

    grid.innerHTML = '';

    shorts.forEach((short, index) => {
        const card = createShortCard(short, index);
        grid.appendChild(card);
    });
}

function createShortCard(short, index) {
    const card = document.createElement('div');
    card.className = 'short-card';

    const moment = short.moment || {};
    const metadata = short.metadata || {};

    card.innerHTML = `
        <div class="short-card-inner">
            <div class="short-thumbnail" style="background-image: url('${short.web_thumbnail_path || ''}')">
                <video class="short-preview" loop muted>
                    <source src="${short.web_video_path}" type="video/mp4">
                </video>
                <div class="virality-badge">${moment.virality_score || 5}/10</div>
            </div>
            <div class="short-info">
                <span class="category-badge badge-${(moment.category || 'intense').toLowerCase()}">${moment.category || 'INTENSE'}</span>
                <span class="duration-badge">${short.duration || 0}s</span>
                <h6 class="short-title">${metadata.title || 'Untitled'}</h6>
            </div>
        </div>
    `;

    // Add hover preview
    const videoEl = card.querySelector('.short-preview');
    card.addEventListener('mouseenter', () => {
        if (videoEl) videoEl.play();
    });
    card.addEventListener('mouseleave', () => {
        if (videoEl) {
            videoEl.pause();
            videoEl.currentTime = 0;
        }
    });

    // Add click handler to show details
    card.addEventListener('click', () => showShortDetails(short, index));

    return card;
}

function showShortDetails(short, index) {
    // Show modal with short details
    // This is a placeholder - implement based on your modal structure
    console.log('Show short details:', short);
}

function loadStory(storyPath) {
    // Load and display story
    // Placeholder implementation
    console.log('Load story from:', storyPath);
}

function updateStats(stats) {
    // Update statistics display
    // Placeholder implementation
    console.log('Update stats:', stats);
}
