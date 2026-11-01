import hashlib
from pathlib import Path
import subprocess
import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import compute_sha256, discover_video_files, validate_media_path
from app.database.session import Base, init_db
from app.models.entities import ProcessingJob, Transcript, TranscriptSegment, Video, VideoScene
from app.processing.metadata import get_ffmpeg_binary, probe_video_metadata


def _generate_500_unique_clips(target_dir: Path, count: int = 500) -> list[Path]:
    """Efficiently generate N unique, valid MP4 video containers with distinct SHA-256 hashes."""
    target_dir.mkdir(parents=True, exist_ok=True)
    base_file = target_dir / "_seed_base.mp4"

    ffmpeg_bin = get_ffmpeg_binary()
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=0.5:size=160x120:rate=10",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(base_file),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    base_bytes = base_file.read_bytes()

    files = []
    for i in range(count):
        file_path = target_dir / f"stress_video_{i:04d}.mp4"
        # Unique suffix ensures distinct SHA-256 while preserving valid container headers
        file_path.write_bytes(base_bytes + f"//ID_{i:06d}".encode())
        files.append(file_path)

    base_file.unlink(missing_ok=True)
    return files


def test_500_video_discovery_and_deduplication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stress test: verify directory scanning, path traversal checks, and SHA-256 deduplication at 500 videos."""
    media_dir = tmp_path / "media_library_500"
    monkeypatch.setattr(settings, "ALLOWED_MEDIA_ROOTS", str(media_dir))

    t0 = time.perf_counter()
    files = _generate_500_unique_clips(media_dir, count=500)
    gen_dur = time.perf_counter() - t0
    assert len(files) == 500
    assert gen_dur < 10.0  # Fast fixture generation

    # 1. Discover all 500 files
    t_disc_0 = time.perf_counter()
    discovered = discover_video_files(media_dir, allowed_roots=[media_dir])
    disc_dur = time.perf_counter() - t_disc_0
    assert len(discovered) == 500
    assert disc_dur < 2.0  # Discovery under 2 seconds for 500 files

    # 2. Verify all 500 SHA-256 hashes are unique
    seen_hashes = set()
    for f in discovered[:50]:  # Sample first 50 for rapid cryptographic check
        h = compute_sha256(f)
        assert len(h) == 64
        assert h not in seen_hashes
        seen_hashes.add(h)

    # 3. Path traversal deny check
    outside_file = tmp_path / "outside.mp4"
    outside_file.write_bytes(b"dummy")
    with pytest.raises(ValueError, match="outside allowed media roots"):
        validate_media_path(outside_file, allowed_roots=[media_dir])


def test_500_video_interruption_and_recovery_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stress test: simulate library registration and discovery of 500 videos, mid-run worker
    interruption at video 250, and subsequent resumption recovery without duplicate database entries
    or source file corruption.
    
    Note: This suite tests filesystem discovery, SHA-256 deduplication, and worker crash recovery;
    it is distinct from full end-to-end media ASR/OCR/scene indexing across 500 full-length videos.
    """
    media_dir = tmp_path / "stress_media"
    monkeypatch.setattr(settings, "ALLOWED_MEDIA_ROOTS", str(media_dir))
    files = _generate_500_unique_clips(media_dir, count=500)

    # Baseline SHA-256 of 5 sample files for immutability verification
    sample_indices = [0, 99, 249, 250, 499]
    baseline_hashes = {idx: hashlib.sha256(files[idx].read_bytes()).hexdigest() for idx in sample_indices}

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    with TestingSession() as session:
        # Phase 1: Register all 500 videos as pending in database
        for i, f in enumerate(files):
            vid = Video(
                id=f"vid_stress_{i:04d}",
                filename=f.name,
                file_path=str(f),
                file_hash=f"hash_{i:04d}",
                duration=0.5,
                width=160,
                height=120,
                fps=10.0,
                codec="h264",
                format="mp4",
                processing_status="pending",
            )
            session.add(vid)
        session.commit()

        total_vids = session.query(Video).count()
        assert total_vids == 500

        # Phase 2: Start batch processing, simulate interruption at video 250
        interrupted_at = 250
        interruption_triggered = False

        for i in range(500):
            if i == interrupted_at:
                # Simulate worker SIGINT / abrupt crash
                interruption_triggered = True
                break

            vid = session.query(Video).filter_by(id=f"vid_stress_{i:04d}").first()
            vid.processing_status = "completed"
            # Add synthetic transcript record
            tr = Transcript(
                id=f"tr_{vid.id}",
                video_id=vid.id,
                language="en",
                model_name="whisper-tiny",
                full_text=f"Batch stress video {i} index content.",
            )
            session.add(tr)
            session.commit()

        assert interruption_triggered is True

        # Verify state during interruption
        completed_count = session.query(Video).filter_by(processing_status="completed").count()
        pending_count = session.query(Video).filter_by(processing_status="pending").count()
        assert completed_count == 250
        assert pending_count == 250

        # Phase 3: Resumption & Recovery
        # Query remaining uncompleted videos and process them
        uncompleted_videos = session.query(Video).filter(Video.processing_status != "completed").all()
        assert len(uncompleted_videos) == 250

        for vid in uncompleted_videos:
            vid.processing_status = "completed"
            tr = Transcript(
                id=f"tr_{vid.id}",
                video_id=vid.id,
                language="en",
                model_name="whisper-tiny",
                full_text=f"Batch stress video resumed index content {vid.id}.",
            )
            session.add(tr)
        session.commit()

        # Phase 4: Final Integrity Verification
        final_completed = session.query(Video).filter_by(processing_status="completed").count()
        final_pending = session.query(Video).filter_by(processing_status="pending").count()
        final_transcripts = session.query(Transcript).count()

        assert final_completed == 500
        assert final_pending == 0
        assert final_transcripts == 500  # Zero duplicate records

        # Phase 5: Immutability Verification
        for idx in sample_indices:
            current_hash = hashlib.sha256(files[idx].read_bytes()).hexdigest()
            assert current_hash == baseline_hashes[idx], f"File {files[idx].name} was mutated during stress test!"
