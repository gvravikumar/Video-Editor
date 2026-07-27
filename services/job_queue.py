"""
Job Queue Service (agent-in-the-loop)

Replaces the old local-model AI pipeline. The web app no longer runs BLIP /
TinyLlama. Instead it:

  1. Extracts frames from the uploaded gameplay video (deterministic, OpenCV).
  2. Writes a JOB file describing the work to do.
  3. Waits for the *agent* (Copilot, driven by the shorts-generator skill) to
     analyze the frames and write a PLAN.
  4. Renders the shorts deterministically from that plan.

This module owns the job lifecycle + the on-disk contract the agent reads/writes.

Job lifecycle (status field):
    pending_frames   -> app is extracting frames
    awaiting_agent   -> frames ready; the agent must analyze + write plan.json
    plan_ready       -> agent wrote plan.json; app is rendering shorts
    rendering        -> app is cutting/encoding shorts + thumbnails
    completed        -> shorts + metadata ready
    error            -> something failed (see 'error' field)

On-disk layout (all under <base>/jobs/<job_id>/):
    job.json         -> this job's state (single source of truth)
    plan.json        -> written by the AGENT (moments + hook + metadata)

Frames live under <frames>/<video_id>/ (shared per video, reused across jobs).
Shorts are rendered under <shorts>/<job_id>/.
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Job status constants
STATUS_PENDING_FRAMES = "pending_frames"
STATUS_AWAITING_AGENT = "awaiting_agent"
STATUS_PLAN_READY = "plan_ready"
STATUS_RENDERING = "rendering"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"

ACTIVE_STATUSES = {
    STATUS_PENDING_FRAMES,
    STATUS_AWAITING_AGENT,
    STATUS_PLAN_READY,
    STATUS_RENDERING,
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobQueue:
    """
    File-backed job queue shared between the Flask app and the agent.

    Thread-safe within a process (lock) and safe across processes because every
    write is atomic (temp file + rename) and job.json is the single source of
    truth that both the app and the agent read.
    """

    def __init__(self, jobs_dir: str):
        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        logger.info("JobQueue initialized at %s", self.jobs_dir)

    # ------------------------------------------------------------------ paths
    def _job_dir(self, job_id: str) -> Path:
        return self.jobs_dir / job_id

    def _job_file(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "job.json"

    def plan_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "plan.json"

    # ------------------------------------------------------------- atomic io
    @staticmethod
    def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(path)

    @staticmethod
    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    # -------------------------------------------------------------- mutations
    def create_job(self, job_id: str, **fields) -> Dict[str, Any]:
        """Create a new job in the pending_frames state."""
        with self._lock:
            job = {
                "job_id": job_id,
                "status": STATUS_PENDING_FRAMES,
                "percentage": 0,
                "step_message": "Job created",
                "created_at": _utcnow(),
                "updated_at": _utcnow(),
                "error": None,
                **fields,
            }
            self._atomic_write(self._job_file(job_id), job)
            logger.info("Created job %s", job_id)
            return dict(job)

    def update_job(self, job_id: str, **updates) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._read_json(self._job_file(job_id))
            if job is None:
                logger.warning("update_job: %s not found", job_id)
                return None
            job.update(updates)
            job["updated_at"] = _utcnow()
            self._atomic_write(self._job_file(job_id), job)
            return dict(job)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._read_json(self._job_file(job_id))

    def list_jobs(self, statuses: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """List all jobs, optionally filtered by status. Newest first."""
        jobs: List[Dict[str, Any]] = []
        for child in self.jobs_dir.iterdir():
            if not child.is_dir():
                continue
            job = self._read_json(child / "job.json")
            if job is None:
                continue
            if statuses and job.get("status") not in statuses:
                continue
            jobs.append(job)
        jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
        return jobs

    def awaiting_agent_jobs(self) -> List[Dict[str, Any]]:
        """Jobs whose frames are ready and that need the agent to write a plan."""
        return self.list_jobs(statuses=[STATUS_AWAITING_AGENT])

    def mark_awaiting_agent(self, job_id: str, frames_dir: str, manifest: Dict[str, Any]) -> None:
        self.update_job(
            job_id,
            status=STATUS_AWAITING_AGENT,
            percentage=25,
            step_message="Frames ready — waiting for the AI agent to analyze gameplay…",
            frames_dir=frames_dir,
            frame_count=manifest.get("frame_count", 0),
            duration=manifest.get("duration", 0),
            original_fps=manifest.get("original_fps", 0),
            manifest_path=os.path.join(frames_dir, "manifest.json"),
        )

    def mark_error(self, job_id: str, error: str) -> None:
        self.update_job(
            job_id,
            status=STATUS_ERROR,
            error=str(error),
            step_message=f"Error: {error}",
        )
        logger.error("Job %s error: %s", job_id, error)

    def mark_completed(self, job_id: str, result: Dict[str, Any]) -> None:
        self.update_job(
            job_id,
            status=STATUS_COMPLETED,
            percentage=100,
            step_message="Shorts ready!",
            result=result,
        )
        logger.info("Job %s completed", job_id)

    # ----------------------------------------------------------- agent handoff
    def save_plan(self, job_id: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Called by the agent (via the skill) after analyzing frames.
        Writes plan.json and flips the job to plan_ready so the app renders it.
        """
        from services.plan_schema import validate_plan  # local import avoids cycle

        normalized = validate_plan(plan)
        self._atomic_write(self.plan_path(job_id), normalized)
        self.update_job(
            job_id,
            status=STATUS_PLAN_READY,
            percentage=55,
            step_message=f"Agent selected {len(normalized['moments'])} moments — rendering shorts…",
            moment_count=len(normalized["moments"]),
        )
        logger.info("Job %s: plan saved (%d moments)", job_id, len(normalized["moments"]))
        return normalized

    def load_plan(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._read_json(self.plan_path(job_id))

    def wait_for_plan(self, job_id: str, timeout: float = 1800, poll: float = 2.0) -> Optional[Dict[str, Any]]:
        """
        Block until the agent writes a plan (status becomes plan_ready) or timeout.
        Returns the plan dict, or None on timeout/error.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.get_job(job_id)
            if job is None:
                return None
            status = job.get("status")
            if status == STATUS_PLAN_READY:
                return self.load_plan(job_id)
            if status in (STATUS_RENDERING, STATUS_COMPLETED):
                return self.load_plan(job_id)
            if status == STATUS_ERROR:
                return None
            time.sleep(poll)
        logger.warning("Job %s: timed out waiting for agent plan", job_id)
        return None

    def clear_all(self) -> None:
        """Delete all job records (used by cache clear)."""
        import shutil
        with self._lock:
            for child in list(self.jobs_dir.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
        logger.info("Cleared all jobs")


# Global singleton, mirroring state_manager's pattern
_job_queue: Optional[JobQueue] = None


def init_job_queue(jobs_dir: str) -> JobQueue:
    global _job_queue
    _job_queue = JobQueue(jobs_dir)
    return _job_queue


def get_job_queue() -> JobQueue:
    if _job_queue is None:
        raise RuntimeError("JobQueue not initialized. Call init_job_queue() first.")
    return _job_queue
