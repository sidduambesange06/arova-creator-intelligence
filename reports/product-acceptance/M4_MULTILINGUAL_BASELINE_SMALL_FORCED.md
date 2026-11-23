# M4 5-Language Held-Out Baseline Report (faster-whisper-small, forced, cpu/int8/t4)

- **Generated UTC:** 2026-11-20T08:28:17.277664+00:00
- **Git HEAD:** `7b5dc8d86f91b597e343a5eb672180fb838917be`
- **Execution Status:** `COMPLETED`
- **Dataset:** `m4_multilingual_eval_50clip@1.0.0` (`split=test`, `license=CC-BY-4.0 (FLEURS, Conneau et al., 2022)`)
- **Manifest SHA-256:** `4426c1e10c85c5caf304db120cd83e445740a077778fdde7086647749c9a1480`
- **Model:** `faster-whisper-small` (revision `536b0662742c02347bc0e980a01041f333bce120`, device `cpu`, compute_type `int8`)
- **Language Mode:** `forced` | **Word Timestamps:** `False` | **CPU Threads:** `4` | **Normalization:** `v2_indic_unicode_safe_nfc`
- **Config Fingerprint:** `ca6e822bca18510103fbf7fdd798e61f762b938dc9b74f18adc3e947346fa153`
- **Sample Coverage:** `50/50` succeeded, `0` failed, `0` skipped (`coverage_complete=True`)
- **Timing Validity (Independent of WER):** `invalid_timing`

> **Scope Disclaimer:** 50-clip test partition (m4_multilingual_eval_50clip); does not establish population-level quality. Hinglish remains excluded (`NO_VERIFIED_REFERENCE`).

## Timing & Resource Measurements

| Metric | Value |
|---|---|
| Cold Model Init (s) | `1.8633` |
| Total Inference Time (s) | `1587.0527` |
| Total Audio Duration (s) | `563.92` |
| Corpus RTF (`inference / audio`) | `2.8143` |
| RSS Before (MB) | `91.36` |
| RSS After Init (MB) | `355.44` |
| RSS Sampled Max (MB, `50ms` x `25415`) | `994.82` |
| OS Peak Working Set (MB) | `995.09` |
| RSS Peak Combined (MB, `single_process_no_children`) | `994.82` |
| VRAM (MB) | `NOT_MEASURED` |
| Energy (Joules) | `NOT_MEASURED` |

## Per-Language Results

Aggregation method: micro (total edits / total ref tokens) and macro (unweighted mean of utterance rates).

| Language | Succeeded / Total | Failed | Empty Hyp | Ref Words | Audio (s) | Infer (s) | RTF | Micro WER (S/D/I) | Micro CER | Macro WER | Macro CER | Timing Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `en_us` | 10/10 | 0 | 0 | 200 | 83.56 | 35.46 | 0.4244 | `0.11` (16/0/6) | 0.062613 | 0.114873 | 0.06935 | `invalid_timing` |
| `hi_in` | 10/10 | 0 | 0 | 232 | 118.50 | 104.38 | 0.8809 | `0.594828` (112/7/19) | 0.237825 | 0.595401 | 0.233976 | `segment_only_valid` |
| `kn_in` | 10/10 | 0 | 2 | 136 | 110.28 | 590.08 | 5.3508 | `1.110294` (88/48/15) | 0.940796 | 1.102381 | 0.932923 | `invalid_timing` |
| `ta_in` | 10/10 | 0 | 0 | 145 | 118.50 | 165.41 | 1.3958 | `0.655172` (77/7/11) | 0.159657 | 0.65453 | 0.175375 | `segment_only_valid` |
| `te_in` | 10/10 | 0 | 3 | 193 | 133.08 | 691.72 | 5.1977 | `1.160622` (64/129/31) | 0.995452 | 1.17 | 0.997196 | `invalid_timing` |

**Corpus Micro WER / CER:** `0.695364` / `0.499519` (Word S/D/I: `357/191/82` over `906` ref words)  
**Corpus Macro WER / CER:** `0.727437` / `0.481764` | **Empty Hypotheses:** `5` (`0.1`)

## Per-Utterance Evidence

