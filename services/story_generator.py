"""
Story Generator Service
Uses TinyLlama-1.1B-Chat to generate gameplay narratives,
detect key moments, and assign virality scores.
Auto-detects hardware: MPS → CUDA → CPU.
"""

import os
import json
import logging
import re
import torch
from pathlib import Path

logger = logging.getLogger(__name__)

# Global model cache
_model = None
_tokenizer = None
_device = None

MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")


def get_device():
    """Auto-detect best available compute device."""
    if torch.backends.mps.is_available():
        logger.info("Using MPS (Apple Silicon) backend")
        return torch.device("mps")
    elif torch.cuda.is_available():
        logger.info(f"Using CUDA backend: {torch.cuda.get_device_name(0)}")
        return torch.device("cuda")
    else:
        logger.info("Using CPU backend")
        return torch.device("cpu")


def load_model():
    """Load TinyLlama model and tokenizer. Downloads on first run, cached locally."""
    global _model, _tokenizer, _device

    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer, _device

    from transformers import AutoTokenizer, AutoModelForCausalLM

    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path = os.path.join(MODELS_DIR, "tinyllama-chat")

    _device = get_device()

    logger.info(f"Loading TinyLlama model...")

    if os.path.exists(os.path.join(model_path, "config.json")):
        logger.info("Loading model from local cache...")
        _tokenizer = AutoTokenizer.from_pretrained(model_path)
        _model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if _device.type != "cpu" else torch.float32
        )
    else:
        logger.info(f"Downloading TinyLlama model ({MODEL_NAME})... This may take a few minutes.")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float16 if _device.type != "cpu" else torch.float32
        )
        _tokenizer.save_pretrained(model_path)
        _model.save_pretrained(model_path)
        logger.info(f"Model saved to {model_path}")

    _model = _model.to(_device)
    _model.eval()

    logger.info("TinyLlama model loaded successfully.")
    return _model, _tokenizer, _device


def generate_text(prompt, max_new_tokens=512, temperature=0.7):
    """Generate text from a prompt using TinyLlama chat format."""
    model, tokenizer, device = load_model()

    # TinyLlama chat format
    chat_prompt = f"<|system|>\nYou are a gaming content analyst expert. You analyze gameplay footage descriptions and identify key moments.</s>\n<|user|>\n{prompt}</s>\n<|assistant|>\n"

    inputs = tokenizer(chat_prompt, return_tensors="pt", truncation=True, max_length=2048).to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return response.strip()


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
    Generate a complete gameplay story from frame captions.
    
    Args:
        captions_data: dict with 'captions' list from frame_analyzer
        progress_callback: Optional callable(current, total, status_message)
    
    Returns:
        dict with story text and timestamp mappings
    """
    captions = captions_data["captions"]
    total_captions = len(captions)

    if progress_callback:
        progress_callback(0, 4, "Loading AI story model...")

    load_model()

    if progress_callback:
        progress_callback(1, 4, "Generating gameplay narrative...")

    # Generate story in chunks
    chunks = _chunk_captions(captions, chunk_size=80)
    story_parts = []

    for idx, chunk in enumerate(chunks):
        caption_text = _format_captions_for_prompt(chunk)
        start_time = chunk[0]["timestamp"]
        end_time = chunk[-1]["timestamp"]

        prompt = f"""Analyze these gameplay frame descriptions with timestamps and write a brief narrative paragraph describing what's happening in the game. Focus on actions, battles, victories, defeats, and key gameplay events.

Frame descriptions:
{caption_text}

Write a concise gameplay narrative for the period {start_time:.1f}s to {end_time:.1f}s:"""

        narrative = generate_text(prompt, max_new_tokens=300, temperature=0.7)
        story_parts.append({
            "start_time": start_time,
            "end_time": end_time,
            "narrative": narrative,
            "frame_range": [chunk[0]["index"], chunk[-1]["index"]]
        })

    if progress_callback:
        progress_callback(2, 4, "Story generated. Detecting key moments...")

    # Combine into full story
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
        progress_callback(3, 4, "Story generation complete!")

    return story_result


def detect_moments(captions_data, progress_callback=None):
    """
    Detect key moments (wins, losses, satisfying, intense) from frame captions.
    Assigns virality scores to each moment.
    
    Args:
        captions_data: dict with 'captions' list from frame_analyzer
        progress_callback: Optional callable(current, total, status_message)
    
    Returns:
        list of moments sorted by virality score (descending)
    """
    captions = captions_data["captions"]

    if progress_callback:
        progress_callback(0, 3, "Loading AI model for moment detection...")

    load_model()

    if progress_callback:
        progress_callback(1, 3, "Detecting key moments in gameplay...")

    chunks = _chunk_captions(captions, chunk_size=60)
    all_moments = []

    for idx, chunk in enumerate(chunks):
        caption_text = _format_captions_for_prompt(chunk)
        start_time = chunk[0]["timestamp"]
        end_time = chunk[-1]["timestamp"]

        prompt = f"""Analyze these gameplay frame descriptions and identify ALL key moments. For each moment found, provide the information in this EXACT format (one per line):

