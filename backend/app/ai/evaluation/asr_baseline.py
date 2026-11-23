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
import threading
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


def _get_os_peak_wset_mb() -> float | None:
    """Read OS process peak working set (Windows peak_wset or POSIX ru_maxrss)."""
    try:
        import psutil

        mi = psutil.Process().memory_info()
        peak_wset = getattr(mi, "peak_wset", None)
        if peak_wset is not None:
            return round(peak_wset / (1024.0 * 1024.0), 2)
    except Exception:
        pass
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        divisor = 1024.0 * 1024.0 if sys.platform == "darwin" else 1024.0
        return round(usage / divisor, 2)
    except Exception:
        return None


class _MemorySampler:
    """Background daemon sampler for single-process RSS high-water mark."""

    def __init__(self, interval_ms: int = 50) -> None:
        self.interval_ms = interval_ms
        self.sampled_max_rss_mb: float | None = None
        self.sample_count = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _poll(self) -> None:
        rss = _get_rss_mb()
        if rss is not None:
            self.sample_count += 1
            if self.sampled_max_rss_mb is None or rss > self.sampled_max_rss_mb:
                self.sampled_max_rss_mb = rss

    def _run(self) -> None:
        interval_sec = self.interval_ms / 1000.0
        while not self._stop.is_set():
            self._poll()
            self._stop.wait(interval_sec)

    def start(self) -> None:
        self._poll()
        self._thread = threading.Thread(target=self._run, name="asr-rss-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._poll()


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
    if "unsupported_language" in msg:
        return "UNSUPPORTED_LANGUAGE"
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


def _load_checkpoint(
    checkpoint_path: Path | None,
    config_fingerprint: str,
    *,
    manifest_sha256: str,
    model_id: str,
    model_revision: str,
) -> dict[str, dict[str, Any]]:
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
            and obj.get("manifest_sha256") == manifest_sha256
            and obj.get("model_id") == model_id
            and obj.get("model_revision") == model_revision
            and obj.get("status") == "COMPLETED"
            and isinstance(obj.get("utterance_id"), str)
        ):
            loaded[obj["utterance_id"]] = obj
    return loaded


def _assess_utterance_timing(segments: list[Any], duration_sec: float) -> dict[str, Any]:
    """Validate segment & word timing boundaries independently of transcription accuracy."""
    if not segments:
        return {
            "status": "no_segments",
            "segment_timing_valid": True,
            "word_timing_present": False,
            "word_timing_valid": None,
            "segment_count": 0,
            "word_count": 0,
        }

    max_end = max(duration_sec, 0.0) + 0.5
    seg_valid = True
    prev_start = -0.001
    word_count = 0
    word_valid = True

    for seg in segments:
        start = float(getattr(seg, "start_time", -1.0))
        end = float(getattr(seg, "end_time", -1.0))
        if start < -0.001 or end <= start or start + 0.001 < prev_start or end > max_end:
            seg_valid = False
        prev_start = start

        words = getattr(seg, "words", None) or []
        if words:
            prev_w_start = -0.001
            for w in words:
                word_count += 1
                ws = float(w.get("start", -1.0))
                we = float(w.get("end", -1.0))
                if ws < -0.001 or we < ws or ws + 0.001 < prev_w_start or we > max_end:
                    word_valid = False
                prev_w_start = ws

    has_words = word_count > 0
    if not seg_valid or (has_words and not word_valid):
        status = "invalid_timing"
    elif has_words:
        status = "word_level_valid"
    else:
        status = "segment_only_valid"

    return {
        "status": status,
        "segment_timing_valid": seg_valid,
        "word_timing_present": has_words,
        "word_timing_valid": word_valid if has_words else None,
        "segment_count": len(segments),
        "word_count": word_count,
    }


