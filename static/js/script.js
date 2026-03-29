// ============================================================
// State
// ============================================================
let currentFilename = null;
let currentTaskId = null;
let videoDuration = 0;

// ============================================================
// localStorage helpers — persist task_id ↔ filename mapping
// ============================================================

function saveTaskToStorage(filename, taskId) {
    try {
        const map = JSON.parse(localStorage.getItem('vsTaskMap') || '{}');
        map[filename] = taskId;
        // Keep only last 30 entries
        const keys = Object.keys(map);
        if (keys.length > 30) keys.slice(0, keys.length - 30).forEach(k => delete map[k]);
        localStorage.setItem('vsTaskMap', JSON.stringify(map));
        localStorage.setItem('vsLastTaskId', taskId);
        localStorage.setItem('vsLastFilename', filename);
    } catch (e) {}
}

function getTaskIdForFile(filename) {
    try {
        const map = JSON.parse(localStorage.getItem('vsTaskMap') || '{}');
        return map[filename] || null;
    } catch (e) { return null; }
}

function getLastSession() {
    return {
        taskId: localStorage.getItem('vsLastTaskId'),
        filename: localStorage.getItem('vsLastFilename')
    };
}

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const videoInput = document.getElementById('video-input');

    // Load previously uploaded files
    loadPreviousUploads();

    // Check if there's an in-progress or completed task to restore
    checkForExistingTasks();
    
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
            updateFpsEstimates(fpsValue);
        });
    }

    // Fetch system info and show device badge
    fetch('/system/info')
        .then(r => r.json())
        .then(info => {
            const badge = document.getElementById('system-badge');
            const nameEl = document.getElementById('device-name');
            if (badge && nameEl) {
                nameEl.textContent = info.device_name;
                badge.classList.remove('d-none');
            }
        })
        .catch(() => {}); // silently ignore if unavailable
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

    // Update FPS estimates now that duration is known
    const fpsSlider = document.getElementById('ai-fps-slider');
    if (fpsSlider) {
        updateFpsEstimates(parseFloat(fpsSlider.value));
    }

    // Formatting metadata
    const res = metadata.resolution;
    const durStr = new Date(metadata.duration * 1000).toISOString().substring(11, 19);
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
    .catch(() => {
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

// All loaded files — kept in memory so the search filter can work without re-fetching
let _allUploadedFiles = [];

function loadPreviousUploads() {
    const container = document.getElementById('previous-files-container');
    const loadingEl = document.getElementById('uploads-loading');
    const listEl = document.getElementById('previous-files-list');

    // Show loading skeleton while fetching
    if (container) container.classList.remove('d-none');
    if (loadingEl) loadingEl.classList.remove('d-none');
    if (listEl) listEl.innerHTML = '';

    fetch('/uploads/list')
        .then(response => response.json())
        .then(data => {
            if (loadingEl) loadingEl.classList.add('d-none');
            if (data.error) {
                console.error('Error loading uploads:', data.error);
                if (container) container.classList.add('d-none');
                return;
            }
            _allUploadedFiles = data.files || [];
            if (_allUploadedFiles.length > 0) {
                displayPreviousFiles(_allUploadedFiles);
            } else {
                if (container) container.classList.add('d-none');
            }
        })
        .catch(error => {
            if (loadingEl) loadingEl.classList.add('d-none');
            if (container) container.classList.add('d-none');
            console.error('Error loading previous uploads:', error);
        });
}

function displayPreviousFiles(files) {
    const container = document.getElementById('previous-files-container');
    const listElement = document.getElementById('previous-files-list');
    const countEl = document.getElementById('uploads-count');
    const emptyEl = document.getElementById('uploads-empty');
    const searchEl = document.getElementById('uploads-search');

    if (countEl) countEl.textContent = `${files.length} video${files.length !== 1 ? 's' : ''}`;
    if (emptyEl) emptyEl.classList.add('d-none');

    listElement.innerHTML = '';
    files.forEach(file => {
        listElement.appendChild(createFileListItem(file));
    });

    if (container) container.classList.remove('d-none');

    // Reset search box when list is refreshed
    if (searchEl) searchEl.value = '';
}

function filterUploads(query) {
    const listEl = document.getElementById('previous-files-list');
    const emptyEl = document.getElementById('uploads-empty');
    const countEl = document.getElementById('uploads-count');
    const q = query.trim().toLowerCase();

    const matched = q
        ? _allUploadedFiles.filter(f => f.filename.toLowerCase().includes(q))
        : _allUploadedFiles;

    listEl.innerHTML = '';
    matched.forEach(file => listEl.appendChild(createFileListItem(file)));

    if (countEl) countEl.textContent = `${matched.length} / ${_allUploadedFiles.length} video${_allUploadedFiles.length !== 1 ? 's' : ''}`;
    if (emptyEl) emptyEl.classList.toggle('d-none', matched.length > 0);
}

function taskStatusBadge(status) {
    const map = {
        completed: '<span class="badge bg-success">Done</span>',
        interrupted: '<span class="badge bg-warning text-dark">Interrupted</span>',
        error: '<span class="badge bg-danger">Error</span>',
        extracting_frames: '<span class="badge bg-primary">Extracting</span>',
        analyzing_frames: '<span class="badge bg-primary">Analyzing</span>',
        generating_story: '<span class="badge bg-primary">Story</span>',
        generating_shorts: '<span class="badge bg-primary">Shorts</span>',
        generating_metadata: '<span class="badge bg-primary">Metadata</span>',
        queued: '<span class="badge bg-secondary">Queued</span>'
    };
    return map[status] || '<span class="badge bg-primary">Click to use</span>';
}

function createFileListItem(file) {
    const item = document.createElement('a');
    item.href = '#';
    item.className = 'list-group-item list-group-item-action bg-surface border-darker text-white hover-highlight';
    item.onclick = (e) => {
        e.preventDefault();
        selectPreviousFile(file);
    };

    let durationStr = 'Unknown';
    let resolutionStr = 'Unknown';
    if (file.metadata) {
        const dur = file.metadata.duration;
        durationStr = new Date(dur * 1000).toISOString().substring(11, 19);
        resolutionStr = `${file.metadata.resolution[0]}x${file.metadata.resolution[1]}`;
    }

    const modDate = new Date(file.modified * 1000);
    const dateStr = modDate.toLocaleDateString() + ' ' + modDate.toLocaleTimeString();
    const statusBadge = file.task_status
        ? taskStatusBadge(file.task_status)
        : '<span class="badge bg-primary">Click to use</span>';

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
                <div class="mt-1">${statusBadge}</div>
            </div>
        </div>
    `;

    return item;
}

async function selectPreviousFile(file) {
    currentFilename = file.filename;

    const metadata = {
        duration: file.metadata ? file.metadata.duration : 0,
        resolution: file.metadata ? file.metadata.resolution : [0, 0],
        fps: file.metadata ? file.metadata.fps : 0,
        format: file.filename.split('.').pop().toUpperCase()
    };

    // Check if this file already has a task (from backend task_status or localStorage)
    const taskId = file.task_id || getTaskIdForFile(file.filename);

    if (taskId) {
        try {
            const resp = await fetch('/ai/status/' + taskId);
            const data = await resp.json();
            if (!data.error) {
                if (data.status === 'completed') {
                    setupEditor(file.url, metadata);
                    if (confirm('AI processing results are available for this video.\nView results? (Cancel to start fresh)')) {
                        const results = await fetch('/ai/results/' + taskId).then(r => r.json());
                        showAIResultsFromAPI(results);
                        return;
                    }
                } else if (data.status === 'interrupted' || data.resumable) {
                    setupEditor(file.url, metadata);
                    if (confirm(`AI processing was interrupted at ${data.percentage || 0}%.\nResume from last checkpoint? (Cancel to start fresh)`)) {
                        resumeTask(taskId);
                        return;
                    }
                } else if (['queued', 'extracting_frames', 'analyzing_frames',
                             'generating_story', 'generating_shorts', 'generating_metadata'].includes(data.status)) {
                    setupEditor(file.url, metadata);
                    if (confirm(`AI processing is in progress (${data.percentage || 0}%).\nReconnect to live progress?`)) {
                        currentTaskId = taskId;
                        document.getElementById('video-column').classList.add('d-none');
                        document.getElementById('controls-column').classList.add('d-none');
                        document.getElementById('ai-progress-container').classList.remove('d-none');
                        resetAIProgress();
                        pollAIProgress(taskId);
                        return;
                    }
                }
            }
        } catch (e) { /* ignore, fall through to normal editor */ }
    }

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

    // Hide video/controls columns only — keep editor-section visible so ai-progress-container shows
    document.getElementById('video-column').classList.add('d-none');
    document.getElementById('controls-column').classList.add('d-none');
    document.getElementById('ai-progress-container').classList.remove('d-none');

    // Reset AI progress
    resetAIProgress();

    // Start AI pipeline via persistent /ai/start endpoint
    fetch('/ai/start', {
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
            document.getElementById('video-column').classList.remove('d-none');
            document.getElementById('controls-column').classList.remove('d-none');
            document.getElementById('ai-progress-container').classList.add('d-none');
        } else {
            currentTaskId = data.task_id;
            saveTaskToStorage(currentFilename, data.task_id);
            pollAIProgress(data.task_id);
        }
    })
    .catch(error => {
        alert('Error starting AI pipeline: ' + error);
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-stars me-2"></i> Generate AI Shorts';
        document.getElementById('video-column').classList.remove('d-none');
        document.getElementById('controls-column').classList.remove('d-none');
        document.getElementById('ai-progress-container').classList.add('d-none');
    });
}

function resetAIProgress() {
    // Reset all progress indicators
    updateAIStep('extracting_frames', 0, 'Initializing...');
}

function pollAIProgress(taskId) {
    const interval = setInterval(() => {
        fetch('/ai/status/' + taskId)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                clearInterval(interval);
                resetAIGenerateBtn();
                alert('Error: ' + data.error);
                return;
            }

            const step = data.step || data.status;
            const percentage = data.percentage || 0;
            const message = data.step_message || data.status;

            updateAIStep(step, percentage, message);

            if (data.status === 'completed') {
                clearInterval(interval);
                // Fetch full results (status endpoint only has summary counts)
                fetch('/ai/results/' + taskId)
                    .then(r => r.json())
                    .then(results => showAIResultsFromAPI(results))
                    .catch(() => {
                        alert('Pipeline finished but could not load results. Refresh and select the video again.');
                        resetAIGenerateBtn();
                    });
            } else if (data.status === 'interrupted') {
                clearInterval(interval);
                showResumePrompt(taskId, 'Processing was interrupted by a server restart.');
            } else if (data.status === 'error') {
                clearInterval(interval);
                resetAIGenerateBtn();
                alert('AI processing failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(() => {
            // Network error / server restart — keep polling; server will mark task interrupted
        });
    }, 2000);
}

function resetAIGenerateBtn() {
    const btn = document.getElementById('ai-generate-btn');
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-stars me-2"></i> Generate AI Shorts';
    document.getElementById('video-column').classList.remove('d-none');
    document.getElementById('controls-column').classList.remove('d-none');
    document.getElementById('ai-progress-container').classList.add('d-none');
}

function updateAIStep(step, percentage, message) {
    // Update progress bar
    const progressBar = document.getElementById('ai-progress');
    const percentageDisplay = document.getElementById('ai-percentage');
    const statusText = document.getElementById('ai-status-text');
    const stepText = document.getElementById('ai-step-text');

    if (progressBar) {
        progressBar.style.width = percentage + '%';
    }

    if (percentageDisplay) {
        percentageDisplay.innerText = percentage + '%';
    }

    if (statusText) {
        statusText.innerText = message || 'Processing...';
    }

    if (stepText) {
        // Show current step name
        const stepNames = {
            'extracting_frames': 'Extracting Frames',
            'analyzing_frames': 'AI Analyzing Frames',
            'generating_story': 'Generating Story',
            'detecting_moments': 'Detecting Moments',
            'generating_shorts': 'Creating Short Videos',
            'generating_metadata': 'Generating Metadata'
        };
        stepText.innerText = stepNames[step] || step;
    }

    // Highlight current step icon
    highlightPipelineStep(step);
}

function highlightPipelineStep(step) {
    // Reset all steps
    const stepIds = ['step-extract', 'step-analyze', 'step-story', 'step-shorts', 'step-metadata'];
    stepIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.classList.remove('text-primary', 'text-success');
            el.classList.add('text-muted');
        }
    });

    // Highlight current step
    const stepMap = {
        'extracting_frames': 'step-extract',
        'analyzing_frames': 'step-analyze',
        'generating_story': 'step-story',
        'detecting_moments': 'step-story',
        'generating_shorts': 'step-shorts',
        'generating_metadata': 'step-metadata'
    };

    const currentStepId = stepMap[step];
    if (currentStepId) {
        const el = document.getElementById(currentStepId);
        if (el) {
            el.classList.remove('text-muted');
            el.classList.add('text-primary');
        }
    }
}

function showAIResultsFromAPI(apiData) {
    // Swap spinner → success icon
    const spinner = document.getElementById('ai-spinner');
    const successIcon = document.getElementById('ai-success-icon');
    if (spinner) spinner.classList.add('d-none');
    if (successIcon) successIcon.classList.remove('d-none');

    // Brief pause so the user sees 100% / success state, then reveal results
    setTimeout(() => {
        document.getElementById('ai-progress-container').classList.add('d-none');
        document.getElementById('editor-section').classList.remove('d-none');
        document.getElementById('results-section').classList.remove('d-none');

        // /ai/results/ returns a flat structure — convert to the nested shape
        // that displayShorts / createShortCard / showShortDetails expect
        const shorts = (apiData.shorts || []).map(s => ({
            web_video_path: s.video_url,
            web_thumbnail_path: s.thumbnail_url,
            duration: s.duration,
            moment: {
                category: s.category,
                virality_score: s.virality_score,
                description: s.moment_description,
                start_time: s.start_time,
                end_time: s.end_time
            },
            metadata: {
                title: s.title,
                description: s.description,
                tags: s.tags
            }
        }));

        if (shorts.length > 0) {
            displayShorts(shorts);
        }

        if (apiData.story) {
            loadStory(apiData.story);
        }

        updateStats({
            frames: apiData.frame_count || 0,
            moments: apiData.moment_count || 0,
            shorts: apiData.short_count || shorts.length
        });
    }, 800);
}

function displayShorts(shorts) {
    const grid = document.getElementById('shorts-grid');
    if (!grid) return;

    grid.innerHTML = '';

    shorts.forEach(short => {
        const card = createShortCard(short);
        grid.appendChild(card);
    });
}

function createShortCard(short) {
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
    card.addEventListener('click', () => showShortDetails(short));

    return card;
}

function showShortDetails(short) {
    const moment = short.moment || {};
    const metadata = short.metadata || {};

    // Video
    const videoSource = document.getElementById('modal-video-source');
    const videoEl = document.getElementById('modal-video');
    if (videoSource && videoEl) {
        videoSource.src = short.web_video_path || '';
        videoEl.load();
    }

    // Badges
    const category = (moment.category || 'INTENSE').toUpperCase();
    const categoryBadge = document.getElementById('modal-category-badge');
    if (categoryBadge) {
        const colorMap = { 'INTENSE': 'bg-danger', 'FUNNY': 'bg-warning text-dark', 'CLUTCH': 'bg-success', 'SKILLFUL': 'bg-info text-dark' };
        categoryBadge.className = `badge rounded-pill me-2 ${colorMap[category] || 'bg-secondary'}`;
        categoryBadge.textContent = category;
    }

    const viralityEl = document.getElementById('modal-virality-score');
    if (viralityEl) viralityEl.textContent = moment.virality_score || 5;

    const durationEl = document.getElementById('modal-duration');
    if (durationEl) durationEl.textContent = short.duration || 0;

    // Title & description
    const titleEl = document.getElementById('modal-short-title');
    if (titleEl) titleEl.textContent = metadata.title || 'Untitled';

    const descEl = document.getElementById('modal-description');
    if (descEl) descEl.textContent = metadata.description || '—';

    // Tags
    const tagsEl = document.getElementById('modal-tags');
    if (tagsEl) {
        const tags = metadata.tags || [];
        tagsEl.innerHTML = tags.map(t => `<span class="badge bg-dark rounded-pill me-1 mb-1">#${t}</span>`).join('');
    }

    // Timestamp
    const tsEl = document.getElementById('modal-timestamp');
    if (tsEl) {
        const fmt = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
        tsEl.textContent = `${fmt(moment.start_time || 0)} – ${fmt(moment.end_time || 0)}`;
    }

    // Download button
    const dlBtn = document.getElementById('modal-download-btn');
    if (dlBtn) dlBtn.href = short.web_video_path || '#';

    // Open modal
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('shortDetailModal'));
    modal.show();
}

