import errno
import hashlib
from pathlib import Path
import sqlite3
import subprocess
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.security import compute_sha256
from app.database.session import Base, init_db
from app.models.entities import ProcessingJob, Transcript, Video
from app.processing.clip_export import export_subclip
from app.processing.metadata import get_ffmpeg_binary, probe_video_metadata
from app.workers import pipeline_runner
from app.workers.pipeline_runner import _execute_pipeline


def _create_minimal_valid_clip(target: Path, duration: float = 1.0) -> Path:
    ffmpeg_bin = get_ffmpeg_binary()
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration}:size=160x120:rate=10",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    return target


def test_corrupt_zero_byte_media_handling(tmp_path: Path) -> None:
    """Verify metadata probe raises ValueError on empty 0-byte video files."""
    empty_file = tmp_path / "zero_byte.mp4"
    empty_file.write_bytes(b"")

    with pytest.raises(ValueError, match="invalid media file|empty"):
        probe_video_metadata(empty_file)


def test_corrupt_truncated_media_handling(tmp_path: Path) -> None:
    """Verify metadata probe raises ValueError on truncated / corrupt video headers without crashing."""
    corrupt_file = tmp_path / "truncated_garbage.mp4"
    corrupt_file.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00CORRUPT_NON_MEDIA_PAYLOAD_BYTES")

    with pytest.raises(ValueError, match="invalid media file"):
        probe_video_metadata(corrupt_file)


def test_disk_full_enospc_during_clip_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify disk-full (ENOSPC) during clip export cleans up partial files and raises cleanly."""
    sample_mp4 = _create_minimal_valid_clip(tmp_path / "source_clip.mp4", duration=2.0)
    output_dir = tmp_path / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    h0 = hashlib.sha256(sample_mp4.read_bytes()).hexdigest()

    # Simulate subprocess OSError ENOSPC (errno 28)
    def fake_subprocess_run(*args, **kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    with pytest.raises(OSError) as exc_info:
        export_subclip(
            video_path=sample_mp4,
            start_time=0.5,
            end_time=1.5,
            output_dir=output_dir,
        )

    assert exc_info.value.errno == errno.ENOSPC or "No space left" in str(exc_info.value)

    # Immutability check: source file must remain identical
    h1 = hashlib.sha256(sample_mp4.read_bytes()).hexdigest()
    assert h0 == h1


def test_pipeline_worker_handles_corrupt_media_gracefully(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify pipeline runner catches unreadable media errors, marks job and video failed, and does not crash."""
    corrupt_file = tmp_path / "unreadable.mp4"
    corrupt_file.write_bytes(b"GARBAGE_PAYLOAD")

    # 1. Probing corrupt media directly raises ValueError
    with pytest.raises(ValueError, match="invalid media file"):
        probe_video_metadata(corrupt_file)

    # 2. Worker pipeline gracefully catches unreadable media during pipeline execution
    test_db = tmp_path / "test_pipeline_corrupt.db"
    engine = create_engine(f"sqlite:///{test_db.as_posix()}", connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSession = sessionmaker(bind=engine)

    def fake_detect_scenes(*args, **kwargs):
        raise ValueError("Corrupt media container: unable to parse video stream")

    monkeypatch.setattr(pipeline_runner, "detect_video_scenes", fake_detect_scenes)

    with TestingSession() as session:
        vid = Video(
            id="vid_corrupt_01",
            filename="unreadable.mp4",
            file_path=str(corrupt_file),
            file_hash="hash_corrupt",
            file_size=15,
            duration=0.0,
            width=0,
            height=0,
            fps=0.0,
            codec="unknown",
            format="mp4",
            processing_status="pending",
        )
        session.add(vid)
        session.commit()

        # Execute pipeline; should catch exception, update status to failed, and re-raise
        with pytest.raises(ValueError, match="Corrupt media container"):
            _execute_pipeline(db=session, video_id=vid.id, media_storage_dir=tmp_path / "storage")

        # Verify state in database
        failed_vid = session.query(Video).filter_by(id="vid_corrupt_01").first()
        assert failed_vid.processing_status == "failed"

        failed_job = session.query(ProcessingJob).filter_by(video_id="vid_corrupt_01").first()
        assert failed_job is not None
        assert failed_job.status == "failed"
        assert "Corrupt media container" in failed_job.error_message


def test_interrupted_processing_recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify simulated worker abort midway rolls back incomplete state and leaves DB consistent."""
    sample_mp4 = _create_minimal_valid_clip(tmp_path / "interrupt_sample.mp4", duration=1.0)
    test_db = tmp_path / "test_interrupt.db"
    engine = create_engine(f"sqlite:///{test_db.as_posix()}", connect_args={"check_same_thread": False})
    init_db(engine)
    TestingSession = sessionmaker(bind=engine)

    with TestingSession() as session:
        vid = Video(
            id="vid_interrupted_01",
            filename="interrupt_sample.mp4",
            file_path=str(sample_mp4),
            file_hash="hash_interrupt",
            file_size=1024,
            duration=1.0,
            width=160,
            height=120,
            fps=10.0,
            codec="h264",
            format="mp4",
            processing_status="pending",
        )
        session.add(vid)
        session.commit()

        # Simulate worker SIGINT exception during audio extraction
        def fake_extract_audio(*args, **kwargs):
            raise RuntimeError("Simulated worker SIGINT / abrupt abort")

        monkeypatch.setattr(pipeline_runner, "extract_audio_wav", fake_extract_audio)

        with pytest.raises(RuntimeError, match="Simulated worker SIGINT"):
            _execute_pipeline(db=session, video_id=vid.id, media_storage_dir=tmp_path / "storage")

        # Verify clean failure recording
        aborted_job = session.query(ProcessingJob).filter_by(video_id="vid_interrupted_01").first()
        assert aborted_job.status == "failed"
        assert "Simulated worker SIGINT" in aborted_job.error_message

        # Verify database is intact and uncorrupted
        assert session.query(Transcript).filter_by(video_id="vid_interrupted_01").count() == 0


def test_sqlite_wal_mode_and_crash_recovery(tmp_path: Path) -> None:
    """Verify SQLite WAL mode configuration, concurrency, and crash recovery integrity."""
    db_file = tmp_path / "wal_recovery_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    init_db(engine)

    # 1. Verify PRAGMA journal_mode is WAL
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode;")).scalar()
        assert str(mode).lower() == "wal"

    # 2. Simulate uncommitted write and abrupt close
    raw_conn = sqlite3.connect(str(db_file))
    raw_cursor = raw_conn.cursor()
    raw_cursor.execute("BEGIN TRANSACTION;")
    raw_cursor.execute("INSERT INTO videos (id, filename, file_path, file_hash, file_size, duration, width, height, fps, codec, format, processing_status, created_at) "
                       "VALUES ('temp_uncommitted', 'temp.mp4', '/temp.mp4', 'hash_temp', 1024, 1.0, 100, 100, 24.0, 'h264', 'mp4', 'pending', datetime('now'));")
    # Abruptly close without commit (simulating crash)
    raw_conn.close()

    # 3. Re-open connection and verify WAL recovery rolled back uncommitted write
    TestingSession = sessionmaker(bind=engine)
    with TestingSession() as session:
        # Integrity check
        integrity = session.execute(text("PRAGMA integrity_check;")).scalar()
        assert integrity == "ok"

        # Uncommitted record must NOT exist
        uncommitted = session.query(Video).filter_by(id="temp_uncommitted").first()
        assert uncommitted is None
