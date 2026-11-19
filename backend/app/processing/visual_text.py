"""Optional Optical Character Recognition (OCR) for video keyframes.

Reads actual image pixels when an optional local OCR engine (RapidOCR ONNX or
Tesseract + Pillow) is installed. When no optical OCR engine is available,
explicitly reports an unavailable state and returns empty text — never invents
synthetic or placeholder OCR strings.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
import importlib.util
from pathlib import Path
import re
import shutil
from typing import Any, Sequence
import unicodedata

DEFAULT_MAX_OCR_FRAMES = 60
DEFAULT_MIN_OCR_INTERVAL_SEC = 2.0
DEFAULT_MAX_IMAGE_PIXELS = 4_000_000


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
            import pytesseract  # type: ignore

            ver = str(pytesseract.get_tesseract_version())
        except Exception:
            ver = "installed"
        return ("tesseract", ver)

    return (None, None)


def _run_optical_ocr(path: Path, engine: str, max_image_pixels: int) -> str:
    """Execute genuine pixel-level OCR via the detected optional local engine."""
    if engine == "rapidocr_onnxruntime":
        from rapidocr_onnxruntime import RapidOCR  # type: ignore

        ocr = RapidOCR()
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
