"""
Story Generator Service
Builds a timestamped gameplay timeline from BLIP frame captions (no LLM narration),
then detects key moments using keyword/pattern matching on the actual caption text.
"""

import os
import re
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)



def _chunk_captions(captions, chunk_size=100):
    """Split captions into manageable chunks for the LLM context window."""
    chunks = []
    for i in range(0, len(captions), chunk_size):
        chunk = captions[i:i + chunk_size]
        chunks.append(chunk)
    return chunks


def _format_captions_for_prompt(captions_chunk):
    """Format a chunk of captions into a text block for the prompt."""
    lines = []
    for c in captions_chunk:
        ts = c["timestamp"]
        minutes = int(ts // 60)
        seconds = ts % 60
        time_str = f"{minutes:02d}:{seconds:05.2f}"
        lines.append(f"[{time_str}] {c['caption']}")
    return "\n".join(lines)


def generate_story(captions_data, progress_callback=None):
    """
    Build a gameplay timeline directly from BLIP frame captions.
    No LLM narration — the raw caption per frame is exactly what the AI observed.
    All captions together form an accurate text representation of the full gameplay.

    Args:
        captions_data: dict with 'captions' list from frame_analyzer
        progress_callback: Optional callable(current, total, status_message)

    Returns:
        dict with story text and timestamp mappings
    """
    captions = captions_data["captions"]
    total_captions = len(captions)

    if progress_callback:
        progress_callback(0, 2, "Building gameplay timeline from frame observations...")

    # Group captions into segments of ~80 frames for display / downstream use
    chunks = _chunk_captions(captions, chunk_size=80)
    story_parts = []

    for chunk in chunks:
        start_time = chunk[0]["timestamp"]
        end_time = chunk[-1]["timestamp"]

        # Each line: [MM:SS.ss] <exact caption from BLIP>
        lines = []
        for c in chunk:
            ts = c["timestamp"]
            minutes = int(ts // 60)
            seconds = ts % 60
            time_str = f"{minutes:02d}:{seconds:05.2f}"
            lines.append(f"[{time_str}] {c['caption']}")

        story_parts.append({
            "start_time": start_time,
            "end_time": end_time,
            "narrative": "\n".join(lines),
            "frame_range": [chunk[0]["index"], chunk[-1]["index"]]
        })

    # Full gameplay text: every frame's observed caption in order
    full_story = "\n\n".join([
        f"[{p['start_time']:.1f}s - {p['end_time']:.1f}s]\n{p['narrative']}"
        for p in story_parts
    ])

    story_result = {
        "full_story": full_story,
        "parts": story_parts,
        "total_captions_processed": total_captions
    }

    if progress_callback:
        progress_callback(2, 2, "Gameplay timeline built!")

    return story_result


def detect_moments(captions_data, progress_callback=None):
    """
    Detect key moments directly from BLIP frame captions using keyword/pattern matching.
    No LLM involved — fast, reliable, and grounded in what the vision model actually observed.

    Args:
        captions_data: dict with 'captions' list from frame_analyzer
        progress_callback: Optional callable(current, total, status_message)

    Returns:
        list of moments sorted by virality score (descending)
    """
    captions = captions_data["captions"]
    total = len(captions)

    if progress_callback:
        progress_callback(0, 2, "Scanning frame observations for key moments...")

    all_moments = _heuristic_moment_detection(captions)

    if progress_callback:
        progress_callback(1, 2, f"Found {len(all_moments)} moments, scoring...")

    # Sort by virality score (descending)
    all_moments.sort(key=lambda m: m["virality_score"], reverse=True)

    # Assign unique IDs
    for i, moment in enumerate(all_moments):
        moment["id"] = i + 1

    if progress_callback:
        progress_callback(2, 2, f"Detected {len(all_moments)} key moments!")

    logger.info(f"Detected {len(all_moments)} moments from {total} captions")
    return all_moments



def _match_keywords(text, word_list):
    """
    Match keywords against text with word-boundary checking for single words.
    Multi-word phrases use substring match. Returns (hit_count, unique_matched_set).
    """
    unique_matched = set()
    for word in word_list:
        if ' ' in word:
            # Multi-word phrase: substring match
            if word in text:
                unique_matched.add(word)
        else:
            # Single word: word boundary to avoid false positives (e.g. "fire" ≠ "fireworks")
            if re.search(r'\b' + re.escape(word) + r'\b', text):
                unique_matched.add(word)
    return len(unique_matched), unique_matched


def _heuristic_moment_detection(captions):
    """
    Detect moments based on what BLIP actually reports in captions.
    Keywords are chosen to match BLIP's vocabulary for gameplay visuals.
    Uses word-boundary matching to avoid false positives, and rewards
    keyword diversity (many different keywords = genuinely intense window).
    """
    moments = []

    # Keywords matched against BLIP caption text (lowercase).
    # INTENSE list is expanded to cover BLIP's actual descriptive vocabulary:
    # BLIP describes what it sees literally ("soldier", "armed", "group of enemies")
    # rather than game-mechanic terms ("combo", "kill streak").
    keywords = {
        "WINNING": [
            "victory", "win", "won", "champion", "conquered", "captured",
            "success", "killed", "eliminated", "destroy", "score", "points",
            "reward", "level up", "upgrade", "complete", "finish", "trophy",
            "medal", "first place", "top", "bonus", "achievement"
        ],
        "LOSING": [
            "defeat", "lost", "died", "dead", "death", "destroyed", "fail",
            "game over", "eliminated", "hurt", "damage", "injured", "burning",
            "falling", "trap", "caught", "explosion near", "hit by"
        ],
        "SATISFYING": [
            "perfect", "combo", "streak", "clutch", "amazing", "incredible",
            "build", "castle", "wonder", "craft", "constructed", "assembled",
            "lineup", "collection", "organized", "full", "completed",
            "chain", "simultaneous"
        ],
        "INTENSE": [
            # Combat actions — verbs BLIP commonly outputs for action frames
            "battle", "fight", "fighting", "attack", "attacking", "combat",
            "war", "warfare", "siege", "assault", "ambush", "raid", "brawl",
            "duel", "clash",
            # Weapons — nouns BLIP identifies in gameplay frames
            "gun", "guns", "sword", "weapon", "weapons", "armed", "explosive",
            "grenade", "missile", "arrow", "spear", "bomb", "rifle", "pistol",
            "cannon", "shotgun", "sniper",
            # Effects / events
            "explosion", "exploding", "fire", "flames", "smoke", "debris",
            "destruction", "crash", "collision", "impact", "blast", "burning",
            # Movement / pursuit — BLIP often describes rapid movement
            "running", "chasing", "fleeing", "rushing", "charging", "sprinting",
            "pursuit", "escaping", "retreating", "diving", "jumping",
            # Groups / armies — BLIP describes crowds as "group of soldiers" etc.
            "army", "soldiers", "troops", "enemies", "crowd", "horde", "squad",
            "surrounded", "outnumbered", "group of enemies", "group of soldiers",
            # Vehicles / air
            "tank", "helicopter", "plane", "aircraft", "speeding", "racing",
            "flying", "airborne",
            # Generic intensity signals in BLIP captions
            "dangerous", "intense", "chaos", "chaotic", "rapid", "fast",
            "aggressive", "hostile"
        ],
        "FUNNY": [
            "funny", "glitch", "bug", "weird", "odd", "strange", "stuck",
            "floating", "flying without", "spinning", "upside down",
            "unexpected", "random", "unusual position", "clipping"
        ]
    }

    # Sliding window: 20 frames (~10s at 2fps), step 10 frames (~5s)
    window_size = 20
    step = 10
    last_caption_ts = captions[-1]["timestamp"] if captions else 0

    for i in range(0, len(captions) - window_size, step):
        window = captions[i:i + window_size]
        combined_text = " ".join([c["caption"].lower() for c in window])

        category_scores = {}
        category_unique = {}
        for category, words in keywords.items():
            score, matched = _match_keywords(combined_text, words)
            category_scores[category] = score
            category_unique[category] = matched

        best_category = max(category_scores, key=category_scores.get)
        best_score = category_scores[best_category]

        if best_score < 2:
            continue

        start_time = window[0]["timestamp"]
        end_time = window[-1]["timestamp"]

        # Extend short windows to make a usable clip (~30-45s)
        if end_time - start_time < 30:
            end_time = min(start_time + 45, last_caption_ts)

        # Diversity bonus: ≥4 different keywords matched = genuinely varied/intense window
        unique_count = len(category_unique[best_category])
        diversity_bonus = 1 if unique_count >= 4 else 0

        # Virality: score × 2, +2 for WINNING/LOSING (most shareable), +1 diversity
        virality = min(10, best_score * 2 + diversity_bonus + (2 if best_category in ("WINNING", "LOSING") else 0))

        # Build description from top matching caption in window
        matched_words = category_unique[best_category]
        top_caption = max(
            window,
            key=lambda c: _match_keywords(c["caption"].lower(), keywords[best_category])[0]
        )
        description = (
            f"{best_category.capitalize()} moment around {start_time:.0f}s — "
            f"'{top_caption['caption'].strip()}'"
        )

        moments.append({
            "start_time": round(start_time, 2),
            "end_time": round(end_time, 2),
            "category": best_category,
            "virality_score": virality,
            "description": description,
            "duration": round(end_time - start_time, 2),
            "matched_keywords": sorted(matched_words)
        })

    # Deduplicate overlapping moments — keep the one with higher virality
    moments.sort(key=lambda m: m["virality_score"], reverse=True)
    filtered = []
    for moment in moments:
        overlap = any(
            moment["start_time"] < ex["end_time"] and moment["end_time"] > ex["start_time"]
            for ex in filtered
        )
        if not overlap:
            filtered.append(moment)

    return filtered


def generate_full_analysis(captions_path, output_dir, progress_callback=None):
    """
    Run full analysis pipeline: story + moments.
    
    Args:
        captions_path: Path to captions.json from frame_analyzer
        output_dir: Directory to save results
        progress_callback: Optional callable(current, total, status_message)
    
    Returns:
        dict with story and moments data
    """
    os.makedirs(output_dir, exist_ok=True)

    with open(captions_path, "r") as f:
        captions_data = json.load(f)

    total_steps = 7

    if progress_callback:
        progress_callback(0, total_steps, "Starting AI analysis...")

    # Generate story
    def story_progress(current, total, msg):
        if progress_callback:
            progress_callback(current, total_steps, msg)

    story = generate_story(captions_data, progress_callback=story_progress)

    if progress_callback:
        progress_callback(4, total_steps, "Detecting key moments...")

    # Detect moments
    def moment_progress(current, total, msg):
        if progress_callback:
            step = 4 + current
            progress_callback(min(step, total_steps), total_steps, msg)

    moments = detect_moments(captions_data, progress_callback=moment_progress)

    # Save results
    story_path = os.path.join(output_dir, "story.json")
    with open(story_path, "w") as f:
        json.dump(story, f, indent=2)

    moments_path = os.path.join(output_dir, "moments.json")
    with open(moments_path, "w") as f:
        json.dump({"moments": moments, "total": len(moments)}, f, indent=2)

    if progress_callback:
        progress_callback(total_steps, total_steps, "AI analysis complete!")

    return {
        "story": story,
        "moments": moments,
        "story_path": story_path,
        "moments_path": moments_path
    }