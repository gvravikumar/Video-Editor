"""
Renderer Service (deterministic, no ML)

Turns an agent-produced PLAN (see services/plan_schema.py) into hook-first,
9:16 vertical shorts + thumbnails. Contains NO machine-learning — all the
"intelligence" (which moments, hook text, titles, tags) already lives in the
plan written by the agent. This module only does mechanical video work.

Structure of each generated short:
    [0 .. HOOK_DURATION]  hook = the climax/peak, shown FIRST, with an optional
                          on-screen hook_text overlay ("1v4 CLUTCH?!")
    brief dark transition
    [.. end]              build-up = the gameplay leading to the climax

Hook-text overlays are rendered with PIL (Pillow) and composited as an image,
so we do NOT depend on ImageMagick / MoviePy TextClip (a common breakage point).
"""

import os
import json
import logging

from moviepy.editor import (
    VideoFileClip, concatenate_videoclips, CompositeVideoClip,
    ColorClip, ImageClip,
)

logger = logging.getLogger(__name__)

# Target dimensions for YouTube Shorts / Instagram Reels / TikTok
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
ASPECT_RATIO = 9 / 16  # 0.5625

HOOK_DURATION = 7          # seconds of climax shown first
MIN_SHORT_DURATION = 15
MAX_SHORT_DURATION = 60
DEFAULT_SHORT_DURATION = 40
HOOK_TEXT_SECONDS = 2.5    # how long the hook overlay stays on screen

# Output framerate is matched to the SOURCE (clamped to this range) so that
# smooth 60fps gameplay stays 60fps instead of being downsampled to a juddery 30.
# (Low-fps source captures can't be made smoother than they were recorded.)
MIN_OUTPUT_FPS = 30
MAX_OUTPUT_FPS = 60


def _target_fps(source_fps):
    """Pick the output fps: match the source, clamped to [MIN, MAX]_OUTPUT_FPS."""
    try:
        fps = float(source_fps)
    except (TypeError, ValueError):
        fps = MIN_OUTPUT_FPS
    if fps <= 0:
        fps = MIN_OUTPUT_FPS
    return int(round(max(MIN_OUTPUT_FPS, min(MAX_OUTPUT_FPS, fps))))


# ------------------------------------------------------------------- metadata
def format_tags_csv(tags):
    """
    Normalize a tag list into a single comma-separated hashtag string, e.g.
    ["fortnite", "#clutch"] -> "#fortnite, #clutch". Deduplicates (case-insensitive)
    and guarantees every tag starts with exactly one '#'.
    """
    out, seen = [], set()
    for t in tags or []:
        if not isinstance(t, str):
            continue
        t = "#" + t.strip().lstrip("#").replace(" ", "")
        if t == "#" or t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
    return ", ".join(out)


def _write_short_metadata(txt_path, moment, tags_csv):
    """Write a copy-paste-ready sidecar for one short (title, description, tags)."""
    lines = [
        "TITLE:",
        moment.get("title", "").strip(),
        "",
        "DESCRIPTION:",
        moment.get("description", "").strip(),
        "",
        "TAGS:",
        tags_csv,
        "",
    ]
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# --------------------------------------------------------------------------- crop
def crop_to_vertical(clip):
    """Center-crop a horizontal clip to 9:16 and resize to target resolution."""
    w, h = clip.size
    source_aspect = w / h
    if source_aspect > ASPECT_RATIO:
        new_w = int(h * ASPECT_RATIO)
        new_h = h
        x_offset = (w - new_w) // 2
        y_offset = 0
    else:
        new_w = w
        new_h = int(w / ASPECT_RATIO)
        x_offset = 0
        y_offset = (h - new_h) // 2

    cropped = clip.crop(
        x1=x_offset, y1=y_offset,
        x2=x_offset + new_w, y2=y_offset + new_h,
    )
    return cropped.resize((TARGET_WIDTH, TARGET_HEIGHT))


def _transition(duration=0.3, fps=30):
    return ColorClip(size=(TARGET_WIDTH, TARGET_HEIGHT), color=(0, 0, 0), duration=duration).set_fps(fps)


