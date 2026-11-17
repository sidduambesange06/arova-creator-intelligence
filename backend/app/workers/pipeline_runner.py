from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.ai.providers.transcription import TranscriptionProvider
from app.database.session import SessionLocal
from app.models.entities import ProcessingJob, Video
from app.processing.audio import extract_audio_wav
from app.processing.scene_detection import detect_video_scenes
from app.services.pipeline_orchestrator import PipelineOrchestrator


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
    job_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    start_time = time.perf_counter()
    video = db.query(Video).filter_by(id=video_id).first()
    if not video:
        raise LookupError(f"Video {video_id} not found")

    orchestrator = PipelineOrchestrator(
        db=db,
        media_storage_dir=media_storage_dir,
        provider=provider,
        config=config,
    )

    try:
        final_job_id = orchestrator.run_pipeline(
            video_id=video_id,
            job_id=job_id,
        )

        elapsed = time.perf_counter() - start_time
        rtf = round(elapsed / max(video.duration, 0.1), 3)

        with _telemetry_lock:
            worker_telemetry.jobs_completed += 1
            worker_telemetry.last_rtf = rtf
            worker_telemetry.total_audio_sec += video.duration
            worker_telemetry.total_proc_sec += elapsed
            worker_telemetry.avg_rtf = round(
                worker_telemetry.total_proc_sec / max(worker_telemetry.total_audio_sec, 0.1),
                3,
            )

        return final_job_id

    except Exception:
        with _telemetry_lock:
            worker_telemetry.jobs_failed += 1
        raise


def run_video_pipeline(
    video_id: str,
    db: Session | None = None,
    session_factory: sessionmaker[Session] = SessionLocal,
    provider: TranscriptionProvider | None = None,
    media_storage_dir: str | Path | None = None,
    job_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    if db is not None:
        return _execute_pipeline(
            db=db,
            video_id=video_id,
            provider=provider,
            media_storage_dir=media_storage_dir,
            job_id=job_id,
            config=config,
        )
    with session_factory() as session:
        return _execute_pipeline(
            db=session,
            video_id=video_id,
            provider=provider,
            media_storage_dir=media_storage_dir,
            job_id=job_id,
            config=config,
        )
