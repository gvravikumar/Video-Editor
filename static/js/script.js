let currentFilename = null;
let videoDuration = 0;

let dropZone, videoInput, aiAnalysisSwitch, gameTypeSelect, aiProgress, aiProgressBar, aiProgressText, aiProgressPercent, aiResults, aiTitle, aiDescription, aiTags, aiHashtags, viewMomentsBtn;

document.addEventListener('DOMContentLoaded', () => {
    dropZone = document.getElementById('drop-zone');
    videoInput = document.getElementById('video-input');
    aiAnalysisSwitch = document.getElementById('ai-analysis-switch');
    gameTypeSelect = document.getElementById('game-type');
    aiProgress = document.getElementById('ai-progress');
    aiProgressBar = document.getElementById('ai-progress-bar');
    aiProgressText = document.getElementById('ai-progress-text');
    aiProgressPercent = document.getElementById('ai-progress-percent');
    aiResults = document.getElementById('ai-results');
    aiTitle = document.getElementById('ai-title');
    aiDescription = document.getElementById('ai-description');
    aiTags = document.getElementById('ai-tags');
    aiHashtags = document.getElementById('ai-hashtags');
    viewMomentsBtn = document.getElementById('view-moments-btn');

    // AI Analysis event handlers
    if (aiAnalysisSwitch) {
        aiAnalysisSwitch.addEventListener('change', handleAIAnalysisToggle);
    }

    if (viewMomentsBtn) {
        // Initialize with empty state
        showSatisfyingMoments([]);
        
        viewMomentsBtn.addEventListener('click', () => {
            const modalEl = document.getElementById('momentsModal');
            let momentsModal = bootstrap.Modal.getInstance(modalEl);
            if (!momentsModal) {
                momentsModal = new bootstrap.Modal(modalEl);
            }
            momentsModal.show();
        });
    }
    
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

    // Fetch existing uploaded files on load
    fetchExistingUploads();
});

function fetchExistingUploads() {
    fetch('/api/uploads')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('existing-uploads-container');
            const list = document.getElementById('existing-uploads-list');
            if (data.files && data.files.length > 0) {
                container.classList.remove('d-none');
                list.innerHTML = '';
                data.files.forEach(file => {
                    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                    const date = new Date(file.time * 1000).toLocaleString();
                    const item = document.createElement('a');
                    item.href = '#';
                    item.className = 'list-group-item list-group-item-action bg-dark text-light border-darker d-flex justify-content-between align-items-center py-3';
                    item.innerHTML = `
                        <div class="d-flex align-items-center">
                            <i class="bi bi-file-earmark-play-fill text-primary fs-4 me-3"></i>
                            <div>
                                <h6 class="mb-0 text-truncate" style="max-width: 300px;">${file.filename}</h6>
                                <small class="text-muted">${date} • ${sizeMB} MB</small>
                            </div>
                        </div>
                        <button class="btn btn-sm btn-outline-primary rounded-pill px-3">Select</button>
                    `;
                    item.addEventListener('click', (e) => {
                        e.preventDefault();
                        loadExistingUpload(file.filename);
                    });
                    list.appendChild(item);
                });
            } else {
                container.classList.add('d-none');
            }
        })
        .catch(err => console.error("Error fetching uploads:", err));
}

function loadExistingUpload(filename) {
    document.getElementById('upload-progress-container').classList.remove('d-none');
    document.getElementById('upload-percent').innerText = "Loading...";
    document.getElementById('upload-progress').style.width = '100%';

    fetch('/api/load_upload/' + encodeURIComponent(filename))
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert("Error loading file: " + data.error);
                document.getElementById('upload-progress-container').classList.add('d-none');
            } else {
                currentFilename = data.filepath;
                setupEditor(data.video_input_path, data.metadata);
                document.getElementById('upload-progress-container').classList.add('d-none');
            }
        })
        .catch(err => {
            alert("Error loading file. Check console.");
            console.error(err);
            document.getElementById('upload-progress-container').classList.add('d-none');
        });
}

function handleFiles(file) {
    if (!file.type.match('video.*')) {
        alert("Please upload a supported video file.");
        return;
    }

    // Reset AI analysis state
    if (aiAnalysisSwitch) {
        aiAnalysisSwitch.checked = false;
        handleAIAnalysisToggle();
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

    // Update max duration for AI analysis
    if (aiAnalysisSwitch) {
        document.getElementById('start-time').max = metadata.duration;
        document.getElementById('end-time').max = metadata.duration;
    }
    
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

    // Check if AI analysis is enabled
    const aiAnalysisEnabled = aiAnalysisSwitch ? aiAnalysisSwitch.checked : false;
    
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

    if (aiAnalysisEnabled) {
        operations.ai_analysis = true;
        operations.game_type = gameTypeSelect ? gameTypeSelect.value : 'unknown';
    }
    
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

    if (aiAnalysisEnabled) {
        aiProgress.classList.remove('d-none');
        updateAIProgress(0, 'Analyzing video content...');
    }
    
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
            if (aiAnalysisEnabled && data.ai_analysis) {
                pollAIProgress(data.task_id);
            }
        }
    })
    .catch(error => {
        showErrorStatus("Error starting process.");
    });
}

