"""Compare matched M4 5-language ASR baseline vs challenger JSON reports and emit decision table.

Applies the pre-registered M4 v2.0 per-language gates (`evaluate_multilingual_language_decision`)
unchanged, verifying protocol parity (manifest SHA-256, device, compute_type, cpu_threads,
language_mode, beam_size, vad_filter, word_timestamps, normalization policy) before scoring.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ai.evaluation.asr_baseline import evaluate_multilingual_language_decision

LANGUAGE_ORDER = ("kn_in", "hi_in", "en_us", "ta_in", "te_in")


def _assert_matched_protocol(base: dict[str, Any], cand: dict[str, Any]) -> None:
    b_ds, c_ds = base["dataset"], cand["dataset"]
    if b_ds["manifest_sha256"] != c_ds["manifest_sha256"]:
        raise ValueError(
            f"Manifest SHA mismatch: baseline={b_ds['manifest_sha256']} vs candidate={c_ds['manifest_sha256']}"
        )
    b_p, c_p = base["asr_provenance"], cand["asr_provenance"]
    for key in ("device", "compute_type", "language_mode", "normalization_policy_version"):
        if b_p.get(key) != c_p.get(key):
            raise ValueError(f"Protocol mismatch on '{key}': baseline={b_p.get(key)} vs candidate={c_p.get(key)}")
    b_dec, c_dec = b_p.get("decoding_params") or {}, c_p.get("decoding_params") or {}
    for key in ("beam_size", "vad_filter", "word_timestamps", "condition_on_previous_text", "cpu_threads"):
        if b_dec.get(key) != c_dec.get(key):
            raise ValueError(
                f"Decoding param mismatch on '{key}': baseline={b_dec.get(key)} vs candidate={c_dec.get(key)}"
            )


def _fmt_pct(val: float | None) -> str:
    return f"{val * 100:.2f}%" if val is not None else "N/A"


def compare_reports(base: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any]:
    _assert_matched_protocol(base, cand)

    res = cand.get("resources") or {}
    os_peak = res.get("os_peak_wset_mb")
    rss_max = res.get("rss_sampled_max_mb")
    rss_peak = res.get("rss_peak_mb")
    # Conservative high-water mark: max of measured OS peak WSET and 50ms sampled RSS
    measured_vals = [float(v) for v in (os_peak, rss_max, rss_peak) if isinstance(v, (int, float))]
    measured_memory_mb = max(measured_vals) if measured_vals else None

    rows: list[dict[str, Any]] = []
    for lang in LANGUAGE_ORDER:
        b_lang = (base.get("per_language") or {}).get(lang)
        c_lang = (cand.get("per_language") or {}).get(lang)
        if not b_lang or not c_lang:
            rows.append(
                {
                    "language_code": lang,
                    "verdict": "INCONCLUSIVE",
                    "reason": "Missing per-language baseline or candidate evidence",
                }
            )
            continue

        b_micro = b_lang["micro"]
        c_micro = c_lang["micro"]
        b_wer = b_micro.get("corpus_wer")
        c_wer = c_micro.get("corpus_wer")
        abs_pp = round((b_wer - c_wer) * 100.0, 2) if (b_wer is not None and c_wer is not None) else None

        tv = c_lang.get("timing_validity") or {}
        tv_status = tv.get("status", "not_evaluated")
        timing_valid = tv_status in ("segment_only_valid", "word_level_valid")

        eval_out = evaluate_multilingual_language_decision(
            language_code=lang,
            baseline_micro_wer=b_wer,
            candidate_micro_wer=c_wer,
            empty_count=int(c_micro.get("empty_hypothesis_count", 0)),
            total_count=int(c_lang.get("total_count", 0)),
            failed_count=int(c_lang.get("failed_count", 0)),
            rtf=c_lang.get("rtf"),
            measured_memory_mb=measured_memory_mb,
            timing_valid=timing_valid,
        )
        verdict = eval_out["decision"]
        if verdict == "HOLD_MEMORY_UNMEASURED":
            verdict = "INCONCLUSIVE"

        rows.append(
            {
                "language_code": lang,
                "baseline_micro_wer": b_wer,
                "baseline_macro_wer": b_lang.get("macro_wer"),
                "baseline_sdi": (
                    int(b_micro.get("total_word_substitutions", 0)),
                    int(b_micro.get("total_word_deletions", 0)),
                    int(b_micro.get("total_word_insertions", 0)),
                ),
                "baseline_ref_words": int(b_micro.get("total_ref_words", 0)),
                "candidate_micro_wer": c_wer,
                "candidate_macro_wer": c_lang.get("macro_wer"),
                "candidate_sdi": (
                    int(c_micro.get("total_word_substitutions", 0)),
                    int(c_micro.get("total_word_deletions", 0)),
                    int(c_micro.get("total_word_insertions", 0)),
                ),
                "candidate_ref_words": int(c_micro.get("total_ref_words", 0)),
                "wer_improvement_pp": abs_pp,
                "candidate_micro_cer": c_micro.get("corpus_cer"),
                "candidate_char_edits": int(c_micro.get("total_char_edits", 0)),
                "candidate_ref_chars": int(c_micro.get("total_ref_chars", 0)),
                "empty_count": int(c_micro.get("empty_hypothesis_count", 0)),
                "failed_count": int(c_lang.get("failed_count", 0)),
                "total_count": int(c_lang.get("total_count", 0)),
                "audio_sec": c_lang.get("audio_sec"),
                "inference_sec": c_lang.get("inference_sec"),
                "rtf": c_lang.get("rtf"),
                "measured_os_peak_wset_mb": os_peak,
                "measured_rss_sampled_max_mb": rss_max,
                "measured_memory_mb": measured_memory_mb,
                "timing_status": tv_status,
                "timing_valid_count": int(tv.get("valid_segment_timing_count", 0)),
                "timing_invalid_count": int(tv.get("invalid_timing_count", 0)),
                "gate_details": eval_out,
                "verdict": verdict,
            }
        )

    all_pass = all(r["verdict"] == "PASS_EXPERIMENTAL" for r in rows)
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_id": cand["dataset"]["dataset_id"],
        "manifest_sha256": cand["dataset"]["manifest_sha256"],
        "baseline_model": {
            "model_id": base["asr_provenance"]["model_id"],
            "model_revision": base["asr_provenance"]["model_revision"],
            "config_fingerprint": base["asr_provenance"]["config_fingerprint_sha256"],
        },
        "candidate_model": {
            "model_id": cand["asr_provenance"]["model_id"],
            "model_revision": cand["asr_provenance"]["model_revision"],
            "config_fingerprint": cand["asr_provenance"]["config_fingerprint_sha256"],
            "cold_init_sec": cand["timing"]["cold_init_sec"],
            "total_inference_sec": cand["timing"]["total_inference_sec"],
            "total_audio_sec": cand["timing"]["total_audio_sec"],
            "corpus_rtf": cand["timing"]["corpus_rtf"],
            "resources": res,
        },
        "all_five_passed": all_pass,
        "overall_recommendation": (
            "RETAIN_SINGLE_MULTILINGUAL_MODEL_ADVANCE_TO_CREATOR_RECORDINGS"
            if all_pass
            else "KEEP_DEFAULT_AND_ADDRESS_FAILED_LANGUAGES"
        ),
        "rows": rows,
    }


def render_markdown(summary: dict[str, Any], baseline_rel: str, candidate_rel: str) -> str:
    b = summary["baseline_model"]
    c = summary["candidate_model"]
    res = c["resources"]
    lines = [
        "# M4 5-Language Multilingual Decision Comparison (Baseline vs Large-v3-Turbo)",
        "",
        f"- **Generated UTC:** `{summary['generated_utc']}`",
        f"- **Dataset:** `{summary['dataset_id']}` (`manifest_sha256: {summary['manifest_sha256']}`)",
        f"- **Baseline:** `{b['model_id']}` (`rev={b['model_revision']}`, `fp={b['config_fingerprint']}`)",
        f"- **Challenger:** `{c['model_id']}` (`rev={c['model_revision']}`, `fp={c['config_fingerprint']}`)",
        f"- **Challenger Timing & Memory:** Cold Init `{c['cold_init_sec']}s`, Total Infer `{c['total_inference_sec']}s` / `{c['total_audio_sec']}s` (`Corpus RTF {c['corpus_rtf']}x`), OS Peak WSET `{res.get('os_peak_wset_mb')} MB`, 50ms Sampled Max RSS `{res.get('rss_sampled_max_mb')} MB` (`{res.get('rss_sample_count')} samples`, scope `{res.get('memory_measurement_scope')}`)",
        f"- **Overall Recommendation:** `{summary['overall_recommendation']}` (production default remains unchanged during M4)",
        "",
        "## Five-Language Gate Table (Pre-Registered M4 v2.0 Criteria, Forced Mode)",
        "",
        "| Language | Baseline WER (S/D/I / ref w) | Turbo WER (S/D/I / ref w) | Improvement (pp) | Turbo CER (edits / ref c) | Empty / Failed / Total | RTF (infer / audio) | Peak Memory (OS WSET / 50ms RSS) | Timestamp Validity | Verdict |",
        "|---|---|---|---:|---|---|---|---|---|---|",
    ]
    for r in summary["rows"]:
        bs, bd, bi = r["baseline_sdi"]
        cs, cd, ci = r["candidate_sdi"]
        imp = f"{r['wer_improvement_pp']:+.2f} pp" if r["wer_improvement_pp"] is not None else "N/A"
        mem = f"{r['measured_os_peak_wset_mb']} MB / {r['measured_rss_sampled_max_mb']} MB"
        ts_str = f"`{r['timing_status']}` ({r['timing_valid_count']}/{r['total_count']} valid, {r['timing_invalid_count']} invalid)"
        lines.append(
            f"| `{r['language_code']}` | `{_fmt_pct(r['baseline_micro_wer'])}` ({bs}/{bd}/{bi} / {r['baseline_ref_words']}w) | "
            f"`{_fmt_pct(r['candidate_micro_wer'])}` ({cs}/{cd}/{ci} / {r['candidate_ref_words']}w) | "
            f"`{imp}` | `{_fmt_pct(r['candidate_micro_cer'])}` ({r['candidate_char_edits']}/{r['candidate_ref_chars']}c) | "
            f"`{r['empty_count']}` / `{r['failed_count']}` / `{r['total_count']}` | "
            f"`{r['rtf']}x` ({r['inference_sec']}s / {r['audio_sec']}s) | `{mem}` | {ts_str} | **`{r['verdict']}`** |"
        )
    lines.extend(
        [
            "",
            "## Evidence Paths",
            f"- Baseline JSON: `{baseline_rel}`",
            f"- Challenger JSON: `{candidate_rel}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare matched M4 baseline and challenger reports.")
    parser.add_argument("--baseline-json", type=Path, required=True)
    parser.add_argument("--candidate-json", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--md-out", type=Path, required=True)
    args = parser.parse_args()

    base = json.loads(args.baseline_json.read_text(encoding="utf-8"))
    cand = json.loads(args.candidate_json.read_text(encoding="utf-8"))
    summary = compare_reports(base, cand)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    md_text = render_markdown(summary, str(args.baseline_json).replace("\\", "/"), str(args.candidate_json).replace("\\", "/"))
    args.md_out.write_text(md_text, encoding="utf-8", newline="\n")

    print(f"Overall Recommendation: {summary['overall_recommendation']}")
    for r in summary["rows"]:
        print(
            f"  {r['language_code']}: base={_fmt_pct(r['baseline_micro_wer'])} -> "
            f"cand={_fmt_pct(r['candidate_micro_wer'])} ({r['wer_improvement_pp']:+.2f}pp) "
            f"RTF={r['rtf']}x empty={r['empty_count']}/{r['total_count']} verdict={r['verdict']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
