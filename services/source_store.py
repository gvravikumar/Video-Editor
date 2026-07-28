"""
Source-video metadata store (agent-in-the-loop).

Parallel to the shorts pipeline, but for the FULL uploaded gameplay video: the
agent analyzes the extracted frames / contact sheets and writes one set of
YouTube-ready metadata (title, description, tags) for the whole video, so the user
can upload the source gameplay directly (as a long-form video) instead of / in
addition to generating shorts.

State is kept per source file under state/sources/<key>.json:
    status: idle | pending_frames | awaiting_agent | completed | error
    meta:   {title, description, tags, tags_csv, game, summary, generated_at} | None
    youtube:{video_id, url, privacy, uploaded_at} | None

This is deliberately separate from services/job_queue.py so the shorts gallery /
archive listings never pick up source-metadata jobs.
"""

import os
import re
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STATUS_IDLE = "idle"
STATUS_PENDING_FRAMES = "pending_frames"
STATUS_AWAITING_AGENT = "awaiting_agent"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"

YT_TITLE_MAX = 100
YT_DESCRIPTION_MAX = 5000


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(filename: str) -> str:
    """Stable, filesystem-safe key from a filename."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:120]


class SourceStore:
    def __init__(self, state_dir: str):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()  # reentrant: update() may call ensure()

    def _path(self, filename: str) -> Path:
        return self.dir / f"{_key(filename)}.json"

    @staticmethod
    def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(path)

    def get(self, filename: str) -> Optional[Dict[str, Any]]:
        p = self._path(filename)
        if not p.exists():
            return None
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def ensure(self, filename: str) -> Dict[str, Any]:
        rec = self.get(filename)
        if rec:
            return rec
        rec = {
            "filename": filename,
            "key": _key(filename),
            "status": STATUS_IDLE,
            "percentage": 0,
            "step_message": "",
            "meta": None,
            "youtube": None,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            "error": None,
        }
        with self._lock:
            self._atomic_write(self._path(filename), rec)
        return rec

    def update(self, filename: str, **updates) -> Dict[str, Any]:
        with self._lock:
            rec = self.get(filename) or self.ensure(filename)
            rec.update(updates)
            rec["updated_at"] = _utcnow()
            self._atomic_write(self._path(filename), rec)
            return rec

    def all(self) -> List[Dict[str, Any]]:
        out = []
        for child in self.dir.glob("*.json"):
            try:
                with open(child, encoding="utf-8") as f:
                    out.append(json.load(f))
            except (OSError, json.JSONDecodeError):
                continue
        return out

    def awaiting(self) -> List[Dict[str, Any]]:
        return [r for r in self.all() if r.get("status") == STATUS_AWAITING_AGENT]

    def mark_awaiting_agent(self, filename: str, frames_dir: str, manifest: Dict[str, Any]) -> None:
        self.update(
            filename,
            status=STATUS_AWAITING_AGENT,
            percentage=40,
            step_message="Frames ready — waiting for the AI agent to write full-video metadata…",
            frames_dir=frames_dir,
            frame_count=manifest.get("frame_count", 0),
            duration=manifest.get("duration", 0),
        )

    def save_meta(self, filename: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Validate + normalize agent metadata for the full video, mark completed."""
        from services.renderer import format_tags_csv

        title = str(meta.get("title", "")).strip()[:YT_TITLE_MAX]
        description = str(meta.get("description", "")).strip()[:YT_DESCRIPTION_MAX]
        tags = meta.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        if not title:
            raise ValueError("title is required")
        normalized = {
            "title": title,
            "description": description,
            "tags": tags,
            "tags_csv": format_tags_csv(tags),
            "game": str(meta.get("game", "")).strip()[:80],
            "summary": str(meta.get("summary", "")).strip()[:1000],
            "generated_at": _utcnow(),
        }
        self.update(filename, status=STATUS_COMPLETED, percentage=100,
                    step_message="Full-video metadata ready.", meta=normalized, error=None)
        return normalized

    def set_youtube(self, filename: str, yt: Dict[str, Any]) -> None:
        self.update(filename, youtube=yt)

    def mark_error(self, filename: str, error: str) -> None:
        self.update(filename, status=STATUS_ERROR, error=str(error),
                    step_message=f"Error: {error}")


_store: Optional[SourceStore] = None


def init_source_store(state_dir: str) -> SourceStore:
    global _store
    _store = SourceStore(state_dir)
    return _store


def get_source_store() -> SourceStore:
    if _store is None:
        raise RuntimeError("SourceStore not initialized. Call init_source_store() first.")
    return _store
