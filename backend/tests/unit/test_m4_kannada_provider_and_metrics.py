"""M4 Kannada specialist capability, S/D/I metrics, memory sampling, and split-disjointness tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import wave

import pytest

from app.ai.evaluation.asr_baseline import run_indic_asr_baseline
from app.ai.evaluation.indic_bench import (
    DATASET_SCHEMA_VERSION,
    NORMALIZATION_POLICY_VERSION,
    SAMPLE_SCHEMA_VERSION,
    compute_safe_corpus_metrics,
    compute_safe_utterance_metrics,
    normalize_indic_reference,
)
from app.ai.providers.transcription import FasterWhisperProvider, SegmentResult, TranscriptionResult
from app.core.security import compute_sha256

REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_tiny_wav(path: Path, duration_sec: float = 0.2, rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"\x00\x00" * int(rate * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)


def _make_mini_dataset(tmp_path: Path, lang_code: str = "kn_in") -> Path:
    ds_root = tmp_path / "mini_ds"
    audio_rel = f"audio/{lang_code}/clip_1.wav"
    audio_path = ds_root / audio_rel
    _write_tiny_wav(audio_path, duration_sec=0.25)
    sha = compute_sha256(audio_path)

    if lang_code == "kn_in":
        lang_name, script_code, script_name, ref = "Kannada", "Knda", "Kannada", "ನಮಸ್ಕಾರ ಕರ್ನಾಟಕ"
    else:
        lang_name, script_code, script_name, ref = "English (US)", "Latn", "Latin", "hello world"

    rec = {
        "sample_schema_version": SAMPLE_SCHEMA_VERSION,
        "dataset_id": "m4_unit_mini",
        "dataset_version": "1.0.0",
        "split": "dev",
        "utterance_id": f"unit_{lang_code}_1",
        "audio_relpath": audio_rel,
        "audio_sha256": sha,
        "audio_format": "wav",
        "duration_sec": 0.25,
        "sample_rate_hz": 16000,
        "channels": 1,
        "language_code": lang_code,
        "language_name": lang_name,
        "script_code": script_code,
        "script_name": script_name,
        "domain": "read_speech_multilingual",
        "source_dataset": "unit_synthetic",
        "source_dataset_version": "1.0.0",
        "source_sample_id": "1",
        "source_url_or_origin": "unit://local",
        "license_spdx_or_name": "CC-BY-4.0",
        "attribution_text": "Synthetic unit test clip.",
        "redistribution_status": "local_eval_only",
        "reference_transcript": ref,
        "raw_transcription": ref,
        "reference_status": "verified",
        "reference_normalizer_notes": "Synthetic unit test reference.",
        "code_switch_tags": ["monolingual"],
        "speaker_id": "unit_speaker_1",
        "metadata": {},
    }
    manifest_text = json.dumps(rec, ensure_ascii=False) + "\n"
    (ds_root / "manifest.jsonl").write_text(manifest_text, encoding="utf-8", newline="\n")
    manifest_sha = compute_sha256(ds_root / "manifest.jsonl")
    descriptor = {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "dataset_id": "m4_unit_mini",
        "dataset_name": "Mini Unit Split",
        "dataset_version": "1.0.0",
        "split": "dev",
        "created_at_utc": "2026-11-19T00:00:00Z",
        "description": "Unit test mini dataset",
        "sample_count": 1,
        "manifest_relpath": "manifest.jsonl",
        "manifest_sha256": manifest_sha,
        "languages": [lang_code],
        "scripts": [script_code],
        "source_datasets": [
            {
                "source_dataset": "unit_synthetic",
                "source_dataset_version": "1.0.0",
                "license_spdx_or_name": "CC-BY-4.0",
                "source_url_or_origin": "unit://local",
                "attribution_text": "Synthetic unit test clip.",
            }
        ],
        "license_summary": "CC-BY-4.0",
        "attribution_required": True,
        "redistribution_policy": "local_eval_only",
        "normalization_policy_version": NORMALIZATION_POLICY_VERSION,
    }
    (ds_root / "dataset.json").write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8", newline="\n")
    return ds_root


def test_monolingual_provider_rejects_unsupported_language_before_loading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = tmp_path / "sample.wav"
    _write_tiny_wav(wav)

    provider = FasterWhisperProvider(
        model_size_or_path=str(tmp_path / "nonexistent_model"),
        model_id="vasista22/whisper-kannada-small",
        supported_languages={"kn"},
    )

    load_called = False

    def _forbid_load() -> None:
        nonlocal load_called
        load_called = True
        raise AssertionError("Model loader must not be invoked for unsupported language")

    monkeypatch.setattr(provider, "_get_or_load_model", _forbid_load)

    for bad_lang in (None, "", "en", "te", "hi"):
        with pytest.raises(ValueError, match="UNSUPPORTED_LANGUAGE"):
            provider.transcribe(wav, language=bad_lang)
    assert load_called is False


def test_provider_never_fabricates_word_timestamps_when_unsupported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = tmp_path / "sample.wav"
    _write_tiny_wav(wav)

    captured_kwargs: dict[str, object] = {}

    class _FakeModel:
        def transcribe(self, path: str, **kwargs: object):
            captured_kwargs.update(kwargs)
            fake_word = SimpleNamespace(word="ನಮಸ್ಕಾರ", start=0.0, end=0.2, probability=0.9)
            fake_seg = SimpleNamespace(
                start=0.0,
                end=0.25,
                text="ನಮಸ್ಕಾರ",
                avg_logprob=-0.2,
                no_speech_prob=0.01,
                compression_ratio=1.0,
                temperature=0.0,
                words=[fake_word],  # Even if backend returned words, must be dropped when unsupported
            )
            fake_info = SimpleNamespace(language="kn", language_probability=0.99)
            return [fake_seg], fake_info

    provider = FasterWhisperProvider(
        model_size_or_path="dummy",
        model_id="vasista22/whisper-kannada-small",
        supported_languages={"kn"},
        supports_word_timestamps=False,
    )
    monkeypatch.setattr(provider, "_get_or_load_model", lambda: _FakeModel())

    res = provider.transcribe(wav, language="kn", word_timestamps=True)
    assert captured_kwargs["word_timestamps"] is False
    assert len(res.segments) == 1
    assert res.segments[0].words is None


def test_missing_local_weights_reports_unavailable_and_explicit_error(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing_ct2_weights"
    provider = FasterWhisperProvider(
        model_size_or_path=str(missing_dir),
        model_id="vasista22/whisper-kannada-small",
        supported_languages={"kn"},
    )
    assert provider.is_available() is False
    with pytest.raises(RuntimeError, match=r"(?i)model_not_installed"):
        provider._get_or_load_model()


def test_sdi_edit_decomposition_and_corpus_aggregation() -> None:
    # ref: a b c d  -> hyp: a x c d e  => 1 sub (b->x), 0 del, 1 ins (e)
    m1 = compute_safe_utterance_metrics("a b c d", "a x c d e", "en_us")
    assert m1["word_edits"] == 2
    assert m1["word_substitutions"] == 1
    assert m1["word_deletions"] == 0
    assert m1["word_insertions"] == 1
    assert m1["empty_hypothesis"] is False

    # Kannada empty hypothesis => all deletions
    m2 = compute_safe_utterance_metrics("ನಮಸ್ಕಾರ ಕರ್ನಾಟಕ ರಾಜ್ಯ", "", "kn_in")
    assert m2["word_edits"] == 3
    assert m2["word_substitutions"] == 0
    assert m2["word_deletions"] == 3
    assert m2["word_insertions"] == 0
    assert m2["empty_hypothesis"] is True

    corpus = compute_safe_corpus_metrics([m1, m2])
    assert corpus["total_word_edits"] == 5
    assert corpus["total_word_substitutions"] == 1
    assert corpus["total_word_deletions"] == 3
    assert corpus["total_word_insertions"] == 1
    assert corpus["empty_hypothesis_count"] == 1
    assert corpus["empty_hypothesis_rate"] == 0.5


def test_baseline_runner_records_unsupported_language_and_memory_scope(tmp_path: Path) -> None:
    ds_root = _make_mini_dataset(tmp_path, lang_code="en_us")

    class _KannadaOnlyStub:
        def __init__(self) -> None:
            self.calls = 0

        def is_available(self) -> bool:
            return True

        def transcribe(self, audio_path: Path, language: str | None = None, **kwargs: object) -> TranscriptionResult:
            self.calls += 1
            if language != "kn":
                raise ValueError(f"UNSUPPORTED_LANGUAGE: only kn supported, got '{language}'")
            return TranscriptionResult(
                language="kn",
                model_name="stub-kn",
                full_text="ನಮಸ್ಕಾರ",
                segments=[SegmentResult(start_time=0.0, end_time=0.2, text="ನಮಸ್ಕಾರ", confidence=-0.1)],
            )

    stub = _KannadaOnlyStub()
    report = run_indic_asr_baseline(
        ds_root,
        stub,
        model_id="vasista22/whisper-kannada-small",
        max_retries=2,
        word_timestamps=False,
    )
    # Must fail explicitly with UNSUPPORTED_LANGUAGE without retrying
    assert stub.calls == 1
    assert report["execution_status"] == "FAILED"
    assert report["batch_provenance"]["failed_items"] == 1
    assert report["corpus_metrics"]["coverage_complete"] is False
    assert report["utterances"][0]["error_code"] == "UNSUPPORTED_LANGUAGE"

    # Memory instrumentation metadata must be honest and populated on psutil-enabled env
    res = report["resources"]
    assert res["memory_measurement_scope"] == "single_process_no_children"
    assert res["rss_sampling_interval_ms"] == 50
    assert res["rss_sample_count"] >= 1
    assert res["rss_sampled_max_mb"] is not None
    assert res["os_peak_wset_mb"] is not None


def test_m4_kannada_dev_eval_and_smoke_splits_are_strictly_disjoint() -> None:
    def _load_records(dataset_id: str) -> list[dict]:
        p = REPO_ROOT / "sample_data" / "indic_creator_bench" / dataset_id / "manifest.jsonl"
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]

    smoke_kn = [r for r in _load_records("m2_smoke_10clip") if r["language_code"] == "kn_in"]
    dev_kn = _load_records("m4_kn_dev_10clip")
    eval_kn = _load_records("m4_kn_eval_10clip")

    assert len(dev_kn) == 10
    assert len(eval_kn) == 10

    sets = {
        "smoke": smoke_kn,
        "dev": dev_kn,
        "eval": eval_kn,
    }
    for name_a, recs_a in sets.items():
        for name_b, recs_b in sets.items():
            if name_a >= name_b:
                continue
            ids_a = {r["source_sample_id"] for r in recs_a}
            ids_b = {r["source_sample_id"] for r in recs_b}
            assert ids_a.isdisjoint(ids_b), f"Overlap in source_sample_id between {name_a} and {name_b}"

            shas_a = {r["audio_sha256"] for r in recs_a}
            shas_b = {r["audio_sha256"] for r in recs_b}
            assert shas_a.isdisjoint(shas_b), f"Overlap in audio_sha256 between {name_a} and {name_b}"

            tx_a = {normalize_indic_reference(r["reference_transcript"], "kn_in") for r in recs_a}
            tx_b = {normalize_indic_reference(r["reference_transcript"], "kn_in") for r in recs_b}
            assert tx_a.isdisjoint(tx_b), f"Overlap in normalized text between {name_a} and {name_b}"
