# M4 Kannada Held-Out Baseline Report (faster-whisper-small)

- **Generated UTC:** 2026-11-19T18:22:23.161302+00:00
- **Git HEAD:** `1fd67346c4a2b544a806e4d172b80650607c3c70`
- **Execution Status:** `COMPLETED`
- **Dataset:** `m4_kn_eval_10clip@1.0.0` (`split=test`, `license=CC-BY-4.0 (FLEURS, Conneau et al., 2022)`)
- **Manifest SHA-256:** `f30350a95db7cfa8d19cc9d23d48ac4535a414cc02d30fea242c8398c579a5e0`
- **Model:** `faster-whisper-small` (revision `local_pinned`, device `cpu`, compute_type `int8`)
- **Language Mode:** `forced` | **Word Timestamps:** `False` | **Normalization:** `v2_indic_unicode_safe_nfc`
- **Config Fingerprint:** `c252e40088495b19912df18de917412c4a3507f3e161c4813fd887fae8e49225`
- **Sample Coverage:** `10/10` succeeded, `0` failed, `0` skipped (`coverage_complete=True`)

> **Scope Disclaimer:** 10-clip test partition (m4_kn_eval_10clip); does not establish population-level quality. Hinglish remains excluded (`NO_VERIFIED_REFERENCE`).

## Timing & Resource Measurements

| Metric | Value |
|---|---|
| Cold Model Init (s) | `1.7847` |
| Total Inference Time (s) | `616.6324` |
| Total Audio Duration (s) | `110.28` |
| Corpus RTF (`inference / audio`) | `5.5915` |
| RSS Before (MB) | `91.17` |
| RSS After Init (MB) | `354.62` |
| RSS Sampled Max (MB, `50ms` x `9871`) | `993.62` |
| OS Peak Working Set (MB) | `994.84` |
| RSS Peak Combined (MB, `single_process_no_children`) | `993.62` |
| VRAM (MB) | `NOT_MEASURED` |
| Energy (Joules) | `NOT_MEASURED` |

## Per-Language Results

Aggregation method: micro (total edits / total ref tokens) and macro (unweighted mean of utterance rates).

| Language | Succeeded / Total | Failed | Empty Hyp | Audio (s) | Infer (s) | RTF | Micro WER (S/D/I) | Micro CER | Macro WER | Macro CER |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| `kn_in` | 10/10 | 0 | 2 | 110.28 | 616.63 | 5.5915 | `1.073529` (93/43/10) | 0.93062 | 1.08 | 0.933783 |

**Corpus Micro WER / CER:** `1.073529` / `0.93062` (Word S/D/I: `93/43/10` over `136` ref words)  
**Corpus Macro WER / CER:** `1.08` / `0.933783` | **Empty Hypotheses:** `2` (`0.2`)

## Per-Utterance Evidence

| Utterance ID | Lang | Status | Audio (s) | Infer (s) | RTF | WER (S/D/I) | CER | Words |
|---|---|---|---:|---:|---:|---|---:|---:|
| `fleurs_168de341_kn_in_1972` | `kn_in` | `COMPLETED` | 11.34 | 78.16 | 6.8924 | `1.0` (14/0/0) | 0.981308 | 0 |
| `fleurs_168de341_kn_in_1663` | `kn_in` | `COMPLETED` | 18.96 | 81.37 | 4.2916 | `1.0` (12/9/0) | 0.834395 | 0 |
| `fleurs_168de341_kn_in_1755` | `kn_in` | `COMPLETED` | 4.32 | 83.01 | 19.2161 | `1.0` (6/1/0) | 0.893617 | 0 |
| `fleurs_168de341_kn_in_1844` | `kn_in` | `COMPLETED` | 11.16 | 77.03 | 6.9022 | `1.0` (12/0/0) | 0.901961 | 0 |
| `fleurs_168de341_kn_in_1917` | `kn_in` | `COMPLETED` | 11.88 | 71.33 | 6.0042 | `1.0` (9/5/0) | 0.872 | 0 |
| `fleurs_168de341_kn_in_1702` | `kn_in` | `COMPLETED` | 10.80 | 74.81 | 6.9271 | `1.333333` (15/0/5) | 0.900826 | 0 |
| `fleurs_168de341_kn_in_1693` | `kn_in` | `COMPLETED` | 11.34 | 8.21 | 0.7241 | `1.066667` (15/0/1) | 1.009901 | 0 |
| `fleurs_168de341_kn_in_1901` | `kn_in` | `COMPLETED` | 14.16 | 68.00 | 4.8023 | `1.0` (0/19/0) | 1.0 | 0 |
| `fleurs_168de341_kn_in_1828` | `kn_in` | `COMPLETED` | 9.00 | 7.06 | 0.7843 | `1.4` (10/0/4) | 0.94382 | 0 |
| `fleurs_168de341_kn_in_1677` | `kn_in` | `COMPLETED` | 7.32 | 67.65 | 9.2414 | `1.0` (0/9/0) | 1.0 | 0 |
