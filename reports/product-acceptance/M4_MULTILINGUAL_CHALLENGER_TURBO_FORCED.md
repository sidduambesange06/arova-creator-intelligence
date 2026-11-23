# M4 5-Language Held-Out Challenger Report (faster-whisper-large-v3-turbo, forced, cpu/int8/t4)

- **Generated UTC:** 2026-11-20T09:02:27.660500+00:00
- **Git HEAD:** `e61b205d709b0b8e62a41d8dcd15c019dc948047`
- **Execution Status:** `COMPLETED`
- **Dataset:** `m4_multilingual_eval_50clip@1.0.0` (`split=test`, `license=CC-BY-4.0 (FLEURS, Conneau et al., 2022)`)
- **Manifest SHA-256:** `4426c1e10c85c5caf304db120cd83e445740a077778fdde7086647749c9a1480`
- **Model:** `faster-whisper-large-v3-turbo` (revision `4df90f75321148c3a29a9e2351b7ddf8f5b115a8`, device `cpu`, compute_type `int8`)
- **Language Mode:** `forced` | **Word Timestamps:** `False` | **CPU Threads:** `4` | **Normalization:** `v2_indic_unicode_safe_nfc`
- **Config Fingerprint:** `53f5b47969d4f8d811e7631e8375ca620ada27b7d3989ec4f5a2d949c75aec60`
- **Sample Coverage:** `50/50` succeeded, `0` failed, `0` skipped (`coverage_complete=True`)
- **Timing Validity (Independent of WER):** `segment_only_valid`

> **Scope Disclaimer:** 50-clip test partition (m4_multilingual_eval_50clip); does not establish population-level quality. Hinglish remains excluded (`NO_VERIFIED_REFERENCE`).

## Timing & Resource Measurements

| Metric | Value |
|---|---|
| Cold Model Init (s) | `5.2957` |
| Total Inference Time (s) | `808.1968` |
| Total Audio Duration (s) | `563.92` |
| Corpus RTF (`inference / audio`) | `1.4332` |
| RSS Before (MB) | `90.95` |
| RSS After Init (MB) | `911.73` |
| RSS Sampled Max (MB, `50ms` x `12992`) | `1823.61` |
| OS Peak Working Set (MB) | `1917.66` |
| RSS Peak Combined (MB, `single_process_no_children`) | `1823.61` |
| VRAM (MB) | `NOT_MEASURED` |
| Energy (Joules) | `NOT_MEASURED` |

## Per-Language Results

Aggregation method: micro (total edits / total ref tokens) and macro (unweighted mean of utterance rates).

| Language | Succeeded / Total | Failed | Empty Hyp | Ref Words | Audio (s) | Infer (s) | RTF | Micro WER (S/D/I) | Micro CER | Macro WER | Macro CER | Timing Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `en_us` | 10/10 | 0 | 0 | 200 | 83.56 | 114.48 | 1.3701 | `0.075` (11/0/4) | 0.033575 | 0.076085 | 0.041985 | `segment_only_valid` |
| `hi_in` | 10/10 | 0 | 0 | 232 | 118.50 | 180.51 | 1.5233 | `0.383621` (81/0/8) | 0.198052 | 0.388853 | 0.192996 | `segment_only_valid` |
| `kn_in` | 10/10 | 0 | 0 | 136 | 110.28 | 150.17 | 1.3617 | `0.573529` (66/9/3) | 0.19334 | 0.577548 | 0.220986 | `segment_only_valid` |
| `ta_in` | 10/10 | 0 | 0 | 145 | 118.50 | 167.65 | 1.4147 | `0.765517` (94/9/8) | 0.333333 | 0.739849 | 0.272944 | `segment_only_valid` |
| `te_in` | 10/10 | 0 | 0 | 193 | 133.08 | 195.39 | 1.4682 | `0.854922` (124/36/5) | 0.398311 | 0.838091 | 0.369486 | `segment_only_valid` |

**Corpus Micro WER / CER:** `0.505519` / `0.245431` (Word S/D/I: `376/54/28` over `906` ref words)  
**Corpus Macro WER / CER:** `0.524085` / `0.219679` | **Empty Hypotheses:** `0` (`0.0`)

## Per-Utterance Evidence

