"""
Short Video Generator Service
Generates 9:16 vertical short clips from detected moments.
First 7 seconds = hook (climax/result), then the build-up gameplay.
"""

import os
import json
import logging
import math
from moviepy.editor import (
    VideoFileClip, concatenate_videoclips,
    CompositeVideoClip, TextClip, ColorClip
)
import moviepy.video.fx.all as vfx

logger = logging.getLogger(__name__)

# Target dimensions for YouTube Shorts / Instagram Reels
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
ASPECT_RATIO = 9 / 16  # 0.5625

# Short video constraints
HOOK_DURATION = 7  # seconds - the intense result shown first
MIN_SHORT_DURATION = 15
MAX_SHORT_DURATION = 60
DEFAULT_SHORT_DURATION = 45


def crop_to_vertical(clip):
    """
    Center-crop a horizontal video to 9:16 vertical aspect ratio.
    Maintains the center of the frame for gameplay focus.
    """
    w, h = clip.size

    # Calculate crop dimensions
    source_aspect = w / h
    target_aspect = ASPECT_RATIO  # 9/16

    if source_aspect > target_aspect:
        # Source is wider — crop width
        new_w = int(h * target_aspect)
        new_h = h
        x_offset = (w - new_w) // 2
        y_offset = 0
    else:
        # Source is taller — crop height
        new_w = w
        new_h = int(w / target_aspect)
        x_offset = 0
        y_offset = (h - new_h) // 2

    cropped = clip.crop(
        x1=x_offset,
        y1=y_offset,
        x2=x_offset + new_w,
        y2=y_offset + new_h
    )

    # Resize to target resolution
    resized = cropped.resize((TARGET_WIDTH, TARGET_HEIGHT))
    return resized


def create_transition_clip(duration=0.5):
    """Create a brief dark transition clip."""
    return ColorClip(
        size=(TARGET_WIDTH, TARGET_HEIGHT),
        color=(0, 0, 0),
        duration=duration
    ).set_fps(30)


def generate_short(video_path, moment, output_path, short_index=0, progress_callback=None):
    """
    Generate a single vertical short from a detected moment.
    
    Structure:
    - First 7 seconds: The climax/result (end of the moment)
    - Brief transition
    - Remaining: The build-up gameplay leading to the climax
    
    Args:
        video_path: Path to the source video
        moment: dict with start_time, end_time, category, etc.
        output_path: Where to save the generated short
        short_index: Index for logging
        progress_callback: Optional callable(current, total, status_message)
    
    Returns:
        dict with short metadata
    """
    if progress_callback:
        progress_callback(0, 3, f"Generating short #{short_index + 1}...")

    try:
        source_clip = VideoFileClip(video_path)
    except Exception as e:
        logger.error(f"Cannot open video: {e}")
        raise

    start_time = moment["start_time"]
    end_time = moment["end_time"]
    duration = end_time - start_time

    # Ensure reasonable duration
    if duration > MAX_SHORT_DURATION:
        # Trim to MAX_SHORT_DURATION, keeping the end (climax)
        start_time = end_time - MAX_SHORT_DURATION
        duration = MAX_SHORT_DURATION
    elif duration < MIN_SHORT_DURATION:
        # Try to extend the start to get more build-up
        desired_start = end_time - DEFAULT_SHORT_DURATION
        start_time = max(0, desired_start)
        duration = end_time - start_time

    # Define hook and build-up segments
    hook_end_time = end_time
    hook_start_time = max(start_time, end_time - HOOK_DURATION)

    buildup_start_time = start_time
    buildup_end_time = hook_start_time

    # Ensure buildup has some content
    if buildup_end_time - buildup_start_time < 3:
        # Not enough build-up, just use the whole segment
        buildup_start_time = start_time
        buildup_end_time = end_time - HOOK_DURATION
        if buildup_end_time <= buildup_start_time:
            # Very short moment — just use it linearly
            try:
                segment = source_clip.subclip(start_time, end_time)
                vertical = crop_to_vertical(segment)

                if progress_callback:
                    progress_callback(2, 3, f"Encoding short #{short_index + 1}...")

                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                vertical.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    fps=30,
                    preset='medium',
                    bitrate='8M'
                )
                vertical.close()
                segment.close()
                source_clip.close()

                if progress_callback:
                    progress_callback(3, 3, f"Short #{short_index + 1} complete!")

                return {
                    "index": short_index,
                    "output_path": output_path,
                    "duration": round(duration, 2),
                    "hook_structure": "linear",
                    "moment": moment
                }
            except Exception as e:
                logger.error(f"Error generating linear short: {e}")
                source_clip.close()
                raise

    if progress_callback:
        progress_callback(1, 3, f"Creating hook-first structure for short #{short_index + 1}...")

    try:
        # Extract hook (climax/result — shown first)
        hook_clip = source_clip.subclip(hook_start_time, hook_end_time)
        hook_vertical = crop_to_vertical(hook_clip)

        # Extract build-up (gameplay leading to climax — shown after hook)
        buildup_clip = source_clip.subclip(buildup_start_time, buildup_end_time)
        buildup_vertical = crop_to_vertical(buildup_clip)

        # Create brief transition
        transition = create_transition_clip(0.3)

        # Concatenate: HOOK → transition → BUILD-UP
        final_clip = concatenate_videoclips(
            [hook_vertical, transition, buildup_vertical],
            method="compose"
        )

        if progress_callback:
            progress_callback(2, 3, f"Encoding short #{short_index + 1}...")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=30,
            preset='medium',
            bitrate='8M'
        )

        final_duration = final_clip.duration

        # Cleanup
        final_clip.close()
        hook_vertical.close()
        buildup_vertical.close()
        hook_clip.close()
        buildup_clip.close()
        transition.close()
        source_clip.close()

        if progress_callback:
            progress_callback(3, 3, f"Short #{short_index + 1} complete!")

        return {
            "index": short_index,
            "output_path": output_path,
            "duration": round(final_duration, 2),
            "hook_duration": round(hook_end_time - hook_start_time, 2),
            "buildup_duration": round(buildup_end_time - buildup_start_time, 2),
            "hook_structure": "hook_first",
            "moment": moment
        }

    except Exception as e:
        logger.error(f"Error generating hook-first short: {e}")
        source_clip.close()
        raise


