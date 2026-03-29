"""
Frame Analyzer Service
Uses Salesforce/blip-image-captioning-base to generate captions for extracted frames.
Auto-detects hardware: MPS (Apple Silicon) → CUDA (NVIDIA) → CPU fallback.
"""

import os
import json
import logging
import torch
from PIL import Image
from pathlib import Path

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

# Available vision models — user picks one in the UI before running the pipeline
AVAILABLE_MODELS = {
    "blip-base": {
        "model_id": "Salesforce/blip-image-captioning-base",
        "local_dir": "blip-captioning-base",
        "display_name": "BLIP Base",
        "size_label": "~1 GB",
        "speed_label": "Fast",
        "quality_label": "Good",
        "variant": "blip",
    },
    "blip-large": {
        "model_id": "Salesforce/blip-image-captioning-large",
        "local_dir": "blip-captioning-large",
        "display_name": "BLIP Large",
        "size_label": "~1.5 GB",
        "speed_label": "Medium",
        "quality_label": "Better",
        "variant": "blip",
    },
    "blip2": {
        "model_id": "Salesforce/blip2-opt-2.7b",
        "local_dir": "blip2-opt-2.7b",
        "display_name": "BLIP-2",
        "size_label": "~5.5 GB",
        "speed_label": "Slow",
        "quality_label": "Best",
        "variant": "blip2",
    },
}
DEFAULT_MODEL = "blip-base"

# Per-model cache: model_key -> (model, processor, device)
_loaded_models = {}
_device = None


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


def load_model(model_key=DEFAULT_MODEL):
    """
    Load the requested vision model and processor.
    Downloads on first use and caches locally. Results are cached in memory per model key.
    """
    global _loaded_models, _device

    if model_key not in AVAILABLE_MODELS:
        logger.warning(f"Unknown model key '{model_key}', falling back to {DEFAULT_MODEL}")
        model_key = DEFAULT_MODEL

    if model_key in _loaded_models:
        return _loaded_models[model_key]

    if _device is None:
        _device = get_device()
    device = _device

    config = AVAILABLE_MODELS[model_key]
    model_id = config["model_id"]
    local_path = os.path.join(MODELS_DIR, config["local_dir"])
    variant = config["variant"]

    os.makedirs(MODELS_DIR, exist_ok=True)
    logger.info(f"Loading {config['display_name']} ({model_id})...")

    cached = os.path.exists(os.path.join(local_path, "config.json"))

    if variant == "blip2":
        from transformers import Blip2Processor, Blip2ForConditionalGeneration
        # BLIP-2 is large — float16 saves ~half the VRAM/RAM on GPU/MPS
        dtype = torch.float16 if device.type in ("cuda", "mps") else torch.float32
        if cached:
            processor = Blip2Processor.from_pretrained(local_path)
            model = Blip2ForConditionalGeneration.from_pretrained(local_path, torch_dtype=dtype)
        else:
            logger.info(f"Downloading {config['display_name']} ({config['size_label']})... this may take a while.")
            processor = Blip2Processor.from_pretrained(model_id)
            model = Blip2ForConditionalGeneration.from_pretrained(model_id, torch_dtype=dtype)
            processor.save_pretrained(local_path)
            model.save_pretrained(local_path)
    else:
        from transformers import BlipProcessor, BlipForConditionalGeneration
        if cached:
            processor = BlipProcessor.from_pretrained(local_path)
            model = BlipForConditionalGeneration.from_pretrained(local_path)
        else:
            logger.info(f"Downloading {config['display_name']} ({config['size_label']})... this may take a few minutes.")
            processor = BlipProcessor.from_pretrained(model_id)
            model = BlipForConditionalGeneration.from_pretrained(model_id)
            processor.save_pretrained(local_path)
            model.save_pretrained(local_path)

    model = model.to(device)
    model.eval()

    _loaded_models[model_key] = (model, processor, device)
    logger.info(f"{config['display_name']} loaded on {device}.")
    return model, processor, device


def _get_prompt(model_key):
    """Return the generation prompt for the given model variant."""
    config = AVAILABLE_MODELS.get(model_key, AVAILABLE_MODELS[DEFAULT_MODEL])
    if config["variant"] == "blip2":
        # BLIP-2 (OPT backbone) works best with an instruction-style prompt
        return "Question: Describe the action and intensity of this gameplay screenshot in detail. Answer:"
    return "a video game action scene showing"


def caption_single_frame(image_path, model=None, processor=None, device=None, model_key=DEFAULT_MODEL):
    """Generate a caption for a single image frame."""
    if model is None or processor is None or device is None:
        model, processor, device = load_model(model_key)

    config = AVAILABLE_MODELS.get(model_key, AVAILABLE_MODELS[DEFAULT_MODEL])
    image = Image.open(image_path).convert("RGB")
    prompt = _get_prompt(model_key)

    if config["variant"] == "blip2":
        dtype = next(model.parameters()).dtype
        inputs = processor(images=image, text=prompt, return_tensors="pt").to(device, dtype)
    else:
        inputs = processor(image, text=prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=75,
            num_beams=5,
            early_stopping=True
        )

    caption = processor.decode(output[0], skip_special_tokens=True)
    return caption


