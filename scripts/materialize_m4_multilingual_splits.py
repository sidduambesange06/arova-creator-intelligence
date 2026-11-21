"""Deterministic materializer for M4 5-language internal dev & frozen held-out eval splits.

Builds `m4_multilingual_dev_50clip` (10 clips x 5 languages) and
`m4_multilingual_eval_50clip` (10 clips x 5 languages) from pinned local FLEURS
test parquets (168de341b3db6859a9bac1c50a2ef5e3b47647e0, CC-BY-4.0):
- Preserves ALL 10 frozen Kannada clips from `m4_kn_dev_10clip` and `m4_kn_eval_10clip` verbatim.
- Deterministically samples 10 dev + 10 held-out eval clips for `en_us`, `hi_in`, `ta_in`, `te_in`.
- Enforces language-scoped zero overlap with `m2_smoke_10clip` and between dev and eval
  by `(language_code, source_sample_id)`, `audio_sha256`, and `(language_code, normalized_text)`.
- Validates both splits with M2/M3 `validate_indic_bench_dataset(..., require_audio=True)`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ai.evaluation.indic_bench import (
    DATASET_SCHEMA_VERSION,
    LANGUAGE_REGISTRY,
    NORMALIZATION_POLICY_VERSION,
    SAMPLE_SCHEMA_VERSION,
    _inspect_audio_stream,
    normalize_indic_reference,
    validate_indic_bench_dataset,
)
from app.core.security import compute_sha256

FLEURS_REV = "168de341b3db6859a9bac1c50a2ef5e3b47647e0"
FLEURS_REV_SHORT = FLEURS_REV[:8]
DEFAULT_FLEURS_ROOT = Path(os.environ.get("AROVA_FLEURS_ROOT", r"D:\ArovaStep2ASRProgram\eval_data\fleurs"))
SMOKE_MANIFEST = REPO_ROOT / "sample_data" / "indic_creator_bench" / "m2_smoke_10clip" / "manifest.jsonl"
LANGUAGES_ORDER = ("en_us", "hi_in", "kn_in", "ta_in", "te_in")
CLIPS_PER_LANG = 10
SEED = 404


def _load_smoke_exclusions() -> tuple[set[tuple[str, str]], set[str], set[tuple[str, str]]]:
    lang_ids: set[tuple[str, str]] = set()
    shas: set[str] = set()
    lang_texts: set[tuple[str, str]] = set()
    for line in SMOKE_MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        lang = str(rec["language_code"])
        lang_ids.add((lang, str(rec["source_sample_id"])))
        shas.add(str(rec["audio_sha256"]))
        lang_texts.add((lang, normalize_indic_reference(rec["reference_transcript"], lang)))
    return lang_ids, shas, lang_texts


def _load_frozen_kannada(source_dataset_id: str, target_dataset_id: str, target_runtime_dir: Path) -> list[dict[str, Any]]:
    src_manifest = REPO_ROOT / "sample_data" / "indic_creator_bench" / source_dataset_id / "manifest.jsonl"
    src_runtime = REPO_ROOT / "data" / "indic_creator_bench" / source_dataset_id
    out: list[dict[str, Any]] = []
    for line in src_manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        src_audio = src_runtime / rec["audio_relpath"]
        if not src_audio.is_file():
            raise FileNotFoundError(f"Frozen Kannada audio missing: {src_audio}")
        dst_audio = target_runtime_dir / rec["audio_relpath"]
        dst_audio.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_audio, dst_audio)
        actual_sha = compute_sha256(dst_audio)
        if actual_sha != rec["audio_sha256"]:
            raise RuntimeError(f"Frozen Kannada SHA mismatch on {rec['utterance_id']}")
        cloned = dict(rec)
        cloned["dataset_id"] = target_dataset_id
        out.append(cloned)
    return out


def _sample_language_rows(
    lang: str,
    smoke_lang_ids: set[tuple[str, str]],
    smoke_shas: set[str],
    smoke_lang_texts: set[tuple[str, str]],
    fleurs_root: Path = DEFAULT_FLEURS_ROOT,
) -> tuple[str, int, list[dict[str, Any]], list[dict[str, Any]]]:
    import pyarrow.parquet as pq

    parquet_path = fleurs_root / lang / "test" / "0000.parquet"
    if not parquet_path.is_file():
        raise FileNotFoundError(f"Missing local FLEURS parquet for {lang}: {parquet_path}")

    parquet_sha = compute_sha256(parquet_path)
    table = pq.read_table(parquet_path).to_pydict()
    candidates: list[dict[str, Any]] = []
    seen_ids = {sid for (lc, sid) in smoke_lang_ids if lc == lang}
    seen_shas = set(smoke_shas)
    seen_texts = {txt for (lc, txt) in smoke_lang_texts if lc == lang}

    for idx in range(len(table["id"])):
        sid = str(table["id"][idx])
        raw_tx = str(table["raw_transcription"][idx] or "").strip()
        audio_obj = table["audio"][idx]
        audio_bytes = audio_obj.get("bytes") if isinstance(audio_obj, dict) else None
        if not raw_tx or not audio_bytes:
            continue
        sha = hashlib.sha256(audio_bytes).hexdigest()
        norm_tx = normalize_indic_reference(raw_tx, lang)
        if not norm_tx or sid in seen_ids or sha in seen_shas or norm_tx in seen_texts:
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

    if len(candidates) < CLIPS_PER_LANG * 2:
        raise RuntimeError(f"Not enough unique FLEURS rows for {lang}: {len(candidates)}")

    rng = random.Random(SEED)
    rng.shuffle(candidates)
    return parquet_sha, len(candidates), candidates[:CLIPS_PER_LANG], candidates[CLIPS_PER_LANG : CLIPS_PER_LANG * 2]


def _build_record(
    *,
    dataset_id: str,
    split: str,
    lang: str,
    row: dict[str, Any],
    parquet_sha: str,
    runtime_dir: Path,
) -> dict[str, Any]:
    meta_lang = LANGUAGE_REGISTRY[lang]
    sid = str(row["id"])
    uid = f"fleurs_{FLEURS_REV_SHORT}_{lang}_{sid}"
    relpath = f"audio/{lang}/{uid}.wav"
    audio_path = runtime_dir / relpath
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_bytes: bytes = row["audio_bytes"]
    audio_path.write_bytes(audio_bytes)
    audio_sha = hashlib.sha256(audio_bytes).hexdigest()
    info = _inspect_audio_stream(audio_path)
    raw_tx = str(row["raw_transcription"]).strip()

    return {
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
        "language_code": lang,
        "language_name": meta_lang["language_name"],
        "script_code": meta_lang["script_code"],
        "script_name": meta_lang["script_name"],
        "domain": "read_speech_multilingual",
        "source_dataset": "google/fleurs",
        "source_dataset_version": FLEURS_REV,
        "source_sample_id": sid,
        "source_url_or_origin": f"https://huggingface.co/datasets/google/fleurs ({lang}/test/0000.parquet row_id={sid})",
        "license_spdx_or_name": "CC-BY-4.0",
        "attribution_text": "FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech (Conneau et al., 2022), licensed under CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/).",
        "redistribution_status": "redistributable",
        "reference_transcript": raw_tx,
        "raw_transcription": raw_tx,
        "reference_status": "verified",
        "reference_normalizer_notes": "Dataset-provided verbatim FLEURS raw_transcription (not newly human-verified); preserves matras, viramas, nukta, ZWJ/ZWNJ.",
        "code_switch_tags": ["monolingual"],
        "speaker_id": f"fleurs_{lang}_gender_{row['gender']}_id_{sid}",
        "metadata": {
            "fleurs_parquet_relpath": f"{lang}/test/0000.parquet",
            "fleurs_parquet_sha256": parquet_sha,
            "fleurs_gender_code": row["gender"],
            "fleurs_num_samples": row["num_samples"],
            "reference_provenance": "dataset_provided_fleurs_test",
            "manifest_seed": SEED,
        },
    }


def _write_and_validate_split(
    *,
    dataset_id: str,
    dataset_name: str,
    split: str,
    description: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    tracked_dir = REPO_ROOT / "sample_data" / "indic_creator_bench" / dataset_id
    runtime_dir = REPO_ROOT / "data" / "indic_creator_bench" / dataset_id
    tracked_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    manifest_text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    manifest_sha = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

    langs = sorted({r["language_code"] for r in records})
    scripts = sorted({r["script_code"] for r in records})
    descriptor = {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "dataset_version": "1.0.0",
        "split": split,
        "created_at_utc": "2026-11-20T08:00:00Z",
        "description": description,
        "sample_count": len(records),
        "manifest_relpath": "manifest.jsonl",
        "manifest_sha256": manifest_sha,
        "languages": langs,
        "scripts": scripts,
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

    per_lang_sec: dict[str, float] = {}
    for lang in LANGUAGES_ORDER:
        per_lang_sec[lang] = round(sum(r["duration_sec"] for r in records if r["language_code"] == lang), 3)

    return {
        "dataset_id": dataset_id,
        "split": split,
        "sample_count": len(records),
        "manifest_sha256": manifest_sha,
        "total_audio_sec": round(sum(r["duration_sec"] for r in records), 3),
        "per_language_audio_sec": per_lang_sec,
        "validation_status": report.status,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize frozen M4 5-language dev/eval splits from pinned FLEURS parquets.")
    parser.add_argument(
        "--fleurs-root",
        type=Path,
        default=DEFAULT_FLEURS_ROOT,
        help="Directory containing <lang>/test/0000.parquet from google/fleurs@168de341... (or set AROVA_FLEURS_ROOT).",
    )
    args = parser.parse_args(argv)
    fleurs_root = args.fleurs_root

    smoke_lang_ids, smoke_shas, smoke_lang_texts = _load_smoke_exclusions()

    dev_id = "m4_multilingual_dev_50clip"
    eval_id = "m4_multilingual_eval_50clip"
    dev_runtime = REPO_ROOT / "data" / "indic_creator_bench" / dev_id
    eval_runtime = REPO_ROOT / "data" / "indic_creator_bench" / eval_id

    dev_records: list[dict[str, Any]] = []
    eval_records: list[dict[str, Any]] = []
    parquet_audit: dict[str, dict[str, Any]] = {}

    for lang in LANGUAGES_ORDER:
        if lang == "kn_in":
            kn_dev = _load_frozen_kannada("m4_kn_dev_10clip", dev_id, dev_runtime)
            kn_eval = _load_frozen_kannada("m4_kn_eval_10clip", eval_id, eval_runtime)
            dev_records.extend(kn_dev)
            eval_records.extend(kn_eval)
            parquet_audit[lang] = {
                "parquet_sha256": kn_eval[0]["metadata"]["fleurs_parquet_sha256"],
                "preserved_from_frozen": ["m4_kn_dev_10clip", "m4_kn_eval_10clip"],
            }
            continue

        parquet_sha, eligible_count, d_rows, e_rows = _sample_language_rows(
            lang, smoke_lang_ids, smoke_shas, smoke_lang_texts, fleurs_root=fleurs_root
        )
        parquet_audit[lang] = {
            "parquet_sha256": parquet_sha,
            "eligible_unique_candidates": eligible_count,
        }
        for row in d_rows:
            dev_records.append(
                _build_record(
                    dataset_id=dev_id,
                    split="dev",
                    lang=lang,
                    row=row,
                    parquet_sha=parquet_sha,
                    runtime_dir=dev_runtime,
                )
            )
        for row in e_rows:
            eval_records.append(
                _build_record(
                    dataset_id=eval_id,
                    split="test",
                    lang=lang,
                    row=row,
                    parquet_sha=parquet_sha,
                    runtime_dir=eval_runtime,
                )
            )

    dev_summary = _write_and_validate_split(
        dataset_id=dev_id,
        dataset_name="M4 5-Language Internal Development Partition (50 clips from FLEURS test)",
        split="dev",
        description=(
            "Arova internal 5-language development partition (en_us, hi_in, kn_in, ta_in, te_in; 10 clips each) "
            "sampled from pinned FLEURS test parquets. Preserves frozen m4_kn_dev_10clip Kannada samples verbatim; "
            "strictly disjoint from m2_smoke_10clip and m4_multilingual_eval_50clip."
        ),
        records=dev_records,
    )
    eval_summary = _write_and_validate_split(
        dataset_id=eval_id,
        dataset_name="M4 5-Language Frozen Held-Out Evaluation Partition (50 clips from FLEURS test)",
        split="test",
        description=(
            "Frozen 5-language held-out evaluation partition (en_us, hi_in, kn_in, ta_in, te_in; 10 clips each) "
            "sampled from pinned FLEURS test parquets. Preserves frozen m4_kn_eval_10clip Kannada samples verbatim; "
            "strictly disjoint from m2_smoke_10clip and m4_multilingual_dev_50clip. Zero tuning permitted."
        ),
        records=eval_records,
    )

    print(
        json.dumps(
            {
                "fleurs_revision": FLEURS_REV,
                "seed": SEED,
                "parquets": parquet_audit,
                "dev": dev_summary,
                "eval": eval_summary,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
