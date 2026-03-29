"""
Model Download Script
Downloads all required AI models for offline operation.
Run this once with internet connection to prepare for offline/production use.
"""

import os
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Models directory
BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "models"

# Model configurations
MODELS = {
    "blip-captioning-base": {
        "name": "Salesforce/blip-image-captioning-base",
        "description": "BLIP Image Captioning (Base) - ~990MB",
        "type": "vision"
    },
    "tinyllama-chat": {
        "name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "description": "TinyLlama 1.1B Chat - ~2.2GB",
        "type": "text"
    }
}


def check_dependencies():
    """Check if required packages are installed."""
    try:
        import torch
        import transformers
        from PIL import Image
        logger.info("✓ All required packages are installed")
        return True
    except ImportError as e:
        logger.error(f"✗ Missing dependency: {e}")
        logger.error("Please run: pip install -r requirements.txt")
        return False


def check_device():
    """Check available compute device."""
    import torch

    if torch.backends.mps.is_available():
        device = "mps"
        device_name = "Apple Silicon (MPS)"
    elif torch.cuda.is_available():
        device = "cuda"
        device_name = torch.cuda.get_device_name(0)
    else:
        device = "cpu"
        device_name = "CPU"

    logger.info(f"✓ Compute device: {device_name}")
    return device


def download_vision_model(model_id, model_dir):
    """Download BLIP vision model."""
    from transformers import BlipProcessor, BlipForConditionalGeneration

    logger.info(f"Downloading {model_id}...")
    logger.info("This may take several minutes depending on your internet speed...")

    try:
        processor = BlipProcessor.from_pretrained(model_id)
        model = BlipForConditionalGeneration.from_pretrained(model_id)

        # Save to local directory
        processor.save_pretrained(model_dir)
        model.save_pretrained(model_dir)

        logger.info(f"✓ Successfully downloaded and saved to {model_dir}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to download {model_id}: {e}")
        return False


def download_text_model(model_id, model_dir):
    """Download TinyLlama text model."""
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch

    logger.info(f"Downloading {model_id}...")
    logger.info("This may take several minutes depending on your internet speed...")

    try:
        # Determine dtype based on device
        device = check_device()
        torch_dtype = torch.float16 if device != "cpu" else torch.float32

        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch_dtype
        )

        # Save to local directory
        tokenizer.save_pretrained(model_dir)
        model.save_pretrained(model_dir)

        logger.info(f"✓ Successfully downloaded and saved to {model_dir}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to download {model_id}: {e}")
        return False


def verify_model(model_dir, model_type):
    """Verify that a model was downloaded correctly."""
    config_file = model_dir / "config.json"

    if not config_file.exists():
        return False

    # Check for model files
    has_safetensors = list(model_dir.glob("*.safetensors"))
    has_bin = list(model_dir.glob("*.bin"))

    if not (has_safetensors or has_bin):
        return False

    logger.info(f"✓ Model verified: {model_dir.name}")
    return True


def get_directory_size(directory):
    """Calculate total size of directory in MB."""
    total = 0
    try:
        for entry in os.scandir(directory):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_directory_size(entry.path)
    except Exception:
        pass
    return total / (1024 * 1024)  # Convert to MB


def main():
    """Main download script."""
    print("=" * 60)
    print("AI Model Download Script for Video Editor")
    print("=" * 60)
    print()

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Check device
    device = check_device()
    print()

    # Create models directory
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Models directory: {MODELS_DIR}")
    print()

    # Download each model
    total_models = len(MODELS)
    downloaded = 0

    for idx, (model_key, model_info) in enumerate(MODELS.items(), 1):
        print(f"[{idx}/{total_models}] {model_info['description']}")
        print("-" * 60)

        model_dir = MODELS_DIR / model_key

        # Check if already exists
        if verify_model(model_dir, model_info['type']):
            size_mb = get_directory_size(model_dir)
            logger.info(f"Model already exists ({size_mb:.1f} MB). Skipping download.")
            downloaded += 1
        else:
            # Download based on type
            if model_info['type'] == 'vision':
                success = download_vision_model(model_info['name'], model_dir)
            elif model_info['type'] == 'text':
                success = download_text_model(model_info['name'], model_dir)
            else:
                logger.error(f"Unknown model type: {model_info['type']}")
                success = False

            if success:
                size_mb = get_directory_size(model_dir)
                logger.info(f"Download size: {size_mb:.1f} MB")
                downloaded += 1

        print()

    # Summary
    print("=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)

    total_size = get_directory_size(MODELS_DIR)
    logger.info(f"Models downloaded: {downloaded}/{total_models}")
    logger.info(f"Total size: {total_size:.1f} MB")

    if downloaded == total_models:
        print()
        logger.info("✓ All models ready for offline use!")
        logger.info("You can now run the application without internet.")
        return 0
    else:
        print()
        logger.warning("⚠ Some models failed to download.")
        logger.warning("Please check errors above and try again.")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
