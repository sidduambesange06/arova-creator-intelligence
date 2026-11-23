# M3.1 Faster-Whisper Baseline Execution Report — Indic Creator Bench

- **Generated UTC:** 2026-11-19T10:11:45.220480+00:00
- **Git HEAD:** `8ca9fc25e502abad1a81785a9b94abfbd19dc062`
- **Execution Status:** `COMPLETED`
- **Dataset:** `indic_creator_bench_m2_smoke@1.0.0` (`split=smoke`, `license=CC-BY-4.0 (FLEURS, Conneau et al., 2022)`)
- **Manifest SHA-256:** `6fd397de981ab35e0ac884b9e37873630f5920ce0f0b886e3c33ac93a46b93a4`
- **Model:** `faster-whisper-small` (revision `local_pinned`, device `cpu`, compute_type `int8`)
- **Language Mode:** `forced` | **Normalization:** `v2_indic_unicode_safe_nfc`
- **Config Fingerprint:** `c15a5f1ca15efdd02fcc19a14c5925c87f7b38e8dd162da3fdabc2aea93ef6a4`
- **Sample Coverage:** `10/10` succeeded, `0` failed, `0` skipped

> **Scope Disclaimer:** This 10-clip FLEURS smoke corpus validates genuine local ASR execution, timing, and per-language baseline behavior. It does **not** establish population-level accuracy claims. Hinglish remains excluded (`NO_VERIFIED_REFERENCE`).

## Timing & Resource Measurements

| Metric | Value |
|---|---|
| Cold Model Init (s) | `1.92` |
| Total Inference Time (s) | `473.2134` |
| Total Audio Duration (s) | `134.3` |
| Corpus RTF (`inference / audio`) | `3.5236` |
| RSS Before (MB) | `90.88` |
| RSS After Init (MB) | `354.8` |
| RSS Peak (MB) | `377.18` |
| VRAM (MB) | `NOT_MEASURED` |
| Energy (Joules) | `NOT_MEASURED` |

## Per-Language Results

Aggregation method: micro (total edits / total ref tokens) and macro (unweighted mean of utterance rates).

| Language | Succeeded / Total | Failed | Audio (s) | Infer (s) | RTF | Micro WER | Micro CER | Macro WER | Macro CER |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `en_us` | 2/2 | 0 | 22.88 | 6.84 | 0.2991 | 0.09434 | 0.033639 | 0.075758 | 0.02957 |
| `hi_in` | 2/2 | 0 | 32.10 | 39.00 | 1.215 | 0.544118 | 0.209945 | 0.545093 | 0.207786 |
| `kn_in` | 2/2 | 0 | 35.88 | 222.41 | 6.1988 | 1.0 | 0.888298 | 1.0 | 0.907895 |
| `ta_in` | 2/2 | 0 | 22.74 | 28.83 | 1.2676 | 0.611111 | 0.186813 | 0.645485 | 0.188957 |
| `te_in` | 2/2 | 0 | 20.70 | 176.13 | 8.5089 | 1.0 | 0.83871 | 1.0 | 0.83896 |

**Corpus Micro WER / CER:** `0.599138` / `0.428752`  
**Corpus Macro WER / CER:** `0.653267` / `0.434633`

## Per-Utterance Evidence

| Utterance ID | Lang | Status | Audio (s) | Infer (s) | RTF | WER | CER | Words |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `fleurs_hi_in_1718` | `hi_in` | `COMPLETED` | 15.00 | 9.07 | 0.605 | 0.551724 | 0.195946 | 28 |
| `fleurs_hi_in_1836` | `hi_in` | `COMPLETED` | 17.10 | 29.93 | 1.75 | 0.538462 | 0.219626 | 39 |
| `fleurs_kn_in_1923` | `kn_in` | `COMPLETED` | 21.96 | 150.88 | 6.8709 | 1.0 | 0.815789 | 14 |
| `fleurs_kn_in_1970` | `kn_in` | `COMPLETED` | 13.92 | 71.53 | 5.1384 | 1.0 | 1.0 | 0 |
| `fleurs_ta_in_1740` | `ta_in` | `COMPLETED` | 7.74 | 20.36 | 2.6299 | 0.769231 | 0.2 | 14 |
| `fleurs_ta_in_1732` | `ta_in` | `COMPLETED` | 15.00 | 8.47 | 0.5646 | 0.521739 | 0.177914 | 22 |
| `fleurs_te_in_1666` | `te_in` | `COMPLETED` | 10.08 | 126.40 | 12.5398 | 1.0 | 0.869919 | 4 |
| `fleurs_te_in_2002` | `te_in` | `COMPLETED` | 10.62 | 49.73 | 4.6829 | 1.0 | 0.808 | 3 |
| `fleurs_en_us_1950` | `en_us` | `COMPLETED` | 11.46 | 3.90 | 0.3407 | 0.151515 | 0.05914 | 33 |
| `fleurs_en_us_1938` | `en_us` | `COMPLETED` | 11.42 | 2.94 | 0.2573 | 0.0 | 0.0 | 20 |