function loadStory(storyText) {
    const contentEl = document.getElementById('story-content');
    if (contentEl) {
        contentEl.textContent = storyText;
    }
    // Story panel is revealed when user clicks "View Story"
}

function updateStats(stats) {
    const framesEl = document.getElementById('stat-frames');
    const momentsEl = document.getElementById('stat-moments');
    const shortsEl = document.getElementById('stat-shorts');
    const statsRow = document.getElementById('ai-stats-row');

    if (framesEl) framesEl.textContent = (stats.frames || 0).toLocaleString();
    if (momentsEl) momentsEl.textContent = stats.moments || 0;
    if (shortsEl) shortsEl.textContent = stats.shorts || 0;
    if (statsRow) statsRow.classList.remove('d-none');
}

function toggleStoryView() {
    const panel = document.getElementById('story-panel');
    if (panel) panel.classList.toggle('d-none');
}

function copyToClipboard(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    navigator.clipboard.writeText(el.textContent.trim()).catch(() => {});
}

// ============================================================
// State Restoration — check for interrupted/active tasks on load
// ============================================================

async function checkForExistingTasks() {
    const { taskId, filename } = getLastSession();
    if (!taskId || !filename) return;

    try {
        const response = await fetch('/ai/status/' + taskId);
        if (!response.ok) return;
        const data = await response.json();
        if (data.error) return;

        const status = data.status;

        if (status === 'completed') {
            showTaskBanner(filename, taskId, 'completed',
                `Previous AI processing for <strong>${filename}</strong> is complete. View results?`);
        } else if (status === 'interrupted' || data.resumable) {
            showTaskBanner(filename, taskId, 'interrupted',
                `AI processing for <strong>${filename}</strong> was interrupted at ${data.percentage || 0}%. Resume?`);
        } else if (['queued', 'extracting_frames', 'analyzing_frames',
                     'generating_story', 'generating_shorts', 'generating_metadata'].includes(status)) {
            // Still running (e.g. tab was closed and reopened) — reattach
            showTaskBanner(filename, taskId, 'running',
                `AI processing for <strong>${filename}</strong> is in progress (${data.percentage || 0}%). Reconnect?`);
        }
    } catch (e) { /* server not available yet */ }
}