function showErrorStatus(msg) {
    document.getElementById('process-status-text').innerText = "Error!";
    document.getElementById('process-spinner').classList.add('d-none');
    if (aiProgress) {
        aiProgress.classList.add('d-none');
    }
    alert(msg);
    document.getElementById('process-btn').disabled = false;
}

function updateAIProgress(percent, text) {
    if (!aiProgress) return;
    aiProgressBar.style.width = percent + '%';
    aiProgressPercent.innerText = percent + '%';
    aiProgressText.innerText = text;
}

function handleAIAnalysisToggle() {
    if (aiAnalysisSwitch.checked) {
        aiResults.classList.remove('d-none');
    } else {
        aiResults.classList.add('d-none');
        if (aiProgress) {
            aiProgress.classList.add('d-none');
        }
    }
}

function pollAIProgress(taskId) {
    const interval = setInterval(() => {
        fetch('/status/' + taskId)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                clearInterval(interval);
                return;
            }

            if (data.status === 'analyzing') {
                const percent = data.percentage || 0;
                // Show live captioning/scoring status directly from backend
                const statusMsg = data.status_text || 'Analyzing video content...';
                updateAIProgress(percent, statusMsg);
            } else if (data.status === 'generating') {
                const percent = data.percentage || 80;
                updateAIProgress(percent, data.status_text || 'Rendering short clips...');
            } else if (data.status === 'completed' && data.ai_analysis) {
                clearInterval(interval);
                updateAIProgress(100, '✅ Analysis complete!');

                // Populate the AI results panel
                if (data.metadata) {
                    aiTitle.value       = data.metadata.title || '';
                    aiDescription.value = data.metadata.description || '';
                    aiTags.value        = data.metadata.tags ? data.metadata.tags.join(', ') : '';
                    aiHashtags.value    = data.metadata.hashtags || '';
                }

                // Populate story tab
                if (data.story) {
                    const storyEl = document.getElementById('story-text');
                    if (storyEl) storyEl.textContent = data.story;
                }

                // Populate clips tab and show button
                if (data.satisfying_moments && data.satisfying_moments.length > 0) {
                    showSatisfyingMoments(data.satisfying_moments, data.result_files);
                    viewMomentsBtn.classList.remove('d-none');
                }
            }
        })
        .catch(error => {
            console.error(error);
        });
    }, 1500);
}

function showSatisfyingMoments(moments, clips) {
    const momentsList = document.getElementById('moments-list');
    if (!momentsList) return;

    if (!moments || moments.length === 0) {
        momentsList.innerHTML = `
            <div class="text-center py-5">
                <i class="bi bi-camera-reels text-secondary mb-3" style="font-size: 3rem;"></i>
                <h5 class="text-light">No Clips Yet</h5>
                <p class="text-muted small">Enable AI Analysis and click Process Video to generate your AI-curated shorts here.</p>
            </div>
        `;
        return;
    }

    let html = '<div class="row row-cols-1 g-4">';
    moments.forEach((moment, index) => {
        const start = moment.start.toFixed(1);
        const end   = moment.end.toFixed(1);
        const dur   = (moment.end - moment.start).toFixed(1);
        const desc  = moment.description || '';

        let videoTag = '';
        if (clips && clips[index]) {
            let videoUrl = clips[index].replace(/\\/g, '/');
            if (!videoUrl.startsWith('/')) videoUrl = '/' + videoUrl;
            videoTag = `<video class="card-img-top bg-black" style="height:380px;object-fit:contain;" controls src="${videoUrl}"></video>`;
        }

        html += `
            <div class="col">
                <div class="card bg-darker border-secondary shadow h-100 overflow-hidden text-light">
                    ${videoTag}
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="card-title fw-bold mb-0 text-primary">
                                <i class="bi bi-lightning-charge-fill me-1 text-warning"></i>Short #${index + 1}
                            </h6>
                            <span class="badge bg-secondary rounded-pill">
                                <i class="bi bi-clock me-1"></i>${dur}s
                            </span>
                        </div>
                        <p class="small text-muted mb-2">
                            <i class="bi bi-stopwatch me-1"></i>Timestamp: <strong>${start}s &rarr; ${end}s</strong>
                        </p>
                        ${desc ? `<div class="story-desc bg-dark rounded-3 p-2 small text-secondary" style="border-left:3px solid #6c757d;">
                            <i class="bi bi-chat-quote me-1 text-info"></i>${desc}
                        </div>` : ''}
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    momentsList.innerHTML = html;
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
