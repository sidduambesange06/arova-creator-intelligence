"""Deterministic materializer for M4 Kannada internal dev & held-out eval splits.

Extracts strictly disjoint Kannada (kn_in) WAV clips from pinned local FLEURS
test parquet (168de341b3db6859a9bac1c50a2ef5e3b47647e0, CC-BY-4.0), enforcing:
- Zero overlap with m2_smoke_10clip by source_sample_id, audio_sha256, and normalized text.
- Zero overlap between m4_kn_dev_10clip and m4_kn_eval_10clip.
- Namespaced utterance_id: fleurs_168de341_kn_in_<row_id>.
- Full M2/M3 schema & SHA-256 validation on both splits.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ai.evaluation.indic_bench import (
    DATASET_SCHEMA_VERSION,
    NORMALIZATION_POLICY_VERSION,
    SAMPLE_SCHEMA_VERSION,
    _inspect_audio_stream,
    normalize_indic_reference,
    validate_indic_bench_dataset,
)
from app.core.security import compute_sha256

FLEURS_REV = "168de341b3db6859a9bac1c50a2ef5e3b47647e0"
FLEURS_REV_SHORT = FLEURS_REV[:8]
FLEURS_KN_PARQUET = Path(r"D:\ArovaStep2ASRProgram\eval_data\fleurs\kn_in\test\0000.parquet")
SMOKE_MANIFEST = REPO_ROOT / "sample_data" / "indic_creator_bench" / "m2_smoke_10clip" / "manifest.jsonl"


def _load_smoke_exclusions() -> tuple[set[str], set[str], set[str]]:
    ids: set[str] = set()
    shas: set[str] = set()
    norm_texts: set[str] = set()
    for line in SMOKE_MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("language_code") == "kn_in":
            ids.add(str(rec["source_sample_id"]))
            shas.add(str(rec["audio_sha256"]))
            norm_texts.add(normalize_indic_reference(rec["reference_transcript"], "kn_in"))
    return ids, shas, norm_texts


def _materialize_split(
    *,
    dataset_id: str,
    dataset_name: str,
    split: str,
    description: str,
    rows: list[dict[str, Any]],
    parquet_sha: str,
    seed: int,
) -> dict[str, Any]:
    tracked_dir = REPO_ROOT / "sample_data" / "indic_creator_bench" / dataset_id
    runtime_dir = REPO_ROOT / "data" / "indic_creator_bench" / dataset_id
    tracked_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "audio" / "kn_in").mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for row in rows:
        sid = str(row["id"])
        uid = f"fleurs_{FLEURS_REV_SHORT}_kn_in_{sid}"
        relpath = f"audio/kn_in/{uid}.wav"
        audio_path = runtime_dir / relpath
        audio_bytes: bytes = row["audio_bytes"]
        audio_path.write_bytes(audio_bytes)
        audio_sha = hashlib.sha256(audio_bytes).hexdigest()
        info = _inspect_audio_stream(audio_path)

        raw_tx = str(row["raw_transcription"]).strip()
        records.append(
            {
                "sample_schema_version": SAMPLE_SCHEMA_VERSION,
                "dataset_id": dataset_id,
                "dataset_version": "1.0.0",
                "split": split,
                "utterance_id": uid,
                "audio_relpath": relpath,
                "audio_sha256": audio_sha,
                "audio_format": "wav",
                "duration_sec": round(info.duration, 3),
                "sample_rate_hz": info.samplerate,
                "channels": info.channels,
                "language_code": "kn_in",
                "language_name": "Kannada",
                "script_code": "Knda",
                "script_name": "Kannada",
                "domain": "read_speech_multilingual",
                "source_dataset": "google/fleurs",
                "source_dataset_version": FLEURS_REV,
                "source_sample_id": sid,
                "source_url_or_origin": f"https://huggingface.co/datasets/google/fleurs (kn_in/test/0000.parquet row_id={sid})",
                "license_spdx_or_name": "CC-BY-4.0",
                "attribution_text": "FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech (Conneau et al., 2022), licensed under CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/).",
                "redistribution_status": "redistributable",
                "reference_transcript": raw_tx,
                "raw_transcription": raw_tx,
                "reference_status": "verified",
                "reference_normalizer_notes": "Dataset-provided verbatim FLEURS raw_transcription (not newly human-verified); preserves matras, viramas, nukta, ZWJ/ZWNJ.",
                "code_switch_tags": ["monolingual"],
                "speaker_id": f"fleurs_kn_in_gender_{row['gender']}_id_{sid}",
                "metadata": {
                    "fleurs_parquet_relpath": "kn_in/test/0000.parquet",
                    "fleurs_parquet_sha256": parquet_sha,
                    "fleurs_gender_code": row["gender"],
                    "fleurs_num_samples": row["num_samples"],
                    "reference_provenance": "dataset_provided_fleurs_test",
                    "manifest_seed": seed,
                },
            }
        )

    manifest_text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    manifest_sha = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

    descriptor = {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "dataset_version": "1.0.0",
        "split": split,
        "created_at_utc": "2026-11-19T18:00:00Z",
        "description": description,
        "sample_count": len(records),
        "manifest_relpath": "manifest.jsonl",
        "manifest_sha256": manifest_sha,
        "languages": ["kn_in"],
        "scripts": ["Knda"],
        "source_datasets": [
            {
                "source_dataset": "google/fleurs",
                "source_dataset_version": FLEURS_REV,
                "license_spdx_or_name": "CC-BY-4.0",
                "source_url_or_origin": "https://huggingface.co/datasets/google/fleurs",
                "attribution_text": "FLEURS (Conneau et al., 2022), CC-BY-4.0.",
            }
        ],
        "license_summary": "CC-BY-4.0 (FLEURS, Conneau et al., 2022)",
        "attribution_required": True,
        "redistribution_policy": "source_license_attribution_required",
        "normalization_policy_version": NORMALIZATION_POLICY_VERSION,
    }

    for target_dir in (tracked_dir, runtime_dir):
        (target_dir / "manifest.jsonl").write_text(manifest_text, encoding="utf-8", newline="\n")
        (target_dir / "dataset.json").write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8", newline="\n")

    report, _ = validate_indic_bench_dataset(runtime_dir, require_audio=True)
    if report.status != "VALID":
        raise RuntimeError(f"Validation failed for {dataset_id}: {report.failures}")

    return {
        "dataset_id": dataset_id,
        "split": split,
        "sample_count": len(records),
        "manifest_sha256": manifest_sha,
        "total_audio_sec": round(sum(r["duration_sec"] for r in records), 3),
        "validation_status": report.status,
    }


def main() -> int:
    import pyarrow.parquet as pq

    if not FLEURS_KN_PARQUET.is_file():
        raise FileNotFoundError(f"Missing local FLEURS Kannada parquet: {FLEURS_KN_PARQUET}")

    parquet_sha = compute_sha256(FLEURS_KN_PARQUET)
    smoke_ids, smoke_shas, smoke_texts = _load_smoke_exclusions()

    table = pq.read_table(FLEURS_KN_PARQUET).to_pydict()
    candidates: list[dict[str, Any]] = []
    seen_ids = set(smoke_ids)
    seen_shas = set(smoke_shas)
    seen_texts = set(smoke_texts)

    total_rows = len(table["id"])
    for idx in range(total_rows):
        sid = str(table["id"][idx])
        raw_tx = str(table["raw_transcription"][idx] or "").strip()
        audio_obj = table["audio"][idx]
        audio_bytes = audio_obj.get("bytes") if isinstance(audio_obj, dict) else None
        if not raw_tx or not audio_bytes:
            continue
        sha = hashlib.sha256(audio_bytes).hexdigest()
        norm_tx = normalize_indic_reference(raw_tx, "kn_in")
        if sid in seen_ids or sha in seen_shas or norm_tx in seen_texts:
            continue
        seen_ids.add(sid)
        seen_shas.add(sha)
        seen_texts.add(norm_tx)
        candidates.append(
            {
                "id": sid,
                "raw_transcription": raw_tx,
                "audio_bytes": audio_bytes,
                "gender": int(table["gender"][idx]),
                "num_samples": int(table["num_samples"][idx]),
            }
        )

    # Deterministic shuffle (seed=404) and partition: 10 internal dev + 10 held-out eval
    rng = random.Random(404)
    rng.shuffle(candidates)
    dev_rows = candidates[:10]
    eval_rows = candidates[10:20]

    dev_summary = _materialize_split(
        dataset_id="m4_kn_dev_10clip",
        dataset_name="M4 Kannada Internal Development Partition (10 clips from FLEURS test)",
        split="dev",
        description="Arova internal Kannada development partition sampled from pinned FLEURS kn_in/test; strictly disjoint from m2_smoke_10clip and m4_kn_eval_10clip by ID, SHA-256, and normalized text.",
        rows=dev_rows,
        parquet_sha=parquet_sha,
        seed=404,
    )
    eval_summary = _materialize_split(
        dataset_id="m4_kn_eval_10clip",
        dataset_name="M4 Kannada Held-Out Evaluation Partition (10 clips from FLEURS test)",
        split="test",
        description="Frozen Kannada held-out evaluation partition sampled from pinned FLEURS kn_in/test; strictly disjoint from m2_smoke_10clip and m4_kn_dev_10clip by ID, SHA-256, and normalized text. Zero tuning permitted.",
        rows=eval_rows,
        parquet_sha=parquet_sha,
        seed=404,
    )

    print(json.dumps({
        "parquet_sha256": parquet_sha,
        "eligible_unique_candidates": len(candidates),
        "dev": dev_summary,
        "eval": eval_summary,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
