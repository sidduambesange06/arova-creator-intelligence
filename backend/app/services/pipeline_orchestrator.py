"""Resumable Intelligence Processing Orchestrator for Task 4C.

Implements:
1. Persistent SQLite-backed pipeline jobs and granular stage runs.
2. Directed Acyclic Graph (DAG) stage dependencies and topological evaluation.
3. Deterministic SHA-256 stage fingerprints and config sensitivity.
4. Idempotent stage skips when outputs already exist.
5. Lease locking, heartbeats, and stale run recovery.
6. Graceful cancellation and pipeline resumption.
7. Atomic artifact persistence and superseding (is_current).
8. Model revision tracking and config hashing.
9. Disk-space safeguards and structured errors.
10. Non-AI stage preservation on optional AI stage failure.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import compute_sha256
from app.models.entities import (
    Annotation,
    Artifact,
    Asset,
    AssetLocation,
    AssetVersion,
    Library,
    LibraryRoot,
    Moment,
    ProcessingJob,
    StageRun,
    Transcript,
    Video,
    VideoScene,
)
from app.models.enums import (
    AuthorType,
    IdentityState,
    LocationAvailability,
    RootPolicy,
    RootType,
    StageStatus,
    TrustLevel,
    compute_deterministic_version_id,
)

# Standard Stage Identifiers
STAGE_METADATA_PROBE = "metadata_probe"
STAGE_PROBE_METADATA = STAGE_METADATA_PROBE
STAGE_SCENE_DETECTION = "scene_detection"
STAGE_OCR_DETECTION = "ocr_detection"
STAGE_AUDIO_EXTRACTION = "audio_extraction"
STAGE_ASR_TRANSCRIPTION = "asr_transcription"
STAGE_EMBEDDING_INDEXING = "embedding_indexing"
STAGE_SUMMARIZATION = "summarization"

# Stage Dependency Graph (DAG)
STAGE_DEPENDENCIES: dict[str, list[str]] = {
    STAGE_PROBE_METADATA: [],
    STAGE_SCENE_DETECTION: [STAGE_PROBE_METADATA],
    STAGE_OCR_DETECTION: [STAGE_SCENE_DETECTION],
    STAGE_AUDIO_EXTRACTION: [STAGE_PROBE_METADATA],
    STAGE_ASR_TRANSCRIPTION: [STAGE_AUDIO_EXTRACTION],
    STAGE_EMBEDDING_INDEXING: [STAGE_ASR_TRANSCRIPTION],
    STAGE_SUMMARIZATION: [STAGE_EMBEDDING_INDEXING],
}

# Topological execution sequence
STAGE_EXECUTION_ORDER: list[str] = [
    STAGE_PROBE_METADATA,
    STAGE_SCENE_DETECTION,
    STAGE_OCR_DETECTION,
    STAGE_AUDIO_EXTRACTION,
    STAGE_ASR_TRANSCRIPTION,
    STAGE_EMBEDDING_INDEXING,
    STAGE_SUMMARIZATION,
]


class InsufficientDiskSpaceError(RuntimeError):
    """Raised when available disk space is below safety threshold."""


class PipelineCancelledError(RuntimeError):
    """Raised when job or version processing has been cancelled by user."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def check_disk_space(target_path: Path | str, min_free_mb: float = 200.0) -> None:
    """Enforce minimum free disk space safeguard before disk-heavy operations."""
    path = Path(target_path).resolve()
    # Find existing ancestor directory to probe disk usage
    probe_dir = path if path.exists() else path.parent
    while not probe_dir.exists() and probe_dir.parent != probe_dir:
        probe_dir = probe_dir.parent

    try:
        usage = shutil.disk_usage(probe_dir)
        free_mb = usage.free / (1024 * 1024)
        if free_mb < min_free_mb:
            raise InsufficientDiskSpaceError(
                f"Available disk space ({free_mb:.1f} MB) is below safe minimum ({min_free_mb} MB) at {probe_dir}"
            )
    except OSError:
        # If filesystem doesn't support statvfs/disk_usage, skip check
        pass


