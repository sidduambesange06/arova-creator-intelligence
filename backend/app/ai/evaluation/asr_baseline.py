"""M3.1 Faster-Whisper ASR Baseline Runner for Arova Indic Creator Bench.

Executes genuine local ASR inference through the existing TranscriptionProvider seam
against validated M2 dataset manifests, producing per-utterance hypotheses, per-language
WER/CER aggregations (micro and macro), cold-init vs inference timing, RTF, measured
RAM/VRAM, and schema-validated secret-safe provenance.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time
from typing import Any
import uuid

from app.ai.evaluation.indic_bench import (
    NORMALIZATION_POLICY_VERSION,
    build_asr_run_provenance,
    build_batch_run_provenance,
    compute_safe_corpus_metrics,
    compute_safe_utterance_metrics,
    validate_indic_bench_dataset,
)
from app.ai.providers.transcription import TranscriptionProvider

WHISPER_LANG_MAP: dict[str, str] = {
    "hi_in": "hi",
    "kn_in": "kn",
    "ta_in": "ta",
    "te_in": "te",
    "en_us": "en",
}


def _get_rss_mb() -> float | None:
    try:
        import psutil

        return round(psutil.Process().memory_info().rss / (1024.0 * 1024.0), 2)
    except Exception:
        return None


def _get_dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    for pkg in ("faster-whisper", "ctranslate2", "psutil"):
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[pkg] = "NOT_INSTALLED"
    return versions


def _classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if isinstance(exc, MemoryError) or "memory" in msg or "oom" in msg:
        return "INSUFFICIENT_MEMORY"
    if isinstance(exc, TimeoutError) or "timeout" in msg or "timed out" in msg:
        return "TIMEOUT"
    if "model_not_installed" in msg or "not found locally" in msg:
        return "MODEL_NOT_INSTALLED"
    if "device" in msg or "cuda" in msg:
        return "UNSUPPORTED_DEVICE"
    if isinstance(exc, FileNotFoundError):
        return "MISSING_ASSET"
    return "INFERENCE_ERROR"


def _load_checkpoint(checkpoint_path: Path | None, config_fingerprint: str) -> dict[str, dict[str, Any]]:
    if checkpoint_path is None or not checkpoint_path.is_file():
        return {}
    loaded: dict[str, dict[str, Any]] = {}
    for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if (
            obj.get("config_fingerprint_sha256") == config_fingerprint
            and obj.get("status") == "COMPLETED"
            and isinstance(obj.get("utterance_id"), str)
        ):
            loaded[obj["utterance_id"]] = obj
    return loaded


def _append_checkpoint(checkpoint_path: Path | None, record: dict[str, Any]) -> None:
    if checkpoint_path is None:
        return
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_indic_asr_baseline(
    dataset_root: Path | str,
    provider: TranscriptionProvider,
    *,
    model_id: str,
    model_revision: str = "local_pinned",
    provider_type: str = "faster_whisper",
    device: str = "cpu",
    compute_type: str = "int8",
    language_mode: str = "forced",
    beam_size: int = 5,
    vad_filter: bool = False,
    word_timestamps: bool = True,
    condition_on_previous_text: bool = False,
    max_retries: int = 0,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    """Run local ASR baseline over a validated M2 Indic Creator Bench dataset."""
    if language_mode not in ("forced", "auto"):
        raise ValueError(f"Unsupported language_mode '{language_mode}'; expected 'forced' or 'auto'.")

    root = Path(dataset_root).resolve()
    val_report, samples = validate_indic_bench_dataset(root, require_audio=True)
    if val_report.status != "VALID" or not samples:
        codes = sorted({f.code for f in val_report.failures})
        raise ValueError(
            f"Dataset validation failed (status={val_report.status}, codes={codes}). "
            "Refusing to run ASR on unvalidated or tampered dataset."
        )

    descriptor = json.loads((root / "dataset.json").read_text(encoding="utf-8"))
    manifest_sha256 = str(descriptor["manifest_sha256"])
    dataset_id = str(descriptor["dataset_id"])
    dataset_version = str(descriptor["dataset_version"])
    split = str(descriptor["split"])
    license_summary = str(descriptor.get("license_summary", "UNKNOWN"))

    run_id = f"m3-asr-{uuid.uuid4().hex[:12]}"
    batch_id = f"m3-batch-{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()
    decoding_params = {
        "beam_size": beam_size,
        "vad_filter": vad_filter,
        "word_timestamps": word_timestamps,
        "condition_on_previous_text": condition_on_previous_text,
    }
    env_info = _get_dependency_versions()

    # Check provider availability before inference (never fabricate output when weights are absent)
    if not provider.is_available():
        asr_prov = build_asr_run_provenance(
            run_id=run_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            split=split,
            manifest_sha256=manifest_sha256,
            provider_type=provider_type,
            model_id=model_id,
            model_revision=model_revision,
            device=device,
            compute_type=compute_type,
            language_mode=language_mode,
            normalization_policy_version=NORMALIZATION_POLICY_VERSION,
            decoding_params=decoding_params,
            execution_status="NOT_RUN",
            created_at_utc=created_at,
            environment=env_info,
        )
        batch_prov = build_batch_run_provenance(
            batch_id=batch_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            split=split,
            manifest_sha256=manifest_sha256,
            total_items=len(samples),
            processed_items=0,
            succeeded_items=0,
            failed_items=0,
            skipped_items=len(samples),
            run_ids=[run_id],
            batch_config={"language_mode": language_mode, "max_retries": max_retries},
            execution_status="NOT_RUN",
            created_at_utc=created_at,
            notes="Provider unavailable (MODEL_NOT_INSTALLED or dependency missing).",
        )
        return {
            "execution_status": "BLOCKED",
            "blocker_reason": "MODEL_NOT_INSTALLED",
            "dataset": {
                "dataset_id": dataset_id,
                "dataset_version": dataset_version,
                "split": split,
                "manifest_sha256": manifest_sha256,
                "license_summary": license_summary,
                "total_samples": len(samples),
            },
            "asr_provenance": asr_prov,
            "batch_provenance": batch_prov,
            "timing": {
                "cold_init_sec": 0.0,
                "total_inference_sec": 0.0,
                "total_audio_sec": round(sum(float(s["duration_sec"]) for s in samples), 3),
                "corpus_rtf": None,
            },
            "resources": {
                "rss_before_mb": _get_rss_mb(),
                "rss_after_init_mb": None,
                "rss_peak_mb": _get_rss_mb(),
                "vram_mb": "NOT_MEASURED",
                "energy_joules": "NOT_MEASURED",
            },
            "corpus_metrics": compute_safe_corpus_metrics([]),
            "per_language": {},
            "utterances": [],
        }

    # Build provisional fingerprint for checkpoint matching
    provisional_prov = build_asr_run_provenance(
        run_id=run_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        split=split,
        manifest_sha256=manifest_sha256,
        provider_type=provider_type,
        model_id=model_id,
        model_revision=model_revision,
        device=device,
        compute_type=compute_type,
        language_mode=language_mode,
        normalization_policy_version=NORMALIZATION_POLICY_VERSION,
        decoding_params=decoding_params,
        execution_status="NOT_RUN",
        created_at_utc=created_at,
        environment=env_info,
    )
    cfg_fp = provisional_prov["config_fingerprint_sha256"]
    cached_records = _load_checkpoint(checkpoint_path, cfg_fp)

    rss_before = _get_rss_mb()
    rss_peak = rss_before

    # Measure cold model initialization separately from per-clip inference
    cold_init_start = time.perf_counter()
    if hasattr(provider, "_get_or_load_model"):
        provider._get_or_load_model()  # type: ignore[attr-defined]
    cold_init_sec = round(time.perf_counter() - cold_init_start, 4)
    rss_after_init = _get_rss_mb()
    if rss_after_init is not None and (rss_peak is None or rss_after_init > rss_peak):
        rss_peak = rss_after_init

    utterances: list[dict[str, Any]] = []
    succeeded_metrics: list[dict[str, Any]] = []
    per_lang_metrics: dict[str, list[dict[str, Any]]] = defaultdict(list)
    per_lang_audio_sec: dict[str, float] = defaultdict(float)
    per_lang_infer_sec: dict[str, float] = defaultdict(float)
    per_lang_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "succeeded": 0, "failed": 0})

    total_inference_sec = 0.0
    total_audio_sec = 0.0
    succeeded_count = 0
    failed_count = 0
    resumed_count = 0

    for sample in samples:
        uid = str(sample["utterance_id"])
        lang_code = str(sample["language_code"])
        duration_sec = float(sample["duration_sec"])
        raw_ref = str(sample["reference_transcript"])
        audio_path = (root / str(sample["audio_relpath"])).resolve()

        per_lang_counts[lang_code]["total"] += 1
        total_audio_sec += duration_sec

        if uid in cached_records:
            rec = dict(cached_records[uid])
            rec["resumed_from_checkpoint"] = True
            utterances.append(rec)
            succeeded_count += 1
            resumed_count += 1
            per_lang_counts[lang_code]["succeeded"] += 1
            per_lang_audio_sec[lang_code] += duration_sec
            per_lang_infer_sec[lang_code] += float(rec.get("inference_sec", 0.0))
            total_inference_sec += float(rec.get("inference_sec", 0.0))
            m = rec["metrics"]
            succeeded_metrics.append(m)
            per_lang_metrics[lang_code].append(m)
            continue

        forced_lang = WHISPER_LANG_MAP.get(lang_code) if language_mode == "forced" else None
        last_exc: Exception | None = None
        tx_result = None
        infer_sec = 0.0
        attempts = 0

        for attempt in range(max_retries + 1):
            attempts = attempt + 1
            t0 = time.perf_counter()
            try:
                tx_result = provider.transcribe(
                    audio_path,
                    language=forced_lang,
                    vad_filter=vad_filter,
                    word_timestamps=word_timestamps,
                    beam_size=beam_size,
                    condition_on_previous_text=condition_on_previous_text,
                )
                infer_sec = round(time.perf_counter() - t0, 4)
                last_exc = None
                break
            except Exception as exc:
                infer_sec = round(time.perf_counter() - t0, 4)
                last_exc = exc
                if _classify_error(exc) in ("INSUFFICIENT_MEMORY", "MODEL_NOT_INSTALLED", "UNSUPPORTED_DEVICE", "MISSING_ASSET"):
                    break

        cur_rss = _get_rss_mb()
        if cur_rss is not None and (rss_peak is None or cur_rss > rss_peak):
            rss_peak = cur_rss

        if last_exc is not None or tx_result is None:
            failed_count += 1
            per_lang_counts[lang_code]["failed"] += 1
            utterances.append(
                {
                    "utterance_id": uid,
                    "language_code": lang_code,
                    "script_code": sample["script_code"],
                    "audio_relpath": sample["audio_relpath"],
                    "audio_sha256": sample["audio_sha256"],
                    "duration_sec": duration_sec,
                    "status": "FAILED",
                    "error_code": _classify_error(last_exc) if last_exc else "INFERENCE_ERROR",
                    "error_message": str(last_exc) if last_exc else "Unknown inference error",
                    "attempts": attempts,
                    "inference_sec": infer_sec,
                    "rtf": None,
                    "raw_reference": raw_ref,
                    "raw_hypothesis": None,
                    "metrics": None,
                }
            )
            continue

        raw_hyp = tx_result.full_text
        utt_metrics = compute_safe_utterance_metrics(
            raw_reference=raw_ref,
            raw_hypothesis=raw_hyp,
            language_code=lang_code,
            policy_version=NORMALIZATION_POLICY_VERSION,
        )
        rtf = round(infer_sec / duration_sec, 4) if duration_sec > 0 else None

        rec = {
            "utterance_id": uid,
            "language_code": lang_code,
            "script_code": sample["script_code"],
            "audio_relpath": sample["audio_relpath"],
            "audio_sha256": sample["audio_sha256"],
            "duration_sec": duration_sec,
            "status": "COMPLETED",
            "attempts": attempts,
            "forced_language": forced_lang,
            "detected_language": tx_result.language,
            "segment_count": len(tx_result.segments),
            "word_count": sum(len(s.words or []) for s in tx_result.segments),
            "inference_sec": infer_sec,
            "rtf": rtf,
            "raw_reference": raw_ref,
            "raw_hypothesis": raw_hyp,
            "metrics": utt_metrics,
            "config_fingerprint_sha256": cfg_fp,
        }
        _append_checkpoint(checkpoint_path, rec)
        utterances.append(rec)

        succeeded_count += 1
        per_lang_counts[lang_code]["succeeded"] += 1
        per_lang_audio_sec[lang_code] += duration_sec
        per_lang_infer_sec[lang_code] += infer_sec
        total_inference_sec += infer_sec
        succeeded_metrics.append(utt_metrics)
        per_lang_metrics[lang_code].append(utt_metrics)

    if succeeded_count == len(samples):
        exec_status = "COMPLETED"
    elif succeeded_count > 0:
        exec_status = "PARTIAL"
    else:
        exec_status = "FAILED"

    asr_prov = build_asr_run_provenance(
        run_id=run_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        split=split,
        manifest_sha256=manifest_sha256,
        provider_type=provider_type,
        model_id=model_id,
        model_revision=model_revision,
        device=device,
        compute_type=compute_type,
        language_mode=language_mode,
        normalization_policy_version=NORMALIZATION_POLICY_VERSION,
        decoding_params=decoding_params,
        execution_status=exec_status,
        created_at_utc=created_at,
        environment=env_info,
    )
    batch_prov = build_batch_run_provenance(
        batch_id=batch_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        split=split,
        manifest_sha256=manifest_sha256,
        total_items=len(samples),
        processed_items=succeeded_count + failed_count,
        succeeded_items=succeeded_count,
        failed_items=failed_count,
        skipped_items=0,
        run_ids=[run_id],
        batch_config={"language_mode": language_mode, "max_retries": max_retries, "resumed_items": resumed_count},
        execution_status=exec_status,
        created_at_utc=created_at,
    )

    per_language_summary: dict[str, Any] = {}
    for lang_code in sorted(per_lang_counts.keys()):
        lang_ms = per_lang_metrics[lang_code]
        micro = compute_safe_corpus_metrics(lang_ms)
        valid_wers = [m["wer"] for m in lang_ms if m["wer"] is not None]
        valid_cers = [m["cer"] for m in lang_ms if m["cer"] is not None]
        lang_audio = round(per_lang_audio_sec[lang_code], 3)
        lang_infer = round(per_lang_infer_sec[lang_code], 4)
        per_language_summary[lang_code] = {
            "total_count": per_lang_counts[lang_code]["total"],
            "succeeded_count": per_lang_counts[lang_code]["succeeded"],
            "failed_count": per_lang_counts[lang_code]["failed"],
            "audio_sec": lang_audio,
            "inference_sec": lang_infer,
            "rtf": round(lang_infer / lang_audio, 4) if lang_audio > 0 else None,
            "micro": micro,
            "macro_wer": round(sum(valid_wers) / len(valid_wers), 6) if valid_wers else None,
            "macro_cer": round(sum(valid_cers) / len(valid_cers), 6) if valid_cers else None,
        }

    succeeded_audio_sec = round(sum(per_lang_audio_sec.values()), 3)
    corpus_micro = compute_safe_corpus_metrics(succeeded_metrics)
    valid_all_wers = [m["wer"] for m in succeeded_metrics if m["wer"] is not None]
    valid_all_cers = [m["cer"] for m in succeeded_metrics if m["cer"] is not None]

    return {
        "execution_status": exec_status,
        "blocker_reason": None,
        "dataset": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "split": split,
            "manifest_sha256": manifest_sha256,
            "license_summary": license_summary,
            "total_samples": len(samples),
            "note": "10-clip smoke corpus validates pipeline & baseline behavior; does not establish population-level quality.",
        },
        "asr_provenance": asr_prov,
        "batch_provenance": batch_prov,
        "timing": {
            "cold_init_sec": cold_init_sec,
            "total_inference_sec": round(total_inference_sec, 4),
            "total_audio_sec": round(total_audio_sec, 3),
            "succeeded_audio_sec": succeeded_audio_sec,
            "corpus_rtf": round(total_inference_sec / succeeded_audio_sec, 4) if succeeded_audio_sec > 0 else None,
        },
        "resources": {
            "rss_before_mb": rss_before,
            "rss_after_init_mb": rss_after_init,
            "rss_peak_mb": rss_peak,
            "vram_mb": "NOT_MEASURED",
            "energy_joules": "NOT_MEASURED",
        },
        "corpus_metrics": {
            "aggregation_method": "micro (total edits / total ref tokens) and macro (unweighted mean of utterance rates)",
            "micro": corpus_micro,
            "macro_wer": round(sum(valid_all_wers) / len(valid_all_wers), 6) if valid_all_wers else None,
            "macro_cer": round(sum(valid_all_cers) / len(valid_all_cers), 6) if valid_all_cers else None,
        },
        "per_language": per_language_summary,
        "utterances": utterances,
    }
