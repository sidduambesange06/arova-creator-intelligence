from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entities import Artifact, ProcessingJob, StageRun, Video
from app.schemas.pipeline import ArtifactOut, ProcessingJobOut, StageRunOut
from app.services.pipeline_orchestrator import cancel_pipeline
from app.workers.pipeline_runner import get_worker_telemetry, run_video_pipeline

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=list[ProcessingJobOut])
def list_jobs(db: Session = Depends(get_db)) -> list[ProcessingJobOut]:
    jobs = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).all()
    return [ProcessingJobOut.model_validate(j) for j in jobs]


@router.get("/telemetry/stats")
def get_telemetry_stats() -> dict[str, float | int]:
    tel = get_worker_telemetry()
    return {
        "jobs_completed": tel.jobs_completed,
        "jobs_failed": tel.jobs_failed,
        "last_rtf": tel.last_rtf,
        "avg_rtf": tel.avg_rtf,
        "total_audio_sec": tel.total_audio_sec,
        "total_proc_sec": tel.total_proc_sec,
    }


@router.get("/{job_id}", response_model=ProcessingJobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> ProcessingJobOut:
    job = db.query(ProcessingJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return ProcessingJobOut.model_validate(job)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    job = db.query(ProcessingJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    cancelled = cancel_pipeline(db=db, job_id=job_id)
    return {"job_id": job_id, "status": "cancelled" if cancelled else job.status}


@router.post("/{job_id}/resume", response_model=ProcessingJobOut)
def resume_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    job = db.query(ProcessingJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if sync:
        run_video_pipeline(video_id=job.video_id, db=db, job_id=job.id)
        db.refresh(job)
        return ProcessingJobOut.model_validate(job)

    background_tasks.add_task(run_video_pipeline, video_id=job.video_id, job_id=job.id)
    job.status = "processing"
    db.commit()
    db.refresh(job)
    return ProcessingJobOut.model_validate(job)


@router.get("/{job_id}/stages", response_model=list[StageRunOut])
def get_job_stages(job_id: str, db: Session = Depends(get_db)) -> list[StageRunOut]:
    job = db.query(ProcessingJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    video = db.query(Video).filter_by(id=job.video_id).first()
    if not video or not video.version_id:
        return []

    stages = (
        db.query(StageRun)
        .filter_by(version_id=video.version_id)
        .order_by(StageRun.started_at.asc(), StageRun.id.asc())
        .all()
    )
    return [StageRunOut.model_validate(s) for s in stages]


@router.get("/versions/{version_id}/stages", response_model=list[StageRunOut])
def get_version_stages(version_id: str, db: Session = Depends(get_db)) -> list[StageRunOut]:
    stages = (
        db.query(StageRun)
        .filter_by(version_id=version_id)
        .order_by(StageRun.started_at.asc(), StageRun.id.asc())
        .all()
    )
    return [StageRunOut.model_validate(s) for s in stages]


@router.get("/versions/{version_id}/artifacts", response_model=list[ArtifactOut])
def get_version_artifacts(
    version_id: str,
    current_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[ArtifactOut]:
    query = db.query(Artifact).filter_by(version_id=version_id)
    if current_only:
        query = query.filter_by(is_current=True)
    artifacts = query.order_by(Artifact.created_at.desc()).all()
    return [ArtifactOut.model_validate(a) for a in artifacts]
