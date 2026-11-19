"""CLI runner for M3.1 Faster-Whisper Baseline Execution on Indic Creator Bench.

Executes genuine local Faster-Whisper inference through FasterWhisperProvider
against the validated M2 smoke corpus and writes honest JSON + Markdown reports.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ai.evaluation.asr_baseline import run_indic_asr_baseline
from app.ai.providers.transcription import FasterWhisperProvider


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "UNKNOWN"


def _render_markdown(report: dict, git_sha: str, dataset_root: Path) -> str:
    ds = report["dataset"]
    prov = report["asr_provenance"]
    batch = report["batch_provenance"]
    timing = report["timing"]
    res = report["resources"]
    cm = report["corpus_metrics"]

    lines = [
        "# M3.1 Faster-Whisper Baseline Execution Report — Indic Creator Bench",
        "",
        f"- **Generated UTC:** {datetime.now(timezone.utc).isoformat()}",
        f"- **Git HEAD:** `{git_sha}`",
        f"- **Execution Status:** `{report['execution_status']}`",
        f"- **Dataset:** `{ds['dataset_id']}@{ds['dataset_version']}` (`split={ds['split']}`, `license={ds['license_summary']}`)",
        f"- **Manifest SHA-256:** `{ds['manifest_sha256']}`",
        f"- **Model:** `{prov['model_id']}` (revision `{prov['model_revision']}`, device `{prov['device']}`, compute_type `{prov['compute_type']}`)",
        f"- **Language Mode:** `{prov['language_mode']}` | **Normalization:** `{prov['normalization_policy_version']}`",
        f"- **Config Fingerprint:** `{prov['config_fingerprint_sha256']}`",
        f"- **Sample Coverage:** `{batch['succeeded_items']}/{batch['total_items']}` succeeded, `{batch['failed_items']}` failed, `{batch['skipped_items']}` skipped",
        "",
        "> **Scope Disclaimer:** This 10-clip FLEURS smoke corpus validates genuine local ASR execution, timing, and per-language baseline behavior. It does **not** establish population-level accuracy claims. Hinglish remains excluded (`NO_VERIFIED_REFERENCE`).",
        "",
        "## Timing & Resource Measurements",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Cold Model Init (s) | `{timing['cold_init_sec']}` |",
        f"| Total Inference Time (s) | `{timing['total_inference_sec']}` |",
        f"| Total Audio Duration (s) | `{timing['total_audio_sec']}` |",
        f"| Corpus RTF (`inference / audio`) | `{timing['corpus_rtf']}` |",
        f"| RSS Before (MB) | `{res['rss_before_mb']}` |",
        f"| RSS After Init (MB) | `{res['rss_after_init_mb']}` |",
        f"| RSS Peak (MB) | `{res['rss_peak_mb']}` |",
        f"| VRAM (MB) | `{res['vram_mb']}` |",
        f"| Energy (Joules) | `{res['energy_joules']}` |",
        "",
        "## Per-Language Results",
        "",
        f"Aggregation method: {cm['aggregation_method']}.",
        "",
        "| Language | Succeeded / Total | Failed | Audio (s) | Infer (s) | RTF | Micro WER | Micro CER | Macro WER | Macro CER |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for lang, stats in report["per_language"].items():
        micro = stats["micro"]
        lines.append(
            f"| `{lang}` | {stats['succeeded_count']}/{stats['total_count']} | {stats['failed_count']} | "
            f"{stats['audio_sec']:.2f} | {stats['inference_sec']:.2f} | {stats['rtf']} | "
            f"{micro['corpus_wer']} | {micro['corpus_cer']} | {stats['macro_wer']} | {stats['macro_cer']} |"
        )
    lines.extend(
        [
            "",
            f"**Corpus Micro WER / CER:** `{cm['micro']['corpus_wer']}` / `{cm['micro']['corpus_cer']}`  ",
            f"**Corpus Macro WER / CER:** `{cm['macro_wer']}` / `{cm['macro_cer']}`",
            "",
            "## Per-Utterance Evidence",
            "",
            "| Utterance ID | Lang | Status | Audio (s) | Infer (s) | RTF | WER | CER | Words |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for u in report["utterances"]:
        m = u.get("metrics") or {}
        lines.append(
            f"| `{u['utterance_id']}` | `{u['language_code']}` | `{u['status']}` | "
            f"{u['duration_sec']:.2f} | {u['inference_sec']:.2f} | {u['rtf']} | "
            f"{m.get('wer')} | {m.get('cer')} | {u.get('word_count', 0)} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run M3.1 Faster-Whisper baseline on validated Indic Creator Bench.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=REPO_ROOT / "data" / "indic_creator_bench" / "m2_smoke_10clip",
    )
    parser.add_argument("--model-size-or-path", type=str, default="small")
    parser.add_argument("--model-id", type=str, default="faster-whisper-small")
    parser.add_argument("--model-revision", type=str, default="local_pinned")
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--compute-type", type=str, default="int8")
    parser.add_argument("--language-mode", type=str, choices=("forced", "auto"), default="forced")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--vad-filter", action="store_true")
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=REPO_ROOT / "reports" / "product-acceptance" / "M3_BASELINE_EXECUTION_REPORT.json",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=REPO_ROOT / "reports" / "product-acceptance" / "M3_BASELINE_EXECUTION_REPORT.md",
    )
    args = parser.parse_args()

    provider = FasterWhisperProvider(
        model_size_or_path=args.model_size_or_path,
        compute_type=args.compute_type,
        device=args.device,
        model_id=args.model_id,
        model_revision=args.model_revision,
    )

    report = run_indic_asr_baseline(
        args.dataset_root,
        provider,
        model_id=args.model_id,
        model_revision=args.model_revision,
        device=args.device,
        compute_type=args.compute_type,
        language_mode=args.language_mode,
        beam_size=args.beam_size,
        vad_filter=args.vad_filter,
        word_timestamps=True,
        checkpoint_path=args.checkpoint,
    )

    git_sha = _git_head()
    report["git_head"] = git_sha
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    args.md_out.write_text(_render_markdown(report, git_sha, args.dataset_root), encoding="utf-8", newline="\n")

    print(f"Execution Status   : {report['execution_status']}")
    print(f"Model              : {args.model_id} ({args.device}/{args.compute_type})")
    print(f"Succeeded / Total  : {report['batch_provenance']['succeeded_items']} / {report['batch_provenance']['total_items']}")
    print(f"Cold Init / Infer  : {report['timing']['cold_init_sec']}s / {report['timing']['total_inference_sec']}s")
    print(f"Corpus RTF         : {report['timing']['corpus_rtf']}")
    print(f"RSS Peak (MB)      : {report['resources']['rss_peak_mb']}")
    print(f"JSON Report        : {args.json_out}")
    print(f"Markdown Report    : {args.md_out}")
    return 0 if report["execution_status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
