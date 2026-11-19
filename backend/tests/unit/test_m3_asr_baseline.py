"""Unit tests for M3.1 Indic Creator Bench Faster-Whisper baseline runner.

Uses deterministic in-memory provider doubles strictly for unit isolation of
contract, provenance, error-handling, retry, and restartability behavior.
Real ASR inference evidence is produced separately by scripts/run_m3_asr_baseline.py.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any
import wave

import pytest

from app.ai.evaluation.asr_baseline import (
    WHISPER_LANG_MAP,
    run_indic_asr_baseline,
)
from app.ai.evaluation.indic_bench import (
    DATASET_SCHEMA_VERSION,
    NORMALIZATION_POLICY_VERSION,
    SAMPLE_SCHEMA_VERSION,
)
from app.ai.providers.transcription import SegmentResult, TranscriptionResult


def _write_wav(path: Path, samplerate: int = 16000, duration_sec: float = 1.0) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(samplerate * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(3276.7 * math.sin(2.0 * math.pi * 440.0 * (i / samplerate)))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_sample(
    utterance_id: str,
    relpath: str,
    sha256: str,
    language_code: str,
    language_name: str,
    script_code: str,
    script_name: str,
    reference_transcript: str,
    duration_sec: float = 1.0,
) -> dict[str, Any]:
    return {
        "sample_schema_version": SAMPLE_SCHEMA_VERSION,
        "dataset_id": "unit_m3_bench",
        "dataset_version": "1.0.0",
        "split": "smoke",
        "utterance_id": utterance_id,
        "audio_relpath": relpath,
        "audio_sha256": sha256,
        "audio_format": "wav",
        "duration_sec": duration_sec,
        "sample_rate_hz": 16000,
        "channels": 1,
        "language_code": language_code,
        "language_name": language_name,
        "script_code": script_code,
        "script_name": script_name,
        "domain": "read_speech",
        "source_dataset": "unit_test_fixture",
        "source_dataset_version": "1.0.0",
        "source_sample_id": utterance_id,
        "source_url_or_origin": "local://unit-test",
        "license_spdx_or_name": "CC-BY-4.0",
        "attribution_text": "Unit test fixture",
        "redistribution_status": "local_eval_only",
        "reference_transcript": reference_transcript,
        "raw_transcription": reference_transcript,
        "reference_status": "verified",
        "reference_normalizer_notes": "Preserved verbatim",
        "code_switch_tags": ["monolingual"],
        "speaker_id": "spk_01",
        "metadata": {},
    }


def _write_dataset(root: Path, records: list[dict[str, Any]]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.jsonl"
    manifest_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
        newline="\n",
    )
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    descriptor = {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "dataset_id": "unit_m3_bench",
        "dataset_name": "Unit M3 Bench",
        "dataset_version": "1.0.0",
        "split": "smoke",
        "created_at_utc": "2026-11-19T00:00:00Z",
        "description": "Synthetic test dataset fixture",
        "sample_count": len(records),
        "manifest_relpath": "manifest.jsonl",
        "manifest_sha256": manifest_sha,
        "languages": sorted({r["language_code"] for r in records}),
        "scripts": sorted({r["script_code"] for r in records}),
        "source_datasets": [
            {
                "source_dataset": "unit_test_fixture",
                "source_dataset_version": "1.0.0",
                "license_spdx_or_name": "CC-BY-4.0",
                "source_url_or_origin": "local://unit-test",
                "attribution_text": "Unit test fixture",
            }
        ],
        "license_summary": "CC-BY-4.0",
        "attribution_required": True,
        "redistribution_policy": "local_eval_only",
        "normalization_policy_version": NORMALIZATION_POLICY_VERSION,
    }
    (root / "dataset.json").write_text(json.dumps(descriptor, indent=2), encoding="utf-8", newline="\n")
    return root


class _StubASRProvider:
    """Deterministic test double for unit isolation (not real inference)."""

    def __init__(
        self,
        hypotheses: dict[str, str],
        fail_on: dict[str, Exception] | None = None,
        available: bool = True,
    ) -> None:
        self.hypotheses = hypotheses
        self.fail_on = fail_on or {}
        self._available = available
        self.calls: list[tuple[str, str | None]] = []

    def is_available(self) -> bool:
        return self._available

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        vad_filter: bool = False,
        word_timestamps: bool = True,
        beam_size: int = 5,
        min_silence_duration_ms: int = 500,
        condition_on_previous_text: bool = False,
    ) -> TranscriptionResult:
        stem = audio_path.stem
        self.calls.append((stem, language))
        if stem in self.fail_on:
            raise self.fail_on[stem]
        text = self.hypotheses.get(stem, "")
        return TranscriptionResult(
            language=language or "en",
            model_name="stub-whisper-unit",
            full_text=text,
            segments=[
                SegmentResult(
                    start_time=0.0,
                    end_time=1.0,
                    text=text,
                    confidence=-0.12,
                    avg_logprob=-0.12,
                    detected_language=language or "en",
                    forced_language=language,
                )
            ],
            model_id="stub-whisper-unit",
            model_revision="unit_test",
            device="cpu",
            compute_type="int8",
            parameter_hash="0123456789abcdef",
        )


def test_m3_runner_rejects_tampered_audio_before_asr(tmp_path: Path):
    wav_path = tmp_path / "audio" / "en_us" / "clip_en_1.wav"
    _write_wav(wav_path)
    _write_dataset(
        tmp_path,
        [
            _make_sample(
                "clip_en_1",
                "audio/en_us/clip_en_1.wav",
                "f" * 64,  # corrupted sha256
                "en_us",
                "English (US)",
                "Latn",
                "Latin",
                "Hello world.",
            )
        ],
    )
    provider = _StubASRProvider({"clip_en_1": "Hello world."})
    with pytest.raises(ValueError, match="Dataset validation failed"):
        run_indic_asr_baseline(
            tmp_path,
            provider,
            model_id="stub-whisper-unit",
            model_revision="unit_test",
        )
    assert provider.calls == []


def test_m3_runner_computes_per_language_metrics_provenance_and_rtf(tmp_path: Path):
    sha_en = _write_wav(tmp_path / "audio" / "en_us" / "clip_en_1.wav", duration_sec=1.0)
    sha_hi = _write_wav(tmp_path / "audio" / "hi_in" / "clip_hi_1.wav", duration_sec=2.0)
    _write_dataset(
        tmp_path,
        [
            _make_sample(
                "clip_en_1",
                "audio/en_us/clip_en_1.wav",
                sha_en,
                "en_us",
                "English (US)",
                "Latn",
                "Latin",
                "Hello world.",
                duration_sec=1.0,
            ),
            _make_sample(
                "clip_hi_1",
                "audio/hi_in/clip_hi_1.wav",
                sha_hi,
                "hi_in",
                "Hindi",
                "Deva",
                "Devanagari",
                "नमस्ते भारत।",
                duration_sec=2.0,
            ),
        ],
    )
    provider = _StubASRProvider(
        {
            "clip_en_1": "Hello world",
            "clip_hi_1": "नमस्ते दुनिया",
        }
    )
    result = run_indic_asr_baseline(
        tmp_path,
        provider,
        model_id="stub-whisper-unit",
        model_revision="unit_test",
        language_mode="forced",
    )

    assert provider.calls == [("clip_en_1", WHISPER_LANG_MAP["en_us"]), ("clip_hi_1", WHISPER_LANG_MAP["hi_in"])]
    assert result["execution_status"] == "COMPLETED"
    assert result["asr_provenance"]["execution_status"] == "COMPLETED"
    assert result["batch_provenance"]["succeeded_items"] == 2
    assert result["batch_provenance"]["failed_items"] == 0
    assert result["resources"]["energy_joules"] == "NOT_MEASURED"
    assert result["resources"]["vram_mb"] == "NOT_MEASURED"
    assert result["timing"]["cold_init_sec"] >= 0.0
    assert result["timing"]["total_audio_sec"] == 3.0
    assert result["timing"]["corpus_rtf"] >= 0.0

    # Per-language metrics
    assert result["per_language"]["en_us"]["micro"]["corpus_wer"] == 0.0
    assert result["per_language"]["hi_in"]["micro"]["corpus_wer"] == 0.5
    assert result["per_language"]["hi_in"]["macro_wer"] == 0.5

    # Raw reference and raw hypothesis preserved separately
    hi_item = next(u for u in result["utterances"] if u["utterance_id"] == "clip_hi_1")
    assert hi_item["raw_reference"] == "नमस्ते भारत।"
    assert hi_item["raw_hypothesis"] == "नमस्ते दुनिया"
    assert hi_item["status"] == "COMPLETED"


def test_m3_runner_records_failures_and_absent_weights_honestly(tmp_path: Path):
    sha_1 = _write_wav(tmp_path / "audio" / "en_us" / "ok_1.wav", duration_sec=1.0)
    sha_2 = _write_wav(tmp_path / "audio" / "en_us" / "oom_2.wav", duration_sec=1.0)
    _write_dataset(
        tmp_path,
        [
            _make_sample("ok_1", "audio/en_us/ok_1.wav", sha_1, "en_us", "English (US)", "Latn", "Latin", "One two"),
            _make_sample("oom_2", "audio/en_us/oom_2.wav", sha_2, "en_us", "English (US)", "Latn", "Latin", "Three four"),
        ],
    )

    # Absent weights -> BLOCKED without fabricating results
    missing_provider = _StubASRProvider({}, available=False)
    blocked = run_indic_asr_baseline(
        tmp_path,
        missing_provider,
        model_id="faster-whisper-small",
        model_revision="local_pinned",
    )
    assert blocked["execution_status"] == "BLOCKED"
    assert blocked["blocker_reason"] == "MODEL_NOT_INSTALLED"
    assert blocked["batch_provenance"]["processed_items"] == 0

    # Partial failure -> records failed sample explicitly, never drops it
    flaky_provider = _StubASRProvider(
        {"ok_1": "One two"},
        fail_on={"oom_2": MemoryError("Insufficient RAM for decode")},
    )
    partial = run_indic_asr_baseline(
        tmp_path,
        flaky_provider,
        model_id="stub-whisper-unit",
        model_revision="unit_test",
    )
    assert partial["execution_status"] == "PARTIAL"
    assert partial["batch_provenance"]["succeeded_items"] == 1
    assert partial["batch_provenance"]["failed_items"] == 1
    assert partial["per_language"]["en_us"]["failed_count"] == 1
    failed_entry = next(u for u in partial["utterances"] if u["utterance_id"] == "oom_2")
    assert failed_entry["status"] == "FAILED"
    assert failed_entry["error_code"] == "INSUFFICIENT_MEMORY"


def test_m3_runner_checkpoint_restartability(tmp_path: Path):
    sha_1 = _write_wav(tmp_path / "audio" / "en_us" / "c1.wav", duration_sec=1.0)
    sha_2 = _write_wav(tmp_path / "audio" / "en_us" / "c2.wav", duration_sec=1.0)
    _write_dataset(
        tmp_path,
        [
            _make_sample("c1", "audio/en_us/c1.wav", sha_1, "en_us", "English (US)", "Latn", "Latin", "Alpha beta"),
            _make_sample("c2", "audio/en_us/c2.wav", sha_2, "en_us", "English (US)", "Latn", "Latin", "Gamma delta"),
        ],
    )
    ckpt = tmp_path / "m3_ckpt.jsonl"

    # First run: c1 succeeds, c2 fails
    p1 = _StubASRProvider({"c1": "Alpha beta"}, fail_on={"c2": RuntimeError("transient error")})
    r1 = run_indic_asr_baseline(
        tmp_path,
        p1,
        model_id="stub-whisper-unit",
        model_revision="unit_test",
        checkpoint_path=ckpt,
    )
    assert r1["execution_status"] == "PARTIAL"
    assert len(p1.calls) == 2

    # Second run: resumes from checkpoint, only runs c2!
    p2 = _StubASRProvider({"c1": "SHOULD_NOT_RUN", "c2": "Gamma delta"})
    r2 = run_indic_asr_baseline(
        tmp_path,
        p2,
        model_id="stub-whisper-unit",
        model_revision="unit_test",
        checkpoint_path=ckpt,
    )
    assert r2["execution_status"] == "COMPLETED"
    assert p2.calls == [("c2", "en")]
    assert r2["batch_provenance"]["succeeded_items"] == 2
