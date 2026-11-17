# Arova Indic Creator Bench — M2 10-Clip Smoke Corpus

- **Dataset ID:** `indic_creator_bench_m2_smoke` (`1.0.0`, split: `smoke`)
- **Schema Versions:** Descriptor `1.0.0`, Sample `1.0.0`, Normalization `v2_indic_unicode_safe_nfc`
- **Source Dataset:** `google/fleurs` (commit `168de341b3db6859a9bac1c50a2ef5e3b47647e0`, `test/0000.parquet`)
- **License & Attribution:** `CC-BY-4.0` — *"FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech (Conneau et al., 2022), licensed under CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/)."*

## Governance Rules

1. **Zero Audio Files in Git:** `.wav` files are never committed to Git. Audio clips are materialized locally into git-ignored `data/indic_creator_bench/m2_smoke_10clip/audio/<lang>/`.
2. **Hinglish Excluded:** Hinglish / romanized code-switch clips are **explicitly excluded** from verified benchmark claims because `reports/asr_eval/hinglish_template.json` records `status: "NO_VERIFIED_REFERENCE"` and `samples: []`.
3. **Verbatim References Preserved:** `raw_transcription` and `reference_transcript` preserve original FLEURS Unicode text untouched (including Telugu ZWNJ `\u200c`, Indic matras, viramas, and nukta marks).

## Clip Inventory (10 Real Speech Clips)

| Utterance ID | Language | Script | Source ID | Sample Rate | Channels | Duration (s) | Audio SHA-256 Prefix | Reference Status |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `fleurs_hi_in_1718` | Hindi (`hi_in`) | `Deva` | `1718` | 16000 Hz | 1 | 15.000 | `6c1e02d23469dcb2` | `verified` |
| `fleurs_hi_in_1836` | Hindi (`hi_in`) | `Deva` | `1836` | 16000 Hz | 1 | 17.100 | `c1c970d98d4ac10c` | `verified` |
| `fleurs_kn_in_1923` | Kannada (`kn_in`) | `Knda` | `1923` | 16000 Hz | 1 | 21.960 | `9698d295a967f041` | `verified` |
| `fleurs_kn_in_1970` | Kannada (`kn_in`) | `Knda` | `1970` | 16000 Hz | 1 | 13.920 | `006e3b910efffc2e` | `verified` |
| `fleurs_ta_in_1740` | Tamil (`ta_in`) | `Taml` | `1740` | 16000 Hz | 1 | 7.740 | `ca25c226a26abf6a` | `verified` |
| `fleurs_ta_in_1732` | Tamil (`ta_in`) | `Taml` | `1732` | 16000 Hz | 1 | 15.000 | `f1d3805ce8a47e16` | `verified` |
| `fleurs_te_in_1666` | Telugu (`te_in`) | `Telu` | `1666` | 16000 Hz | 1 | 10.080 | `7012022d111ae038` | `verified` |
| `fleurs_te_in_2002` | Telugu (`te_in`) | `Telu` | `2002` | 16000 Hz | 1 | 10.620 | `89bca5318ba1737a` | `verified` |
| `fleurs_en_us_1950` | English (`en_us`) | `Latn` | `1950` | 16000 Hz | 1 | 11.460 | `260bdd1a15e1d35b` | `verified` |
| `fleurs_en_us_1938` | English (`en_us`) | `Latn` | `1938` | 16000 Hz | 1 | 11.420 | `3802ffc3e69c66e0` | `verified` |

## Local Materialization & Validation

```powershell
# Materialize unmodified WAVs from local FLEURS parquets and validate full SHA-256 + audio headers:
.venv\Scripts\python.exe scripts/validate_indic_bench.py --materialize

# Validate tracked manifest contracts without audio files:
.venv\Scripts\python.exe scripts/validate_indic_bench.py --dataset-root sample_data/indic_creator_bench/m2_smoke_10clip --manifest-only
```
