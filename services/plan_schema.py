"""
Plan Schema + Validator (agent output contract)

The AI agent (Copilot, driven by the shorts-generator skill) analyzes the
extracted gameplay frames and writes a PLAN describing which moments to turn
into hook-based shorts. This module defines and validates that contract so the
deterministic renderer can trust its input.

A plan looks like:

{
  "game": "Valorant",                     # optional, agent's best guess
  "summary": "Ranked match, several...",  # optional, short overview
  "moments": [
    {
      "start_time": 812.0,                # seconds into source video (build-up start)
      "end_time":   840.0,                # seconds — the climax/result timestamp
      "peak_time":  838.5,                # seconds — the single most epic instant
      "category":   "WINNING",            # WINNING|LOSING|SATISFYING|INTENSE|FUNNY|CLUTCH
      "virality_score": 9,                # 1..10, agent's ranking of shareability
      "hook_text":  "1v4 CLUTCH?!",       # <= ~30 chars, on-screen hook overlay
      "reason":     "Player wins a 1v4 ...", # why this is epic (grounding)
      "title":      "🔥 INSANE 1v4 Clutch to Win!",
      "description":"Down to the last player...",
      "tags":       ["#valorant", "#clutch", ...]
    },
    ...
  ]
}

The renderer only strictly requires, per moment: start_time, end_time, category.
Everything else is normalized/defaulted here so a partial plan still renders.
"""

from typing import Any, Dict, List

VALID_CATEGORIES = {
    "WINNING", "LOSING", "SATISFYING", "INTENSE", "FUNNY", "CLUTCH",
}

DEFAULT_TAGS = ["#gaming", "#shorts", "#viral", "#gameplay"]

CATEGORY_TAGS = {
    "WINNING": ["#win", "#victory", "#epic"],
    "LOSING": ["#fail", "#epicfail", "#gameover"],
    "SATISFYING": ["#satisfying", "#oddlysatisfying", "#perfect"],
    "INTENSE": ["#intense", "#insane", "#action"],
    "FUNNY": ["#funny", "#lol", "#funnymoments"],
    "CLUTCH": ["#clutch", "#insane", "#nodebate"],
}


class PlanValidationError(ValueError):
    """Raised when a plan is structurally unusable."""


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def _normalize_tags(tags: Any, category: str) -> List[str]:
    out: List[str] = []
    if isinstance(tags, list):
        for t in tags:
            if not isinstance(t, str):
                continue
            t = t.strip()
            if not t:
                continue
            if not t.startswith("#"):
                t = "#" + t.lstrip("#")
            t = t.replace(" ", "")
            if t.lower() not in [o.lower() for o in out]:
                out.append(t)
    # Ensure category + base tags are present, capped at 15
    for t in CATEGORY_TAGS.get(category, []) + DEFAULT_TAGS:
        if t.lower() not in [o.lower() for o in out]:
            out.append(t)
    return out[:15]


def _normalize_moment(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise PlanValidationError(f"moment[{index}] is not an object")

    start = _coerce_float(raw.get("start_time"))
    end = _coerce_float(raw.get("end_time"))
    if end <= start:
        # Give it a sane 30s window ending at end (or start+30 if end invalid)
        if end > 0:
            start = max(0.0, end - 30.0)
        else:
            end = start + 30.0

    category = str(raw.get("category", "INTENSE")).upper().strip()
    if category not in VALID_CATEGORIES:
        category = "INTENSE"

    peak = _coerce_float(raw.get("peak_time"), default=end)
    # peak should fall within [start, end]; default to the climax (end)
    if not (start <= peak <= end):
        peak = end

    virality = _coerce_int(raw.get("virality_score"), default=5, lo=1, hi=10)

    hook_text = str(raw.get("hook_text", "")).strip()[:40]
    title = str(raw.get("title", "")).strip()[:100]
    description = str(raw.get("description", "")).strip()[:400]
    reason = str(raw.get("reason", "")).strip()[:400]
    tags = _normalize_tags(raw.get("tags"), category)

    if not title:
        title = f"Epic {category.title()} Moment 🎮🔥"
    if not description:
        description = "An incredible gameplay moment you don't want to miss! Watch till the end."

    return {
        "start_time": round(start, 2),
        "end_time": round(end, 2),
        "peak_time": round(peak, 2),
        "category": category,
        "virality_score": virality,
        "hook_text": hook_text,
        "reason": reason,
        "title": title,
        "description": description,
        "tags": tags,
        "duration": round(end - start, 2),
    }


def validate_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate + normalize an agent-produced plan. Raises PlanValidationError if
    the plan has no usable moments; otherwise returns a fully-normalized plan.
    """
    if not isinstance(plan, dict):
        raise PlanValidationError("plan must be a JSON object")

    raw_moments = plan.get("moments")
    if not isinstance(raw_moments, list) or not raw_moments:
        raise PlanValidationError("plan.moments must be a non-empty list")

    moments = [_normalize_moment(m, i) for i, m in enumerate(raw_moments)]

    # Sort by virality (desc) and assign stable ids
    moments.sort(key=lambda m: m["virality_score"], reverse=True)
    for i, m in enumerate(moments):
        m["id"] = i + 1

    return {
        "game": str(plan.get("game", "")).strip()[:80],
        "summary": str(plan.get("summary", "")).strip()[:1000],
        "moments": moments,
        "total": len(moments),
    }