def compute_stage_fingerprint(
    version_id: str,
    stage_name: str,
    config: dict[str, Any] | None = None,
    upstream_fingerprints: list[str] | None = None,
) -> str:
    """Compute deterministic SHA-256 fingerprint for a stage run."""
    config_serialized = json.dumps(config or {}, sort_keys=True)
    config_hash = hashlib.sha256(config_serialized.encode("utf-8")).hexdigest()[:16]
    upstream_chain = ":".join(sorted(upstream_fingerprints or []))
    payload = f"{version_id}:{stage_name}:{config_hash}:{upstream_chain}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ensure_asset_and_version(db: Session, video: Video) -> tuple[Asset, AssetVersion]:
    """Ensure Video is linked to canonical Asset and AssetVersion records."""
    if video.version_id:
        version = db.get(AssetVersion, video.version_id)
        if version:
            asset = db.get(Asset, version.asset_id)
            if asset:
                return asset, version

    file_path = Path(video.file_path).resolve()
    file_hash = video.file_hash or (compute_sha256(file_path) if file_path.is_file() else None)
    version_id = None
    is_verified = False
    if file_hash:
        try:
            version_id = compute_deterministic_version_id(file_hash)
            is_verified = True
        except ValueError:
            version_id = str(uuid4())
    else:
        version_id = str(uuid4())

    version = db.get(AssetVersion, version_id)
    if version:
        asset = db.get(Asset, version.asset_id)
        if not asset:
            asset = Asset(id=version.asset_id, created_at=_utcnow())
            db.add(asset)
            db.flush()
    else:
        asset = Asset(id=str(uuid4()), created_at=_utcnow())
        db.add(asset)
        db.flush()

        version = AssetVersion(
            id=version_id,
            asset_id=asset.id,
            sha256=file_hash,
            size_bytes=video.file_size or (file_path.stat().st_size if file_path.is_file() else 0),
            media_meta=json.dumps({"filename": video.filename, "duration": video.duration}),
            identity_state=IdentityState.VERIFIED.value if is_verified else IdentityState.IDENTITY_UNVERIFIED.value,
            created_at=_utcnow(),
        )
        db.add(version)
        asset.current_version_id = version.id
        db.flush()

    video.asset_id = asset.id
    video.version_id = version.id
    db.flush()
    return asset, version


def persist_stage_artifact(
    db: Session,
    version_id: str,
    kind: str,
    producer_stage: str,
    producer_model: str | None = None,
    producer_revision: str | None = None,
    config_hash: str | None = None,
    trust: str = TrustLevel.UNVERIFIED.value,
) -> Artifact:
    """Persist stage artifact and atomically supersede prior current artifacts of same kind."""
    # Mark prior active artifacts of the same kind as superseded
    prior_artifacts = (
        db.query(Artifact)
        .filter_by(version_id=version_id, kind=kind, is_current=True)
        .all()
    )
    for art in prior_artifacts:
        art.is_current = False

    new_artifact = Artifact(
        id=str(uuid4()),
        version_id=version_id,
        kind=kind,
        producer_stage=producer_stage,
        producer_model=producer_model,
        producer_revision=producer_revision,
        config_hash=config_hash,
        is_current=True,
        trust=trust,
        created_at=_utcnow(),
    )
    db.add(new_artifact)
    db.flush()
    return new_artifact


def recover_stale_stage_runs(db: Session, max_attempts: int = 3) -> list[StageRun]:
    """Detect and recover stage runs whose worker leases have expired."""
    now = _utcnow()
    stale_runs = (
        db.query(StageRun)
        .filter(
            StageRun.status == StageStatus.RUNNING.value,
            StageRun.lease_until.is_not(None),
            StageRun.lease_until < now,
        )
        .all()
    )

    recovered: list[StageRun] = []
    for run in stale_runs:
        if run.attempt < max_attempts:
            run.status = StageStatus.PENDING.value
            run.error_code = "LEASE_EXPIRED_RECOVERED"
            run.error_detail = f"Lease expired at {run.lease_until.isoformat()}; recovered for retry attempt {run.attempt + 1}"
            run.lease_until = None
        else:
            run.status = StageStatus.FAILED.value
            run.error_code = "LEASE_EXPIRED"
            run.error_detail = f"Lease expired and max attempts ({max_attempts}) reached"
            run.lease_until = None
            run.finished_at = now
        recovered.append(run)

    if recovered:
        db.commit()
    return recovered


