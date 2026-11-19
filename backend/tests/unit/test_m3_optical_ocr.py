"""Unit tests for M3.3 genuine optional optical OCR, unavailable state, and bounded sampling."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.processing.visual_text import (
    OCRFrameResult,
    detect_ocr_engine,
    extract_visual_text_from_frame,
    extract_visual_text_with_provenance,
    select_bounded_ocr_scenes,
)


def test_ocr_reports_explicit_unavailable_state_without_inventing_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    frame = tmp_path / "frame_001.jpg"
    frame.write_bytes(b"\xff\xd8\xff\xe0dummy_jpeg")

    monkeypatch.setattr("app.processing.visual_text.detect_ocr_engine", lambda: (None, None))

    res = extract_visual_text_with_provenance(frame, timestamp_sec=12.5)
    assert isinstance(res, OCRFrameResult)
    assert res.status == "unavailable"
    assert res.text == ""
    assert res.engine is None
    assert res.reason == "DEPENDENCY_MISSING"
    assert res.timestamp_sec == 12.5
    assert res.frame_path == str(frame)

    # Backward-compatible wrapper also returns empty string, never invented text
    assert extract_visual_text_from_frame(frame) == ""


def test_ocr_missing_frame_returns_error_without_crashing():
    res = extract_visual_text_with_provenance(Path("does_not_exist_12345.jpg"), timestamp_sec=4.0)
    assert res.status == "error"
    assert res.reason == "FILE_NOT_FOUND"
    assert res.text == ""


def test_ocr_extracts_text_with_provenance_when_engine_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    frame = tmp_path / "slide_01.png"
    frame.write_bytes(b"\x89PNG\r\n\x1a\nfake_png_bytes")

    monkeypatch.setattr("app.processing.visual_text.detect_ocr_engine", lambda: ("tesseract", "5.3.0"))
    monkeypatch.setattr(
        "app.processing.visual_text._run_optical_ocr",
        lambda path, engine, max_image_pixels: "  FastAPI   GET /api/v1/health \n 200 OK ",
    )

    res = extract_visual_text_with_provenance(frame, timestamp_sec=33.25)
    assert res.status == "extracted"
    assert res.text == "FastAPI GET /api/v1/health 200 OK"
    assert res.engine == "tesseract"
    assert res.engine_version == "5.3.0"
    assert res.timestamp_sec == 33.25
    assert res.reason is None


def test_select_bounded_ocr_scenes_enforces_interval_and_max_frames():
    scenes = [
        SimpleNamespace(scene_index=i, start_time=float(i) * 0.5, thumbnail_path=f"f{i}.jpg")
        for i in range(200)
    ]
    selected = select_bounded_ocr_scenes(scenes, max_frames=20, min_interval_sec=2.0)
    assert len(selected) <= 20
    # Verify minimum interval respected
    for prev, curr in zip(selected, selected[1:]):
        assert (curr.start_time - prev.start_time) >= 2.0
