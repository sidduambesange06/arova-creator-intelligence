from dataclasses import asdict
from fastapi import APIRouter, HTTPException

from app.ai.evaluation.eval_harness import (
    EvaluationReport,
    get_latest_evaluation_report,
    run_evaluation,
)
from app.workers.pipeline_runner import get_worker_telemetry

router = APIRouter(prefix="/api/v1", tags=["ml-eval"])


@router.post("/ml/eval/run")
def trigger_eval_run() -> dict:
    try:
        report = run_evaluation()
        return asdict(report)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evaluation run failed: {exc}") from exc


@router.get("/ml/eval/report")
def get_eval_report() -> dict:
    report = get_latest_evaluation_report()
    if report is None:
        report = run_evaluation()
    return asdict(report)


@router.get("/system/telemetry")
def get_system_telemetry() -> dict:
    worker_stats = get_worker_telemetry()
    eval_rep = get_latest_evaluation_report()

    return {
        "worker": {
            "jobs_completed": worker_stats.jobs_completed,
            "jobs_failed": worker_stats.jobs_failed,
            "last_rtf": worker_stats.last_rtf,
            "avg_rtf": worker_stats.avg_rtf,
            "total_audio_sec": worker_stats.total_audio_sec,
            "total_proc_sec": worker_stats.total_proc_sec,
        },
        "ml_benchmark": {
            "mrr_at_10_stage1": eval_rep.stage1_metrics.mrr_at_10 if eval_rep else None,
            "mrr_at_10_stage2": eval_rep.stage2_metrics.mrr_at_10 if eval_rep else None,
            "ndcg_at_10_stage1": eval_rep.stage1_metrics.ndcg_at_10 if eval_rep else None,
            "ndcg_at_10_stage2": eval_rep.stage2_metrics.ndcg_at_10 if eval_rep else None,
            "mrr_delta_percent": eval_rep.mrr_delta_percent if eval_rep else None,
            "stage1_latency_p50_ms": eval_rep.stage1_latency_p50_ms if eval_rep else None,
            "stage2_latency_p50_ms": eval_rep.stage2_latency_p50_ms if eval_rep else None,
        },
    }