def generate_all_shorts(video_path, moments, output_dir, progress_callback=None):
    """
    Generate short videos for all detected moments.
    
    Args:
        video_path: Path to the source video
        moments: list of moment dicts (sorted by virality)
        output_dir: Base directory for shorts output
        progress_callback: Optional callable(current, total, status_message)
    
    Returns:
        list of short metadata dicts
    """
    os.makedirs(output_dir, exist_ok=True)
    total = len(moments)
    shorts = []

    if progress_callback:
        progress_callback(0, total, f"Generating {total} short videos...")

    for idx, moment in enumerate(moments):
        output_filename = f"short_{idx + 1:03d}_{moment['category'].lower()}.mp4"
        output_path = os.path.join(output_dir, output_filename)

        try:
            def short_progress(current, step_total, msg):
                if progress_callback:
                    overall_progress = idx + (current / step_total) if step_total > 0 else idx
                    progress_callback(
                        overall_progress, total,
                        f"[{idx + 1}/{total}] {msg}"
                    )

            short_info = generate_short(
                video_path, moment, output_path,
                short_index=idx,
                progress_callback=short_progress
            )

            # Generate thumbnail from the hook (first frame)
            thumbnail_path = os.path.join(output_dir, f"thumb_{idx + 1:03d}.jpg")
            try:
                _generate_thumbnail(output_path, thumbnail_path)
                short_info["thumbnail_path"] = thumbnail_path
            except Exception as e:
                logger.warning(f"Could not generate thumbnail for short {idx + 1}: {e}")
                short_info["thumbnail_path"] = None

            # Add web-accessible paths
            short_info["web_video_path"] = f"/shorts/{os.path.basename(output_dir)}/{output_filename}"
            if short_info.get("thumbnail_path"):
                short_info["web_thumbnail_path"] = f"/shorts/{os.path.basename(output_dir)}/thumb_{idx + 1:03d}.jpg"
            else:
                short_info["web_thumbnail_path"] = None

            shorts.append(short_info)
            logger.info(f"Generated short {idx + 1}/{total}: {output_filename}")

        except Exception as e:
            logger.error(f"Failed to generate short {idx + 1}: {e}")
            shorts.append({
                "index": idx,
                "error": str(e),
                "moment": moment,
                "output_path": None
            })

        if progress_callback:
            progress_callback(idx + 1, total, f"Completed {idx + 1}/{total} shorts")

    # Save shorts manifest
    manifest_path = os.path.join(output_dir, "shorts_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump({
            "total": len(shorts),
            "successful": sum(1 for s in shorts if s.get("output_path")),
            "shorts": shorts
        }, f, indent=2)

    if progress_callback:
        success_count = sum(1 for s in shorts if s.get("output_path"))
        progress_callback(total, total, f"Generated {success_count}/{total} shorts!")

    return shorts


def _generate_thumbnail(video_path, thumbnail_path, time_offset=1.0):
    """Generate a thumbnail from a video at specified time offset."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video for thumbnail: {video_path}")

    # Seek to the specified time
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_number = int(time_offset * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError(f"Cannot read frame at {time_offset}s")

    cv2.imwrite(thumbnail_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])