def analyze_frames(frames_dir, manifest_path=None, progress_callback=None, vision_model=DEFAULT_MODEL):
    """
    Analyze all extracted frames and generate captions.

    Args:
        frames_dir: Directory containing extracted frame images
        manifest_path: Path to frames manifest JSON (optional, auto-detected)
        progress_callback: Optional callable(current, total, status_message)
        vision_model: Model key from AVAILABLE_MODELS (default: "blip-base")

    Returns:
        dict with:
            - captions: list of {index, timestamp, filename, caption}
            - total_frames: number of frames processed
    """
    if vision_model not in AVAILABLE_MODELS:
        logger.warning(f"Unknown vision_model '{vision_model}', falling back to {DEFAULT_MODEL}")
        vision_model = DEFAULT_MODEL
    model_config = AVAILABLE_MODELS[vision_model]
    # Load manifest
    if manifest_path is None:
        manifest_path = os.path.join(frames_dir, "manifest.json")

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    frames = manifest["frames"]
    total = len(frames)

    logger.info(f"Analyzing {total} frames with {model_config['display_name']}...")

    if progress_callback:
        progress_callback(0, total, f"Loading {model_config['display_name']} ({model_config['size_label']})...")

    # Load the requested model
    model, processor, device = load_model(vision_model)
    prompt = _get_prompt(vision_model)

    if progress_callback:
        progress_callback(0, total, f"{model_config['display_name']} loaded. Starting frame analysis...")

    captions = []
    batch_size = 8  # Process in small batches for memory efficiency

    for i in range(0, total, batch_size):
        batch = frames[i:i + batch_size]
        batch_images = []
        batch_prompts = []

        for frame_info in batch:
            img_path = os.path.join(frames_dir, frame_info["filename"])
            if os.path.exists(img_path):
                image = Image.open(img_path).convert("RGB")
                batch_images.append(image)
                batch_prompts.append(prompt)
            else:
                logger.warning(f"Frame not found: {img_path}")
                batch_images.append(None)
                batch_prompts.append(None)

        # Process valid images in batch
        valid_indices = [j for j, img in enumerate(batch_images) if img is not None]
        valid_images = [batch_images[j] for j in valid_indices]
        valid_prompts = [batch_prompts[j] for j in valid_indices]

        if valid_images:
            try:
                if model_config["variant"] == "blip2":
                    dtype = next(model.parameters()).dtype
                    inputs = processor(
                        images=valid_images,
                        text=valid_prompts,
                        return_tensors="pt",
                        padding=True
                    ).to(device, dtype)
                else:
                    inputs = processor(
                        images=valid_images,
                        text=valid_prompts,
                        return_tensors="pt",
                        padding=True
                    ).to(device)

                with torch.no_grad():
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=75,
                        num_beams=5,
                        early_stopping=True
                    )

                decoded = processor.batch_decode(outputs, skip_special_tokens=True)

                # Map captions back to frame info
                valid_idx = 0
                for j, frame_info in enumerate(batch):
                    if j in valid_indices:
                        captions.append({
                            "index": frame_info["index"],
                            "timestamp": frame_info["timestamp"],
                            "filename": frame_info["filename"],
                            "caption": decoded[valid_idx].strip()
                        })
                        valid_idx += 1
                    else:
                        captions.append({
                            "index": frame_info["index"],
                            "timestamp": frame_info["timestamp"],
                            "filename": frame_info["filename"],
                            "caption": "[frame unavailable]"
                        })
            except Exception as e:
                logger.error(f"Error processing batch at index {i}: {e}")
                # Fallback: process individually
                for j, frame_info in enumerate(batch):
                    if batch_images[j] is not None:
                        try:
                            caption = caption_single_frame(
                                os.path.join(frames_dir, frame_info["filename"]),
                                model, processor, device, model_key=vision_model
                            )
                            captions.append({
                                "index": frame_info["index"],
                                "timestamp": frame_info["timestamp"],
                                "filename": frame_info["filename"],
                                "caption": caption.strip()
                            })
                        except Exception as e2:
                            logger.error(f"Error on frame {frame_info['filename']}: {e2}")
                            captions.append({
                                "index": frame_info["index"],
                                "timestamp": frame_info["timestamp"],
                                "filename": frame_info["filename"],
                                "caption": "[error processing frame]"
                            })

        processed = min(i + batch_size, total)
        if progress_callback:
            progress_callback(
                processed, total,
                f"Analyzed {processed}/{total} frames"
            )

    # Save captions
    captions_path = os.path.join(frames_dir, "captions.json")
    captions_data = {
        "total_frames": len(captions),
        "model": model_config["model_id"],
        "model_key": vision_model,
        "device": str(device),
        "captions": captions
    }
    with open(captions_path, "w") as f:
        json.dump(captions_data, f, indent=2)

    if progress_callback:
        progress_callback(total, total, "Frame analysis complete!")

    logger.info(f"Generated {len(captions)} captions, saved to {captions_path}")
    return captions_data