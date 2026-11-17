"""Unit and integration tests for M2 Indic Creator Bench contracts, security, and provenance."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf

from app.ai.evaluation.indic_bench import (
    DATASET_SCHEMA_VERSION,
    ERR_CHECKSUM_MISMATCH,
    ERR_DUPLICATE_SAMPLE,
    ERR_INVALID_LANGUAGE_METADATA,
    ERR_INVALID_MANIFEST,
    ERR_MISSING_ASSET,
    ERR_MISSING_REFERENCE,
    ERR_PATH_ESCAPE,
    ERR_SYMLINK_ESCAPE,
    ERR_UNSUPPORTED_AUDIO_FORMAT,
    ERR_UNSUPPORTED_SCHEMA,
    NORMALIZATION_POLICY_VERSION,
    SAMPLE_SCHEMA_VERSION,
    build_asr_run_provenance,
    build_batch_run_provenance,
    compute_config_fingerprint,
    compute_safe_corpus_metrics,
    compute_safe_utterance_metrics,
    normalize_indic_reference,
    validate_indic_bench_dataset,
    validate_secret_safe,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
TRACKED_SMOKE_DIR = REPO_ROOT / "sample_data" / "indic_creator_bench" / "m2_smoke_10clip"
RUNTIME_SMOKE_DIR = REPO_ROOT / "data" / "indic_creator_bench" / "m2_smoke_10clip"


def _write_wav(path: Path, samplerate: int = 16000, duration_sec: float = 0.5) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(samplerate * duration_sec)
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False, dtype=np.float32)
    wave = 0.1 * np.sin(2.0 * np.pi * 440.0 * t)
    sf.write(str(path), wave, samplerate, format="WAV", subtype="PCM_16")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_sample(
    *,
    utterance_id: str = "sample_hi_01",
    relpath: str = "audio/hi_in/sample_hi_01.wav",
    sha256: str = "0" * 64,
    duration_sec: float = 0.5,
    language_code: str = "hi_in",
    language_name: str = "Hindi",
    script_code: str = "Deva",
    script_name: str = "Devanagari",
    reference_transcript: str = "नमस्ते भारत",
    raw_transcription: str = "नमस्ते भारत",
    reference_status: str = "verified",
) -> dict[str, Any]:
    return {
        "sample_schema_version": SAMPLE_SCHEMA_VERSION,
        "dataset_id": "test_bench_v1",
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
        "attribution_text": "Unit test synthetic fixture",
        "redistribution_status": "local_eval_only",
        "reference_transcript": reference_transcript,
        "raw_transcription": raw_transcription,
        "reference_status": reference_status,
        "reference_normalizer_notes": "Preserved verbatim",
        "code_switch_tags": ["monolingual"],
        "speaker_id": "spk_01",
        "metadata": {},
    }


def _write_dataset(root: Path, records: list[dict[str, Any]], descriptor_overrides: dict[str, Any] | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.jsonl"
    manifest_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
        newline="\n",
    )
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    descriptor: dict[str, Any] = {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "dataset_id": "test_bench_v1",
        "dataset_name": "Unit Test Bench",
        "dataset_version": "1.0.0",
        "split": "smoke",
        "created_at_utc": "2026-11-15T00:00:00Z",
        "description": "Synthetic test dataset fixture",
        "sample_count": len(records),
        "manifest_relpath": "manifest.jsonl",
        "manifest_sha256": manifest_sha,
        "languages": sorted({r["language_code"] for r in records}) or ["hi_in"],
        "scripts": sorted({r["script_code"] for r in records}) or ["Deva"],
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
    if descriptor_overrides:
        descriptor.update(descriptor_overrides)
    (root / "dataset.json").write_text(json.dumps(descriptor, indent=2), encoding="utf-8", newline="\n")
    return root


def test_tracked_10clip_smoke_contracts_and_materialized_corpus():
    report_meta, samples = validate_indic_bench_dataset(TRACKED_SMOKE_DIR, require_audio=False)
    assert report_meta.status == "VALID"
    assert report_meta.total_samples == 10
    assert report_meta.valid_samples == 10
    assert report_meta.language_counts == {"en_us": 2, "hi_in": 2, "kn_in": 2, "ta_in": 2, "te_in": 2}
    assert report_meta.reference_status_counts == {"verified": 10}
    assert len(samples) == 10

    if (RUNTIME_SMOKE_DIR / "audio").is_dir():
        report_full, _ = validate_indic_bench_dataset(RUNTIME_SMOKE_DIR, require_audio=True)
        assert report_full.status == "VALID"
        assert report_full.valid_samples == 10
        assert report_full.invalid_samples == 0

    hinglish_path = REPO_ROOT / "reports" / "asr_eval" / "hinglish_template.json"
    if hinglish_path.is_file():
        hinglish_data = json.loads(hinglish_path.read_text(encoding="utf-8"))
        assert hinglish_data["status"] == "NO_VERIFIED_REFERENCE"
        assert hinglish_data["samples"] == []


def test_real_audio_validation_passes(tmp_path: Path):
    sha = _write_wav(tmp_path / "audio" / "hi_in" / "sample_hi_01.wav")
    _write_dataset(tmp_path, [_make_sample(sha256=sha)])
    report, parsed = validate_indic_bench_dataset(tmp_path, require_audio=True)
    assert report.status == "VALID"
    assert report.valid_samples == 1
    assert len(parsed) == 1


def test_unsupported_schema_versions_rejected(tmp_path: Path):
    sha = _write_wav(tmp_path / "audio" / "hi_in" / "sample_hi_01.wav")
    rec = _make_sample(sha256=sha)
    rec["sample_schema_version"] = "9.9.9"
    _write_dataset(tmp_path, [rec], descriptor_overrides={"dataset_schema_version": "9.9.9"})
    report, _ = validate_indic_bench_dataset(tmp_path, require_audio=True)
    codes = {f.code for f in report.failures}
    assert report.status == "INVALID"
    assert ERR_UNSUPPORTED_SCHEMA in codes


def test_duplicate_sample_id_rejected(tmp_path: Path):
    sha = _write_wav(tmp_path / "audio" / "hi_in" / "sample_hi_01.wav")
    _write_dataset(tmp_path, [_make_sample(sha256=sha), _make_sample(sha256=sha)])
    report, _ = validate_indic_bench_dataset(tmp_path, require_audio=True)
    codes = {f.code for f in report.failures}
    assert report.status == "PARTIAL"
    assert ERR_DUPLICATE_SAMPLE in codes


def test_missing_audio_asset_and_partial_status(tmp_path: Path):
    sha1 = _write_wav(tmp_path / "audio" / "hi_in" / "sample_hi_01.wav")
    rec1 = _make_sample(utterance_id="s1", sha256=sha1)
    rec2 = _make_sample(utterance_id="s2", relpath="audio/hi_in/does_not_exist.wav", sha256=sha1)
    _write_dataset(tmp_path, [rec1, rec2])
    report, _ = validate_indic_bench_dataset(tmp_path, require_audio=True)
    assert report.status == "PARTIAL"
    assert report.valid_samples == 1
    assert report.invalid_samples == 1
    assert any(f.code == ERR_MISSING_ASSET for f in report.failures)


def test_corrupted_sha256_rejected(tmp_path: Path):
    _write_wav(tmp_path / "audio" / "hi_in" / "sample_hi_01.wav")
    rec = _make_sample(sha256="a" * 64)
    _write_dataset(tmp_path, [rec])
    report, _ = validate_indic_bench_dataset(tmp_path, require_audio=True)
    assert report.status == "INVALID"
    assert any(f.code == ERR_CHECKSUM_MISMATCH for f in report.failures)


@pytest.mark.parametrize("bad_relpath", ["../outside.wav", "/etc/passwd", "C:\\Windows\\System32\\x.wav"])
def test_path_traversal_and_absolute_paths_rejected(tmp_path: Path, bad_relpath: str):
    _write_dataset(tmp_path, [_make_sample(relpath=bad_relpath)])
    report, _ = validate_indic_bench_dataset(tmp_path, require_audio=True)
    assert report.status == "INVALID"
    assert any(f.code == ERR_PATH_ESCAPE for f in report.failures)


def test_symlink_escape_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    outside = tmp_path / "outside.wav"
    sha = _write_wav(outside)
    ds_root = tmp_path / "dataset"
    audio_dir = ds_root / "audio" / "hi_in"
    audio_dir.mkdir(parents=True, exist_ok=True)
    link_path = audio_dir / "link.wav"

    used_real_symlink = False
    try:
        os.symlink(outside, link_path)
        used_real_symlink = True
    except OSError:
        # Windows without Developer Mode denies unprivileged symlinks; verify via deterministic stub
        link_path.write_bytes(outside.read_bytes())
        orig_is_symlink = Path.is_symlink

        def fake_is_symlink(self: Path) -> bool:
            if self == link_path:
                return True
            return orig_is_symlink(self)

        monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    _write_dataset(ds_root, [_make_sample(relpath="audio/hi_in/link.wav", sha256=sha)])
    report, _ = validate_indic_bench_dataset(ds_root, require_audio=True)
    assert report.status == "INVALID"
    assert any(f.code == ERR_SYMLINK_ESCAPE for f in report.failures), f"real_symlink={used_real_symlink}"


def test_corrupt_audio_header_rejected(tmp_path: Path):
    bad_wav = tmp_path / "audio" / "hi_in" / "corrupt.wav"
    bad_wav.parent.mkdir(parents=True, exist_ok=True)
    bad_wav.write_bytes(b"NOT_A_REAL_AUDIO_FILE")
    sha = hashlib.sha256(bad_wav.read_bytes()).hexdigest()
    _write_dataset(tmp_path, [_make_sample(relpath="audio/hi_in/corrupt.wav", sha256=sha)])
    report, _ = validate_indic_bench_dataset(tmp_path, require_audio=True)
    assert report.status == "INVALID"
    assert any(f.code == ERR_UNSUPPORTED_AUDIO_FORMAT for f in report.failures)


def test_missing_reference_and_language_script_mismatch_rejected(tmp_path: Path):
    sha1 = _write_wav(tmp_path / "audio" / "hi_in" / "s1.wav")
    sha2 = _write_wav(tmp_path / "audio" / "hi_in" / "s2.wav")
    rec_missing_ref = _make_sample(
        utterance_id="s1",
        relpath="audio/hi_in/s1.wav",
        sha256=sha1,
        reference_transcript="   ",
        raw_transcription="",
        reference_status="verified",
    )
    rec_bad_script = _make_sample(
        utterance_id="s2",
        relpath="audio/hi_in/s2.wav",
        sha256=sha2,
        language_code="hi_in",
        language_name="Hindi",
        script_code="Taml",
        script_name="Tamil",
        reference_transcript="Latin only text",
        raw_transcription="Latin only text",
    )
    _write_dataset(tmp_path, [rec_missing_ref, rec_bad_script])
    report, _ = validate_indic_bench_dataset(tmp_path, require_audio=True)
    codes = {f.code for f in report.failures}
    assert ERR_MISSING_REFERENCE in codes
    assert ERR_INVALID_LANGUAGE_METADATA in codes


def test_indic_unicode_preservation_and_safe_wer_cer():
    # Hindi with nukta (ज़), matras, virama (प्रौद्योगिकी), Kannada, Tamil, Telugu with ZWNJ (\u200c) & ZWJ (\u200d)
    samples = [
        ("hi_in", "ज़िंदगी और प्रौद्योगिकी।", "ज़िंदगी और प्रौद्योगिकी"),
        ("kn_in", "ಬೆಂಗಳೂರು ಕನ್ನಡ, ನಮಸ್ಕಾರ!", "ಬೆಂಗಳೂರು ಕನ್ನಡ ನಮಸ್ಕಾರ"),
        ("ta_in", "தமிழ் சென்னை.", "தமிழ் சென்னை"),
        ("te_in", "వీడియో గేమ్స్\u200cలో ఆటగాళ్లు", "వీడియో గేమ్స్\u200cలో ఆటగాళ్లు"),
        ("hi_in", "क\u094d\u200dष", "क\u094d\u200dष"),
    ]
    for lang, raw_text, expected_norm in samples:
        normalized = normalize_indic_reference(raw_text, lang)
        assert normalized == expected_norm
        assert "\u200c" in normalized if "\u200c" in expected_norm else True
        assert "\u200d" in normalized if "\u200d" in expected_norm else True

    # Ensure raw_transcription is preserved untouched in utterance metrics
    te_raw = "వీడియో గేమ్స్\u200cలో."
    m_te = compute_safe_utterance_metrics(te_raw, "వీడియో గేమ్స్\u200cలో", "te_in")
    assert m_te["raw_reference"] == te_raw
    assert "\u200c" in m_te["normalized_reference"]
    assert m_te["wer"] == 0.0
    assert m_te["cer"] == 0.0

    # Empty reference edge cases never crash with ZeroDivisionError
    m_empty_hyp = compute_safe_utterance_metrics("", "hello", "en_us")
    assert m_empty_hyp["empty_reference"] is True
    assert m_empty_hyp["wer"] is None
    assert m_empty_hyp["cer"] is None

    m_both_empty = compute_safe_utterance_metrics("", "", "en_us")
    assert m_both_empty["wer"] == 0.0
    assert m_both_empty["cer"] == 0.0

    corpus = compute_safe_corpus_metrics([m_te, m_empty_hyp])
    assert corpus["total_ref_words"] == 2
    assert corpus["corpus_wer"] is not None


def test_provenance_determinism_and_secret_rejection():
    prov_a = build_asr_run_provenance(
        run_id="run-a",
        dataset_id="indic_creator_bench_m2_smoke",
        dataset_version="1.0.0",
        split="smoke",
        manifest_sha256="b" * 64,
        provider_type="faster_whisper",
        model_id="faster-whisper-small",
        model_revision="local_pinned",
        created_at_utc="2026-11-15T00:00:00Z",
    )
    prov_b = build_asr_run_provenance(
        run_id="run-b",
        dataset_id="indic_creator_bench_m2_smoke",
        dataset_version="1.0.0",
        split="smoke",
        manifest_sha256="b" * 64,
        provider_type="faster_whisper",
        model_id="faster-whisper-small",
        model_revision="local_pinned",
        created_at_utc="2026-11-15T01:00:00Z",
    )
    assert prov_a["config_fingerprint_sha256"] == prov_b["config_fingerprint_sha256"]
    assert prov_a["secret_safe_verified"] is True

    batch = build_batch_run_provenance(
        batch_id="batch-1",
        dataset_id="indic_creator_bench_m2_smoke",
        dataset_version="1.0.0",
        split="smoke",
        manifest_sha256="b" * 64,
        total_items=10,
        processed_items=0,
        succeeded_items=0,
        failed_items=0,
        skipped_items=10,
        run_ids=["run-a"],
        batch_config={"validation_only": True},
    )
    assert batch["execution_status"] == "NOT_RUN"
    assert batch["secret_safe_verified"] is True

    with pytest.raises(ValueError, match="Secret"):
        compute_config_fingerprint({"openai_api_key": "12345"})
    with pytest.raises(ValueError, match="Secret"):
        validate_secret_safe({"headers": "Bearer sk-1234567890abcdef"})
    with pytest.raises(ValueError, match="Secret"):
        validate_secret_safe({"nested": {"value": "sk-proj123456789012345"}})
