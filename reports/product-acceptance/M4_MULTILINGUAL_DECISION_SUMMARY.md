# M4 Multilingual ASR Decision Summary (Baseline vs Large-v3-Turbo)

- **Date:** 2026-11-20
- **Branch:** `feat/m4-multilingual-asr` (stacked on `e36c524` -> `feat/m4-indic-asr-research` `9747503` -> `feat/m3-baseline-execution` `761c9ed`)
- **Dataset (Frozen Held-Out):** `m4_multilingual_eval_50clip@1.0.0` (`50` clips = `10` × `5` languages, `563.92s`, `manifest_sha256: 4426c1e10c85c5caf304db120cd83e445740a077778fdde7086647749c9a1480`; preserves frozen `m4_kn_eval_10clip` verbatim)
- **Dataset (Internal Dev Sanity):** `m4_multilingual_dev_50clip@1.0.0` (`manifest_sha256: 07a0a362931b144fc715be4b0091b1513c50705013b899821665187718ca0c25`; 5-clip 1/language dev sanity passed `5/5` `script_ok=True`, `0` invalid timings, `1,916.87 MB` peak WSET)
- **Baseline Model:** `faster-whisper-small` (`Systran/faster-whisper-small`, rev `536b0662742c02347bc0e980a01041f333bce120`, Apache-2.0, `fp=ca6e822bca18510103fbf7fdd798e61f762b938dc9b74f18adc3e947346fa153`)
- **Challenger Model:** `faster-whisper-large-v3-turbo` (`deepdml/faster-whisper-large-v3-turbo-ct2`, rev `4df90f75321148c3a29a9e2351b7ddf8f5b115a8`, MIT, `model.bin` SHA-256 `e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da`, `fp=53f5b47969d4f8d811e7631e8375ca620ada27b7d3989ec4f5a2d949c75aec60`)
- **Matched Execution Protocol:** `device="cpu"`, `compute_type="int8"`, `cpu_threads=4`, `language_mode="forced"`, `beam_size=5`, `vad_filter=False`, `condition_on_previous_text=False`, `word_timestamps=False`, `normalization="v2_indic_unicode_safe_nfc"`, sequential execution, `HF_HUB_OFFLINE=1`
- **Production Default Decision:** **`KEEP_CURRENT_DEFAULT_UNCHANGED`** (`faster-whisper-small` remains production default during M4; `faster-whisper-large-v3-turbo` earns `PASS_EXPERIMENTAL` on `kn_in` and `en_us`, `NON_REGRESSION_ONLY_BELOW_USABILITY_TARGET` on `hi_in`, and `KEEP_DEFAULT_FAIL` on `ta_in` and `te_in`).

---

## 1. Five-Language Gate Table (Pre-Registered M4 v2.0 Criteria Unchanged, Forced Mode)

