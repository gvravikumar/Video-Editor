"""
Metadata Generator Service
Uses TinyLlama to generate titles, descriptions, and tags for each short video
grounded in the actual gameplay caption descriptions.
Auto-detects hardware: MPS → CUDA → CPU.
"""

import os
import json
import logging
import torch

logger = logging.getLogger(__name__)

MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

_model = None
_tokenizer = None
_device = None


def _get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    elif torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _load_model():
    global _model, _tokenizer, _device
    if _model is not None:
        return _model, _tokenizer, _device

    from transformers import AutoTokenizer, AutoModelForCausalLM

    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path = os.path.join(MODELS_DIR, "tinyllama-chat")
    _device = _get_device()

    if os.path.exists(os.path.join(model_path, "config.json")):
        logger.info("Metadata: loading TinyLlama from local cache...")
        _tokenizer = AutoTokenizer.from_pretrained(model_path)
        _model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if _device.type != "cpu" else torch.float32
        )
    else:
        logger.info(f"Metadata: downloading TinyLlama ({MODEL_NAME})...")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float16 if _device.type != "cpu" else torch.float32
        )
        _tokenizer.save_pretrained(model_path)
        _model.save_pretrained(model_path)

    _model = _model.to(_device)
    _model.eval()
    logger.info(f"Metadata: TinyLlama ready on {_device}")
    return _model, _tokenizer, _device


def _generate_text(prompt, max_new_tokens=80, temperature=0.7):
    model, tokenizer, device = _load_model()
    system = (
        "You are a YouTube Shorts content creator. "
        "Write catchy, accurate metadata strictly based on the gameplay "
        "description provided. Never invent events not mentioned."
    )
    chat_prompt = (
        f"<|system|>\n{system}</s>\n"
        f"<|user|>\n{prompt}</s>\n<|assistant|>\n"
    )
    inputs = tokenizer(
        chat_prompt, return_tensors="pt", truncation=True, max_length=1024
    ).to(device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    return tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def generate_metadata_for_short(short_info):
    """
    Generate title, description, and tags for a single short using TinyLlama,
    grounded in the actual BLIP caption description of the moment.

    Args:
        short_info: dict with moment data

    Returns:
        dict with title, description, tags
    """
    moment = short_info.get("moment", {})
    category = moment.get("category", "INTENSE")
    description = moment.get("description", "an exciting gameplay moment")
    virality_score = moment.get("virality_score", 5)
    start_time = moment.get("start_time", 0)
    duration = short_info.get("duration", 30)

    minutes = int(start_time // 60)
    seconds = int(start_time % 60)
    time_str = f"{minutes}:{seconds:02d}"

    # --- Title ---
    title_prompt = (
        f"Write ONE YouTube Shorts title for this gameplay clip. "
        f"Use 1-2 emojis. Under 60 characters. No quotes.\n\n"
        f"Clip: {category} moment at {time_str} — {description[:200]}\n\n"
        f"Title:"
    )
    title = _generate_text(title_prompt, max_new_tokens=30, temperature=0.8)
    title = title.split("\n")[0].strip().strip('"').strip("'")
    if len(title) > 80:
        title = title[:77] + "..."

    # --- Description ---
    desc_prompt = (
        f"Write a 2-sentence YouTube Shorts description for this clip. "
        f"End with a call to action. Based only on what's described.\n\n"
        f"Clip: {category} moment — {description[:200]}\n\n"
        f"Description:"
    )
    desc = _generate_text(desc_prompt, max_new_tokens=80, temperature=0.7)
    desc = desc.strip().split("\n\n")[0]
    if len(desc) > 300:
        desc = desc[:297] + "..."

    # --- Tags ---
    tags_prompt = (
        f"List 10 hashtags for this {category.lower()} gameplay clip. "
        f"Based on: {description[:150]}\n"
        f"Format: #tag1 #tag2 ...\n\nHashtags:"
    )
    tags_text = _generate_text(tags_prompt, max_new_tokens=60, temperature=0.6)
    tags = _parse_tags(tags_text, category)

    return {"title": title, "description": desc, "tags": tags}


def _parse_tags(tags_text, category):
    import re
    found = re.findall(r'#\w+', tags_text)
    base = ["#gaming", "#shorts", "#viral", "#gameplay"]
    cat_tags = {
        "WINNING": ["#win", "#victory", "#clutch", "#epic"],
        "LOSING": ["#fail", "#epicfail", "#gameover"],
        "SATISFYING": ["#satisfying", "#oddlysatisfying", "#perfect"],
        "INTENSE": ["#intense", "#insane", "#action"],
        "FUNNY": ["#funny", "#lol", "#comedy"],
    }
    all_tags = list(dict.fromkeys(found + base + cat_tags.get(category, [])))
    return all_tags[:15]


def generate_all_metadata(shorts, output_dir, progress_callback=None):
    """
    Generate metadata for all shorts. Shows per-short progress.

    Args:
        shorts: list of short info dicts from short_generator
        output_dir: Directory to save metadata
        progress_callback: Optional callable(current, total, status_message)

    Returns:
        list of shorts with metadata added
    """
    os.makedirs(output_dir, exist_ok=True)

    valid_shorts = [s for s in shorts if s.get("output_path")]
    total = len(valid_shorts)

    if progress_callback:
        progress_callback(0, total, f"Loading AI model for metadata (0/{total} shorts)...")

    # Pre-load model so first short doesn't stall silently
    _load_model()

    enriched_shorts = []

    for idx, short_info in enumerate(valid_shorts):
        moment = short_info.get("moment", {})
        category = moment.get("category", "INTENSE")
        start_time = moment.get("start_time", 0)
        minutes = int(start_time // 60)
        seconds = int(start_time % 60)

        if progress_callback:
            progress_callback(
                idx, total,
                f"[{idx + 1}/{total}] Generating title & tags for {category} clip at {minutes}:{seconds:02d}..."
            )

        try:
            metadata = generate_metadata_for_short(short_info)
            short_info["metadata"] = metadata
            logger.info("Short %d/%d metadata: %s", idx + 1, total, metadata['title'])

            if progress_callback:
                progress_callback(
                    idx + 1, total,
                    f"[{idx + 1}/{total}] Done — \"{metadata['title'][:50]}\""
                )
        except (RuntimeError, ValueError, KeyError) as e:
            logger.error("Error generating metadata for short %d: %s", idx + 1, e)
            short_info["metadata"] = {
                "title": f"Epic {category.title()} Moment 🎮🔥",
                "description": "An incredible gameplay moment you don't want to miss!",
                "tags": ["#gaming", "#shorts", "#viral", "#gameplay", "#epic"]
            }
            if progress_callback:
                progress_callback(
                    idx + 1, total,
                    f"[{idx + 1}/{total}] Metadata done (used fallback)"
                )

        enriched_shorts.append(short_info)

    # Save results
    metadata_path = os.path.join(output_dir, "shorts_with_metadata.json")
    enriched_shorts_path = os.path.join(output_dir, "enriched_shorts.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump({"total": len(enriched_shorts), "shorts": enriched_shorts}, f, indent=2)
    with open(enriched_shorts_path, "w", encoding="utf-8") as f:
        json.dump(enriched_shorts, f, indent=2)

    if progress_callback:
        progress_callback(total, total, f"Metadata complete! Generated for all {total} shorts.")

    logger.info("Generated metadata for %d shorts", len(enriched_shorts))
    return enriched_shorts
