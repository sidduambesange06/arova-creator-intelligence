"""Optional Optical Character Recognition (OCR) for video keyframes.

Reads actual image pixels when an optional local OCR engine (RapidOCR ONNX or
Tesseract + Pillow) is installed. When no optical OCR engine is available,
explicitly reports an unavailable state and returns empty text — never invents
synthetic or placeholder OCR strings.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import importlib.util
from pathlib import Path
import re
import shutil
import threading
from typing import Any, Sequence
import unicodedata

DEFAULT_MAX_OCR_FRAMES = 60
DEFAULT_MIN_OCR_INTERVAL_SEC = 2.0
DEFAULT_MAX_IMAGE_PIXELS = 4_000_000

_OCR_LOCK = threading.Lock()
_RAPIDOCR_INSTANCE: Any = None
_MODEL_HASH_CACHE: dict[tuple[str, str], str] = {}


@dataclass(frozen=True)
class OCRFrameResult:
    """Structured optical OCR result with explicit status and engine provenance."""

    status: str  # "extracted" | "empty" | "unavailable" | "error"
    text: str
    engine: str | None = None
    engine_version: str | None = None
    reason: str | None = None
    frame_path: str | None = None
    timestamp_sec: float | None = None


def detect_ocr_engine() -> tuple[str | None, str | None]:
    """Detect an installed local optical OCR engine without network calls.

    Returns (engine_name, engine_version) or (None, None) when unavailable.
    """
    if importlib.util.find_spec("rapidocr_onnxruntime") is not None:
        try:
            ver = importlib.metadata.version("rapidocr-onnxruntime")
        except importlib.metadata.PackageNotFoundError:
            ver = "installed"
        return ("rapidocr_onnxruntime", ver)

    if (
        importlib.util.find_spec("pytesseract") is not None
        and importlib.util.find_spec("PIL") is not None
        and shutil.which("tesseract") is not None
    ):
        try:
            ver = importlib.metadata.version("pytesseract")
        except importlib.metadata.PackageNotFoundError:
            ver = "installed"
        return ("tesseract", ver)

    return (None, None)


def _compute_rapidocr_weights_hash(engine_version: str) -> str:
    cache_key = ("rapidocr_onnxruntime", engine_version)
    if cache_key in _MODEL_HASH_CACHE:
        return _MODEL_HASH_CACHE[cache_key]

    spec = importlib.util.find_spec("rapidocr_onnxruntime")
    search_locs = list(spec.submodule_search_locations) if (spec and spec.submodule_search_locations) else []
    if not search_locs:
        return "unknown"

    pkg_root = Path(search_locs[0]).resolve()
    h = hashlib.sha256()
    for onnx_file in sorted(pkg_root.rglob("*.onnx")):
        h.update(str(onnx_file.relative_to(pkg_root)).replace("\\", "/").encode("utf-8"))
        h.update(str(onnx_file.stat().st_size).encode("utf-8"))
        with onnx_file.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    digest = h.hexdigest()[:24]
    _MODEL_HASH_CACHE[cache_key] = digest
    return digest


def get_ocr_fingerprint_config(
    *,
    max_frames: int = DEFAULT_MAX_OCR_FRAMES,
    min_interval_sec: float = DEFAULT_MIN_OCR_INTERVAL_SEC,
    max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
) -> dict[str, Any]:
    """Return deterministic OCR engine, weight, and preprocessing metadata for stage fingerprinting.

    Avoids importing heavy ONNX/OpenCV runtimes and caches weight hashes per (engine, version).
    """
    engine_name, engine_version = detect_ocr_engine()
    model_hash = "none"
    if engine_name == "rapidocr_onnxruntime":
        try:
            model_hash = _compute_rapidocr_weights_hash(engine_version or "installed")
        except Exception:
            model_hash = "unknown"

    return {
        "ocr_engine": engine_name or "unavailable",
        "ocr_engine_version": engine_version or "none",
        "ocr_model_weights_hash": model_hash,
        "max_frames": max_frames,
        "min_interval_sec": min_interval_sec,
        "max_image_pixels": max_image_pixels,
    }


def _get_rapidocr_instance() -> Any:
    global _RAPIDOCR_INSTANCE
    with _OCR_LOCK:
        if _RAPIDOCR_INSTANCE is None:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore

            _RAPIDOCR_INSTANCE = RapidOCR()
        return _RAPIDOCR_INSTANCE


def _run_optical_ocr(path: Path, engine: str, max_image_pixels: int) -> str:
    """Execute genuine pixel-level OCR via the detected optional local engine."""
    if engine == "rapidocr_onnxruntime":
        ocr = _get_rapidocr_instance()
        with _OCR_LOCK:
            result, _ = ocr(str(path))
        if not result:
            return ""
        return " ".join(str(item[1]) for item in result if len(item) >= 2 and item[1])

    if engine == "tesseract":
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore

        with Image.open(path) as img:
            width, height = img.size
            pixels = width * height
            if pixels > max_image_pixels and pixels > 0:
                scale = (max_image_pixels / float(pixels)) ** 0.5
                new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
                img = img.resize(new_size)
            return str(pytesseract.image_to_string(img) or "")

    raise ValueError(f"Unsupported OCR engine: {engine}")


def extract_visual_text_with_provenance(
    thumbnail_path: str | Path | None,
    *,
    timestamp_sec: float | None = None,
    max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
) -> OCRFrameResult:
    """Run genuine optical OCR on a frame image with explicit provenance and unavailable state."""
    if not thumbnail_path:
        return OCRFrameResult(
            status="error",
            text="",
            reason="FILE_NOT_FOUND",
            frame_path=None,
            timestamp_sec=timestamp_sec,
        )

    path = Path(thumbnail_path)
    if not path.is_file():
        return OCRFrameResult(
            status="error",
            text="",
            reason="FILE_NOT_FOUND",
            frame_path=str(path),
            timestamp_sec=timestamp_sec,
        )

    engine, engine_version = detect_ocr_engine()
    if engine is None:
        return OCRFrameResult(
            status="unavailable",
            text="",
            engine=None,
            engine_version=None,
            reason="DEPENDENCY_MISSING",
            frame_path=str(path),
            timestamp_sec=timestamp_sec,
        )

    try:
        raw_text = _run_optical_ocr(path, engine, max_image_pixels)
        cleaned = re.sub(r"\s+", " ", unicodedata.normalize("NFC", raw_text)).strip()
        return OCRFrameResult(
            status="extracted" if cleaned else "empty",
            text=cleaned,
            engine=engine,
            engine_version=engine_version,
            reason=None,
            frame_path=str(path),
            timestamp_sec=timestamp_sec,
        )
    except Exception as exc:
        return OCRFrameResult(
            status="error",
            text="",
            engine=engine,
            engine_version=engine_version,
            reason=f"OCR_ERROR:{type(exc).__name__}",
            frame_path=str(path),
            timestamp_sec=timestamp_sec,
        )


def extract_visual_text_from_frame(thumbnail_path: str | Path | None) -> str:
    """Backward-compatible wrapper returning extracted optical OCR text or empty string."""
    return extract_visual_text_with_provenance(thumbnail_path).text


def select_bounded_ocr_scenes(
    scenes: Sequence[Any],
    *,
    max_frames: int = DEFAULT_MAX_OCR_FRAMES,
    min_interval_sec: float = DEFAULT_MIN_OCR_INTERVAL_SEC,
) -> list[Any]:
    """Deterministically bound scene frames sampled for OCR to cap CPU and memory usage."""
    if max_frames <= 0:
        return []
    ordered = sorted(scenes, key=lambda s: float(getattr(s, "start_time", 0.0)))
    selected: list[Any] = []
    last_ts: float | None = None
    for scene in ordered:
        if len(selected) >= max_frames:
            break
        if not getattr(scene, "thumbnail_path", None):
            continue
        ts = float(getattr(scene, "start_time", 0.0))
        if last_ts is not None and (ts - last_ts) < min_interval_sec:
            continue
        selected.append(scene)
        last_ts = ts
    return selected