| Language | Baseline WER (S/D/I / ref w) | Turbo WER (S/D/I / ref w) | Improvement (pp) | Turbo CER (edits / ref c) | Empty / Failed / Total | RTF (infer / audio) | Peak Memory (OS WSET / 50ms RSS) | Timestamp Validity | Verdict | Evidence Path |
|---|---|---|---:|---|---|---|---|---|---|---|
| `kn_in` | `111.03%` (`88/48/15` / `136w`) | `57.35%` (`66/9/3` / `136w`) | **`+53.68 pp`** | `19.33%` (`209/1081c`) | `0` / `0` / `10` | `1.3617x` (`150.17s` / `110.28s`) | `1917.66 MB` / `1823.61 MB` | `segment_only_valid` (`10/10`) | **`PASS_EXPERIMENTAL`** | `reports/product-acceptance/M4_MULTILINGUAL_CHALLENGER_TURBO_FORCED.json` |
| `hi_in` | `59.48%` (`112/7/19` / `232w`) | `38.36%` (`81/0/8` / `232w`) | **`+21.12 pp`** | `19.81%` (`244/1232c`) | `0` / `0` / `10` | `1.5233x` (`180.51s` / `118.50s`) | `1917.66 MB` / `1823.61 MB` | `segment_only_valid` (`10/10`) | **`NON_REGRESSION_ONLY_BELOW_USABILITY_TARGET`** | `reports/product-acceptance/M4_MULTILINGUAL_CHALLENGER_TURBO_FORCED.json` |
| `en_us` | `11.00%` (`16/0/6` / `200w`) | `7.50%` (`11/0/4` / `200w`) | **`+3.50 pp`** | `3.36%` (`37/1102c`) | `0` / `0` / `10` | `1.3701x` (`114.48s` / `83.56s`) | `1917.66 MB` / `1823.61 MB` | `segment_only_valid` (`10/10`) | **`PASS_EXPERIMENTAL`** | `reports/product-acceptance/M4_MULTILINGUAL_CHALLENGER_TURBO_FORCED.json` |
| `ta_in` | `65.52%` (`77/7/11` / `145w`) | `76.55%` (`94/9/8` / `145w`) | **`-11.03 pp`** | `33.33%` (`428/1284c`) | `0` / `0` / `10` | `1.4147x` (`167.65s` / `118.50s`) | `1917.66 MB` / `1823.61 MB` | `segment_only_valid` (`10/10`) | **`KEEP_DEFAULT_FAIL`** | `reports/product-acceptance/M4_MULTILINGUAL_CHALLENGER_TURBO_FORCED.json` |
| `te_in` | `116.06%` (`64/129/31` / `193w`) | `85.49%` (`124/36/5` / `193w`) | **`+30.57 pp`** | `39.83%` (`613/1539c`) | `0` / `0` / `10` | `1.4682x` (`195.39s` / `133.08s`) | `1917.66 MB` / `1823.61 MB` | `segment_only_valid` (`10/10`) | **`KEEP_DEFAULT_FAIL`** | `reports/product-acceptance/M4_MULTILINGUAL_CHALLENGER_TURBO_FORCED.json` |

- **Challenger Corpus Summary:** `50/50` succeeded, `0` crashes, **`0/50` empty hypotheses** (vs `5/50` empty on baseline), Cold Init `5.2957s`, Total Infer `808.1968s` over `563.92s` audio (**`Corpus RTF 1.4332x`**, nearly 2× faster than baseline `2.8143x`!), `50ms` Sampled Max RSS `1,823.61 MB` (`12,992` samples), OS Peak Working Set `1,917.66 MB` (`single_process_no_children`, well within `<= 3,500 MB` budget), `50/50` valid segment timings (`0` invalid), VRAM & Energy `NOT_MEASURED`.
- **Mode & Scope Disclosures:** This run supplied `language_mode="forced"`; automatic language detection (`language_mode="auto"`) and mixed-language / Hinglish speech require separate evaluations and are NOT covered by these verdicts. FLEURS speaker disjointness is `UNKNOWN` and upstream training contamination is `CONTAMINATION_RISK_DISCLOSED`.

---

## 2. Failure-Pattern Diagnosis for Missed Languages & Specialist Proposals

1. **Tamil (`ta_in` — `KEEP_DEFAULT_FAIL`, regressed `-11.03 pp` to `76.55%` WER / `33.33%` CER):**
   - **Failure Pattern A (Cross-lingual decoder derailment):** On `fleurs_168de341_ta_in_1795` (`19.68s`), the pruned 4-layer decoder broke into mixed Russian/French/English/Hindi/Turkish subwords (`"99.98 Кстати हeb intéressant வாக்குப்பட்டfallsdoingulos... Winter"`, `100%` WER, `87.6%` CER, `56.96s` infer).
   - **Failure Pattern B (Numeral/acronym expansion & Tamil consonant confusion):** Spoken numerals/acronyms (`10:00-11:00 pm MDT`, `1200 GMT`) were expanded in Tamil script while consonant retroflex/dental confusions (`இரவு -> இறவு`, `விபத்து -> விவத்து`) inflated word-level edits across agglutinative compounds.
   - **Proposed Specialist Comparison (requires separate approval):** Evaluate a pinned Tamil specialist (e.g., `vasista22/whisper-tamil-small` or `ai4bharat/indic-conformer-600m-multilingual`) under the exact same frozen `m4_multilingual_eval_50clip` Tamil partition with explicit `language="ta"` override.
