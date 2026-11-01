import ctypes
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def collect_system_environment() -> dict[str, Any]:
    """Gather hardware, operating system, and software runtime configuration."""
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    total_ram_gb = 0.0
    avail_ram_gb = 0.0
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        total_ram_gb = round(stat.ullTotalPhys / (1024**3), 2)
        avail_ram_gb = round(stat.ullAvailPhys / (1024**3), 2)
    except Exception:
        pass

    # GPU / CUDA detection
    gpu_info = {
        "cuda_available": False,
        "device_count": 0,
        "device_name": None,
        "vram_gb": None,
        "mode": "CPU-Only",
    }
    try:
        import torch  # type: ignore

        gpu_info["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            gpu_info["device_count"] = torch.cuda.device_count()
            gpu_info["device_name"] = torch.cuda.get_device_name(0)
            gpu_info["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
            gpu_info["mode"] = f"GPU: {gpu_info['device_name']}"
    except Exception:
        pass

    # FFmpeg / ffprobe resolution
    ffmpeg_version_str = "Unavailable"
    ffmpeg_bin_path = None
    try:
        from app.processing.metadata import get_ffmpeg_binary

        ffmpeg_bin_path = get_ffmpeg_binary()
        proc = subprocess.run([ffmpeg_bin_path, "-version"], capture_output=True, text=True, timeout=10)
        if proc.stdout:
            ffmpeg_version_str = proc.stdout.splitlines()[0]
    except Exception as e:
        ffmpeg_version_str = f"Error: {e}"

    ffprobe_path = shutil.which("ffprobe")

    # uv version
    uv_version_str = "Unavailable"
    try:
        p_uv = subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=5)
        if p_uv.stdout:
            uv_version_str = p_uv.stdout.strip()
    except Exception:
        pass

    # Git commit & branch
    git_commit = "unknown"
    git_branch = "unknown"
    try:
        p_c = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        git_commit = p_c.stdout.strip()
        p_b = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=5)
        git_branch = p_b.stdout.strip()
    except Exception:
        pass

    # AI Model Readiness & Library Status
    models_status = {
        "faster_whisper": {
            "installed": False,
            "version": None,
            "configured_model": "base",
            "active_mode": "Deterministic Acoustic Fallback (faster-whisper package not installed in environment)",
        },
        "sentence_transformers": {
            "installed": False,
            "version": None,
            "configured_model": "sentence-transformers/all-MiniLM-L6-v2",
            "active_mode": "Deterministic 384-d Token Projection (sentence-transformers not installed in environment)",
        },
        "cross_encoder": {
            "installed": False,
            "version": None,
            "configured_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "active_mode": "Deterministic Term Proximity Coverage Reranker (PyTorch weights offline)",
        },
        "chromadb": {
            "installed": False,
            "version": None,
            "active_mode": "Filesystem JSON Vector Persistence",
        },
    }

    try:
        import faster_whisper  # type: ignore

        models_status["faster_whisper"]["installed"] = True
        models_status["faster_whisper"]["version"] = faster_whisper.__version__
        models_status["faster_whisper"]["active_mode"] = "Neural ASR Model"
    except Exception:
        pass

    try:
        import sentence_transformers  # type: ignore

        models_status["sentence_transformers"]["installed"] = True
        models_status["sentence_transformers"]["version"] = sentence_transformers.__version__
        models_status["sentence_transformers"]["active_mode"] = "Neural MiniLM Embeddings"
    except Exception:
        pass

    try:
        import chromadb  # type: ignore

        models_status["chromadb"]["installed"] = True
        models_status["chromadb"]["version"] = chromadb.__version__
        models_status["chromadb"]["active_mode"] = "Dense ChromaDB Storage"
    except Exception:
        pass

    return {
        "operating_system": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
        },
        "hardware": {
            "cpu_cores_logical": os.cpu_count() or 1,
            "ram_total_gb": total_ram_gb,
            "ram_available_gb": avail_ram_gb,
            "gpu": gpu_info,
        },
        "software": {
            "python_version": sys.version,
            "sqlite_version": sqlite3.sqlite_version,
            "ffmpeg_binary": str(ffmpeg_bin_path) if ffmpeg_bin_path else None,
            "ffmpeg_version": ffmpeg_version_str,
            "ffprobe_on_path": ffprobe_path,
            "uv_version": uv_version_str,
        },
        "models": models_status,
        "repository": {
            "git_commit": git_commit,
            "git_branch": git_branch,
        },
    }


def main() -> None:
    env_data = collect_system_environment()
    out_dir = ROOT_DIR / "reports" / "benchmarks" / "alpha-baseline"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "environment.json"
    out_file.write_text(json.dumps(env_data, indent=2), encoding="utf-8")
    print(json.dumps(env_data, indent=2))
    print(f"\n[OK] Environment report saved to: {out_file}")


if __name__ == "__main__":
    main()

