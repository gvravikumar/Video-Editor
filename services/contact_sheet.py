"""
Contact Sheet Builder (agent aid)

The agent analyzes gameplay by *looking* at the extracted frames. Viewing
thousands of individual JPEGs is slow and burns context, so this builds compact
labeled contact sheets (grids) — each cell stamped with its timestamp — so the
agent can scan a whole match quickly and zoom into specific frames only where
something epic is happening.

Output: <frames_dir>/sheets/sheet_000.jpg, sheet_001.jpg, ...
plus sheets/index.json mapping each cell to (timestamp, frame filename).
"""

import os
import json
import logging

logger = logging.getLogger(__name__)


def build_contact_sheets(
    frames_dir,
    manifest_path=None,
    cols=6,
    rows=6,
    cell_w=320,
    cell_h=180,
    progress_callback=None,
):
    """
    Build labeled contact sheets from extracted frames.

    Returns dict: {"sheets": [{path, web_path, cells:[{timestamp, filename}]}], "total_frames": N}
    """
    from PIL import Image, ImageDraw, ImageFont

    if manifest_path is None:
        manifest_path = os.path.join(frames_dir, "manifest.json")
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    frames = manifest["frames"]
    total = len(frames)
    per_sheet = cols * rows
    sheets_dir = os.path.join(frames_dir, "sheets")
    os.makedirs(sheets_dir, exist_ok=True)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 18)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        except Exception:
            font = ImageFont.load_default()

    sheets = []
    sheet_w = cols * cell_w
    sheet_h = rows * cell_h
    num_sheets = (total + per_sheet - 1) // per_sheet

    for s in range(num_sheets):
        sheet_img = Image.new("RGB", (sheet_w, sheet_h), (18, 18, 18))
        draw = ImageDraw.Draw(sheet_img)
        cells = []
        batch = frames[s * per_sheet:(s + 1) * per_sheet]

        for i, frame_info in enumerate(batch):
            r, c = divmod(i, cols)
            x, y = c * cell_w, r * cell_h
            img_path = os.path.join(frames_dir, frame_info["filename"])
            try:
                thumb = Image.open(img_path).convert("RGB").resize((cell_w, cell_h))
                sheet_img.paste(thumb, (x, y))
            except Exception:
                draw.rectangle([x, y, x + cell_w, y + cell_h], fill=(40, 40, 40))

            ts = frame_info["timestamp"]
            label = f"{int(ts // 60):02d}:{ts % 60:05.2f}"
            # dark strip + timestamp
            draw.rectangle([x, y, x + 96, y + 22], fill=(0, 0, 0))
            draw.text((x + 4, y + 2), label, fill=(255, 214, 10), font=font)
            cells.append({"timestamp": ts, "filename": frame_info["filename"]})

        sheet_name = f"sheet_{s:03d}.jpg"
        sheet_path = os.path.join(sheets_dir, sheet_name)
        sheet_img.save(sheet_path, "JPEG", quality=82)
        video_id = os.path.basename(os.path.normpath(frames_dir))
        sheets.append({
            "path": sheet_path,
            "web_path": f"/frames/{video_id}/sheets/{sheet_name}",
            "cells": cells,
        })
        if progress_callback:
            progress_callback(s + 1, num_sheets, f"Built contact sheet {s + 1}/{num_sheets}")

    index = {
        "total_frames": total,
        "sheet_count": len(sheets),
        "grid": {"cols": cols, "rows": rows, "cell_w": cell_w, "cell_h": cell_h},
        "duration": manifest.get("duration", 0),
        "sheets": sheets,
    }
    with open(os.path.join(sheets_dir, "index.json"), "w") as f:
        json.dump(index, f, indent=2)

    logger.info("Built %d contact sheets for %d frames", len(sheets), total)
    return index