2. **Telugu (`te_in` — `KEEP_DEFAULT_FAIL`, improved `+30.57 pp` to `85.49%` WER / `39.83%` CER):**
   - **Failure Pattern:** Eliminated all empty outputs (`3/10 -> 0/10`) and slashed CER by `59.7 pp` (`99.55% -> 39.83%`), confirming genuine Telugu script recognition, but still missed both `>= 35pp` WER reduction (`+30.57pp`) and `<= 65%` WER (`85.49%`) due to aspirated consonant substitutions (`124S`) and tail-end truncation (`36D` across `193` ref words on clips like `te_in_1995`, `te_in_1683`, `te_in_1690`).
   - **Proposed Specialist Comparison (requires separate approval):** Evaluate pinned **`vasista22/whisper-telugu-small`** (`717212f9c4c16a78a86ddcb98f93c7f73ef8a5cc`, Apache-2.0, ungated, `0` `.py` files, `~924.0 MB` selective PyTorch transfer to `D:`, converted to CT2 `int8`) under the exact same frozen Telugu held-out partition with explicit `language="te"` override.
3. **Hindi (`hi_in` — `NON_REGRESSION_ONLY_BELOW_USABILITY_TARGET`, improved `+21.12 pp` to `38.36%` WER / `19.81%` CER):**
   - **Failure Pattern:** Cleared non-regression by `24.12 pp` margin, missing the `<= 35.0%` absolute usability target by `3.36 pp` due to (a) one severe acoustic derailment outlier (`hi_in_1939`, `100%` WER, `23S`, `6.30x` RTF — the other 9 clips average `31.6%` micro WER) and (b) Latin-script rendering of English loanwords (`device`, `move`, `action`, `USA Gymnastics`, `USOC`) where FLEURS references use Devanagari transliteration.
   - **Proposed Next Step:** Confirm Hindi usability on authorized real Hindi creator recordings (where natural English loanwords match creator expectations) before deciding whether a Hindi specialist is needed.
4. **Kannada Residual Risk (`kn_in` — `PASS_EXPERIMENTAL`, `57.35%` WER / `19.33%` CER):**
   - Passed all M4 v2.0 gates cleanly (`+53.68 pp` drop, `0/10` empty, `1.36x` RTF, `10/10` valid timing). One short clip (`kn_in_1755`, `4.32s`) showed Devanagari script bleed (`100%` WER / `91.5%` CER) despite `forced="kn"`; the remaining 9 clips emitted pure Kannada script (`5.2%–30.6%` CER). Still requires confirmation on authorized real Kannada creator footage before any default promotion.

---

## 3. Prerequisites & Exact Reproduction Commands

### Prerequisites
1. **Backend + ASR extra:** `uv sync --project backend --group dev --extra asr --locked` (installs `faster-whisper`, `ctranslate2`, `psutil`).
2. **Pinned FLEURS parquets (only if re-materializing WAV clips from source parquets):** `google/fleurs@168de341b3db6859a9bac1c50a2ef5e3b47647e0` (`CC-BY-4.0`) test parquets (`<lang>/test/0000.parquet` for `en_us`, `hi_in`, `kn_in`, `ta_in`, `te_in`, SHA-256 registry in `M4_EVALUATION_PLAN.md`). Pass `--fleurs-root <path>` (or set `AROVA_FLEURS_ROOT`) and run with `--with pyarrow` if `pyarrow` is not installed in the backend venv.
3. **Pinned local CTranslate2 weights (kept outside Git):**
   - `faster-whisper-small` (`Systran/faster-whisper-small@536b0662742c02347bc0e980a01041f333bce120`, Apache-2.0)
   - `faster-whisper-large-v3-turbo` (`deepdml/faster-whisper-large-v3-turbo-ct2@4df90f75321148c3a29a9e2351b7ddf8f5b115a8`, MIT, `model.bin` SHA-256 `e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da`)
   - Install locally via `python -m arova models install faster-whisper-small` and `python -m arova models install faster-whisper-large-v3-turbo` (storage location controlled by `AROVA_MODELS_HOME`).

