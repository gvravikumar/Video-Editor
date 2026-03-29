#!/usr/bin/env python3
"""
System Verification Script
Checks if all dependencies and models are properly installed.
"""

import sys
import os
from pathlib import Path

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def check_python():
    """Check Python version."""
    print("\n✓ Python version:", sys.version.split()[0])
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 8):
        print("  ⚠️  WARNING: Python 3.8+ recommended")
        return False
    return True

def check_imports():
    """Check if all required packages can be imported."""
    print("\n📦 Checking Python packages...")

    packages = {
        'flask': 'Flask',
        'moviepy': 'MoviePy',
        'cv2': 'OpenCV',
        'PIL': 'Pillow',
        'torch': 'PyTorch',
        'transformers': 'Transformers',
        'werkzeug': 'Werkzeug',
        'proglog': 'Proglog'
    }

    all_ok = True
    for module, name in packages.items():
        try:
            __import__(module)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ✗ {name} - NOT INSTALLED")
            all_ok = False

    return all_ok

def check_torch():
    """Check PyTorch and hardware acceleration."""
    print("\n🔥 Checking PyTorch configuration...")

    try:
        import torch
        print(f"  ✓ PyTorch version: {torch.__version__}")

        # Check device
        if torch.backends.mps.is_available():
            device = "mps"
            device_name = "Apple Silicon (MPS)"
        elif torch.cuda.is_available():
            device = "cuda"
            device_name = f"CUDA - {torch.cuda.get_device_name(0)}"
        else:
            device = "cpu"
            device_name = "CPU (No GPU acceleration)"

        print(f"  ✓ Compute device: {device_name}")

        if device == "cpu":
            print("  ⚠️  Note: Processing will be slower on CPU")
            print("     Consider using lower FPS settings (1-2 FPS)")

        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def check_models():
    """Check if AI models are downloaded."""
    print("\n🤖 Checking AI models...")

    models_dir = Path(__file__).parent / "models"

    models = {
        'blip-captioning-base': 'BLIP Image Captioning (~990 MB)',
        'tinyllama-chat': 'TinyLlama Chat (~2.2 GB)'
    }

    all_ok = True
    for model_dir, description in models.items():
        model_path = models_dir / model_dir
        config_file = model_path / "config.json"

        if config_file.exists():
            # Calculate size
            total_size = 0
            try:
                for root, dirs, files in os.walk(model_path):
                    for file in files:
                        filepath = os.path.join(root, file)
                        total_size += os.path.getsize(filepath)
                size_mb = total_size / (1024 * 1024)
                print(f"  ✓ {description} - {size_mb:.1f} MB")
            except:
                print(f"  ✓ {description}")
        else:
            print(f"  ✗ {description} - NOT DOWNLOADED")
            all_ok = False

    if not all_ok:
        print("\n  💡 To download models, run:")
        print("     python download_models.py")

    return all_ok

def check_directories():
    """Check if required directories exist."""
    print("\n📁 Checking directories...")

    base_dir = Path(__file__).parent
    dirs = ['templates', 'static', 'services']

    all_ok = True
    for dir_name in dirs:
        dir_path = base_dir / dir_name
        if dir_path.exists():
            print(f"  ✓ {dir_name}/")
        else:
            print(f"  ✗ {dir_name}/ - MISSING")
            all_ok = False

    # Auto-created directories
    print("\n  Auto-created on first run:")
    auto_dirs = ['uploads', 'processed', 'frames', 'shorts', 'stories', 'models']
    for dir_name in auto_dirs:
        dir_path = base_dir / dir_name
        if dir_path.exists():
            print(f"  ✓ {dir_name}/")
        else:
            print(f"  • {dir_name}/ - will be created")

    return all_ok

def check_files():
    """Check if key files exist."""
    print("\n📄 Checking key files...")

    base_dir = Path(__file__).parent
    files = {
        'app.py': 'Main application',
        'requirements.txt': 'Dependencies list',
        'download_models.py': 'Model downloader',
        'start.sh': 'Mac/Linux startup',
        'start.bat': 'Windows startup',
        'services/frame_extractor.py': 'Frame extraction',
        'services/frame_analyzer.py': 'Frame analysis (BLIP)',
        'services/story_generator.py': 'Story generation (TinyLlama)',
        'services/short_generator.py': 'Short video creation',
        'services/metadata_generator.py': 'Metadata generation',
        'templates/index.html': 'Web UI'
    }

    all_ok = True
    for filepath, description in files.items():
        full_path = base_dir / filepath
        if full_path.exists():
            print(f"  ✓ {filepath}")
        else:
            print(f"  ✗ {filepath} - MISSING ({description})")
            all_ok = False

    return all_ok

def estimate_performance():
    """Estimate performance based on hardware."""
    print("\n⚡ Performance estimate (2-hour video, 2 FPS):")

    try:
        import torch

        if torch.backends.mps.is_available():
            print("  Apple Silicon (MPS) detected")
            print("  • Estimated total time: ~30-40 minutes")
            print("  • Recommended FPS: 2-3")
        elif torch.cuda.is_available():
            print(f"  NVIDIA GPU detected: {torch.cuda.get_device_name(0)}")
            print("  • Estimated total time: ~25-35 minutes")
            print("  • Recommended FPS: 2-4")
        else:
            print("  CPU-only processing")
            print("  • Estimated total time: ~60-90 minutes")
            print("  • Recommended FPS: 1-2")
            print("  • Tip: Use shorter videos or lower FPS")
    except:
        pass

def main():
    print_header("VideoStudio AI - System Verification")

    print("\n🔍 Verifying installation...")

    checks = {
        'Python version': check_python(),
        'Python packages': check_imports(),
        'PyTorch setup': check_torch(),
        'AI models': check_models(),
        'Project directories': check_directories(),
        'Project files': check_files()
    }

    # Summary
    print_header("Verification Summary")

    passed = sum(1 for v in checks.values() if v)
    total = len(checks)

    for check, status in checks.items():
        status_icon = "✓" if status else "✗"
        print(f"  {status_icon} {check}")

    print(f"\n📊 Status: {passed}/{total} checks passed")

    if all(checks.values()):
        print("\n✅ All checks passed! System is ready.")
        estimate_performance()
        print("\n🚀 To start the application:")
        print("   ./start.sh      (macOS/Linux)")
        print("   start.bat       (Windows)")
        print("   python app.py   (Manual)")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please review the issues above.")

        if not checks['Python packages']:
            print("\n💡 To install missing packages:")
            print("   pip install -r requirements.txt")

        if not checks['AI models']:
            print("\n💡 To download AI models:")
            print("   python download_models.py")

        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nVerification cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
