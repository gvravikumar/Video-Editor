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

# Global model cache to avoid reloading
_model = None
_processor = None
_device = None

MODEL_NAME = "Salesforce/blip-image-captioning-base"
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
    """Load BLIP model and processor. Downloads on first run, cached locally."""
    global _model, _processor, _device

    if _model is not None and _processor is not None:
        return _model, _processor, _device

    from transformers import BlipProcessor, BlipForConditionalGeneration

    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path = os.path.join(MODELS_DIR, "blip-captioning-base")

    _device = get_device()

    logger.info(f"Loading BLIP model from {model_path}...")

    # Check if model exists locally
    if os.path.exists(os.path.join(model_path, "config.json")):
        logger.info("Loading model from local cache...")
        _processor = BlipProcessor.from_pretrained(model_path)
        _model = BlipForConditionalGeneration.from_pretrained(model_path)
    else:
        logger.info(f"Downloading BLIP model ({MODEL_NAME})... This may take a few minutes.")
        _processor = BlipProcessor.from_pretrained(MODEL_NAME)
        _model = BlipForConditionalGeneration.from_pretrained(MODEL_NAME)
        # Save locally for offline use
        _processor.save_pretrained(model_path)
        _model.save_pretrained(model_path)
        logger.info(f"Model saved to {model_path}")

    _model = _model.to(_device)
    _model.eval()

    logger.info("BLIP model loaded successfully.")
    return _model, _processor, _device


def caption_single_frame(image_path, model=None, processor=None, device=None):
    """Generate a caption for a single image frame."""
    if model is None or processor is None or device is None:
        model, processor, device = load_model()

    image = Image.open(image_path).convert("RGB")

    # Conditional generation with a gameplay-oriented prompt
    prompt = "a gameplay screenshot showing"
    inputs = processor(image, text=prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=50,
            num_beams=3,
            early_stopping=True
        )

    caption = processor.decode(output[0], skip_special_tokens=True)
    return caption


def analyze_frames(frames_dir, manifest_path=None, progress_callback=None):
    """
    Analyze all extracted frames and generate captions.
    
    Args:
        frames_dir: Directory containing extracted frame images
        manifest_path: Path to frames manifest JSON (optional, auto-detected)
        progress_callback: Optional callable(current, total, status_message)
    
    Returns:
        dict with:
            - captions: list of {index, timestamp, filename, caption}
            - total_frames: number of frames processed
    """
    # Load manifest
    if manifest_path is None:
        manifest_path = os.path.join(frames_dir, "manifest.json")

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    frames = manifest["frames"]
    total = len(frames)

    logger.info(f"Analyzing {total} frames with BLIP model...")

    if progress_callback:
        progress_callback(0, total, "Loading AI model for frame analysis...")

    # Load model
    model, processor, device = load_model()

    if progress_callback:
        progress_callback(0, total, "AI model loaded. Starting frame analysis...")

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
                batch_prompts.append("a gameplay screenshot showing")
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
                inputs = processor(
                    images=valid_images,
                    text=valid_prompts,
                    return_tensors="pt",
                    padding=True
                ).to(device)

                with torch.no_grad():
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=50,
                        num_beams=3,
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
                                model, processor, device
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
        "model": MODEL_NAME,
        "device": str(device),
        "captions": captions
    }
    with open(captions_path, "w") as f:
        json.dump(captions_data, f, indent=2)

    if progress_callback:
        progress_callback(total, total, "Frame analysis complete!")

    logger.info(f"Generated {len(captions)} captions, saved to {captions_path}")
    return captions_data