def cancel_pipeline(db: Session, job_id: str | None = None, version_id: str | None = None) -> bool:
    """Cancel a running or scheduled pipeline job and its stage runs."""
    cancelled_any = False
    now = _utcnow()

    if job_id:
        job = db.get(ProcessingJob, job_id)
        if job and job.status not in ("completed", "failed", "cancelled"):
            job.status = "cancelled"
            job.error_message = "Processing cancelled by user"
            cancelled_any = True

            # If job is associated with a video, cancel its stage runs
            video = db.get(Video, job.video_id)
            if video and video.version_id:
                version_id = video.version_id

    if version_id:
        active_runs = (
            db.query(StageRun)
            .filter(
                StageRun.version_id == version_id,
                StageRun.status.in_([StageStatus.PENDING.value, StageStatus.RUNNING.value]),
            )
            .all()
        )
        for r in active_runs:
            r.status = StageStatus.CANCELLED.value
            r.finished_at = now
            r.lease_until = None
            cancelled_any = True

    if cancelled_any:
        db.commit()
    return cancelled_any


class PipelineOrchestrator:
    """Resumable pipeline execution orchestrator managing stage DAG, leases, artifacts, and recovery."""

    def __init__(
        self,
        db: Session,
        media_storage_dir: Path | str | None = None,
        provider: Any = None,
        config: dict[str, Any] | None = None,
        min_free_mb: float = 200.0,
        lease_duration_sec: int = 60,
    ) -> None:
        self.db = db
        self.media_storage_dir = Path(media_storage_dir) if media_storage_dir else Path(settings.MEDIA_STORAGE_DIR)
        self.provider = provider
        self.config = config or {}
        self.min_free_mb = min_free_mb
        self.lease_duration_sec = lease_duration_sec

    def heartbeat(self, stage_run: StageRun) -> None:
        """Extend lease duration for active stage run."""
        stage_run.heartbeat_at = _utcnow()
        stage_run.lease_until = _utcnow() + timedelta(seconds=self.lease_duration_sec)
        self.db.flush()

    def _is_job_cancelled(self, job_id: str) -> bool:
        job = self.db.get(ProcessingJob, job_id)
        return job is not None and job.status == "cancelled"

    def run_pipeline(
        self,
        video_id: str,
        job_id: str | None = None,
        resume_only: bool = False,
    ) -> str:
        """Execute or resume the processing pipeline for video_id."""
        video = self.db.get(Video, video_id)
        if not video:
            raise LookupError(f"Video {video_id} not found")

        # Recover any orphaned or stale stage runs before starting
        recover_stale_stage_runs(self.db)

        asset, version = ensure_asset_and_version(self.db, video)
        version_id = version.id

        if not job_id:
            job_id = str(uuid4())
            job = ProcessingJob(
                id=job_id,
                video_id=video.id,
                job_type="full_pipeline",
                status="processing",
                progress=5.0,
                created_at=_utcnow(),
            )
            self.db.add(job)
        else:
            job = self.db.get(ProcessingJob, job_id)
            if not job:
                job = ProcessingJob(
                    id=job_id,
                    video_id=video.id,
                    job_type="full_pipeline",
                    status="processing",
                    progress=5.0,
                    created_at=_utcnow(),
                )
                self.db.add(job)
            elif job.status == "cancelled":
                # Job was already cancelled; do not execute
                return job.id
            else:
                job.status = "processing"
                job.error_message = None

        video.processing_status = "processing"
        self.db.commit()

        start_time = time.perf_counter()
        stage_fingerprints: dict[str, str] = {}

        try:
            # Stage 1: Metadata Probe
            self._check_cancellation(job.id)
            fp_probe = compute_stage_fingerprint(version_id, STAGE_PROBE_METADATA, self.config.get(STAGE_PROBE_METADATA))
            stage_fingerprints[STAGE_PROBE_METADATA] = fp_probe
            self._run_or_resume_stage(
                version_id=version_id,
                stage_name=STAGE_PROBE_METADATA,
                fingerprint=fp_probe,
                action=lambda sr: self._exec_metadata_probe(video, version, sr),
                progress_on_success=15.0,
                job=job,
            )

            # Stage 2: Scene Detection
            self._check_cancellation(job.id)
            fp_scenes = compute_stage_fingerprint(
                version_id,
                STAGE_SCENE_DETECTION,
                self.config.get(STAGE_SCENE_DETECTION),
                [stage_fingerprints[STAGE_PROBE_METADATA]],
            )
            stage_fingerprints[STAGE_SCENE_DETECTION] = fp_scenes
            self._run_or_resume_stage(
                version_id=version_id,
                stage_name=STAGE_SCENE_DETECTION,
                fingerprint=fp_scenes,
                action=lambda sr: self._exec_scene_detection(video, version, sr),
                progress_on_success=35.0,
                job=job,
            )

            # Stage 3: OCR Detection
            self._check_cancellation(job.id)
            fp_ocr = compute_stage_fingerprint(
                version_id,
                STAGE_OCR_DETECTION,
                self.config.get(STAGE_OCR_DETECTION),
                [stage_fingerprints[STAGE_SCENE_DETECTION]],
            )
            stage_fingerprints[STAGE_OCR_DETECTION] = fp_ocr
            self._run_or_resume_stage(
                version_id=version_id,
                stage_name=STAGE_OCR_DETECTION,
                fingerprint=fp_ocr,
                action=lambda sr: self._exec_ocr_detection(video, version, sr),
                progress_on_success=50.0,
                job=job,
            )

            # Stage 4: Audio Extraction (if audio stream exists and no sidecar subtitles)
            self._check_cancellation(job.id)
            fp_audio = compute_stage_fingerprint(
                version_id,
                STAGE_AUDIO_EXTRACTION,
                self.config.get(STAGE_AUDIO_EXTRACTION),
                [stage_fingerprints[STAGE_PROBE_METADATA]],
            )
            stage_fingerprints[STAGE_AUDIO_EXTRACTION] = fp_audio
            wav_path = self._run_or_resume_stage(
                version_id=version_id,
                stage_name=STAGE_AUDIO_EXTRACTION,
                fingerprint=fp_audio,
                action=lambda sr: self._exec_audio_extraction(video, version, sr),
                progress_on_success=65.0,
                job=job,
            )

            # Stage 5: ASR Transcription (or Subtitle Ingestion)
            self._check_cancellation(job.id)
            fp_asr = compute_stage_fingerprint(
                version_id,
                STAGE_ASR_TRANSCRIPTION,
                self.config.get(STAGE_ASR_TRANSCRIPTION),
                [stage_fingerprints[STAGE_AUDIO_EXTRACTION]],
            )
            stage_fingerprints[STAGE_ASR_TRANSCRIPTION] = fp_asr
            has_transcript = self._run_or_resume_stage(
                version_id=version_id,
                stage_name=STAGE_ASR_TRANSCRIPTION,
                fingerprint=fp_asr,
                action=lambda sr: self._exec_asr_transcription(video, version, wav_path, sr),
                progress_on_success=85.0,
                job=job,
            )

            # Stage 6: Embedding Indexing
            self._check_cancellation(job.id)
            fp_embed = compute_stage_fingerprint(
                version_id,
                STAGE_EMBEDDING_INDEXING,
                self.config.get(STAGE_EMBEDDING_INDEXING),
                [stage_fingerprints[STAGE_ASR_TRANSCRIPTION]],
            )
            stage_fingerprints[STAGE_EMBEDDING_INDEXING] = fp_embed
            self._run_or_resume_stage(
                version_id=version_id,
                stage_name=STAGE_EMBEDDING_INDEXING,
                fingerprint=fp_embed,
                action=lambda sr: self._exec_embedding_indexing(video, version, has_transcript, sr),
                progress_on_success=95.0,
                job=job,
            )

            # Mark Complete
            job.status = "completed"
            job.progress = 100.0
            job.completed_at = _utcnow()
            video.processing_status = "completed"
            self.db.commit()
            return job.id

        except PipelineCancelledError:
            self.db.rollback()
            job = self.db.get(ProcessingJob, job_id)
            if job:
                job.status = "cancelled"
                job.error_message = "Pipeline cancelled by user"
            video = self.db.get(Video, video_id)
            if video:
                video.processing_status = "cancelled"
            self.db.commit()
            return job_id

        except Exception as exc:
            self.db.rollback()
            job = self.db.get(ProcessingJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)
            video = self.db.get(Video, video_id)
            if video:
                video.processing_status = "failed"
            self.db.commit()
            raise

    def _check_cancellation(self, job_id: str) -> None:
        if self._is_job_cancelled(job_id):
            raise PipelineCancelledError("Processing job was cancelled by user")

    def _run_or_resume_stage(
        self,
        version_id: str,
        stage_name: str,
        fingerprint: str,
        action: Any,
        progress_on_success: float,
        job: ProcessingJob,
    ) -> Any:
        """Execute stage with idempotent skip, lease locking, and artifact tracking."""
        existing_run = (
            self.db.query(StageRun)
            .filter_by(version_id=version_id, stage=stage_name, fingerprint=fingerprint)
            .first()
        )

        if existing_run and existing_run.status == StageStatus.SUCCEEDED.value:
            if stage_name == STAGE_ASR_TRANSCRIPTION:
                from app.models.entities import TranscriptSegment
                # Ensure a transcript actually exists for this video
                has_t = self.db.query(Transcript).filter_by(video_id=job.video_id).first() is not None
                if not has_t:
                    existing_t = (
                        self.db.query(Transcript)
                        .join(Video, Video.id == Transcript.video_id)
                        .filter(Video.version_id == version_id)
                        .first()
                    )
                    if existing_t:
                        new_t = Transcript(
                            id=str(uuid4()),
                            video_id=job.video_id,
                            language=existing_t.language,
                            model_name=existing_t.model_name,
                            full_text=existing_t.full_text,
                        )
                        self.db.add(new_t)
                        self.db.flush()
                        for seg in existing_t.segments:
                            self.db.add(
                                TranscriptSegment(
                                    id=str(uuid4()),
                                    transcript_id=new_t.id,
                                    video_id=job.video_id,
                                    start_time=seg.start_time,
                                    end_time=seg.end_time,
                                    text=seg.text,
                                    confidence=seg.confidence,
                                )
                            )
                        self.db.commit()
                        job.progress = progress_on_success
                        return existing_run.output_ref
                    # No transcript exists anywhere in DB for this version; re-execute stage
                else:
                    job.progress = progress_on_success
                    self.db.commit()
                    return existing_run.output_ref
            else:
                job.progress = progress_on_success
                self.db.commit()
                return existing_run.output_ref

        if not existing_run:
            existing_run = StageRun(
                id=str(uuid4()),
                version_id=version_id,
                stage=stage_name,
                fingerprint=fingerprint,
                status=StageStatus.PENDING.value,
                attempt=1,
            )
            self.db.add(existing_run)
            self.db.flush()

        # Check lease
        now = _utcnow()
        if existing_run.status == StageStatus.RUNNING.value and existing_run.lease_until and existing_run.lease_until > now:
            # Another worker currently holds a valid lease
            return existing_run.output_ref

        # Acquire lease
        existing_run.status = StageStatus.RUNNING.value
        existing_run.started_at = now
        existing_run.heartbeat_at = now
        existing_run.lease_until = now + timedelta(seconds=self.lease_duration_sec)
        existing_run.attempt += 1
        self.db.commit()

        try:
            # Check disk space safeguard before executing
            check_disk_space(self.media_storage_dir, min_free_mb=self.min_free_mb)

            # Execute action
            output_result = action(existing_run)

            # Success
            existing_run.status = StageStatus.SUCCEEDED.value
            existing_run.output_ref = str(output_result) if output_result is not None else None
            existing_run.finished_at = _utcnow()
            existing_run.lease_until = None
            existing_run.error_code = None
            existing_run.error_detail = None

            job.progress = progress_on_success
            self.db.commit()
            return output_result

        except Exception as exc:
            self.db.rollback()
            # Reload stage run in fresh transaction to record failure
            run_to_update = self.db.get(StageRun, existing_run.id)
            if run_to_update:
                run_to_update.status = StageStatus.FAILED.value
                run_to_update.finished_at = _utcnow()
                run_to_update.lease_until = None
                if isinstance(exc, InsufficientDiskSpaceError):
                    run_to_update.error_code = "INSUFFICIENT_DISK_SPACE"
                elif isinstance(exc, PipelineCancelledError):
                    run_to_update.status = StageStatus.CANCELLED.value
                    run_to_update.error_code = "CANCELLED"
                else:
                    run_to_update.error_code = f"{stage_name.upper()}_FAILED"
                run_to_update.error_detail = str(exc)
                self.db.commit()
            raise

    # -------------------------------------------------------------------------
    # Stage Implementations
    # -------------------------------------------------------------------------

    def _exec_metadata_probe(self, video: Video, version: AssetVersion, stage_run: StageRun) -> str:
        meta_dict = {
            "duration": video.duration or 0.0,
            "width": video.width or 0,
            "height": video.height or 0,
            "fps": video.fps or 0.0,
            "codec": video.codec or "unknown",
            "format": video.format or "unknown",
            "file_size": video.file_size or 0,
        }
        if video.duration <= 0 or not video.codec or video.codec == "unknown":
            try:
                from app.processing.metadata import probe_video_metadata
                file_path = Path(video.file_path).resolve()
                if file_path.is_file():
                    meta = probe_video_metadata(file_path)
                    video.duration = meta.duration
                    video.width = meta.width
                    video.height = meta.height
                    video.fps = meta.fps
                    video.codec = meta.codec
                    video.format = meta.format
                    video.file_size = meta.file_size
                    meta_dict = {
                        "duration": meta.duration,
                        "width": meta.width,
                        "height": meta.height,
                        "fps": meta.fps,
                        "codec": meta.codec,
                        "format": meta.format,
                        "file_size": meta.file_size,
                    }
            except Exception:
                pass

        version.media_meta = json.dumps(meta_dict)

        persist_stage_artifact(
            db=self.db,
            version_id=version.id,
            kind="metadata",
            producer_stage=STAGE_PROBE_METADATA,
            config_hash=stage_run.fingerprint[:16],
            trust=TrustLevel.HUMAN_CONFIRMED.value,
        )
        self.db.flush()
        return json.dumps(meta_dict)

    def _exec_scene_detection(self, video: Video, version: AssetVersion, stage_run: StageRun) -> int:
        import app.workers.pipeline_runner as runner_mod
        detect_fn = getattr(runner_mod, "detect_video_scenes", None)
        if detect_fn is None:
            from app.processing.scene_detection import detect_video_scenes as detect_fn

        scenes = detect_fn(
            video_path=video.file_path,
            video_id=video.id,
            duration=video.duration,
            output_dir=self.media_storage_dir,
        )

        self.db.query(VideoScene).filter_by(video_id=video.id).delete()
        self.db.query(Moment).filter_by(version_id=version.id, kind="scene").delete()

        for s in scenes:
            scene_id = str(uuid4())
            self.db.add(
                VideoScene(
                    id=scene_id,
                    video_id=video.id,
                    scene_index=s.scene_index,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    thumbnail_path=s.thumbnail_path,
                )
            )
            # Create immutable Moment record
            self.db.add(
                Moment(
                    id=str(uuid4()),
                    version_id=version.id,
                    start_ms=int(s.start_time * 1000),
                    end_ms=int(s.end_time * 1000),
                    kind="scene",
                    created_at=_utcnow(),
                )
            )

        persist_stage_artifact(
            db=self.db,
            version_id=version.id,
            kind="scenes",
            producer_stage=STAGE_SCENE_DETECTION,
            config_hash=stage_run.fingerprint[:16],
            trust=TrustLevel.UNVERIFIED.value,
        )
        self.db.flush()
        return len(scenes)

    def _exec_ocr_detection(self, video: Video, version: AssetVersion, stage_run: StageRun) -> int:
        from app.processing.visual_text import extract_visual_text_from_frame
        scenes = self.db.query(VideoScene).filter_by(video_id=video.id).all()
        ocr_count = 0

        for s in scenes:
            if s.thumbnail_path:
                vis_text = extract_visual_text_from_frame(s.thumbnail_path)
                if vis_text:
                    s.description = vis_text
                    ocr_count += 1
                    # Record visual annotation
                    self.db.add(
                        Annotation(
                            id=str(uuid4()),
                            version_id=version.id,
                            author_type=AuthorType.AI.value,
                            display_name="On-Screen Visual Text",
                            trust=TrustLevel.AI_GENERATED.value,
                            text_content=vis_text,
                            created_at=_utcnow(),
                        )
                    )

        persist_stage_artifact(
            db=self.db,
            version_id=version.id,
            kind="ocr",
            producer_stage=STAGE_OCR_DETECTION,
            config_hash=stage_run.fingerprint[:16],
            trust=TrustLevel.AI_GENERATED.value,
        )
        self.db.flush()
        return ocr_count

    def _exec_audio_extraction(self, video: Video, version: AssetVersion, stage_run: StageRun) -> str | None:
        from app.processing.metadata import has_audio_stream
        from app.processing.subtitles import find_sidecar_subtitles
        from app.processing.audio import extract_audio_wav

        # If sidecar subtitle is present, audio extraction is not needed
        sidecar = find_sidecar_subtitles(video.file_path)
        if sidecar and sidecar.is_file():
            stage_run.skip_reason = "sidecar_subtitles_present"
            return None

        if not has_audio_stream(video.file_path):
            stage_run.skip_reason = "no_audio_stream"
            return None

        import app.workers.pipeline_runner as runner_mod
        extract_fn = getattr(runner_mod, "extract_audio_wav", None)
        if extract_fn is None:
            from app.processing.audio import extract_audio_wav as extract_fn

        wav_path = extract_fn(
            video_path=video.file_path,
            video_id=video.id,
            output_dir=self.media_storage_dir,
        )
        return str(wav_path) if wav_path and wav_path.is_file() else None

    def _exec_asr_transcription(
        self,
        video: Video,
        version: AssetVersion,
        wav_path_str: str | None,
        stage_run: StageRun,
    ) -> bool:
        from app.processing.subtitles import find_sidecar_subtitles
        from app.services.subtitle_service import ingest_subtitles_for_video
        from app.services.transcription_service import transcribe_and_store

        # 1. Prefer sidecar subtitle if found
        sidecar_path = find_sidecar_subtitles(video.file_path)
        if sidecar_path and sidecar_path.is_file():
            sub_text = sidecar_path.read_text(encoding="utf-8", errors="replace")
            ingest_subtitles_for_video(
                db=self.db,
                video=video,
                content=sub_text,
                source_name=sidecar_path.name,
                media_storage_dir=self.media_storage_dir,
            )
            persist_stage_artifact(
                db=self.db,
                version_id=version.id,
                kind="transcript",
                producer_stage=STAGE_ASR_TRANSCRIPTION,
                producer_model="sidecar_subtitles",
                config_hash=stage_run.fingerprint[:16],
                trust=TrustLevel.HUMAN_CONFIRMED.value,
            )
            return True

        # 2. Transcribe WAV if audio exists
        if not wav_path_str:
            stage_run.skip_reason = "no_audio_or_subtitles"
            return False

        wav_path = Path(wav_path_str)
        if not wav_path.is_file():
            stage_run.skip_reason = "wav_file_missing"
            return False

        try:
            transcript_obj = transcribe_and_store(
                db=self.db,
                video=video,
                audio_path=wav_path,
                provider=self.provider,
            )
            if transcript_obj and transcript_obj.segments:
                # Record transcript annotation
                self.db.add(
                    Annotation(
                        id=str(uuid4()),
                        version_id=version.id,
                        author_type=AuthorType.ASR.value,
                        display_name="Speech Transcript",
                        trust=TrustLevel.ASR.value,
                        text_content=transcript_obj.full_text,
                        created_at=_utcnow(),
                    )
                )
                persist_stage_artifact(
                    db=self.db,
                    version_id=version.id,
                    kind="transcript",
                    producer_stage=STAGE_ASR_TRANSCRIPTION,
                    producer_model=transcript_obj.model_name,
                    config_hash=stage_run.fingerprint[:16],
                    trust=TrustLevel.ASR.value,
                )
                return True
            return False
        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _exec_embedding_indexing(
        self,
        video: Video,
        version: AssetVersion,
        has_transcript: bool,
        stage_run: StageRun,
    ) -> bool:
        from app.ai.providers.embeddings import index_video_chunks

        if not has_transcript:
            # Check if video has transcript in DB
            has_t = self.db.query(Transcript).filter_by(video_id=video.id).first() is not None
            if not has_t:
                stage_run.skip_reason = "no_transcript_to_index"
                return False

        index_video_chunks(
            db=self.db,
            video_id=video.id,
            storage_dir=self.media_storage_dir,
        )

        persist_stage_artifact(
            db=self.db,
            version_id=version.id,
            kind="embeddings",
            producer_stage=STAGE_EMBEDDING_INDEXING,
            config_hash=stage_run.fingerprint[:16],
            trust=TrustLevel.UNVERIFIED.value,
        )
        return True
