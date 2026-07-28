#!/usr/bin/env python3
"""
Agent Worker CLI (used by the shorts-generator skill)

The web app extracts frames and parks jobs as 'awaiting_agent'. The AI agent
(Copilot) uses THIS cli to discover jobs, learn where the frames / contact
sheets are, and submit its analysis plan. The app then renders the shorts.

Commands:
  list                         List jobs awaiting agent analysis (JSON).
  show <job_id>                Show a job's detail + contact-sheet index (JSON).
  frames <job_id> [--stride N] List frame files with timestamps (JSON) so the
                               agent can open specific frames it wants to inspect.
  submit <job_id> <plan.json>  Validate + submit the agent's plan; the app then
                               renders the shorts. Reads '-' for stdin.
  wait  <job_id> [--timeout S] Block until the job completes/errs (for scripting).
  status <job_id>              Print current job status (JSON).

All paths are resolved relative to this repo, so the CLI works no matter the
current working directory.
"""

import os
import sys
import json
import time
import argparse

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)

from services.job_queue import init_job_queue, STATUS_COMPLETED, STATUS_ERROR  # noqa: E402

JOBS_DIR = os.path.join(REPO_DIR, "jobs")


def _jq():
    return init_job_queue(JOBS_DIR)


def _print(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cmd_list(_args):
    jq = _jq()
    jobs = jq.awaiting_agent_jobs()
    _print({
        "awaiting_agent": [
            {
                "job_id": j.get("job_id"),
                "filename": j.get("filename"),
                "frames_dir": j.get("frames_dir"),
                "frame_count": j.get("frame_count"),
                "duration": j.get("duration"),
                "created_at": j.get("created_at"),
            }
            for j in jobs
        ],
        "total": len(jobs),
        "MUST_READ": "Before selecting any moment, read HOOK_DETECTION.md and follow "
                     "it strictly (vision gate, ground-truth payoff signals, score>=6 "
                     "filter, self-verification). 'See it, prove it, or skip it.'",
    })


def cmd_show(args):
    jq = _jq()
    job = jq.get_job(args.job_id)
    if not job:
        _print({"error": "job not found"})
        sys.exit(1)
    sheets = None
    frames_dir = job.get("frames_dir")
    if frames_dir:
        idx = os.path.join(frames_dir, "sheets", "index.json")
        if os.path.exists(idx):
            with open(idx) as f:
                sheets = json.load(f)
    _print({"job": job, "sheets": sheets})


def cmd_frames(args):
    jq = _jq()
    job = jq.get_job(args.job_id)
    if not job:
        _print({"error": "job not found"})
        sys.exit(1)
    frames_dir = job.get("frames_dir")
    manifest_path = os.path.join(frames_dir, "manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    frames = manifest["frames"][:: max(1, args.stride)]
    _print({
        "frames_dir": frames_dir,
        "duration": manifest.get("duration"),
        "total": len(manifest["frames"]),
        "returned": len(frames),
        "frames": [
            {"timestamp": fr["timestamp"], "path": os.path.join(frames_dir, fr["filename"])}
            for fr in frames
        ],
    })


def _lint_plan(plan):
    """
    Enforce the HOOK_DETECTION.md quality bar before a plan is accepted. Returns
    a list of human-readable problems (empty = passes). This is a guardrail so a
    careless agent can't submit obvious filler.
    """
    problems = []
    moments = plan.get("moments") if isinstance(plan, dict) else None
    if not isinstance(moments, list) or not moments:
        return ["plan.moments must be a non-empty list"]

    for i, m in enumerate(moments):
        tag = f"moment[{i}]"
        reason = str(m.get("reason", "")).strip()
        desc = str(m.get("description", "")).strip()
        score = m.get("virality_score", 0)
        # Rule: every moment must be grounded — a 'reason' pointing at what was seen.
        if len(reason) < 15:
            problems.append(f"{tag}: 'reason' too short/absent — you must state the "
                            f"visible payoff you saw (HOOK_DETECTION.md Rule 0).")
        # Rule: score gate >= 6.
        try:
            if float(score) < 6:
                problems.append(f"{tag}: virality_score {score} < 6 — discard it "
                                f"(HOOK_DETECTION.md scoring gate).")
        except (TypeError, ValueError):
            problems.append(f"{tag}: virality_score missing/invalid.")
        # Rule: need a payoff-ish signal word in reason (soft check, warns only).
        if reason and not any(k in reason.lower() for k in (
            "win", "won", "victory", "elimin", "kill", "ko", "knock", "clutch",
            "combo", "mission passed", "placed", "xp", "boss", "defeat", "ace",
            "score", "goal", "finish", "surviv", "headshot", "explos")):
            problems.append(f"{tag}: 'reason' has no clear payoff keyword — make "
                            f"sure a real on-screen result is described, not vibes.")

    # Overlap check
    spans = sorted((float(m.get("start_time", 0)), float(m.get("end_time", 0)))
                   for m in moments if m.get("end_time"))
    for a, b in zip(spans, spans[1:]):
        if b[0] < a[1]:
            problems.append(f"moments overlap ({a} & {b}); keep only the higher score.")
            break
    return problems


def cmd_submit(args):
    jq = _jq()
    if args.plan == "-":
        raw = sys.stdin.read()
    else:
        with open(args.plan) as f:
            raw = f.read()
    plan = json.loads(raw)

    problems = _lint_plan(plan)
    if problems and not args.force:
        _print({
            "status": "rejected",
            "message": "Plan failed the HOOK_DETECTION.md quality gate. Fix these, "
                       "or re-run with --force if you are certain each moment has a "
                       "payoff you actually saw in a frame.",
            "problems": problems,
        })
        sys.exit(2)

    normalized = jq.save_plan(args.job_id, plan)
    _print({
        "status": "submitted",
        "quality_gate": "forced" if (problems and args.force) else "passed",
        "job_id": args.job_id,
        "moment_count": len(normalized["moments"]),
        "moments": [
            {"id": m["id"], "category": m["category"],
             "virality_score": m["virality_score"], "title": m["title"]}
            for m in normalized["moments"]
        ],
    })


def cmd_status(args):
    jq = _jq()
    job = jq.get_job(args.job_id)
    if not job:
        _print({"error": "job not found"})
        sys.exit(1)
    _print({"job_id": args.job_id, "status": job.get("status"),
            "percentage": job.get("percentage"), "step_message": job.get("step_message"),
            "error": job.get("error")})


def cmd_wait(args):
    jq = _jq()
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        job = jq.get_job(args.job_id)
        if not job:
            _print({"error": "job not found"})
            sys.exit(1)
        status = job.get("status")
        if status in (STATUS_COMPLETED, STATUS_ERROR):
            _print({"job_id": args.job_id, "status": status,
                    "result": job.get("result"), "error": job.get("error")})
            return
        time.sleep(2)
    _print({"job_id": args.job_id, "status": "timeout"})


def main():
    parser = argparse.ArgumentParser(description="Agent worker for the shorts generator")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)

    p_show = sub.add_parser("show")
    p_show.add_argument("job_id")
    p_show.set_defaults(func=cmd_show)

    p_frames = sub.add_parser("frames")
    p_frames.add_argument("job_id")
    p_frames.add_argument("--stride", type=int, default=1)
    p_frames.set_defaults(func=cmd_frames)

    p_submit = sub.add_parser("submit")
    p_submit.add_argument("job_id")
    p_submit.add_argument("plan", help="path to plan.json, or '-' for stdin")
    p_submit.add_argument("--force", action="store_true",
                          help="submit even if the HOOK_DETECTION.md quality gate flags issues")
    p_submit.set_defaults(func=cmd_submit)

    p_status = sub.add_parser("status")
    p_status.add_argument("job_id")
    p_status.set_defaults(func=cmd_status)

    p_wait = sub.add_parser("wait")
    p_wait.add_argument("job_id")
    p_wait.add_argument("--timeout", type=int, default=600)
    p_wait.set_defaults(func=cmd_wait)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
