"""M4 multilingual ASR evaluation, timing validity, Auto LID confusion, checkpoint isolation, and pipeline invalidation tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import wave

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.evaluation.asr_baseline import (
    evaluate_multilingual_language_decision,
    run_indic_asr_baseline,
)
from app.ai.evaluation.indic_bench import (
    DATASET_SCHEMA_VERSION,
    NORMALIZATION_POLICY_VERSION,
    SAMPLE_SCHEMA_VERSION,
    normalize_indic_reference,
)
from app.ai.providers.transcription import (
    FasterWhisperProvider,
    SegmentResult,
    TranscriptionResult,
)
from app.core.security import compute_sha256
from app.database.session import Base
from app.models.entities import Artifact, StageRun, Transcript, Video
from app.services.pipeline_orchestrator import (
    STAGE_ASR_TRANSCRIPTION,
    PipelineOrchestrator,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_tiny_wav(path: Path, duration_sec: float = 0.5, rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"\x00\x00" * int(rate * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)


def _make_multilang_mini_dataset(tmp_path: Path) -> Path:
    ds_root = tmp_path / "mini_multi"
    specs = [
        ("en_us", "English (US)", "Latn", "Latin", "hello world"),
        ("kn_in", "Kannada", "Knda", "Kannada", "ನಮಸ್ಕಾರ ಕರ್ನಾಟಕ"),
    ]
    records = []
    for idx, (lang_code, lang_name, script_code, script_name, ref) in enumerate(specs, start=1):
        audio_rel = f"audio/{lang_code}/clip_{idx}.wav"
        audio_path = ds_root / audio_rel
        _write_tiny_wav(audio_path, duration_sec=0.5)
        sha = compute_sha256(audio_path)
        records.append(
            {
                "sample_schema_version": SAMPLE_SCHEMA_VERSION,
                "dataset_id": "m4_unit_multi",
                "dataset_version": "1.0.0",
                "split": "dev",
                "utterance_id": f"unit_{lang_code}_{idx}",
                "audio_relpath": audio_rel,
                "audio_sha256": sha,
                "audio_format": "wav",
                "duration_sec": 0.5,
                "sample_rate_hz": 16000,
                "channels": 1,
                "language_code": lang_code,
                "language_name": lang_name,
                "script_code": script_code,
                "script_name": script_name,
                "domain": "read_speech_multilingual",
                "source_dataset": "unit_synthetic",
                "source_dataset_version": "1.0.0",
                "source_sample_id": str(idx),
                "source_url_or_origin": "unit://local",
                "license_spdx_or_name": "CC-BY-4.0",
                "attribution_text": "Synthetic unit test clip.",
                "redistribution_status": "local_eval_only",
                "reference_transcript": ref,
                "raw_transcription": ref,
                "reference_status": "verified",
                "reference_normalizer_notes": "Synthetic unit test reference.",
                "code_switch_tags": ["monolingual"],
                "speaker_id": f"unit_speaker_{idx}",
                "metadata": {},
            }
        )
    manifest_text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    (ds_root / "manifest.jsonl").write_text(manifest_text, encoding="utf-8", newline="\n")
    manifest_sha = compute_sha256(ds_root / "manifest.jsonl")
    descriptor = {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "dataset_id": "m4_unit_multi",
        "dataset_name": "Mini Multi Unit Split",
        "dataset_version": "1.0.0",
        "split": "dev",
        "created_at_utc": "2026-11-20T00:00:00Z",
        "description": "Unit test mini multi-language dataset",
        "sample_count": len(records),
        "manifest_relpath": "manifest.jsonl",
        "manifest_sha256": manifest_sha,
        "languages": ["en_us", "kn_in"],
        "scripts": ["Knda", "Latn"],
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


def test_m4_multilingual_splits_are_disjoint_and_preserve_frozen_kannada() -> None:
    def _load(dataset_id: str) -> list[dict]:
        p = REPO_ROOT / "sample_data" / "indic_creator_bench" / dataset_id / "manifest.jsonl"
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]

    smoke = _load("m2_smoke_10clip")
    dev_multi = _load("m4_multilingual_dev_50clip")
    eval_multi = _load("m4_multilingual_eval_50clip")
    dev_kn = _load("m4_kn_dev_10clip")
    eval_kn = _load("m4_kn_eval_10clip")

    assert len(dev_multi) == 50
    assert len(eval_multi) == 50

    expected_langs = {"en_us", "hi_in", "kn_in", "ta_in", "te_in"}
    for name, recs in (("dev", dev_multi), ("eval", eval_multi)):
        by_lang = {lang: [r for r in recs if r["language_code"] == lang] for lang in expected_langs}
        for lang, items in by_lang.items():
            assert len(items) == 10, f"Expected 10 {lang} items in {name}, got {len(items)}"

    # Exact preservation of frozen Kannada partitions
    assert [r["utterance_id"] for r in dev_multi if r["language_code"] == "kn_in"] == [r["utterance_id"] for r in dev_kn]
    assert [r["audio_sha256"] for r in dev_multi if r["language_code"] == "kn_in"] == [r["audio_sha256"] for r in dev_kn]
    assert [r["utterance_id"] for r in eval_multi if r["language_code"] == "kn_in"] == [r["utterance_id"] for r in eval_kn]
    assert [r["audio_sha256"] for r in eval_multi if r["language_code"] == "kn_in"] == [r["audio_sha256"] for r in eval_kn]

    # Language-scoped ID, audio hash, and normalized-text disjointness across smoke / dev / eval
    sets = {"smoke": smoke, "dev": dev_multi, "eval": eval_multi}
    for name_a, recs_a in sets.items():
        for name_b, recs_b in sets.items():
            if name_a >= name_b:
                continue
            lang_ids_a = {(r["language_code"], str(r["source_sample_id"])) for r in recs_a}
            lang_ids_b = {(r["language_code"], str(r["source_sample_id"])) for r in recs_b}
            assert lang_ids_a.isdisjoint(lang_ids_b), f"source_sample_id overlap {name_a} vs {name_b}"

            shas_a = {r["audio_sha256"] for r in recs_a}
            shas_b = {r["audio_sha256"] for r in recs_b}
            assert shas_a.isdisjoint(shas_b), f"audio_sha256 overlap {name_a} vs {name_b}"

            tx_a = {(r["language_code"], normalize_indic_reference(r["reference_transcript"], r["language_code"])) for r in recs_a}
            tx_b = {(r["language_code"], normalize_indic_reference(r["reference_transcript"], r["language_code"])) for r in recs_b}
            assert tx_a.isdisjoint(tx_b), f"normalized text overlap {name_a} vs {name_b}"


def test_provider_cpu_threads_in_cache_key_and_param_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = tmp_path / "clip.wav"
    _write_tiny_wav(wav)

    class _FakeModel:
        def transcribe(self, path: str, **kwargs: object):
            seg = SimpleNamespace(
                start=0.0,
                end=0.4,
                text="hello",
                avg_logprob=-0.1,
                no_speech_prob=0.01,
                compression_ratio=1.0,
                temperature=0.0,
                words=None,
            )
            return [seg], SimpleNamespace(language="en", language_probability=0.99)

    p4 = FasterWhisperProvider(model_size_or_path="small", cpu_threads=4)
    p8 = FasterWhisperProvider(model_size_or_path="small", cpu_threads=8)
    assert p4._get_cache_key() != p8._get_cache_key()

    monkeypatch.setattr(p4, "_get_or_load_model", lambda: _FakeModel())
    monkeypatch.setattr(p8, "_get_or_load_model", lambda: _FakeModel())

    r4 = p4.transcribe(wav, language="en", word_timestamps=False)
    r8 = p8.transcribe(wav, language="en", word_timestamps=False)
    assert r4.parameter_hash != r8.parameter_hash


def test_provider_clamps_segment_and_word_timings_to_audio_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wav = tmp_path / "clip.wav"
    _write_tiny_wav(wav, duration_sec=0.5)

    class _OvershootModel:
        def transcribe(self, path: str, **kwargs: object):
            # Simulates Whisper predicting end_time past audio EOF and a post-EOF hallucination segment
            seg1 = SimpleNamespace(
                start=0.0,
                end=9.48,
                text="valid speech slightly overshooting",
                avg_logprob=-0.1,
                no_speech_prob=0.01,
                compression_ratio=1.0,
                temperature=0.0,
                words=[SimpleNamespace(word="yard", start=7.24, end=9.48, probability=0.9)],
            )
            seg2 = SimpleNamespace(
                start=12.0,
                end=29.5,
                text="post-eof hallucination",
                avg_logprob=-0.9,
                no_speech_prob=0.5,
                compression_ratio=2.0,
                temperature=0.0,
                words=None,
            )
            return [seg1, seg2], SimpleNamespace(language="en", language_probability=0.99, duration=8.94)

    provider = FasterWhisperProvider(model_size_or_path="small", cpu_threads=4)
    monkeypatch.setattr(provider, "_get_or_load_model", lambda: _OvershootModel())

    res = provider.transcribe(wav, language="en", word_timestamps=True)
    assert len(res.segments) == 1
    assert res.segments[0].start_time == 0.0
    assert res.segments[0].end_time == 8.94
    assert res.segments[0].words is not None
    assert res.segments[0].words[0]["end"] == 8.94


def test_runner_tracks_timing_validity_auto_lid_confusion_and_checkpoint_isolation(tmp_path: Path) -> None:
    ds_root = _make_multilang_mini_dataset(tmp_path)
    ckpt = tmp_path / "eval.ckpt.jsonl"

    class _StubProvider:
        def __init__(self) -> None:
            self.calls = 0

        def is_available(self) -> bool:
            return True

        def transcribe(self, audio_path: Path, language: str | None = None, **kwargs: object) -> TranscriptionResult:
            self.calls += 1
            if "en_us" in str(audio_path):
                return TranscriptionResult(
                    language="en",
                    model_name="stub-multi",
                    full_text="hello world",
                    segments=[SegmentResult(start_time=0.0, end_time=0.45, text="hello world", confidence=-0.1)],
                )
            # Simulate Auto LID mis-detecting Kannada clip as Hindi ('hi') while returning valid segment timing
            return TranscriptionResult(
                language="hi" if language is None else language,
                model_name="stub-multi",
                full_text="ನಮಸ್ಕಾರ ಕರ್ನಾಟಕ",
                segments=[SegmentResult(start_time=0.0, end_time=0.48, text="ನಮಸ್ಕಾರ ಕರ್ನಾಟಕ", confidence=-0.2)],
            )

    stub = _StubProvider()
    auto_report = run_indic_asr_baseline(
        ds_root,
        stub,
        model_id="stub-multi",
        model_revision="rev-1",
        language_mode="auto",
        cpu_threads=4,
        word_timestamps=False,
        checkpoint_path=ckpt,
    )
    assert stub.calls == 2
    assert auto_report["timing_validity"]["status"] == "segment_only_valid"
    assert auto_report["per_language"]["kn_in"]["timing_validity"]["valid_segment_timing_count"] == 1
    assert auto_report["per_language"]["kn_in"]["timing_validity"]["invalid_timing_count"] == 0

    lid = auto_report["language_id_summary"]
    assert lid["enabled"] is True
    assert lid["total_evaluated"] == 2
    assert lid["correct_count"] == 1
    assert lid["accuracy"] == 0.5
    assert lid["confusion_matrix"]["kn_in"]["hi"] == 1
    assert lid["confusion_matrix"]["en_us"]["en"] == 1

    # Re-running with identical config resumes from checkpoint (0 new provider calls)
    resumed = run_indic_asr_baseline(
        ds_root,
        stub,
        model_id="stub-multi",
        model_revision="rev-1",
        language_mode="auto",
        cpu_threads=4,
        word_timestamps=False,
        checkpoint_path=ckpt,
    )
    assert stub.calls == 2
    assert sum(1 for u in resumed["utterances"] if u.get("resumed_from_checkpoint")) == 2

    # Changing cpu_threads or model_revision must NOT silently mix cached checkpoint items
    rerun_diff_threads = run_indic_asr_baseline(
        ds_root,
        stub,
        model_id="stub-multi",
        model_revision="rev-1",
        language_mode="auto",
        cpu_threads=8,
        word_timestamps=False,
        checkpoint_path=ckpt,
    )
    assert stub.calls == 4
    assert sum(1 for u in rerun_diff_threads["utterances"] if u.get("resumed_from_checkpoint")) == 0


def test_evaluate_multilingual_decision_gates_per_language() -> None:
    # Kannada clears >= 35pp drop, <= 65% WER, <= 6.0x RTF, <= 10% empty, 0 crashes, memory <= 3500 MB
    kn_pass = evaluate_multilingual_language_decision(
        language_code="kn_in",
        baseline_micro_wer=1.0735,
        candidate_micro_wer=0.45,
        empty_count=0,
        total_count=10,
        failed_count=0,
        rtf=2.1,
        measured_memory_mb=2100.0,
        timing_valid=True,
    )
    assert kn_pass["decision"] == "PASS_EXPERIMENTAL"

    # Missing memory measurement MUST leave memory gate open (never PASS)
    kn_no_mem = evaluate_multilingual_language_decision(
        language_code="kn_in",
        baseline_micro_wer=1.0735,
        candidate_micro_wer=0.45,
        empty_count=0,
        total_count=10,
        failed_count=0,
        rtf=2.1,
        measured_memory_mb=None,
        timing_valid=True,
    )
    assert kn_no_mem["decision"] == "HOLD_MEMORY_UNMEASURED"

    # Quality win exceeding laptop memory budget -> EXPERIMENTAL_OVER_BUDGET
    kn_over_ram = evaluate_multilingual_language_decision(
        language_code="kn_in",
        baseline_micro_wer=1.0735,
        candidate_micro_wer=0.45,
        empty_count=0,
        total_count=10,
        failed_count=0,
        rtf=2.1,
        measured_memory_mb=4200.0,
        timing_valid=True,
    )
    assert kn_over_ram["decision"] == "EXPERIMENTAL_OVER_BUDGET"

    # Hindi non-regression alone with poor 52% absolute WER cannot be marked product-ready
    hi_poor_abs = evaluate_multilingual_language_decision(
        language_code="hi_in",
        baseline_micro_wer=0.55,
        candidate_micro_wer=0.52,
        empty_count=0,
        total_count=10,
        failed_count=0,
        rtf=1.5,
        measured_memory_mb=2000.0,
        timing_valid=True,
    )
    assert hi_poor_abs["non_regression_passed"] is True
    assert hi_poor_abs["absolute_usability_passed"] is False
    assert hi_poor_abs["decision"] == "NON_REGRESSION_ONLY_BELOW_USABILITY_TARGET"


def test_pipeline_asr_fingerprint_invalidates_on_model_revision_language_or_decode_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    fake_video = tmp_path / "sample.mp4"
    fake_video.write_bytes(b"fake-video-bytes-for-fingerprint-test")
    fake_wav = tmp_path / "audio.wav"
    _write_tiny_wav(fake_wav, duration_sec=0.5)

    class _ConfigurableStubProvider:
        def __init__(self, model_id: str, model_revision: str, label: str) -> None:
            self.model_id = model_id
            self.model_revision = model_revision
            self.device = "cpu"
            self.compute_type = "int8"
            self.cpu_threads = 4
            self.label = label
            self.seen_languages: list[str | None] = []

        def is_available(self) -> bool:
            return True

        def transcribe(self, audio_path: Path, language: str | None = None, **kwargs: object) -> TranscriptionResult:
            self.seen_languages.append(language)
            return TranscriptionResult(
                language=language or "en",
                model_name=self.model_id,
                full_text=f"{self.label}:{language or 'auto'}",
                segments=[SegmentResult(start_time=0.0, end_time=0.4, text=f"{self.label}:{language or 'auto'}", confidence=-0.1)],
                model_id=self.model_id,
                model_revision=self.model_revision,
            )

    monkeypatch.setattr("app.processing.metadata.has_audio_stream", lambda p: True)
    monkeypatch.setattr("app.processing.subtitles.find_sidecar_subtitles", lambda p: None)
    monkeypatch.setattr("app.workers.pipeline_runner.detect_video_scenes", lambda **kw: [])
    monkeypatch.setattr("app.workers.pipeline_runner.extract_audio_wav", lambda **kw: (_write_tiny_wav(fake_wav), fake_wav)[1])
    monkeypatch.setattr("app.ai.providers.embeddings.index_video_chunks", lambda **kw: 0)

    with SessionLocal() as db:
        v = Video(
            id="vid-fp-1",
            filename="sample.mp4",
            file_path=str(fake_video),
            file_hash=compute_sha256(fake_video),
            file_size=fake_video.stat().st_size,
            duration=0.5,
            width=640,
            height=360,
            fps=24.0,
            codec="h264",
            format="mp4",
        )
        db.add(v)
        db.commit()

        p1 = _ConfigurableStubProvider("faster-whisper-small", "rev-a", "run1")
        orch1 = PipelineOrchestrator(
            db=db,
            media_storage_dir=tmp_path,
            provider=p1,
            config={STAGE_ASR_TRANSCRIPTION: {"language": "kn", "beam_size": 5}},
        )
        orch1.run_pipeline(v.id)
        assert p1.seen_languages == ["kn"]
        t1 = db.query(Transcript).filter_by(video_id=v.id).one()
        assert t1.language == "kn"
        assert t1.full_text == "run1:kn"

        # 1. Identical config + revision -> idempotent skip (0 new calls)
        orch1_repeat = PipelineOrchestrator(
            db=db,
            media_storage_dir=tmp_path,
            provider=p1,
            config={STAGE_ASR_TRANSCRIPTION: {"language": "kn", "beam_size": 5}},
        )
        orch1_repeat.run_pipeline(v.id)
        assert len(p1.seen_languages) == 1

        # 2. Change language -> must invalidate stale transcript and re-run
        p2 = _ConfigurableStubProvider("faster-whisper-small", "rev-a", "run2")
        orch2 = PipelineOrchestrator(
            db=db,
            media_storage_dir=tmp_path,
            provider=p2,
            config={STAGE_ASR_TRANSCRIPTION: {"language": "hi", "beam_size": 5}},
        )
        orch2.run_pipeline(v.id)
        assert p2.seen_languages == ["hi"]
        t2 = db.query(Transcript).filter_by(video_id=v.id).one()
        assert t2.language == "hi"
        assert t2.full_text == "run2:hi"

        # 3. Change model revision -> must invalidate and supersede prior Artifact
        p3 = _ConfigurableStubProvider("faster-whisper-small", "rev-b", "run3")
        orch3 = PipelineOrchestrator(
            db=db,
            media_storage_dir=tmp_path,
            provider=p3,
            config={STAGE_ASR_TRANSCRIPTION: {"language": "hi", "beam_size": 5}},
        )
        orch3.run_pipeline(v.id)
        assert p3.seen_languages == ["hi"]
        t3 = db.query(Transcript).filter_by(video_id=v.id).one()
        assert t3.full_text == "run3:hi"

        artifacts = db.query(Artifact).filter_by(kind="transcript").all()
        assert len(artifacts) == 3
        assert sum(1 for a in artifacts if a.is_current) == 1
        current_art = next(a for a in artifacts if a.is_current)
        assert current_art.producer_revision == "rev-b"

        # 4. Change decode setting (beam_size) -> must invalidate
        p4 = _ConfigurableStubProvider("faster-whisper-small", "rev-b", "run4")
        orch4 = PipelineOrchestrator(
            db=db,
            media_storage_dir=tmp_path,
            provider=p4,
            config={STAGE_ASR_TRANSCRIPTION: {"language": "hi", "beam_size": 1}},
        )
        orch4.run_pipeline(v.id)
        assert p4.seen_languages == ["hi"]
        asr_runs = db.query(StageRun).filter_by(stage=STAGE_ASR_TRANSCRIPTION).all()
        assert len({r.fingerprint for r in asr_runs}) == 4


def test_compare_m4_multilingual_runs_rejects_protocol_mismatch() -> None:
    import sys

    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from compare_m4_multilingual_runs import compare_reports

    base = json.loads(
        (REPO_ROOT / "reports" / "product-acceptance" / "M4_MULTILINGUAL_BASELINE_SMALL_FORCED.json").read_text(
            encoding="utf-8"
        )
    )
    cand = json.loads(
        (REPO_ROOT / "reports" / "product-acceptance" / "M4_MULTILINGUAL_CHALLENGER_TURBO_FORCED.json").read_text(
            encoding="utf-8"
        )
    )

    summary = compare_reports(base, cand)
    assert len(summary["rows"]) == 5
    verdicts = {r["language_code"]: r["verdict"] for r in summary["rows"]}
    assert verdicts["kn_in"] == "PASS_EXPERIMENTAL"
    assert verdicts["en_us"] == "PASS_EXPERIMENTAL"
    assert verdicts["hi_in"] == "NON_REGRESSION_ONLY_BELOW_USABILITY_TARGET"
    assert verdicts["ta_in"] == "KEEP_DEFAULT_FAIL"
    assert verdicts["te_in"] == "KEEP_DEFAULT_FAIL"

    # Mutating cpu_threads must fail loudly rather than mixing unmatched protocols
    bad_cand = json.loads(json.dumps(cand))
    bad_cand["asr_provenance"]["decoding_params"]["cpu_threads"] = 8
    with pytest.raises(ValueError, match="cpu_threads"):
        compare_reports(base, bad_cand)