function showTaskBanner(filename, taskId, type, message) {
    const banner = document.getElementById('task-restore-banner');
    const text = document.getElementById('task-restore-text');
    const btn = document.getElementById('task-restore-btn');
    if (!banner || !text || !btn) return;

    text.innerHTML = message;

    if (type === 'completed') {
        btn.textContent = 'View Results';
        btn.className = 'btn btn-sm btn-success';
        btn.onclick = async () => {
            dismissTaskBanner();
            const results = await fetch('/ai/results/' + taskId).then(r => r.json());
            // Need the file selected first so editor-section is visible
            await restoreFileSelection(filename);
            showAIResultsFromAPI(results);
        };
    } else if (type === 'interrupted') {
        btn.textContent = 'Resume';
        btn.className = 'btn btn-sm btn-warning';
        btn.onclick = async () => {
            dismissTaskBanner();
            await restoreFileSelection(filename);
            resumeTask(taskId);
        };
    } else if (type === 'running') {
        btn.textContent = 'Reconnect';
        btn.className = 'btn btn-sm btn-primary';
        btn.onclick = async () => {
            dismissTaskBanner();
            await restoreFileSelection(filename);
            document.getElementById('video-column').classList.add('d-none');
            document.getElementById('controls-column').classList.add('d-none');
            document.getElementById('ai-progress-container').classList.remove('d-none');
            resetAIProgress();
            pollAIProgress(taskId);
        };
    }

    banner.classList.remove('d-none');
}

