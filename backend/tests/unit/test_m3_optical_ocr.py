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



def test_ocr_status_endpoint_distinguishes_all_six_states_and_fingerprint_invalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database.session import get_db
    from app.main import app
    from app.models.entities import Asset, AssetVersion, Base, Library, StageRun, Video, VideoScene
    from app.services.pipeline_orchestrator import compute_stage_fingerprint

    # 1. Verify OCR fingerprint changes when OCR engine changes (cache invalidation)
    fp_unavail = compute_stage_fingerprint(
        "ver-1", "ocr_detection", {"ocr_engine": "unavailable", "ocr_engine_version": "none"}, ["scene-fp"]
    )
    fp_rapid = compute_stage_fingerprint(
        "ver-1", "ocr_detection", {"ocr_engine": "rapidocr_onnxruntime", "ocr_engine_version": "1.4.0"}, ["scene-fp"]
    )
    assert fp_unavail != fp_rapid

    db_path = tmp_path / "ocr_status.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_db
    try:
        db = SessionLocal()
        asset = Asset(id="asset-1")
        ver = AssetVersion(id="ver-1", asset_id="asset-1", sha256="b" * 64)
        db.add_all([asset, ver])
        db.flush()
        vid = Video(
            id=str(uuid4()),
            asset_id="asset-1",
            version_id="ver-1",
            filename="demo.mp4",
            file_path=str(tmp_path / "demo.mp4"),
            file_hash="b" * 64,
            duration=10.0,
        )
        db.add(vid)
        db.commit()
        client = TestClient(app)

        # State 1: engine_unavailable
        monkeypatch.setattr("app.api.routes.videos.detect_ocr_engine", lambda: (None, None))
        r1 = client.get(f"/api/v1/videos/{vid.id}/ocr/status")
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["status"] == "engine_unavailable"
        assert d1["engine_available"] is False
        assert d1["remediation_hint"]

        # State 2: not_processed (engine available, no StageRun)
        monkeypatch.setattr("app.api.routes.videos.detect_ocr_engine", lambda: ("rapidocr_onnxruntime", "1.4.0"))
        r2 = client.get(f"/api/v1/videos/{vid.id}/ocr/status")
        assert r2.json()["status"] == "not_processed"
        assert r2.json()["engine_available"] is True

        # State 3: running
        sr = StageRun(
            id=str(uuid4()),
            version_id="ver-1",
            stage="ocr_detection",
            fingerprint=fp_rapid,
            status="running",
            attempt=1,
        )
        db.add(sr)
        db.commit()
        assert client.get(f"/api/v1/videos/{vid.id}/ocr/status").json()["status"] == "running"

        # State 4: failed
        sr.status = "failed"
        sr.error_detail = "Corrupt image frame"
        db.commit()
        d4 = client.get(f"/api/v1/videos/{vid.id}/ocr/status").json()
        assert d4["status"] == "failed"
        assert d4["error_message"] == "Corrupt image frame"

        # State 5: completed_no_text
        sr.status = "succeeded"
        sr.error_detail = None
        db.commit()
        assert client.get(f"/api/v1/videos/{vid.id}/ocr/status").json()["status"] == "completed_no_text"

        # State 6: completed_with_text (with frame timestamp & version provenance)
        sc = VideoScene(
            id=str(uuid4()),
            video_id=vid.id,
            scene_index=0,
            start_time=4.25,
            end_time=8.0,
            description="Slide Title: Arova Engine",
        )
        db.add(sc)
        db.commit()
        d6 = client.get(f"/api/v1/videos/{vid.id}/ocr/status").json()
        assert d6["status"] == "completed_with_text"
        assert d6["version_id"] == "ver-1"
        assert d6["extracted_count"] == 1
        assert d6["frames"][0]["timestamp_sec"] == 4.25
        assert d6["frames"][0]["text"] == "Slide Title: Arova Engine"
        db.close()
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()



def test_ocr_fingerprint_config_includes_weights_and_preprocessing():
    from app.processing.visual_text import get_ocr_fingerprint_config

    cfg = get_ocr_fingerprint_config(max_frames=30, min_interval_sec=3.0, max_image_pixels=2_000_000)
    assert "ocr_engine" in cfg
    assert "ocr_engine_version" in cfg
    assert "ocr_model_weights_hash" in cfg
    assert cfg["max_frames"] == 30
    assert cfg["min_interval_sec"] == 3.0
    assert cfg["max_image_pixels"] == 2_000_000


@pytest.mark.skipif(detect_ocr_engine()[0] is None, reason="Optional local OCR engine not installed")
def test_optional_ocr_real_pixel_inference_on_synthetic_fixture(tmp_path: Path):
    """Verifies real pixel-level OCR execution when optional OCR extra is installed.

    Uses a synthetic rendered PNG fixture (distinct from the real-frame Tears of Steel benchmark).
    """
    from PIL import Image, ImageDraw  # type: ignore

    img = Image.new("RGB", (480, 120), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((24, 42), "AROVA OCR 2026", fill=(0, 0, 0))
    fixture_path = tmp_path / "synthetic_ocr_fixture.png"
    img.save(fixture_path)

    res = extract_visual_text_with_provenance(fixture_path, timestamp_sec=1.0)
    assert res.status in ("extracted", "empty")
    assert res.engine is not None
    assert res.reason is None



def test_detect_and_fingerprint_avoid_heavy_imports_and_rehash(monkeypatch: pytest.MonkeyPatch):
    import subprocess
    import sys

    # Fresh subprocess: calling detect_ocr_engine + get_ocr_fingerprint_config must NOT import onnxruntime or cv2
    code = (
        "import sys; "
        "from app.processing.visual_text import detect_ocr_engine, get_ocr_fingerprint_config; "
        "detect_ocr_engine(); get_ocr_fingerprint_config(); "
        "heavy = [m for m in ('onnxruntime', 'cv2', 'rapidocr_onnxruntime') if m in sys.modules]; "
        "assert not heavy, f'Unexpected heavy imports during status/fingerprint check: {heavy}'"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout

    # Repeated calls reuse cached weights hash without re-reading disk
    from app.processing import visual_text as vt

    if vt.detect_ocr_engine()[0] == "rapidocr_onnxruntime":
        vt._MODEL_HASH_CACHE.clear()
        cfg1 = vt.get_ocr_fingerprint_config()
        assert len(vt._MODEL_HASH_CACHE) == 1
        monkeypatch.setattr(vt.hashlib, "sha256", lambda: (_ for _ in ()).throw(AssertionError("rehashed!")))
        cfg2 = vt.get_ocr_fingerprint_config()
        assert cfg1 == cfg2