| Utterance ID | Lang | Status | Audio (s) | Infer (s) | RTF | WER (S/D/I) | CER | Words |
|---|---|---|---:|---:|---:|---|---:|---:|
| `fleurs_168de341_en_us_1810` | `en_us` | `COMPLETED` | 11.34 | 3.16 | 0.279 | `0.0` (0/0/0) | 0.0 | 0 |
| `fleurs_168de341_en_us_1791` | `en_us` | `COMPLETED` | 4.50 | 2.71 | 0.6019 | `0.333333` (3/0/1) | 0.138889 | 0 |
| `fleurs_168de341_en_us_1865` | `en_us` | `COMPLETED` | 7.50 | 3.00 | 0.4004 | `0.058824` (1/0/0) | 0.026087 | 0 |
| `fleurs_168de341_en_us_1808` | `en_us` | `COMPLETED` | 7.68 | 3.71 | 0.4828 | `0.0` (0/0/0) | 0.0 | 0 |
| `fleurs_168de341_en_us_2004` | `en_us` | `COMPLETED` | 6.48 | 4.30 | 0.6632 | `0.117647` (2/0/0) | 0.131313 | 0 |
| `fleurs_168de341_en_us_1885` | `en_us` | `COMPLETED` | 8.94 | 3.58 | 0.4007 | `0.294118` (4/0/1) | 0.222222 | 0 |
| `fleurs_168de341_en_us_1744` | `en_us` | `COMPLETED` | 5.64 | 3.13 | 0.5543 | `0.066667` (1/0/0) | 0.033708 | 0 |
| `fleurs_168de341_en_us_1697` | `en_us` | `COMPLETED` | 6.36 | 3.38 | 0.5317 | `0.0` (0/0/0) | 0.0 | 0 |
| `fleurs_168de341_en_us_1984` | `en_us` | `COMPLETED` | 9.48 | 4.07 | 0.4293 | `0.035714` (1/0/0) | 0.005988 | 0 |
| `fleurs_168de341_en_us_1682` | `en_us` | `COMPLETED` | 15.64 | 4.42 | 0.2827 | `0.242424` (4/0/4) | 0.135294 | 0 |
| `fleurs_168de341_hi_in_1923` | `hi_in` | `COMPLETED` | 19.38 | 13.89 | 0.7165 | `0.6875` (20/0/2) | 0.289216 | 0 |
| `fleurs_168de341_hi_in_1827` | `hi_in` | `COMPLETED` | 7.80 | 5.58 | 0.7148 | `0.857143` (14/0/4) | 0.234694 | 0 |
| `fleurs_168de341_hi_in_1828` | `hi_in` | `COMPLETED` | 13.20 | 7.81 | 0.5918 | `0.555556` (8/0/2) | 0.173077 | 0 |
| `fleurs_168de341_hi_in_2002` | `hi_in` | `COMPLETED` | 7.56 | 6.67 | 0.8825 | `0.470588` (8/0/0) | 0.125 | 0 |
| `fleurs_168de341_hi_in_1945` | `hi_in` | `COMPLETED` | 5.94 | 5.84 | 0.9824 | `0.466667` (5/0/2) | 0.125 | 0 |
| `fleurs_168de341_hi_in_1981` | `hi_in` | `COMPLETED` | 12.78 | 6.10 | 0.4771 | `0.565217` (9/1/3) | 0.190909 | 0 |
| `fleurs_168de341_hi_in_1953` | `hi_in` | `COMPLETED` | 8.40 | 4.83 | 0.5752 | `0.461538` (4/0/2) | 0.194805 | 0 |
| `fleurs_168de341_hi_in_1939` | `hi_in` | `COMPLETED` | 7.56 | 33.79 | 4.4698 | `1.0` (17/6/0) | 0.731092 | 0 |
| `fleurs_168de341_hi_in_1896` | `hi_in` | `COMPLETED` | 19.44 | 12.55 | 0.6456 | `0.421053` (13/0/3) | 0.144928 | 0 |
| `fleurs_168de341_hi_in_1794` | `hi_in` | `COMPLETED` | 16.44 | 7.33 | 0.446 | `0.46875` (14/0/1) | 0.131034 | 0 |
| `fleurs_168de341_kn_in_1972` | `kn_in` | `COMPLETED` | 11.34 | 71.44 | 6.2994 | `1.0` (5/9/0) | 0.831776 | 0 |
| `fleurs_168de341_kn_in_1663` | `kn_in` | `COMPLETED` | 18.96 | 70.98 | 3.7437 | `1.285714` (21/0/6) | 1.025478 | 0 |
| `fleurs_168de341_kn_in_1755` | `kn_in` | `COMPLETED` | 4.32 | 89.17 | 20.6406 | `1.0` (4/3/0) | 0.829787 | 0 |
| `fleurs_168de341_kn_in_1844` | `kn_in` | `COMPLETED` | 11.16 | 73.54 | 6.5894 | `1.0` (4/8/0) | 0.970588 | 0 |
| `fleurs_168de341_kn_in_1917` | `kn_in` | `COMPLETED` | 11.88 | 77.13 | 6.4924 | `1.071429` (14/0/1) | 0.784 | 0 |
| `fleurs_168de341_kn_in_1702` | `kn_in` | `COMPLETED` | 10.80 | 75.28 | 6.9705 | `1.2` (15/0/3) | 0.933884 | 0 |
| `fleurs_168de341_kn_in_1693` | `kn_in` | `COMPLETED` | 11.34 | 7.41 | 0.6538 | `1.066667` (15/0/1) | 1.009901 | 0 |
| `fleurs_168de341_kn_in_1901` | `kn_in` | `COMPLETED` | 14.16 | 55.83 | 3.9427 | `1.0` (0/19/0) | 1.0 | 0 |
| `fleurs_168de341_kn_in_1828` | `kn_in` | `COMPLETED` | 9.00 | 5.86 | 0.6508 | `1.4` (10/0/4) | 0.94382 | 0 |
| `fleurs_168de341_kn_in_1677` | `kn_in` | `COMPLETED` | 7.32 | 63.45 | 8.6677 | `1.0` (0/9/0) | 1.0 | 0 |
| `fleurs_168de341_ta_in_1980` | `ta_in` | `COMPLETED` | 12.20 | 7.75 | 0.6349 | `0.6875` (9/0/2) | 0.143836 | 0 |
| `fleurs_168de341_ta_in_1861` | `ta_in` | `COMPLETED` | 11.76 | 7.39 | 0.6288 | `0.6` (7/0/2) | 0.148148 | 0 |
| `fleurs_168de341_ta_in_1854` | `ta_in` | `COMPLETED` | 15.60 | 5.09 | 0.326 | `0.714286` (8/2/0) | 0.2 | 0 |
| `fleurs_168de341_ta_in_1858` | `ta_in` | `COMPLETED` | 11.20 | 6.84 | 0.611 | `0.705882` (9/3/0) | 0.151515 | 0 |
| `fleurs_168de341_ta_in_1795` | `ta_in` | `COMPLETED` | 19.68 | 97.09 | 4.9335 | `0.64` (13/1/2) | 0.104247 | 0 |
| `fleurs_168de341_ta_in_1959` | `ta_in` | `COMPLETED` | 10.32 | 9.55 | 0.9253 | `0.615385` (7/0/1) | 0.096296 | 0 |
| `fleurs_168de341_ta_in_1885` | `ta_in` | `COMPLETED` | 11.64 | 7.14 | 0.6133 | `0.642857` (8/1/0) | 0.423529 | 0 |
| `fleurs_168de341_ta_in_1796` | `ta_in` | `COMPLETED` | 10.80 | 7.12 | 0.6593 | `0.363636` (4/0/0) | 0.051546 | 0 |
| `fleurs_168de341_ta_in_1837` | `ta_in` | `COMPLETED` | 8.28 | 10.39 | 1.2548 | `0.909091` (8/0/2) | 0.229508 | 0 |
| `fleurs_168de341_ta_in_2005` | `ta_in` | `COMPLETED` | 7.02 | 7.05 | 1.0045 | `0.666667` (4/0/2) | 0.205128 | 0 |
| `fleurs_168de341_te_in_1881` | `te_in` | `COMPLETED` | 10.92 | 86.86 | 7.9538 | `2.4` (20/0/28) | 1.419355 | 0 |
| `fleurs_168de341_te_in_1945` | `te_in` | `COMPLETED` | 8.52 | 58.12 | 6.8213 | `1.3` (10/0/3) | 0.97561 | 0 |
| `fleurs_168de341_te_in_1690` | `te_in` | `COMPLETED` | 19.62 | 59.73 | 3.0442 | `1.0` (0/29/0) | 1.0 | 0 |
| `fleurs_168de341_te_in_1743` | `te_in` | `COMPLETED` | 22.02 | 55.91 | 2.5389 | `1.0` (14/16/0) | 0.950192 | 0 |
| `fleurs_168de341_te_in_1938` | `te_in` | `COMPLETED` | 14.52 | 46.28 | 3.1871 | `1.0` (1/19/0) | 0.869281 | 0 |
| `fleurs_168de341_te_in_1995` | `te_in` | `COMPLETED` | 15.00 | 134.08 | 8.9385 | `1.0` (5/15/0) | 0.979381 | 0 |
| `fleurs_168de341_te_in_1683` | `te_in` | `COMPLETED` | 13.98 | 62.26 | 4.4538 | `1.0` (8/15/0) | 0.869048 | 0 |
| `fleurs_168de341_te_in_1921` | `te_in` | `COMPLETED` | 6.78 | 69.21 | 10.2078 | `1.0` (6/11/0) | 0.909091 | 0 |
| `fleurs_168de341_te_in_1895` | `te_in` | `COMPLETED` | 8.76 | 61.53 | 7.0244 | `1.0` (0/11/0) | 1.0 | 0 |
| `fleurs_168de341_te_in_1796` | `te_in` | `COMPLETED` | 12.96 | 57.75 | 4.4559 | `1.0` (0/13/0) | 1.0 | 0 |
