#!/usr/bin/env python3
"""Reproducible local validation CLI for Arova Indic Creator Bench (M2).

Validates the dataset descriptor, sample manifest JSONL, path containment,
SHA-256 audio checksums, audio stream headers, Indic Unicode safety, and
deterministic secret-safe ASR/batch provenance contracts.

Zero GPU, zero model downloads, zero API keys, and zero network calls required.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ai.evaluation.indic_bench import (  # noqa: E402
    DATASET_SCHEMA_VERSION,
    LANGUAGE_REGISTRY,
    NORMALIZATION_POLICY_VERSION,
    SAMPLE_SCHEMA_VERSION,
    build_asr_run_provenance,
    build_batch_run_provenance,
    compute_safe_utterance_metrics,
    validate_indic_bench_dataset,
)
from app.core.security import compute_sha256  # noqa: E402

FLEURS_COMMIT_SHA = "168de341b3db6859a9bac1c50a2ef5e3b47647e0"
FLEURS_LICENSE = "CC-BY-4.0"
FLEURS_ORIGIN = "https://huggingface.co/datasets/google/fleurs"
FLEURS_ATTRIBUTION = (
    "FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech "
    "(Conneau et al., 2022), licensed under CC-BY-4.0 "
    "(https://creativecommons.org/licenses/by/4.0/)."
)

DEFAULT_TRACKED_CORPUS_DIR = ROOT_DIR / "sample_data" / "indic_creator_bench" / "m2_smoke_10clip"
DEFAULT_RUNTIME_CORPUS_DIR = ROOT_DIR / "data" / "indic_creator_bench" / "m2_smoke_10clip"
DEFAULT_FLEURS_ROOT = Path(r"D:\ArovaStep2ASRProgram\eval_data\fleurs")
DEFAULT_FLEURS_MANIFEST = ROOT_DIR / "reports" / "asr_eval" / "fleurs_manifest.json"
DEFAULT_HINGLISH_TEMPLATE = ROOT_DIR / "reports" / "asr_eval" / "hinglish_template.json"

# Deterministic 10-clip smoke selection: first 2 screening sample IDs per language (seed 42)
SMOKE_CLIP_SPEC: tuple[tuple[str, tuple[int, int]], ...] = (
    ("hi_in", (1718, 1836)),
    ("kn_in", (1923, 1970)),
    ("ta_in", (1740, 1732)),
    ("te_in", (1666, 2002)),
    ("en_us", (1950, 1938)),
)


def _extract_smoke_clips_from_fleurs(
    fleurs_root: Path,
    target_root: Path,
) -> list[dict[str, Any]]:
    """Extract unmodified WAV bytes for the 10 M2 smoke clips from local FLEURS parquets."""
    import pyarrow.parquet as pq
    import soundfile as sf

    records: list[dict[str, Any]] = []
    for lang_code, sample_ids in SMOKE_CLIP_SPEC:
        parquet_path = fleurs_root / lang_code / "test" / "0000.parquet"
        if not parquet_path.is_file():
            raise FileNotFoundError(f"Missing local FLEURS parquet: '{parquet_path}'.")

        parquet_sha256 = compute_sha256(parquet_path)
        table = pq.read_table(parquet_path).to_pydict()
        lang_meta = LANGUAGE_REGISTRY[lang_code]

        audio_dir = target_root / "audio" / lang_code
        audio_dir.mkdir(parents=True, exist_ok=True)

        for sid in sample_ids:
            idx = table["id"].index(sid)
            audio_bytes = table["audio"][idx]["bytes"]
            wav_filename = f"fleurs_{lang_code}_{sid}.wav"
            relpath = f"audio/{lang_code}/{wav_filename}"
            out_wav = target_root / relpath
            out_wav.write_bytes(audio_bytes)

            info = sf.info(io.BytesIO(audio_bytes))
            audio_sha = hashlib.sha256(audio_bytes).hexdigest()
            raw_ref = str(table["raw_transcription"][idx])
            fleurs_norm = str(table["transcription"][idx])

            records.append(
                {
                    "sample_schema_version": SAMPLE_SCHEMA_VERSION,
                    "dataset_id": "indic_creator_bench_m2_smoke",
                    "dataset_version": "1.0.0",
                    "split": "smoke",
                    "utterance_id": f"fleurs_{lang_code}_{sid}",
                    "audio_relpath": relpath,
                    "audio_sha256": audio_sha,
                    "audio_format": "wav",
                    "duration_sec": round(float(info.duration), 6),
                    "sample_rate_hz": int(info.samplerate),
                    "channels": int(info.channels),
                    "language_code": lang_code,
                    "language_name": lang_meta["language_name"],
                    "script_code": lang_meta["script_code"],
                    "script_name": lang_meta["script_name"],
                    "domain": "read_speech_multilingual",
                    "source_dataset": "google/fleurs",
                    "source_dataset_version": FLEURS_COMMIT_SHA,
                    "source_sample_id": str(sid),
                    "source_url_or_origin": f"{FLEURS_ORIGIN} (test/0000.parquet row_id={sid})",
                    "license_spdx_or_name": FLEURS_LICENSE,
                    "attribution_text": FLEURS_ATTRIBUTION,
                    "redistribution_status": "redistributable",
                    "reference_transcript": raw_ref,
                    "raw_transcription": raw_ref,
                    "reference_status": "verified",
                    "reference_normalizer_notes": (
                        "Preserved verbatim from FLEURS raw_transcription without stripping punctuation, "
                        "case, matras, viramas, nukta, or ZWJ/ZWNJ."
                    ),
                    "code_switch_tags": ["monolingual"],
                    "speaker_id": f"fleurs_{lang_code}_speaker_gender_{table['gender'][idx]}_id_{sid}",
                    "metadata": {
                        "fleurs_parquet_relpath": f"{lang_code}/test/0000.parquet",
                        "fleurs_parquet_sha256": parquet_sha256,
                        "fleurs_normalized_transcription": fleurs_norm,
                        "fleurs_gender_code": int(table["gender"][idx]),
                        "fleurs_num_samples": int(table["num_samples"][idx]),
                        "audio_subtype": str(info.subtype),
                        "manifest_seed": 42,
                    },
                }
            )
    return records


def build_smoke_contracts(
    fleurs_root: Path = DEFAULT_FLEURS_ROOT,
    tracked_dir: Path = DEFAULT_TRACKED_CORPUS_DIR,
    runtime_dir: Path = DEFAULT_RUNTIME_CORPUS_DIR,
) -> Path:
    """Build frozen descriptor/manifest contracts in tracked_dir and materialize audio in runtime_dir."""
    records = _extract_smoke_clips_from_fleurs(fleurs_root=fleurs_root, target_root=runtime_dir)

    manifest_text = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    tracked_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    tracked_manifest = tracked_dir / "manifest.jsonl"
    runtime_manifest = runtime_dir / "manifest.jsonl"
    tracked_manifest.write_text(manifest_text, encoding="utf-8", newline="\n")
    runtime_manifest.write_text(manifest_text, encoding="utf-8", newline="\n")

    manifest_sha = compute_sha256(tracked_manifest)
    descriptor = {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "dataset_id": "indic_creator_bench_m2_smoke",
        "dataset_name": "Arova Indic Creator Bench — M2 10-Clip Smoke Corpus",
        "dataset_version": "1.0.0",
        "split": "smoke",
        "created_at_utc": "2026-11-15T00:00:00Z",
        "description": (
            "Verified 10-clip local speech smoke corpus sourced losslessly from pinned google/fleurs "
            "test parquets across Hindi (hi_in), Kannada (kn_in), Tamil (ta_in), Telugu (te_in), "
            "and English control (en_us). Hinglish is explicitly excluded pending verified references."
        ),
        "sample_count": len(records),
        "manifest_relpath": "manifest.jsonl",
        "manifest_sha256": manifest_sha,
        "languages": ["hi_in", "kn_in", "ta_in", "te_in", "en_us"],
        "scripts": ["Deva", "Knda", "Taml", "Telu", "Latn"],
        "source_datasets": [
            {
                "source_dataset": "google/fleurs",
                "source_dataset_version": FLEURS_COMMIT_SHA,
                "license_spdx_or_name": FLEURS_LICENSE,
                "source_url_or_origin": FLEURS_ORIGIN,
                "attribution_text": FLEURS_ATTRIBUTION,
            }
        ],
        "license_summary": "CC-BY-4.0 (FLEURS, Conneau et al., 2022)",
        "attribution_required": True,
        "redistribution_policy": "source_license_attribution_required",
        "normalization_policy_version": NORMALIZATION_POLICY_VERSION,
        "excluded_slices": [
            {
                "slice_id": "hinglish_en_hi_codeswitch",
                "status": "NO_VERIFIED_REFERENCE",
                "reason": (
                    "Excluded from verified gold benchmark claims because "
                    "reports/asr_eval/hinglish_template.json contains zero verified samples."
                ),
                "evidence_path": "reports/asr_eval/hinglish_template.json",
            }
        ],
    }

    descriptor_text = json.dumps(descriptor, indent=2, ensure_ascii=False) + "\n"
    (tracked_dir / "dataset.json").write_text(descriptor_text, encoding="utf-8", newline="\n")
    (runtime_dir / "dataset.json").write_text(descriptor_text, encoding="utf-8", newline="\n")
    return runtime_dir


def materialize_smoke_audio(
    fleurs_root: Path = DEFAULT_FLEURS_ROOT,
    tracked_dir: Path = DEFAULT_TRACKED_CORPUS_DIR,
    runtime_dir: Path = DEFAULT_RUNTIME_CORPUS_DIR,
) -> None:
    """Materialize unmodified WAVs from local FLEURS parquets alongside tracked contracts."""
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("dataset.json", "manifest.jsonl"):
        src = tracked_dir / fname
        if not src.is_file():
            raise FileNotFoundError(f"Tracked M2 contract file missing: '{src}'.")
        shutil.copyfile(src, runtime_dir / fname)
    _extract_smoke_clips_from_fleurs(fleurs_root=fleurs_root, target_root=runtime_dir)


def run_validation(
    dataset_root: Path,
    require_audio: bool = True,
    materialize: bool = False,
    build_contracts: bool = False,
    json_out: Path | None = None,
) -> dict[str, Any]:
    if build_contracts:
        build_smoke_contracts(runtime_dir=dataset_root)
    elif materialize:
        materialize_smoke_audio(runtime_dir=dataset_root)

    report, samples = validate_indic_bench_dataset(dataset_root, require_audio=require_audio)
    descriptor = {}
    desc_path = dataset_root / "dataset.json"
    if desc_path.is_file():
        descriptor = json.loads(desc_path.read_text(encoding="utf-8"))

    # Verify Unicode-safe normalization + zero-error self-score sanity across all loaded samples
    unicode_checks: list[dict[str, Any]] = []
    for sample in samples:
        uid = sample.get("utterance_id", "")
        lang = sample.get("language_code", "en_us")
        raw_ref = sample.get("raw_transcription", "")
        metrics = compute_safe_utterance_metrics(raw_ref, raw_ref, lang)
        unicode_checks.append(
            {
                "utterance_id": uid,
                "language_code": lang,
                "raw_unchanged": metrics["raw_reference"] == raw_ref,
                "self_wer": metrics["wer"],
                "self_cer": metrics["cer"],
            }
        )

    # Construct deterministic, secret-safe M2 provenance sample (explicitly NOT_RUN)
    manifest_sha = descriptor.get("manifest_sha256", "0" * 64)
    sample_run_prov = build_asr_run_provenance(
        run_id="indic-bench-m2-smoke-dryrun-contract",
        dataset_id=descriptor.get("dataset_id", "indic_creator_bench_m2_smoke"),
        dataset_version=descriptor.get("dataset_version", "1.0.0"),
        split=descriptor.get("split", "smoke"),
        manifest_sha256=manifest_sha,
        provider_type="faster_whisper",
        model_id="faster-whisper-small",
        model_revision="local_pinned",
        execution_status="NOT_RUN",
        created_at_utc="2026-11-15T00:00:00Z",
    )
    sample_batch_prov = build_batch_run_provenance(
        batch_id="indic-bench-m2-smoke-batch-contract",
        dataset_id=descriptor.get("dataset_id", "indic_creator_bench_m2_smoke"),
        dataset_version=descriptor.get("dataset_version", "1.0.0"),
        split=descriptor.get("split", "smoke"),
        manifest_sha256=manifest_sha,
        total_items=len(samples),
        processed_items=0,
        succeeded_items=0,
        failed_items=0,
        skipped_items=len(samples),
        run_ids=[sample_run_prov["run_id"]],
        batch_config={"validation_only": True, "normalization_policy_version": NORMALIZATION_POLICY_VERSION},
        execution_status="NOT_RUN",
        created_at_utc="2026-11-15T00:00:00Z",
        notes="M2 data-foundation contract check only; ASR inference NOT_RUN.",
    )

    payload: dict[str, Any] = {
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "asr_inference_status": "NOT_RUN",
        "hinglish_status": (
            json.loads(DEFAULT_HINGLISH_TEMPLATE.read_text(encoding="utf-8")).get("status")
            if DEFAULT_HINGLISH_TEMPLATE.is_file()
            else "NO_VERIFIED_REFERENCE"
        ),
        "validation_report": report.to_dict(),
        "unicode_self_checks": unicode_checks,
        "provenance_contract_check": {
            "asr_run_provenance": sample_run_prov,
            "batch_run_provenance": sample_batch_prov,
        },
    }

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Arova Indic Creator Bench dataset contracts, integrity, and provenance."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_RUNTIME_CORPUS_DIR,
        help="Path to dataset directory containing dataset.json and manifest.jsonl.",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Validate descriptor, schema, paths, and references without requiring local WAV files.",
    )
    parser.add_argument(
        "--materialize",
        action="store_true",
        help="Extract the 10 unmodified M2 smoke WAVs from local FLEURS parquets before validating.",
    )
    parser.add_argument(
        "--build-contracts",
        action="store_true",
        help="Regenerate tracked M2 descriptor/manifest contracts and materialize local audio.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write full JSON validation report.",
    )
    args = parser.parse_args()

    payload = run_validation(
        dataset_root=args.dataset_root,
        require_audio=not args.manifest_only,
        materialize=args.materialize,
        build_contracts=args.build_contracts,
        json_out=args.json_out,
    )
    rep = payload["validation_report"]
    print(f"Indic Creator Bench Validation Status : {rep['status']}")
    print(f"Dataset Root                         : {rep['dataset_root']}")
    print(f"Dataset ID / Version / Schema        : {rep['dataset_id']} @ {rep['dataset_version']} (schema {rep['dataset_schema_version']})")
    print(f"Samples (valid / total / invalid)    : {rep['valid_samples']} / {rep['total_samples']} / {rep['invalid_samples']}")
    print(f"Languages                            : {rep['language_counts']}")
    print(f"Scripts                              : {rep['script_counts']}")
    print(f"Reference Status                     : {rep['reference_status_counts']}")
    print(f"ASR Inference Status                 : {payload['asr_inference_status']}")
    print(f"Hinglish Slice Status                : {payload['hinglish_status']} (excluded)")
    if rep["failures"]:
        print("Failures:")
        for fail in rep["failures"]:
            print(f"  - [{fail['code']}] line={fail['line_number']} id={fail['utterance_id']}: {fail['message']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