# ---------------------------------------------------------------- hook text overlay
def _strip_unrenderable(text):
    """
    Remove emoji / non-BMP characters that standard TTF fonts can't render
    (they'd show as tofu boxes). Titles/tags keep their emojis — this only
    cleans the text we burn into the video/thumbnail. Collapses leftover spaces.
    """
    import re
    cleaned = "".join(ch for ch in text if ord(ch) <= 0xFFFF and ch.isprintable())
    # Drop common BMP symbol/dingbat ranges too (arrows, misc symbols)
    cleaned = re.sub(r"[\u2190-\u21FF\u2300-\u27BF\u2B00-\u2BFF\uFE0F\u20E3]", "", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _render_hook_text_png(text, out_path):
    """
    Render bold, outlined hook text (top third) onto a transparent PNG using PIL.
    Returns out_path on success, or None if PIL/text rendering isn't possible.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as e:  # pragma: no cover
        logger.warning("PIL unavailable for hook text: %s", e)
        return None

    img = Image.new("RGBA", (TARGET_WIDTH, TARGET_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Try a few common bold fonts; fall back to PIL default.
    font = None
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "arialbd.ttf",
    ):
        try:
            font = ImageFont.truetype(candidate, 96)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    text = _strip_unrenderable((text or "").upper().strip())
    if not text:
        return None

    # Word-wrap to fit width
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] > TARGET_WIDTH - 120 and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)

    line_h = (draw.textbbox((0, 0), "Ag", font=font)[3]) + 18
    total_h = line_h * len(lines)
    y = int(TARGET_HEIGHT * 0.12)

    # Semi-transparent band behind the text so it reads on any background.
    band_pad_y = 28
    band_top = max(0, y - band_pad_y)
    band_bottom = min(TARGET_HEIGHT, y + total_h + band_pad_y)
    band = Image.new("RGBA", (TARGET_WIDTH, band_bottom - band_top), (0, 0, 0, 110))
    img.alpha_composite(band, (0, band_top))

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (TARGET_WIDTH - w) // 2
        # Outline
        for dx in (-4, -2, 0, 2, 4):
            for dy in (-4, -2, 0, 2, 4):
                draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
        # Fill
        draw.text((x, y), line, font=font, fill=(255, 214, 10, 255))  # gold
        y += line_h

    img.save(out_path)
    return out_path


# ------------------------------------------------------------------- single short
def _render_one(video_path, moment, output_path, thumb_path, tmp_dir, index):
    source = VideoFileClip(video_path)
    try:
        out_fps = _target_fps(getattr(source, "fps", None))
        video_dur = source.duration
        start_time = max(0.0, min(moment["start_time"], video_dur - 0.1))
        end_time = max(start_time + 1.0, min(moment["end_time"], video_dur))
        duration = end_time - start_time

        # Constrain duration, keeping the climax (end)
        if duration > MAX_SHORT_DURATION:
            start_time = end_time - MAX_SHORT_DURATION
        elif duration < MIN_SHORT_DURATION:
            start_time = max(0.0, end_time - DEFAULT_SHORT_DURATION)
        duration = end_time - start_time

        # Hook = last HOOK_DURATION secs (the climax/result); build-up = the rest
        hook_start = max(start_time, end_time - HOOK_DURATION)
        buildup_start, buildup_end = start_time, hook_start

        hook_clip = crop_to_vertical(source.subclip(hook_start, end_time))

        # Optional hook-text overlay on the hook segment
        hook_text = (moment.get("hook_text") or "").strip()
        if hook_text:
            png = _render_hook_text_png(hook_text, os.path.join(tmp_dir, f"hook_{index}.png"))
            if png:
                overlay = (
                    ImageClip(png)
                    .set_duration(min(HOOK_TEXT_SECONDS, hook_clip.duration))
                    .set_position(("center", "top"))
                )
                hook_clip = CompositeVideoClip([hook_clip, overlay])

        parts = [hook_clip]
        structure = "hook_first"
        if buildup_end - buildup_start >= 2.0:
            parts.append(_transition(0.3, fps=out_fps))
            parts.append(crop_to_vertical(source.subclip(buildup_start, buildup_end)))
        else:
            structure = "linear"

        final = concatenate_videoclips(parts, method="chain")

        # Subtle polish: quick fade in at the very start and fade out at the end
        # so the loop/cut doesn't feel abrupt. Kept short to preserve the hook.
        try:
            final = final.fadein(0.25).fadeout(0.35)
        except Exception:
            pass
        # Smooth the audio edges too (avoids pops on hard cuts), if audio exists.
        if final.audio is not None:
            try:
                from moviepy.audio.fx.all import audio_fadein, audio_fadeout
                final = final.fx(audio_fadein, 0.25).fx(audio_fadeout, 0.35)
            except Exception:
                pass

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # CRF-based x264 (quality-targeted, visually near-lossless at 18) +
        # faststart so the short starts playing before it's fully downloaded.
        final.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            fps=out_fps,
            preset="medium",
            ffmpeg_params=["-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
            logger=None,
        )
        final_duration = final.duration

        # Thumbnail from the peak instant of the source (most epic frame)
        peak = moment.get("peak_time", end_time)
        _grab_thumbnail(source, peak, thumb_path, moment.get("hook_text"))

        final.close()
        for p in parts:
            try:
                p.close()
            except Exception:
                pass

        return {
            "duration": round(final_duration, 2),
            "hook_structure": structure,
            "fps": out_fps,
        }
    finally:
        source.close()


def _grab_thumbnail(source_clip, t, thumb_path, hook_text=None):
    """Save a thumbnail from time t of the source, 9:16, with optional hook text."""
    try:
        from PIL import Image
        t = max(0.0, min(t, source_clip.duration - 0.05))
        frame = source_clip.get_frame(t)  # numpy array HxWx3
        img = Image.fromarray(frame)
        # center-crop to 9:16
        w, h = img.size
        if w / h > ASPECT_RATIO:
            new_w = int(h * ASPECT_RATIO)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / ASPECT_RATIO)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))
        img = img.resize((TARGET_WIDTH, TARGET_HEIGHT))

        if hook_text:
            png = _render_hook_text_png(hook_text, thumb_path + ".txt.png")
            if png:
                overlay = Image.open(png).convert("RGBA")
                img = img.convert("RGBA")
                img.alpha_composite(overlay)
                img = img.convert("RGB")
                try:
                    os.remove(png)
                except OSError:
                    pass

        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
        img.convert("RGB").save(thumb_path, "JPEG", quality=90)
    except Exception as e:
        logger.warning("Thumbnail generation failed at t=%.1f: %s", t, e)


# -------------------------------------------------------------------- render all
def render_shorts(video_path, plan, output_dir, progress_callback=None,
                  smooth=False, smooth_cache_dir=None):
    """
    Render all shorts described by a validated plan.

    Args:
        video_path: source gameplay video
        plan: validated plan dict (services.plan_schema.validate_plan output)
        output_dir: directory to write shorts + thumbnails + manifest
        progress_callback: optional callable(current, total, message)
        smooth: if True, run motion interpolation on choppy (low-fps) sources
            first so the shorts look smoother (auto-skipped when already smooth).
        smooth_cache_dir: where to cache the interpolated video (defaults to a
            sibling of output_dir).

    Returns:
        list of enriched short dicts (with metadata + web paths)
    """
    os.makedirs(output_dir, exist_ok=True)
    tmp_dir = os.path.join(output_dir, "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    render_source = video_path
    # Decide once whether smoothing applies to this (choppy) source. The actual
    # interpolation runs per-short AFTER encode, so cost is bounded by short
    # length, not the (possibly very long) source video.
    do_smooth = False
    if smooth:
        try:
            from services.motion_interpolation import should_interpolate
            do_smooth = should_interpolate(video_path)
        except Exception as e:
            logger.warning("Smoothing availability check failed: %s", e)
            do_smooth = False

    moments = plan["moments"]
    total = len(moments)
    shorts = []

    if progress_callback:
        progress_callback(0, total, f"Rendering {total} shorts…")

    for idx, moment in enumerate(moments):
        category = moment.get("category", "INTENSE").lower()
        out_name = f"short_{idx + 1:03d}_{category}.mp4"
        out_path = os.path.join(output_dir, out_name)
        thumb_name = f"thumb_{idx + 1:03d}.jpg"
        thumb_path = os.path.join(output_dir, thumb_name)

        if progress_callback:
            progress_callback(idx, total, f"[{idx + 1}/{total}] Rendering {category} short…")

        try:
            info = _render_one(render_source, moment, out_path, thumb_path, tmp_dir, idx)

            # Optional per-short motion interpolation (opt-in; only for choppy
            # sources). Bounded by this short's length, runs after encode.
            smoothed = False
            if do_smooth:
                if progress_callback:
                    progress_callback(idx, total,
                                      f"[{idx + 1}/{total}] Smoothing short (motion interpolation, this is slow)…")
                try:
                    from services.motion_interpolation import smooth_file_inplace
                    smoothed = smooth_file_inplace(out_path)
                    if smoothed:
                        info["fps"] = 60
                except Exception as e:
                    logger.warning("Per-short smoothing failed: %s", e)

            base = os.path.basename(output_dir)
            tags_csv = format_tags_csv(moment["tags"])

            # Copy-paste-ready metadata sidecar next to the short.
            meta_name = f"short_{idx + 1:03d}_{category}.txt"
            meta_path = os.path.join(output_dir, meta_name)
            try:
                _write_short_metadata(meta_path, moment, tags_csv)
            except Exception as e:
                logger.warning("Could not write metadata sidecar for short %d: %s", idx + 1, e)

            shorts.append({
                "index": idx,
                "output_path": out_path,
                "thumbnail_path": thumb_path if os.path.exists(thumb_path) else None,
                "web_video_path": f"/shorts/{base}/{out_name}",
                "web_thumbnail_path": f"/shorts/{base}/{thumb_name}" if os.path.exists(thumb_path) else None,
                "web_metadata_path": f"/shorts/{base}/{meta_name}" if os.path.exists(meta_path) else None,
                "duration": info["duration"],
                "fps": info.get("fps"),
                "smoothed": smoothed,
                "hook_structure": info["hook_structure"],
                "moment": moment,
                "metadata": {
                    "title": moment["title"],
                    "description": moment["description"],
                    "tags": moment["tags"],
                    "tags_csv": tags_csv,
                    "hook_text": moment.get("hook_text", ""),
                },
            })
            logger.info("Rendered short %d/%d: %s", idx + 1, total, out_name)
        except Exception as e:
            logger.error("Failed to render short %d: %s", idx + 1, e, exc_info=True)
            shorts.append({"index": idx, "output_path": None, "error": str(e), "moment": moment})

        if progress_callback:
            progress_callback(idx + 1, total, f"Completed {idx + 1}/{total} shorts")

    # Clean tmp overlays
    try:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    manifest_path = os.path.join(output_dir, "shorts_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(shorts),
            "successful": sum(1 for s in shorts if s.get("output_path")),
            "game": plan.get("game", ""),
            "summary": plan.get("summary", ""),
            "smoothed": any(s.get("smoothed") for s in shorts),
            "shorts": shorts,
        }, f, indent=2, ensure_ascii=False)

    # Combined, human-readable metadata for ALL shorts of this video.
    try:
        combined = []
        if plan.get("game"):
            combined.append(f"GAME: {plan['game']}")
        if plan.get("summary"):
            combined.append(f"SUMMARY: {plan['summary']}")
        if combined:
            combined.append("")
            combined.append("=" * 60)
            combined.append("")
        for s in shorts:
            if not s.get("output_path"):
                continue
            m = s["moment"]
            combined += [
                f"SHORT #{s['index'] + 1}  [{m.get('category', 'INTENSE')} · "
                f"virality {m.get('virality_score', 5)}/10 · {s.get('duration', 0)}s]",
                f"File: {os.path.basename(s['output_path'])}",
                "",
                "Title:",
                m.get("title", ""),
                "",
                "Description:",
                m.get("description", ""),
                "",
                "Tags:",
                s["metadata"]["tags_csv"],
                "",
                "-" * 60,
                "",
            ]
        base = os.path.basename(output_dir)
        with open(os.path.join(output_dir, "metadata.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(combined))
    except Exception as e:
        logger.warning("Could not write combined metadata.txt: %s", e)

    if progress_callback:
        ok = sum(1 for s in shorts if s.get("output_path"))
        progress_callback(total, total, f"Rendered {ok}/{total} shorts!")

    return shorts