function dismissTaskBanner() {
    const banner = document.getElementById('task-restore-banner');
    if (banner) banner.classList.add('d-none');
}

async function restoreFileSelection(filename) {
    if (currentFilename === filename) return; // Already selected
    try {
        // Fetch the uploads list to get the file's URL and metadata
        const data = await fetch('/uploads/list').then(r => r.json());
        const file = (data.files || []).find(f => f.filename === filename);
        if (file) {
            currentFilename = file.filename;
            const metadata = file.metadata
                ? { ...file.metadata, format: filename.split('.').pop().toUpperCase() }
                : { duration: 0, resolution: [0, 0], fps: 0, format: 'MP4' };
            setupEditor(file.url, metadata);
        }
    } catch (e) {}
}

async function resumeTask(taskId) {
    try {
        const response = await fetch('/ai/resume/' + taskId, { method: 'POST' });
        const data = await response.json();
        if (data.error) {
            alert('Could not resume: ' + data.error);
            return;
        }
        currentTaskId = taskId;
        document.getElementById('video-column').classList.add('d-none');
        document.getElementById('controls-column').classList.add('d-none');
        document.getElementById('ai-progress-container').classList.remove('d-none');
        resetAIProgress();
        pollAIProgress(taskId);
    } catch (e) {
        alert('Failed to resume task.');
    }
}

function showResumePrompt(taskId, reason) {
    const msg = reason + '\n\nResume from last checkpoint?';
    if (confirm(msg)) {
        resumeTask(taskId);
    } else {
        resetAIGenerateBtn();
    }
}

function updateFpsEstimates(fpsValue) {
    const helpText = document.getElementById('ai-fps-help');
    const framesEl = document.getElementById('estimated-frames');
    const timeEl = document.getElementById('estimated-time');

    if (videoDuration > 0) {
        const estimatedFrames = Math.round(videoDuration * fpsValue);
        const estimatedSecs = Math.round(estimatedFrames * 1.5); // ~1.5s per frame
        const estimatedMin = Math.max(1, Math.round(estimatedSecs / 60));

        if (helpText) helpText.textContent = `~${estimatedFrames.toLocaleString()} frames for this video`;
        if (framesEl) framesEl.textContent = estimatedFrames.toLocaleString();
        if (timeEl) timeEl.textContent = `~${estimatedMin} min`;
    } else {
        if (helpText) helpText.textContent = 'Adjust slider to set frame extraction rate';
        if (framesEl) framesEl.textContent = '—';
        if (timeEl) timeEl.textContent = '—';
    }
}
