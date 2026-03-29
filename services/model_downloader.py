"""
Model Downloader Service
Downloads vision models in background threads at server startup.
Tracks per-file progress via tqdm monkey-patching so the frontend can
poll /ai/models/download-status and show a live progress bar.
"""

import os
import io
import threading
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared status store
# { model_key: { "status": "queued|downloading|done|error", "percent": 0-100, "message": str } }
# ---------------------------------------------------------------------------
_status: dict = {}
_status_lock = threading.Lock()


def get_all_status() -> dict:
    with _status_lock:
        return dict(_status)


def _set(model_key: str, **kwargs):
    with _status_lock:
        if model_key not in _status:
            _status[model_key] = {}
        _status[model_key].update(kwargs)


# ---------------------------------------------------------------------------
# Background download
# ---------------------------------------------------------------------------

class _Devnull:
    """Null write sink — suppresses tqdm console output without disabling it."""
    def write(self, *args): pass
    def flush(self): pass


def _download_model(model_key: str, config: dict, models_dir: str):
    """
    Download a single vision model.
    Monkey-patches tqdm.auto.tqdm (used by both transformers and huggingface_hub)
    to capture per-file download progress without touching the console.
    """
    import tqdm as tqdm_mod
    import tqdm.auto as tqdm_auto_mod

    _orig_tqdm = tqdm_mod.tqdm
    _orig_auto = tqdm_auto_mod.tqdm

    model_id  = config["model_id"]
    local_path = os.path.join(models_dir, config["local_dir"])
    variant   = config["variant"]
    name      = config["display_name"]
    size      = config["size_label"]

    _set(model_key, status="downloading", percent=0,
         message=f"Starting {name} download ({size})…")

    # Per-thread state for tracking the largest (model weights) tqdm bar
    _state = {"max_total": 0}

    class _TrackedTqdm(_orig_auto):
        """
        Redirects tqdm output to a null sink and reports the current
        file's download progress back to _status.
        """
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("file", _Devnull())
            super().__init__(*args, **kwargs)
            # The model weights file is the largest; latch onto it
            if self.total and self.total > _state["max_total"]:
                _state["max_total"] = self.total

        def update(self, n=1):
            super().update(n)
            if not n or not self.total:
                return
            # Only report progress for the largest file seen so far
            if self.total < _state["max_total"]:
                return
            pct = min(99, int(self.n * 100 / self.total))
            mb_done  = self.n         / (1024 * 1024)
            mb_total = self.total     / (1024 * 1024)
            _set(model_key,
                 status="downloading",
                 percent=pct,
                 message=f"Downloading {name}: {mb_done:.0f} / {mb_total:.0f} MB")

    # Patch both tqdm namespaces that transformers / huggingface_hub use
    tqdm_mod.tqdm      = _TrackedTqdm
    tqdm_auto_mod.tqdm = _TrackedTqdm

    try:
        os.makedirs(local_path, exist_ok=True)

        if variant == "blip2":
            from transformers import Blip2Processor, Blip2ForConditionalGeneration
            import torch
            dtype = torch.float16

            _set(model_key, message=f"Downloading {name} tokenizer…")
            processor = Blip2Processor.from_pretrained(model_id)
            processor.save_pretrained(local_path)

            _set(model_key, percent=5,
                 message=f"Downloading {name} model weights ({size})…")
            model = Blip2ForConditionalGeneration.from_pretrained(model_id, torch_dtype=dtype)
            model.save_pretrained(local_path)
            del model

        else:
            from transformers import BlipProcessor, BlipForConditionalGeneration

            _set(model_key, message=f"Downloading {name} tokenizer…")
            processor = BlipProcessor.from_pretrained(model_id)
            processor.save_pretrained(local_path)

            _set(model_key, percent=5,
                 message=f"Downloading {name} model weights ({size})…")
            model = BlipForConditionalGeneration.from_pretrained(model_id)
            model.save_pretrained(local_path)
            del model

        _set(model_key, status="done", percent=100,
             message=f"{name} is ready.")
        logger.info(f"[model_downloader] {model_key} saved to {local_path}")

    except Exception as exc:
        _set(model_key, status="error", percent=0,
             message=f"Download failed: {exc}")
        logger.error(f"[model_downloader] Failed to download {model_key}: {exc}")

    finally:
        # Always restore original tqdm, even if download fails
        tqdm_mod.tqdm      = _orig_tqdm
        tqdm_auto_mod.tqdm = _orig_auto


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def start_startup_downloads(models_dir: str, models_to_download: list = None):
    """
    Start background downloads for the given model keys at server startup.
    Default: ["blip-large"].  BLIP-2 is not auto-downloaded (5.5 GB).
    Models that are already on disk are skipped immediately.
    """
    from services.frame_analyzer import AVAILABLE_MODELS

    if models_to_download is None:
        models_to_download = ["blip-large"]

    for model_key in models_to_download:
        if model_key not in AVAILABLE_MODELS:
            logger.warning(f"[model_downloader] Unknown model key '{model_key}', skipping.")
            continue

        config     = AVAILABLE_MODELS[model_key]
        local_path = os.path.join(models_dir, config["local_dir"])

        if os.path.exists(os.path.join(local_path, "config.json")):
            _set(model_key, status="done", percent=100,
                 message=f"{config['display_name']} already downloaded.")
            logger.info(f"[model_downloader] {model_key} already present — skipping.")
            continue

        logger.info(
            f"[model_downloader] Scheduling startup download: "
            f"{model_key} ({config['size_label']})"
        )
        _set(model_key, status="queued", percent=0,
             message=f"Queued: {config['display_name']} ({config['size_label']})")

        t = threading.Thread(
            target=_download_model,
            args=(model_key, config, models_dir),
            daemon=True,
            name=f"model-dl-{model_key}",
        )
        t.start()