### Step-by-Step Commands (Windows PowerShell; set `PYTHONPATH=backend:.` on Linux/macOS)
```powershell
$env:PYTHONPATH = "backend;."; $env:HF_HUB_OFFLINE = "1"; $env:AROVA_MODELS_HOME = "D:\ArovaStep2ASRProgram\models"

# 1. Materialize (if audio WAVs are not yet unpacked locally) & validate frozen 50-clip eval split
uv run --project backend --no-sync --with pyarrow python scripts/materialize_m4_multilingual_splits.py --fleurs-root D:\ArovaStep2ASRProgram\eval_data\fleurs
uv run --project backend --no-sync python scripts/validate_indic_bench.py --dataset-root data/indic_creator_bench/m4_multilingual_eval_50clip

# 2. Baseline 50-clip forced evaluation (faster-whisper-small, cpu/int8/t4)
uv run --project backend --no-sync python scripts/run_m3_asr_baseline.py `
  --dataset-root data/indic_creator_bench/m4_multilingual_eval_50clip `
  --model-size-or-path "$env:AROVA_MODELS_HOME\faster-whisper-small" `
  --model-id faster-whisper-small `
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 `
  --device cpu --compute-type int8 --cpu-threads 4 `
  --language-mode forced --beam-size 5 --no-word-timestamps `
  --checkpoint D:\ArovaStep2ASRProgram\tmp\m4_small_eval50_forced.ckpt.jsonl `
  --json-out reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.json `
  --md-out reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.md

# 3. Challenger 50-clip forced evaluation (faster-whisper-large-v3-turbo, cpu/int8/t4)
uv run --project backend --no-sync python scripts/run_m3_asr_baseline.py `
  --dataset-root data/indic_creator_bench/m4_multilingual_eval_50clip `
  --model-size-or-path "$env:AROVA_MODELS_HOME\faster-whisper-large-v3-turbo" `
  --model-id faster-whisper-large-v3-turbo `
  --model-revision 4df90f75321148c3a29a9e2351b7ddf8f5b115a8 `
  --device cpu --compute-type int8 --cpu-threads 4 `
  --language-mode forced --beam-size 5 --no-word-timestamps `
  --checkpoint D:\ArovaStep2ASRProgram\tmp\m4_turbo_eval50_forced.ckpt.jsonl `
  --json-out reports/product-acceptance/M4_MULTILINGUAL_CHALLENGER_TURBO_FORCED.json `
  --md-out reports/product-acceptance/M4_MULTILINGUAL_CHALLENGER_TURBO_FORCED.md

# 4. Reproduce five-language comparison table & pre-registered gate verdicts
uv run --project backend --no-sync python scripts/compare_m4_multilingual_runs.py `
  --baseline-json reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.json `
  --candidate-json reports/product-acceptance/M4_MULTILINGUAL_CHALLENGER_TURBO_FORCED.json `
  --json-out reports/product-acceptance/M4_MULTILINGUAL_DECISION_COMPARISON.json `
  --md-out reports/product-acceptance/M4_MULTILINGUAL_DECISION_COMPARISON.md
```

---

## 4. Kannada Creator Workstation Workflow Check — Single Missing Input (Benchmark Closed)

- **Closure Status:** **`M4_MULTILINGUAL_BENCHMARK_CLOSED` (`KEEP_CURRENT_DEFAULT_UNCHANGED`)**
- **Workstation Creator-Clip Audit (2026-11-22):** Inspected `sample_data/`, `data/`, `test_data/`, `benchmarks/`, `D:\ArovaStep2ASRProgram\`, and live `data/app.db`. Only English videos (`tears_of_steel_720p.mov`, `demo_developer_lecture.mp4`, synthetic demo clips) and 10-second read-speech FLEURS `.wav` audio clips exist locally.
- **Single Missing Input:** **No authorized local Kannada creator video clip with known timestamps is available** to execute the end-to-end Small-vs-Turbo workstation indexing, top-3 search, seek, and SRT export comparison on real creator footage.
- **Next Gate (Deferred):** Supply one authorized local Kannada creator video clip with three ground-truth timestamped queries (or separately authorize pinned Telugu/Tamil specialist evaluations) before reconsidering any default-model change. Specialist downloads, automatic routing, and additional dashboards remain deferred.
