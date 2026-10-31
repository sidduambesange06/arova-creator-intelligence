from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.ai.providers.embeddings import index_video_chunks
from app.ai.providers.transcription import TranscriptionProvider
from app.database.session import SessionLocal
from app.models.entities import ProcessingJob, Video, VideoScene
from app.processing.audio import extract_audio_wav
from app.processing.scene_detection import detect_video_scenes
from app.services.transcription_service import transcribe_and_store


@dataclass
class WorkerTelemetry:
    jobs_completed: int = 0
    jobs_failed: int = 0
    last_rtf: float = 0.0
    avg_rtf: float = 0.0
    total_audio_sec: float = 0.0
    total_proc_sec: float = 0.0


worker_telemetry = WorkerTelemetry()
_telemetry_lock = threading.Lock()


def get_worker_telemetry() -> WorkerTelemetry:
    with _telemetry_lock:
        return WorkerTelemetry(
            jobs_completed=worker_telemetry.jobs_completed,
            jobs_failed=worker_telemetry.jobs_failed,
            last_rtf=worker_telemetry.last_rtf,
            avg_rtf=worker_telemetry.avg_rtf,
            total_audio_sec=round(worker_telemetry.total_audio_sec, 2),
            total_proc_sec=round(worker_telemetry.total_proc_sec, 2),
        )


def _execute_pipeline(
    db: Session,
    video_id: str,
    provider: TranscriptionProvider | None = None,
    media_storage_dir: str | Path | None = None,
) -> str:
    start_time = time.perf_counter()
    video = db.query(Video).filter_by(id=video_id).first()
    if not video:
        raise LookupError(f"Video {video_id} not found")

    job_id = str(uuid4())
    job = ProcessingJob(
        id=job_id,
        video_id=video.id,
        job_type="full_pipeline",
        status="processing",
        progress=5.0,
    )
    video.processing_status = "processing"
    db.add(job)
    db.commit()

    try:
        # Step 1 (Scenes)
        job.progress = 15.0
        db.commit()

        from app.processing.visual_text import extract_visual_text_from_frame

        scenes = detect_video_scenes(
            video_path=video.file_path,
            video_id=video.id,
            duration=video.duration,
            output_dir=media_storage_dir,
        )
        db.query(VideoScene).filter_by(video_id=video.id).delete()
        for s in scenes:
            vis_text = extract_visual_text_from_frame(s.thumbnail_path)
            db.add(
                VideoScene(
                    id=str(uuid4()),
                    video_id=video.id,
                    scene_index=s.scene_index,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    thumbnail_path=s.thumbnail_path,
                    description=vis_text or None,
                )
            )

        # Step 2 (Audio WAV extraction)
        job.progress = 50.0
        db.commit()
        wav_path = extract_audio_wav(
            video_path=video.file_path,
            video_id=video.id,
            output_dir=media_storage_dir,
        )

        # Step 3 (Whisper ASR Transcription)
        job.progress = 80.0
        db.commit()
        transcribe_and_store(
            db=db,
            video=video,
            audio_path=wav_path,
            provider=provider,
        )

        # Step 4 (Index Timestamp Windows for Hybrid RAG)
        job.progress = 90.0
        db.commit()
        index_video_chunks(
            db=db,
            video_id=video.id,
            storage_dir=media_storage_dir,
        )

        # Step 5 (Complete)
        elapsed = time.perf_counter() - start_time
        rtf = round(elapsed / max(video.duration, 0.1), 3)

        job.status = "completed"
        job.progress = 100.0
        job.completed_at = datetime.now(timezone.utc)
        video.processing_status = "completed"
        db.commit()

        with _telemetry_lock:
            worker_telemetry.jobs_completed += 1
            worker_telemetry.last_rtf = rtf
            worker_telemetry.total_audio_sec += video.duration
            worker_telemetry.total_proc_sec += elapsed
            worker_telemetry.avg_rtf = round(
                worker_telemetry.total_proc_sec / max(worker_telemetry.total_audio_sec, 0.1),
                3,
            )

        return job.id

    except Exception as exc:
        db.rollback()
        job.status = "failed"
        job.error_message = str(exc)
        video.processing_status = "failed"
        db.commit()

        with _telemetry_lock:
            worker_telemetry.jobs_failed += 1

        raise


def run_video_pipeline(
    video_id: str,
    db: Session | None = None,
    session_factory: sessionmaker[Session] = SessionLocal,
    provider: TranscriptionProvider | None = None,
    media_storage_dir: str | Path | None = None,
) -> str:
    if db is not None:
        return _execute_pipeline(
            db=db,
            video_id=video_id,
            provider=provider,
            media_storage_dir=media_storage_dir,
        )
    with session_factory() as session:
        return _execute_pipeline(
            db=session,
            video_id=video_id,
            provider=provider,
            media_storage_dir=media_storage_dir,
        )