def _summarize_timing_validity(utterances: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [u for u in utterances if u.get("status") == "COMPLETED"]
    valid_seg = 0
    word_level = 0
    invalid = 0
    no_segments = 0
    for u in completed:
        tv = u.get("timing_validity") or {}
        st = tv.get("status")
        if st == "word_level_valid":
            valid_seg += 1
            word_level += 1
        elif st == "segment_only_valid":
            valid_seg += 1
        elif st == "no_segments":
            no_segments += 1
        else:
            invalid += 1

    if not completed:
        overall = "not_evaluated"
    elif invalid > 0:
        overall = "invalid_timing"
    elif valid_seg == 0:
        overall = "no_segments"
    elif word_level == valid_seg:
        overall = "word_level_valid"
    else:
        overall = "segment_only_valid"

    return {
        "status": overall,
        "evaluated_count": len(completed),
        "valid_segment_timing_count": valid_seg,
        "word_level_valid_count": word_level,
        "no_segments_count": no_segments,
        "invalid_timing_count": invalid,
    }


def evaluate_multilingual_language_decision(
    *,
    language_code: str,
    baseline_micro_wer: float | None,
    candidate_micro_wer: float | None,
    empty_count: int,
    total_count: int,
    failed_count: int,
    rtf: float | None,
    measured_memory_mb: float | None,
    timing_valid: bool,
    max_rtf: float = 6.0,
    max_memory_mb: float = 3500.0,
) -> dict[str, Any]:
    """Apply pre-registered M4 v2.0 per-language acceptance gates."""
    empty_rate = (empty_count / float(total_count)) if total_count > 0 else 1.0
    reliability_ok = (failed_count == 0) and (total_count > 0) and (empty_rate <= 0.10) and timing_valid
    memory_measured = measured_memory_mb is not None
    budget_ok = memory_measured and (measured_memory_mb <= max_memory_mb) and (rtf is not None and rtf <= max_rtf)

    non_regression_passed: bool | None = None
    absolute_usability_passed: bool | None = None
    accuracy_passed = False

    if candidate_micro_wer is not None:
        if language_code in ("kn_in", "te_in"):
            drop_ok = baseline_micro_wer is not None and (baseline_micro_wer - candidate_micro_wer) >= 0.35
            abs_ok = candidate_micro_wer <= 0.65
            accuracy_passed = drop_ok and abs_ok
            absolute_usability_passed = abs_ok
        elif language_code == "en_us":
            abs_ok = candidate_micro_wer <= 0.15
            accuracy_passed = abs_ok
            absolute_usability_passed = abs_ok
        elif language_code == "hi_in":
            non_regression_passed = baseline_micro_wer is not None and candidate_micro_wer <= (baseline_micro_wer + 0.03)
            absolute_usability_passed = candidate_micro_wer <= 0.35
            accuracy_passed = bool(non_regression_passed and absolute_usability_passed)
        elif language_code == "ta_in":
            non_regression_passed = baseline_micro_wer is not None and candidate_micro_wer <= (baseline_micro_wer + 0.03)
            absolute_usability_passed = candidate_micro_wer <= 0.40
            accuracy_passed = bool(non_regression_passed and absolute_usability_passed)

    if not memory_measured:
        decision = "HOLD_MEMORY_UNMEASURED"
    elif not reliability_ok:
        decision = "KEEP_DEFAULT_FAIL"
    elif accuracy_passed and budget_ok:
        decision = "PASS_EXPERIMENTAL"
    elif accuracy_passed and not budget_ok:
        decision = "EXPERIMENTAL_OVER_BUDGET"
    elif language_code in ("hi_in", "ta_in") and non_regression_passed and not absolute_usability_passed and budget_ok:
        decision = "NON_REGRESSION_ONLY_BELOW_USABILITY_TARGET"
    else:
        decision = "KEEP_DEFAULT_FAIL"

    return {
        "language_code": language_code,
        "decision": decision,
        "reliability_passed": reliability_ok,
        "memory_measured": memory_measured,
        "budget_passed": budget_ok,
        "accuracy_passed": accuracy_passed,
        "non_regression_passed": non_regression_passed,
        "absolute_usability_passed": absolute_usability_passed,
        "empty_rate": round(empty_rate, 6),
    }


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
    cpu_threads: int = 0,
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
        "cpu_threads": int(cpu_threads),
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
    cached_records = _load_checkpoint(
        checkpoint_path,
        cfg_fp,
        manifest_sha256=manifest_sha256,
        model_id=model_id,
        model_revision=model_revision,
    )

    rss_before = _get_rss_mb()
    rss_peak = rss_before
    sampler = _MemorySampler(interval_ms=50)
    sampler.start()

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

    try:
        # Measure cold model initialization separately from per-clip inference
        cold_init_start = time.perf_counter()
        if hasattr(provider, "_get_or_load_model"):
            provider._get_or_load_model()  # type: ignore[attr-defined]
        cold_init_sec = round(time.perf_counter() - cold_init_start, 4)
        rss_after_init = _get_rss_mb()
        if rss_after_init is not None and (rss_peak is None or rss_after_init > rss_peak):
            rss_peak = rss_after_init

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
                    if _classify_error(exc) in (
                        "UNSUPPORTED_LANGUAGE",
                        "INSUFFICIENT_MEMORY",
                        "MODEL_NOT_INSTALLED",
                        "UNSUPPORTED_DEVICE",
                        "MISSING_ASSET",
                    ):
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
            timing_val = _assess_utterance_timing(tx_result.segments, duration_sec)

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
                "word_count": timing_val["word_count"],
                "timing_validity": timing_val,
                "inference_sec": infer_sec,
                "rtf": rtf,
                "raw_reference": raw_ref,
                "raw_hypothesis": raw_hyp,
                "metrics": utt_metrics,
                "config_fingerprint_sha256": cfg_fp,
                "manifest_sha256": manifest_sha256,
                "model_id": model_id,
                "model_revision": model_revision,
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
    finally:
        sampler.stop()

    if sampler.sampled_max_rss_mb is not None and (rss_peak is None or sampler.sampled_max_rss_mb > rss_peak):
        rss_peak = sampler.sampled_max_rss_mb
    os_peak_wset_mb = _get_os_peak_wset_mb()

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
    lid_confusion: dict[str, dict[str, int]] = {}
    lid_total = 0
    lid_correct = 0

    for lang_code in sorted(per_lang_counts.keys()):
        lang_ms = per_lang_metrics[lang_code]
        lang_utts = [u for u in utterances if u.get("language_code") == lang_code]
        micro = compute_safe_corpus_metrics(lang_ms)
        valid_wers = [m["wer"] for m in lang_ms if m["wer"] is not None]
        valid_cers = [m["cer"] for m in lang_ms if m["cer"] is not None]
        lang_audio = round(per_lang_audio_sec[lang_code], 3)
        lang_infer = round(per_lang_infer_sec[lang_code], 4)
        lang_timing = _summarize_timing_validity(lang_utts)

        expected_whisper_lang = WHISPER_LANG_MAP.get(lang_code, lang_code.split("_")[0])
        if language_mode == "auto":
            counts_for_lang: dict[str, int] = defaultdict(int)
            for u in lang_utts:
                if u.get("status") != "COMPLETED":
                    continue
                det = str(u.get("detected_language") or "unknown").strip().lower()
                counts_for_lang[det] += 1
                lid_total += 1
                if det == expected_whisper_lang:
                    lid_correct += 1
            lid_confusion[lang_code] = dict(sorted(counts_for_lang.items()))

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
            "timing_validity": lang_timing,
        }

    corpus_timing_validity = _summarize_timing_validity(utterances)
    language_id_summary: dict[str, Any] = (
        {
            "enabled": True,
            "total_evaluated": lid_total,
            "correct_count": lid_correct,
            "accuracy": round(lid_correct / float(lid_total), 6) if lid_total > 0 else None,
            "confusion_matrix": lid_confusion,
        }
        if language_mode == "auto"
        else {
            "enabled": False,
            "total_evaluated": 0,
            "correct_count": 0,
            "accuracy": None,
            "confusion_matrix": {},
        }
    )

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
            "note": f"{len(samples)}-clip {split} partition ({dataset_id}); does not establish population-level quality.",
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
        "timing_validity": corpus_timing_validity,
        "language_id_summary": language_id_summary,
        "resources": {
            "rss_before_mb": rss_before,
            "rss_after_init_mb": rss_after_init,
            "rss_peak_mb": rss_peak,
            "rss_sampled_max_mb": sampler.sampled_max_rss_mb,
            "os_peak_wset_mb": os_peak_wset_mb,
            "rss_sample_count": sampler.sample_count,
            "rss_sampling_interval_ms": sampler.interval_ms,
            "memory_measurement_scope": "single_process_no_children",
            "vram_mb": "NOT_MEASURED",
            "energy_joules": "NOT_MEASURED",
        },
        "corpus_metrics": {
            "aggregation_method": "micro (total edits / total ref tokens) and macro (unweighted mean of utterance rates)",
            "coverage_complete": failed_count == 0,
            "failed_items": failed_count,
            "micro": corpus_micro,
            "macro_wer": round(sum(valid_all_wers) / len(valid_all_wers), 6) if valid_all_wers else None,
            "macro_cer": round(sum(valid_all_cers) / len(valid_all_cers), 6) if valid_all_cers else None,
        },
        "per_language": per_language_summary,
        "utterances": utterances,
    }
