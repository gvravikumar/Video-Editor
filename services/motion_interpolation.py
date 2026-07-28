"""
Motion Interpolation Service (optional smoothing, opt-in)

Screen-capture clips recorded at a low framerate (e.g. Bandicam at 10-17 fps)
are inherently choppy — the low framerate is baked into the recording, so no
output fps can add motion that was never captured. This service uses ffmpeg's
`minterpolate` filter to SYNTHESIZE in-between frames (optical-flow motion
compensation), making low-fps gameplay look closer to smooth 60 fps.

IMPORTANT — it is SLOW (optical flow is expensive on CPU). So it is:
  * OPT-IN (default off in the app), and
  * applied PER RENDERED SHORT (bounded by the short's length, ~15-45s), NOT to
    the whole source video (which could be many minutes).

Always fails safe: if ffmpeg is missing or the filter errors, the original file
is left untouched.
"""

import os
import shutil
import logging
import subprocess

logger = logging.getLogger(__name__)

# If the source already runs at/above this fps, interpolation is pointless.
SMOOTH_THRESHOLD = 48
DEFAULT_TARGET_FPS = 60


def _ffmpeg() -> str:
    """
    Resolve an ffmpeg executable. Prefer one on PATH; otherwise fall back to the
    binary bundled with imageio-ffmpeg (which MoviePy installs), so smoothing works
    on Windows/macOS/Linux without a separate ffmpeg install.
    """
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def source_fps(video_path: str) -> float:
    """Best-effort source framerate (0.0 if it can't be read)."""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        return float(fps) if fps and fps > 0 else 0.0
    except Exception:
        return 0.0


def should_interpolate(video_path: str, target_fps: int = DEFAULT_TARGET_FPS) -> bool:
    """True only if the source is choppy enough to benefit from interpolation."""
    src = source_fps(video_path)
    return 0 < src < min(SMOOTH_THRESHOLD, target_fps)


def smooth_file_inplace(
    file_path: str,
    target_fps: int = DEFAULT_TARGET_FPS,
    progress_callback=None,
) -> bool:
    """
    Motion-interpolate an already-rendered short IN PLACE to `target_fps`.

    Returns True if the file was smoothed, False if it was left unchanged
    (ffmpeg missing / filter failed). Bounded by the short's own length.
    """
    if not os.path.exists(file_path):
        return False

    tmp_out = file_path + ".smooth.mp4"
    # Lighter settings than max quality (obmc instead of aobmc, no vsbmc) — still
    # a big visual improvement on choppy footage but noticeably faster.
    vf = f"minterpolate=fps={target_fps}:mi_mode=mci:mc_mode=obmc:me_mode=bidir"
    cmd = [
        _ffmpeg(), "-y", "-i", file_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        tmp_out,
    ]

    if progress_callback:
        progress_callback(0, 1, f"Smoothing short to {target_fps} fps (motion interpolation)...")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.exists(tmp_out):
            logger.warning("minterpolate failed (rc=%s); keeping original. stderr tail:\n%s",
                           proc.returncode, (proc.stderr or "")[-600:])
            if os.path.exists(tmp_out):
                os.remove(tmp_out)
            return False
    except FileNotFoundError:
        logger.warning("ffmpeg not found - skipping interpolation")
        return False
    except Exception as e:  # pragma: no cover
        logger.warning("Interpolation error (%s) - keeping original", e)
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        return False

    os.replace(tmp_out, file_path)
    if progress_callback:
        progress_callback(1, 1, "Short smoothing complete.")
    logger.info("Smoothed %s to %d fps", os.path.basename(file_path), target_fps)
    return True
