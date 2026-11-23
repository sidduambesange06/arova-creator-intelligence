# M4 5-Language Multilingual Decision Comparison (Baseline vs Large-v3-Turbo)

- **Generated UTC:** `2026-11-20T09:02:49.883626+00:00`
- **Dataset:** `m4_multilingual_eval_50clip` (`manifest_sha256: 4426c1e10c85c5caf304db120cd83e445740a077778fdde7086647749c9a1480`)
- **Baseline:** `faster-whisper-small` (`rev=536b0662742c02347bc0e980a01041f333bce120`, `fp=ca6e822bca18510103fbf7fdd798e61f762b938dc9b74f18adc3e947346fa153`)
- **Challenger:** `faster-whisper-large-v3-turbo` (`rev=4df90f75321148c3a29a9e2351b7ddf8f5b115a8`, `fp=53f5b47969d4f8d811e7631e8375ca620ada27b7d3989ec4f5a2d949c75aec60`)
- **Challenger Timing & Memory:** Cold Init `5.2957s`, Total Infer `808.1968s` / `563.92s` (`Corpus RTF 1.4332x`), OS Peak WSET `1917.66 MB`, 50ms Sampled Max RSS `1823.61 MB` (`12992 samples`, scope `single_process_no_children`)
- **Overall Recommendation:** `KEEP_DEFAULT_AND_ADDRESS_FAILED_LANGUAGES` (production default remains unchanged during M4)

## Five-Language Gate Table (Pre-Registered M4 v2.0 Criteria, Forced Mode)

| Language | Baseline WER (S/D/I / ref w) | Turbo WER (S/D/I / ref w) | Improvement (pp) | Turbo CER (edits / ref c) | Empty / Failed / Total | RTF (infer / audio) | Peak Memory (OS WSET / 50ms RSS) | Timestamp Validity | Verdict |
|---|---|---|---:|---|---|---|---|---|---|
| `kn_in` | `111.03%` (88/48/15 / 136w) | `57.35%` (66/9/3 / 136w) | `+53.68 pp` | `19.33%` (209/1081c) | `0` / `0` / `10` | `1.3617x` (150.1698s / 110.28s) | `1917.66 MB / 1823.61 MB` | `segment_only_valid` (10/10 valid, 0 invalid) | **`PASS_EXPERIMENTAL`** |
| `hi_in` | `59.48%` (112/7/19 / 232w) | `38.36%` (81/0/8 / 232w) | `+21.12 pp` | `19.81%` (244/1232c) | `0` / `0` / `10` | `1.5233x` (180.5104s / 118.5s) | `1917.66 MB / 1823.61 MB` | `segment_only_valid` (10/10 valid, 0 invalid) | **`NON_REGRESSION_ONLY_BELOW_USABILITY_TARGET`** |
| `en_us` | `11.00%` (16/0/6 / 200w) | `7.50%` (11/0/4 / 200w) | `+3.50 pp` | `3.36%` (37/1102c) | `0` / `0` / `10` | `1.3701x` (114.4838s / 83.56s) | `1917.66 MB / 1823.61 MB` | `segment_only_valid` (10/10 valid, 0 invalid) | **`PASS_EXPERIMENTAL`** |
| `ta_in` | `65.52%` (77/7/11 / 145w) | `76.55%` (94/9/8 / 145w) | `-11.03 pp` | `33.33%` (428/1284c) | `0` / `0` / `10` | `1.4147x` (167.6458s / 118.5s) | `1917.66 MB / 1823.61 MB` | `segment_only_valid` (10/10 valid, 0 invalid) | **`KEEP_DEFAULT_FAIL`** |
| `te_in` | `116.06%` (64/129/31 / 193w) | `85.49%` (124/36/5 / 193w) | `+30.57 pp` | `39.83%` (613/1539c) | `0` / `0` / `10` | `1.4682x` (195.387s / 133.08s) | `1917.66 MB / 1823.61 MB` | `segment_only_valid` (10/10 valid, 0 invalid) | **`KEEP_DEFAULT_FAIL`** |

## Evidence Paths
- Baseline JSON: `reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.json`
- Challenger JSON: `reports/product-acceptance/M4_MULTILINGUAL_CHALLENGER_TURBO_FORCED.json`
