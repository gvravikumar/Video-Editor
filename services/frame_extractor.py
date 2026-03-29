"""
Frame Extraction Service
Extracts frames from video at configurable FPS using OpenCV.
Cross-platform: works on Windows, macOS, Linux.
"""

import cv2
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_frames(video_path, output_dir, fps=2, progress_callback=None):
    """
    Extract frames from a video file at specified FPS rate.
    
    Args:
        video_path: Path to the input video file
        output_dir: Directory to save extracted frames
        fps: Frames per second to extract (default: 2)
        progress_callback: Optional callable(current, total, status_message)
    
    Returns:
        dict with keys:
            - frame_count: total number of frames extracted
            - manifest: list of {index, timestamp, filename} dicts
            - duration: video duration in seconds
            - original_fps: original video FPS
    """
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video file: {video_path}")

    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / original_fps if original_fps > 0 else 0

    # Calculate frame interval (how many source frames to skip between extractions)
    frame_interval = max(1, int(round(original_fps / fps)))
    expected_frames = int(duration * fps)

    logger.info(
        f"Video: {duration:.1f}s, {original_fps:.1f} FPS, "
        f"extracting at {fps} FPS → ~{expected_frames} frames (interval={frame_interval})"
    )

    if progress_callback:
        progress_callback(0, expected_frames, "Starting frame extraction...")

    manifest = []
    frame_index = 0
    extracted_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_index % frame_interval == 0:
            timestamp = frame_index / original_fps
            filename = f"frame_{extracted_count:06d}.jpg"
            filepath = os.path.join(output_dir, filename)

            # Save frame as JPEG with good quality
            cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

            manifest.append({
                "index": extracted_count,
                "timestamp": round(timestamp, 3),
                "filename": filename
            })

            extracted_count += 1

            if progress_callback and extracted_count % 10 == 0:
                progress_callback(
                    extracted_count,
                    expected_frames,
                    f"Extracted {extracted_count}/{expected_frames} frames"
                )

        frame_index += 1

    cap.release()

    # Save manifest JSON
    manifest_path = os.path.join(output_dir, "manifest.json")
    manifest_data = {
        "video_path": video_path,
        "frame_count": extracted_count,
        "fps_extracted": fps,
        "original_fps": original_fps,
        "duration": round(duration, 3),
        "frames": manifest
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)

    if progress_callback:
        progress_callback(extracted_count, extracted_count, "Frame extraction complete!")

    logger.info(f"Extracted {extracted_count} frames to {output_dir}")
    return manifest_data