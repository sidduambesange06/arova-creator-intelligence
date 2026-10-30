from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entities import ProcessingJob
from app.schemas.pipeline import ProcessingJobOut
from app.workers.pipeline_runner import get_worker_telemetry

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=list[ProcessingJobOut])
def list_jobs(db: Session = Depends(get_db)) -> list[ProcessingJobOut]:
    jobs = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).all()
    return [ProcessingJobOut.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=ProcessingJobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> ProcessingJobOut:
    job = db.query(ProcessingJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return ProcessingJobOut.model_validate(job)


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