MOMENT|<start_seconds>|<end_seconds>|<category>|<virality_score>|<description>

Categories: WINNING, LOSING, SATISFYING, INTENSE, FUNNY
Virality score: 1-10 (10 = most viral potential)

The start/end seconds should be within {start_time:.1f} to {end_time:.1f}.

Frame descriptions:
{caption_text}

List ALL key moments found (one per line, using the exact format MOMENT|start|end|category|score|description):"""

        response = generate_text(prompt, max_new_tokens=500, temperature=0.5)

        # Parse moments from response
        moments = _parse_moments(response, start_time, end_time)
        all_moments.extend(moments)

    # If no moments were found through parsing, create them from caption analysis
    if not all_moments:
        logger.info("No moments parsed from LLM output, using heuristic detection...")
        all_moments = _heuristic_moment_detection(captions)

    # Sort by virality score (descending)
    all_moments.sort(key=lambda m: m["virality_score"], reverse=True)

    # Assign unique IDs
    for i, moment in enumerate(all_moments):
        moment["id"] = i + 1

    if progress_callback:
        progress_callback(3, 3, f"Detected {len(all_moments)} key moments!")

    logger.info(f"Detected {len(all_moments)} moments")
    return all_moments


def _parse_moments(response, chunk_start, chunk_end):
    """Parse moment entries from LLM response text."""
    moments = []
    lines = response.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line.startswith("MOMENT|"):
            continue

        parts = line.split("|")
        if len(parts) < 6:
            continue

        try:
            start = float(parts[1].strip())
            end = float(parts[2].strip())
            category = parts[3].strip().upper()
            score = min(10, max(1, int(float(parts[4].strip()))))
            description = parts[5].strip()

            # Validate category
            valid_categories = ["WINNING", "LOSING", "SATISFYING", "INTENSE", "FUNNY"]
            if category not in valid_categories:
                category = "INTENSE"

            # Ensure times are within bounds
            start = max(chunk_start, min(start, chunk_end))
            end = max(start + 1, min(end, chunk_end))

            # Ensure minimum duration for a short (at least 10 seconds of content)
            if end - start < 10:
                # Extend to at least 10 seconds if possible
                end = min(start + 30, chunk_end)
                if end - start < 10:
                    start = max(chunk_start, end - 30)

            moments.append({
                "start_time": round(start, 2),
                "end_time": round(end, 2),
                "category": category,
                "virality_score": score,
                "description": description,
                "duration": round(end - start, 2)
            })
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse moment line: {line} - {e}")
            continue

    return moments


def _heuristic_moment_detection(captions):
    """
    Fallback heuristic: detect moments based on caption content analysis.
    Looks for action-related keywords in captions.
    """
    moments = []
    keywords = {
        "WINNING": ["victory", "win", "won", "champion", "conquered", "captured", "success", "killed", "eliminated", "destroy"],
        "LOSING": ["defeat", "lost", "died", "dead", "death", "destroyed", "fail", "game over", "eliminated"],
        "SATISFYING": ["perfect", "combo", "streak", "clutch", "amazing", "incredible", "build", "castle", "wonder"],
        "INTENSE": ["battle", "fight", "attack", "explosion", "fire", "war", "combat", "siege", "rush"],
        "FUNNY": ["funny", "glitch", "bug", "weird", "odd", "strange", "stuck"]
    }

    # Sliding window approach
    window_size = 20  # 20 frames = 10 seconds at 2fps
    step = 10

    for i in range(0, len(captions) - window_size, step):
        window = captions[i:i + window_size]
        combined_text = " ".join([c["caption"].lower() for c in window])

        best_category = None
        best_score = 0

        for category, words in keywords.items():
            score = sum(1 for word in words if word in combined_text)
            if score > best_score:
                best_score = score
                best_category = category

        if best_score >= 2:  # At least 2 keyword matches
            start_time = window[0]["timestamp"]
            end_time = window[-1]["timestamp"]

            # Extend to make a proper short (30-60 seconds)
            duration = end_time - start_time
            if duration < 30:
                end_time = min(start_time + 45, captions[-1]["timestamp"])

            virality = min(10, best_score * 2 + (3 if best_category == "WINNING" else 0))

            moments.append({
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "category": best_category,
                "virality_score": virality,
                "description": f"Detected {best_category.lower()} moment with gameplay action",
                "duration": round(end_time - start_time, 2)
            })

    # Deduplicate overlapping moments (keep higher virality)
    moments.sort(key=lambda m: m["virality_score"], reverse=True)
    filtered = []
    for moment in moments:
        overlap = False
        for existing in filtered:
            if (moment["start_time"] < existing["end_time"] and
                    moment["end_time"] > existing["start_time"]):
                overlap = True
                break
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