| Utterance ID | Lang | Status | Audio (s) | Infer (s) | RTF | WER (S/D/I) | CER | Words |
|---|---|---|---:|---:|---:|---|---:|---:|
| `fleurs_168de341_en_us_1810` | `en_us` | `COMPLETED` | 11.34 | 11.67 | 1.0294 | `0.0` (0/0/0) | 0.0 | 0 |
| `fleurs_168de341_en_us_1791` | `en_us` | `COMPLETED` | 4.50 | 11.54 | 2.5649 | `0.0` (0/0/0) | 0.0 | 0 |
| `fleurs_168de341_en_us_1865` | `en_us` | `COMPLETED` | 7.50 | 11.27 | 1.5028 | `0.058824` (1/0/0) | 0.026087 | 0 |
| `fleurs_168de341_en_us_1808` | `en_us` | `COMPLETED` | 7.68 | 11.27 | 1.4677 | `0.0` (0/0/0) | 0.0 | 0 |
| `fleurs_168de341_en_us_2004` | `en_us` | `COMPLETED` | 6.48 | 11.31 | 1.7454 | `0.117647` (2/0/0) | 0.131313 | 0 |
| `fleurs_168de341_en_us_1885` | `en_us` | `COMPLETED` | 8.94 | 11.24 | 1.2571 | `0.294118` (4/0/1) | 0.222222 | 0 |
| `fleurs_168de341_en_us_1744` | `en_us` | `COMPLETED` | 5.64 | 11.25 | 1.9939 | `0.133333` (1/0/1) | 0.022472 | 0 |
| `fleurs_168de341_en_us_1697` | `en_us` | `COMPLETED` | 6.36 | 11.26 | 1.77 | `0.0` (0/0/0) | 0.0 | 0 |
| `fleurs_168de341_en_us_1984` | `en_us` | `COMPLETED` | 9.48 | 11.61 | 1.2249 | `0.035714` (1/0/0) | 0.005988 | 0 |
| `fleurs_168de341_en_us_1682` | `en_us` | `COMPLETED` | 15.64 | 12.06 | 0.7712 | `0.121212` (2/0/2) | 0.011765 | 0 |
| `fleurs_168de341_hi_in_1923` | `hi_in` | `COMPLETED` | 19.38 | 19.37 | 0.9994 | `0.5` (14/0/2) | 0.176471 | 0 |
| `fleurs_168de341_hi_in_1827` | `hi_in` | `COMPLETED` | 7.80 | 13.70 | 1.7563 | `0.380952` (5/0/3) | 0.091837 | 0 |
| `fleurs_168de341_hi_in_1828` | `hi_in` | `COMPLETED` | 13.20 | 14.23 | 1.0778 | `0.333333` (6/0/0) | 0.134615 | 0 |
| `fleurs_168de341_hi_in_2002` | `hi_in` | `COMPLETED` | 7.56 | 12.46 | 1.6479 | `0.352941` (6/0/0) | 0.295455 | 0 |
| `fleurs_168de341_hi_in_1945` | `hi_in` | `COMPLETED` | 5.94 | 13.04 | 2.1955 | `0.333333` (4/0/1) | 0.1125 | 0 |
| `fleurs_168de341_hi_in_1981` | `hi_in` | `COMPLETED` | 12.78 | 13.88 | 1.0864 | `0.26087` (5/0/1) | 0.072727 | 0 |
| `fleurs_168de341_hi_in_1953` | `hi_in` | `COMPLETED` | 8.40 | 12.83 | 1.5275 | `0.307692` (3/0/1) | 0.090909 | 0 |
| `fleurs_168de341_hi_in_1939` | `hi_in` | `COMPLETED` | 7.56 | 47.61 | 6.2982 | `1.0` (23/0/0) | 0.689076 | 0 |
| `fleurs_168de341_hi_in_1896` | `hi_in` | `COMPLETED` | 19.44 | 18.59 | 0.9565 | `0.263158` (10/0/0) | 0.231884 | 0 |
| `fleurs_168de341_hi_in_1794` | `hi_in` | `COMPLETED` | 16.44 | 14.79 | 0.8998 | `0.15625` (5/0/0) | 0.034483 | 0 |
| `fleurs_168de341_kn_in_1972` | `kn_in` | `COMPLETED` | 11.34 | 15.98 | 1.409 | `0.428571` (5/1/0) | 0.102804 | 0 |
| `fleurs_168de341_kn_in_1663` | `kn_in` | `COMPLETED` | 18.96 | 17.39 | 0.9174 | `0.666667` (11/3/0) | 0.305732 | 0 |
| `fleurs_168de341_kn_in_1755` | `kn_in` | `COMPLETED` | 4.32 | 11.02 | 2.5515 | `1.0` (7/0/0) | 0.914894 | 0 |
| `fleurs_168de341_kn_in_1844` | `kn_in` | `COMPLETED` | 11.16 | 15.01 | 1.3447 | `0.583333` (5/1/1) | 0.068627 | 0 |
| `fleurs_168de341_kn_in_1917` | `kn_in` | `COMPLETED` | 11.88 | 16.26 | 1.3683 | `0.857143` (11/0/1) | 0.12 | 0 |
| `fleurs_168de341_kn_in_1702` | `kn_in` | `COMPLETED` | 10.80 | 16.39 | 1.5178 | `0.4` (4/2/0) | 0.082645 | 0 |
| `fleurs_168de341_kn_in_1693` | `kn_in` | `COMPLETED` | 11.34 | 14.75 | 1.301 | `0.333333` (5/0/0) | 0.178218 | 0 |
| `fleurs_168de341_kn_in_1901` | `kn_in` | `COMPLETED` | 14.16 | 16.90 | 1.1938 | `0.684211` (11/2/0) | 0.283871 | 0 |
| `fleurs_168de341_kn_in_1828` | `kn_in` | `COMPLETED` | 9.00 | 13.45 | 1.4949 | `0.6` (5/0/1) | 0.101124 | 0 |
| `fleurs_168de341_kn_in_1677` | `kn_in` | `COMPLETED` | 7.32 | 13.01 | 1.7772 | `0.222222` (2/0/0) | 0.051948 | 0 |
| `fleurs_168de341_ta_in_1980` | `ta_in` | `COMPLETED` | 12.20 | 12.97 | 1.0635 | `0.75` (9/0/3) | 0.116438 | 0 |
| `fleurs_168de341_ta_in_1861` | `ta_in` | `COMPLETED` | 11.76 | 12.79 | 1.0876 | `0.666667` (8/0/2) | 0.177778 | 0 |
| `fleurs_168de341_ta_in_1854` | `ta_in` | `COMPLETED` | 15.60 | 12.05 | 0.7723 | `0.857143` (11/0/1) | 0.368421 | 0 |
| `fleurs_168de341_ta_in_1858` | `ta_in` | `COMPLETED` | 11.20 | 12.49 | 1.115 | `0.764706` (11/2/0) | 0.174242 | 0 |
| `fleurs_168de341_ta_in_1795` | `ta_in` | `COMPLETED` | 19.68 | 56.96 | 2.8943 | `1.0` (18/7/0) | 0.876448 | 0 |
| `fleurs_168de341_ta_in_1959` | `ta_in` | `COMPLETED` | 10.32 | 12.49 | 1.2103 | `0.615385` (7/0/1) | 0.162963 | 0 |
| `fleurs_168de341_ta_in_1885` | `ta_in` | `COMPLETED` | 11.64 | 11.29 | 0.9699 | `0.714286` (10/0/0) | 0.494118 | 0 |
| `fleurs_168de341_ta_in_1796` | `ta_in` | `COMPLETED` | 10.80 | 11.89 | 1.1006 | `0.454545` (5/0/0) | 0.051546 | 0 |
| `fleurs_168de341_ta_in_1837` | `ta_in` | `COMPLETED` | 8.28 | 13.07 | 1.5782 | `0.909091` (10/0/0) | 0.204918 | 0 |
| `fleurs_168de341_ta_in_2005` | `ta_in` | `COMPLETED` | 7.02 | 11.65 | 1.6597 | `0.666667` (5/0/1) | 0.102564 | 0 |
| `fleurs_168de341_te_in_1881` | `te_in` | `COMPLETED` | 10.92 | 17.54 | 1.6063 | `0.9` (13/4/1) | 0.335484 | 0 |
| `fleurs_168de341_te_in_1945` | `te_in` | `COMPLETED` | 8.52 | 14.56 | 1.7091 | `0.7` (6/0/1) | 0.280488 | 0 |
| `fleurs_168de341_te_in_1690` | `te_in` | `COMPLETED` | 19.62 | 17.22 | 0.8779 | `0.896552` (18/8/0) | 0.593458 | 0 |
| `fleurs_168de341_te_in_1743` | `te_in` | `COMPLETED` | 22.02 | 34.94 | 1.5868 | `1.0` (27/3/0) | 0.478927 | 0 |
| `fleurs_168de341_te_in_1938` | `te_in` | `COMPLETED` | 14.52 | 16.80 | 1.1567 | `0.65` (5/7/1) | 0.267974 | 0 |
| `fleurs_168de341_te_in_1995` | `te_in` | `COMPLETED` | 15.00 | 17.14 | 1.1427 | `0.8` (9/7/0) | 0.43299 | 0 |
| `fleurs_168de341_te_in_1683` | `te_in` | `COMPLETED` | 13.98 | 16.83 | 1.2035 | `0.869565` (14/6/0) | 0.392857 | 0 |
| `fleurs_168de341_te_in_1921` | `te_in` | `COMPLETED` | 6.78 | 24.94 | 3.6783 | `0.823529` (13/1/0) | 0.297521 | 0 |
| `fleurs_168de341_te_in_1895` | `te_in` | `COMPLETED` | 8.76 | 15.38 | 1.7561 | `0.818182` (8/0/1) | 0.223404 | 0 |
| `fleurs_168de341_te_in_1796` | `te_in` | `COMPLETED` | 12.96 | 20.03 | 1.5459 | `0.923077` (11/0/1) | 0.391753 | 0 |
