"""
Metadata Generator Service
Generates titles, descriptions, and tags for each short video
using TinyLlama. Optimized for YouTube Shorts / Instagram Reels.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)


def generate_metadata_for_short(short_info, generate_text_fn):
    """
    Generate title, description, and tags for a single short.
    
    Args:
        short_info: dict with moment data (category, description, duration, etc.)
        generate_text_fn: callable to generate text (from story_generator)
    
    Returns:
        dict with title, description, tags
    """
    moment = short_info.get("moment", {})
    category = moment.get("category", "INTENSE")
    description = moment.get("description", "gameplay moment")
    virality_score = moment.get("virality_score", 5)
    duration = short_info.get("duration", 30)
    start_time = moment.get("start_time", 0)

    # Format timestamp for context
    minutes = int(start_time // 60)
    seconds = int(start_time % 60)
    time_str = f"{minutes}:{seconds:02d}"

    # Generate title
    title_prompt = f"""Generate ONE catchy YouTube Shorts title for this gameplay clip. The title should be attention-grabbing, use emojis, and be under 60 characters.

Clip details:
- Category: {category}
- What happens: {description}
- Duration: {duration:.0f} seconds
- Virality potential: {virality_score}/10

Requirements:
- Use 1-3 relevant emojis
- Make it dramatic and clickable
- Under 60 characters
- Do NOT use quotes

Title:"""

    title = generate_text_fn(title_prompt, max_new_tokens=40, temperature=0.8)
    # Clean up title - take first line, remove quotes
    title = title.split("\n")[0].strip().strip('"').strip("'")
    if len(title) > 80:
        title = title[:77] + "..."

    # Generate description
    desc_prompt = f"""Write a short YouTube Shorts description for this gameplay clip. 2-3 sentences max.

Clip details:
- Category: {category}  
- What happens: {description}
- Virality: {virality_score}/10

Description (2-3 sentences, engaging, with a call to action):"""

    desc = generate_text_fn(desc_prompt, max_new_tokens=100, temperature=0.7)
    desc = desc.strip().split("\n\n")[0]  # Take first paragraph only
    if len(desc) > 300:
        desc = desc[:297] + "..."

    # Generate tags
    tags_prompt = f"""Generate 10-15 relevant hashtags for this gameplay short video.

Clip details:
- Category: {category}
- What happens: {description}
- Games: Age of Empires, Call of Duty, Fortnite

List hashtags separated by spaces (e.g., #gaming #shorts #viral):"""

    tags_response = generate_text_fn(tags_prompt, max_new_tokens=80, temperature=0.6)

    # Parse tags
    tags = _parse_tags(tags_response, category)

    return {
        "title": title,
        "description": desc,
        "tags": tags
    }


def _parse_tags(tags_text, category):
    """Parse and clean hashtags from LLM response."""
    import re

    # Extract hashtags
    found_tags = re.findall(r'#\w+', tags_text)

    # Ensure we have base tags
    base_tags = ["#gaming", "#shorts", "#viral", "#gameplay"]

    category_tags = {
        "WINNING": ["#win", "#victory", "#clutch", "#epic"],
        "LOSING": ["#fail", "#epicfail", "#rip", "#gameover"],
        "SATISFYING": ["#satisfying", "#oddlysatisfying", "#perfect", "#clean"],
        "INTENSE": ["#intense", "#insane", "#crazy", "#action"],
        "FUNNY": ["#funny", "#lol", "#humor", "#comedy"]
    }

    # Combine and deduplicate
    all_tags = list(dict.fromkeys(
        found_tags + base_tags + category_tags.get(category, [])
    ))

    # Limit to 15 tags
    return all_tags[:15]


def generate_all_metadata(shorts, output_dir, progress_callback=None):
    """
    Generate metadata for all shorts.
    
    Args:
        shorts: list of short info dicts from short_generator
        output_dir: Directory to save metadata
        progress_callback: Optional callable(current, total, status_message)
    
    Returns:
        list of shorts with metadata added
    """
    from services.story_generator import generate_text, load_model

    os.makedirs(output_dir, exist_ok=True)

    # Only process successful shorts
    valid_shorts = [s for s in shorts if s.get("output_path")]
    total = len(valid_shorts)

    if progress_callback:
        progress_callback(0, total, "Loading AI model for metadata generation...")

    # Ensure model is loaded
    load_model()

    if progress_callback:
        progress_callback(0, total, "Generating titles, descriptions, and tags...")

    enriched_shorts = []

    for idx, short_info in enumerate(valid_shorts):
        try:
            metadata = generate_metadata_for_short(short_info, generate_text)
            short_info["metadata"] = metadata
            logger.info(f"Generated metadata for short {idx + 1}/{total}: {metadata['title']}")
        except Exception as e:
            logger.error(f"Error generating metadata for short {idx + 1}: {e}")
            short_info["metadata"] = {
                "title": f"Epic {short_info.get('moment', {}).get('category', 'Gaming').title()} Moment 🎮🔥",
                "description": "An incredible gameplay moment you don't want to miss!",
                "tags": ["#gaming", "#shorts", "#viral", "#gameplay", "#epic"]
            }

        enriched_shorts.append(short_info)

        if progress_callback:
            progress_callback(idx + 1, total, f"Generated metadata {idx + 1}/{total}")

    # Save enriched metadata
    metadata_path = os.path.join(output_dir, "shorts_with_metadata.json")
    enriched_shorts_path = os.path.join(output_dir, "enriched_shorts.json")
    with open(metadata_path, "w") as f:
        json.dump({
            "total": len(enriched_shorts),
            "shorts": enriched_shorts
        }, f, indent=2)
    
    # Also save in the format expected by resume logic
    with open(enriched_shorts_path, "w") as f:
        json.dump(enriched_shorts, f, indent=2)

    if progress_callback:
        progress_callback(total, total, "Metadata generation complete!")

    logger.info(f"Generated metadata for {len(enriched_shorts)} shorts")
    return enriched_shorts