# M4 Fair 5-Language Multilingual ASR Evaluation Plan (v2.0 — Pre-Execution Contract)

- **Date:** 2026-11-20 (supersedes v1.1 Kannada-only scope; preserves all v1.1 Kannada partitions & registered gates verbatim)
- **Branch:** `feat/m4-multilingual-asr` (stacked cleanly on stabilization checkpoint `e36c524` -> `feat/m4-indic-asr-research` `9747503` -> `feat/m3-baseline-execution` `761c9ed`)
- **Infrastructure Reused:** Existing M2/M3 manifest schemas (`sample_data/indic_creator_bench/schemas/`), integrity validator (`backend/app/ai/evaluation/indic_bench.py`), Unicode-safe normalizer (`v2_indic_unicode_safe_nfc`), provider seam (`backend/app/ai/providers/transcription.py`), and baseline runner (`backend/app/ai/evaluation/asr_baseline.py`).

---

## 1. Strict Dataset Separation, Provenance & Overlap Audit

All 5-language partitions are materialized deterministically from the pinned local `google/fleurs` test parquets (`168de341b3db6859a9bac1c50a2ef5e3b47647e0`, `CC-BY-4.0`) under `D:\ArovaStep2ASRProgram\eval_data\fleurs\` via `scripts/materialize_m4_multilingual_splits.py` (`seed=404`). Existing frozen Kannada partitions (`m4_kn_dev_10clip` and `m4_kn_eval_10clip`) are preserved **verbatim** inside the 5-language manifests.

### Source Parquet SHA-256 Registry (`google/fleurs@168de341b3db6859a9bac1c50a2ef5e3b47647e0`)

| Language | Script | Local Parquet | SHA-256 | Eligible Non-Smoke Rows |
|---|---|---|---|---:|
| `en_us` | `Latn` | `en_us/test/0000.parquet` | `6428a4d04d3aac29e16b45e039bb1470a8bd7aa334cf92f7984c9c520d1f234d` | `348` |
| `hi_in` | `Deva` | `hi_in/test/0000.parquet` | `8a0be26c5584c1478233a6f47fb90275c713f72565327ea1da76c9f1cd5dd38b` | `263` |
| `kn_in` | `Knda` | `kn_in/test/0000.parquet` | `4c1d7d489d34472c631f42cf306f3ba9b912e5d3eaee4d45c172db56c4ff7273` | `342` (preserved from frozen `m4_kn_*`) |
| `ta_in` | `Taml` | `ta_in/test/0000.parquet` | `6a0ca70812792cb075e20ecef7b69aac173af5f1f4ae37d3a42c58e219ea4bb6` | `334` |
| `te_in` | `Telu` | `te_in/test/0000.parquet` | `545a999e972e49649814e2f0267da898965a5e896aa215ac5d85898dff357fa1` | `300` |

### Frozen Split Registry

| Split | Dataset ID | Purpose | Clips / Duration | Frozen `manifest_sha256` | Overlap Audit |
|---|---|---|---|---|---|
| **Smoke** | `m2_smoke_10clip` | Pipeline & contract regression ONLY (2 clips × 5 langs) | `10` clips (`134.30s`) | Frozen in `sample_data/indic_creator_bench/m2_smoke_10clip/` | Excluded from all M4 dev/eval splits; never used for model promotion. |
| **Frozen Kannada Dev** | `m4_kn_dev_10clip` | Preserved v1.1 Kannada dev subset | `10` `kn_in` clips (`156.12s`) | `853943795ab20d941dc1d09081eba27cf6dbe903984dad07ed03b99712dce69c` | Exact verbatim subset of `m4_multilingual_dev_50clip`. |
| **Frozen Kannada Eval** | `m4_kn_eval_10clip` | Preserved v1.1 Kannada held-out subset | `10` `kn_in` clips (`110.28s`) | `f30350a95db7cfa8d19cc9d23d48ac4535a414cc02d30fea242c8398c579a5e0` | Exact verbatim subset of `m4_multilingual_eval_50clip`. |
| **5-Language Internal Dev** | `m4_multilingual_dev_50clip` | Adapter sanity, decoding checks, Auto-LID diagnostics & candidate selection (`10` × `5` langs) | `50` clips (`742.84s`: `en 121.42s`, `hi 135.84s`, `kn 156.12s`, `ta 203.64s`, `te 125.82s`) | `07a0a362931b144fc715be4b0091b1513c50705013b899821665187718ca0c25` | Zero overlap with `m2_smoke_10clip` and `m4_multilingual_eval_50clip` by `(language_code, source_sample_id)`, `audio_sha256`, and `(language_code, normalized_text)` (enforced by unit test). |
| **5-Language Frozen Held-Out Eval** | `m4_multilingual_eval_50clip` | Final matched baseline-vs-candidate decision (**zero tuning permitted**) (`10` × `5` langs) | `50` clips (`563.92s`: `en 83.56s`, `hi 118.50s`, `kn 110.28s`, `ta 118.50s`, `te 133.08s`) | `4426c1e10c85c5caf304db120cd83e445740a077778fdde7086647749c9a1480` | Zero overlap with `m2_smoke_10clip` and `m4_multilingual_dev_50clip` by `(language_code, source_sample_id)`, `audio_sha256`, and `(language_code, normalized_text)` (enforced by unit test). |

### Mandatory Methodology Disclosures
1. **Utterance ID Namespacing:** Revision-namespaced IDs (`fleurs_168de341_<lang>_<row_id>`) prevent cross-revision collisions.
2. **Sample Size Scope:** `10` held-out clips per language (`50` total, `563.92s`) is a bounded **first-gate feasibility and regression screen** sized for local CPU execution — it does **not** establish population-level quality across domains, dialects, background music, or spontaneous creator speech. Small-sample raw counts (`S/D/I`, `ref_words`, `empty/total`) are always reported alongside percentages.
3. **Speaker Overlap:** FLEURS test parquets expose `gender` (`0`/`1`) and row `id`, not persistent speaker IDs; **speaker disjointness across splits is `UNKNOWN` and explicitly disclosed**.
4. **Training Contamination Risk:** Both `openai/whisper-large-v3-turbo` (converted as `deepdml/faster-whisper-large-v3-turbo-ct2`) and fine-tuned Indic Whisper checkpoints (`vasista22/whisper-*-small`) were trained on large public multilingual/Indic corpora; exact exclusion of FLEURS test utterances is **unverified (`CONTAMINATION_RISK_DISCLOSED`)**.
5. **Reference Provenance:** Verbatim `raw_transcription` provided by `google/fleurs` (`reference_provenance="dataset_provided_fleurs_test"`, schema field `reference_status="verified"`). Dataset-provided, not newly human-verified by Arova, and never derived from any candidate ASR model.
6. **Mixed-Language / Hinglish:** Treated strictly as a separate capability requiring consented mixed-language audio and independently verified mixed-language references (`NO_VERIFIED_REFERENCE`, excluded here).
7. **Post-Tuning Hygiene:** If any tuning uses held-out results, a fresh confirmation split must be materialized before promoting a revised model.

---

## 2. Candidate Evaluation Order & Budgets (Pre-Registered Before Held-Out Execution)

1. **Reference Baseline:** `faster-whisper-small` (`Systran/faster-whisper-small`, pinned `536b0662742c02347bc0e980a01041f333bce120`, Apache-2.0, locally cached on `D:\ArovaStep2ASRProgram\models\faster-whisper-small`).
2. **First Challenger (Multilingual-First):** `deepdml/faster-whisper-large-v3-turbo-ct2` (pinned `4df90f75321148c3a29a9e2351b7ddf8f5b115a8`, MIT, converted from `openai/whisper-large-v3-turbo` `41f01f3fe87f28c78e2fbf8b568835947dd65ed9`, `0` `.py` files, `1,621,669,956` bytes = `1,546.54 MiB` download to `D:\ArovaStep2ASRProgram\models\faster-whisper-large-v3-turbo`, loaded with `compute_type="int8"`). *Status: awaiting explicit user download authorization.*
3. **Fallback Per-Language Specialists (ONLY for languages that miss their gate under the multilingual challenger):**
   - Kannada (`kn_in`): `vasista22/whisper-kannada-small` (`6f8e7b770513d941e4713b20adde26af32b2970b`, Apache-2.0, `~924.0 MB` selective PyTorch transfer) — explicit `language="kn"` override only.
   - Telugu (`te_in`): `vasista22/whisper-telugu-small` (`717212f9c4c16a78a86ddcb98f93c7f73ef8a5cc`, Apache-2.0, `~924.0 MB` selective PyTorch transfer) — explicit `language="te"` override only.
   - Automatic routing is NOT introduced unless language detection and fallback behavior have their own independent evidence.

---

## 3. Pre-Registered Per-Language Decision Rule (Fixed Before Candidate Execution)

All gates apply per language on the frozen **`m4_multilingual_eval_50clip`** split under matched conditions (`device="cpu"`, `compute_type="int8"`, `cpu_threads=4`, `language_mode="forced"`, `beam_size=5`, `vad_filter=False`, `condition_on_previous_text=False`, `word_timestamps=False`, `v2_indic_unicode_safe_nfc`).

### Universal Reliability, Resource & Timing Gates (Every Language)
- **Empty-Hypothesis Rate:** `<= 10%` (`<= 1 / 10` clips per language).
- **Crashes / Failures:** `0` (`failed_count == 0`, `coverage_complete == True`). Failed clips are never dropped from denominators.
- **Measured Process Memory:** Both `os_peak_wset_mb` and `50ms` sampled `rss_sampled_max_mb` MUST be measured (`single_process_no_children`) and **`<= 3,500 MB`** on the 16 GB Windows laptop. A missing memory measurement leaves the memory gate **`OPEN`** (`HOLD_MEMORY_UNMEASURED`).
- **Timing Validity (Reported Independently of WER):** Non-empty transcripts must emit valid monotonic segment boundaries (`0 <= start_time < end_time <= duration_sec + 0.5`). Word timings (`words_json`) are preserved only when genuinely supported and never fabricated.

### Language-Specific Accuracy & Latency Gates

| Language | Primary Gate (Registered M4 Criterion) | Absolute Usability Target (Required Before Product Readiness Claim) | Latency Gate (CPU RTF) |
|---|---|---|---|
| **Kannada (`kn_in`)** | Micro WER reduction `>= 35pp` vs matched baseline **AND** Micro WER `<= 0.65` | `<= 0.65` (experimental screen); `<= 0.35` on real creator audio before default promotion | `<= 6.0x` |
| **Telugu (`te_in`)** | Micro WER reduction `>= 35pp` vs matched baseline **AND** Micro WER `<= 0.65` | `<= 0.65` (experimental screen); `<= 0.35` on real creator audio before default promotion | `<= 6.0x` |
| **English (`en_us`)** | Control non-regression: Micro WER `<= 0.15` | `<= 0.15` | `<= 6.0x` |
| **Hindi (`hi_in`)** | Non-regression: Micro WER `<= baseline + 0.03` | **`<= 0.35` Micro WER** (justified below) | `<= 6.0x` |
| **Tamil (`ta_in`)** | Non-regression: Micro WER `<= baseline + 0.03` | **`<= 0.40` Micro WER** (justified below) | `<= 6.0x` |

**Justification for Hindi (`<= 0.35`) and Tamil (`<= 0.40`) Absolute Usability Targets:**
- Because `faster-whisper-small` exhibits poor baseline WER on Hindi (~`54%–65%`) and Tamil (~`61%–79%`), a `<= +3pp` non-regression threshold alone would rubber-stamp a challenger that still misrecognizes more than half of every sentence — unusable for creator subtitle export or search retrieval.
- Setting **`hi_in <= 0.35`** (Devanagari, analytic morphology with moderate inflection; `<= 35%` WER yields intelligible search recall and editable draft captions) and **`ta_in <= 0.40`** (Tamil agglutinative morphology where single-suffix errors inflate word-level WER even when CER is low) separates **"does not regress"** (`NON_REGRESSION_ONLY_BELOW_USABILITY_TARGET`) from **"product-usable"** (`PASS_EXPERIMENTAL`).
- Even clearing all FLEURS gates earns **`PASS_EXPERIMENTAL`** only; changing the product default additionally requires confirmation on authorized real creator recordings (names, background music, varied microphones, spontaneous speech).

### Decision Taxonomy
- `PASS_EXPERIMENTAL`: Clears accuracy, absolute usability, empty-output, crash, RTF, memory, and timing gates on FLEURS held-out (`forced` mode).
- `NON_REGRESSION_ONLY_BELOW_USABILITY_TARGET`: Clears Hindi/Tamil non-regression (`<= baseline + 3pp`) and reliability/budget gates, but fails the absolute usability target (`> 0.35` Hindi / `> 0.40` Tamil).
- `EXPERIMENTAL_OVER_BUDGET`: Wins on accuracy/usability, reliability, and timing, but exceeds laptop CPU RTF (`> 6.0x`) or measured memory (`> 3,500 MB`).
- `HOLD_MEMORY_UNMEASURED`: Missing process memory measurement — gate remains open.
- `KEEP_DEFAULT_FAIL`: Fails accuracy, non-regression, reliability, empty-output, or timing gates; keep current default and (for Kannada/Telugu) evaluate the pinned specialist under the same protocol.

---

## 4. Matched Measurement Protocol & Auto-LID Policy

1. **Sequential Execution:** Run baseline and challenger sequentially (never concurrently) on identical audio files and hardware with explicit `cpu_threads=4`, `beam_size=5`, `vad_filter=False`, `condition_on_previous_text=False`, `word_timestamps=False`.
2. **Cold Init & Full Iterator Consumption:** Time `_get_or_load_model()` separately from inference; consume the entire `faster-whisper` segment iterator inside `FasterWhisperProvider.transcribe()` before stopping per-utterance timers.
3. **Checkpoint Keying:** Per-utterance checkpoints record and verify `(config_fingerprint_sha256, manifest_sha256, model_id, model_revision)` so interrupted runs resume cleanly without ever mixing models, thread counts, language modes, or manifests.
4. **Forced vs Auto Mode:** Forced language (`language_mode="forced"`) is the primary controlled comparison. A pass in `forced` mode certifies forced mode ONLY. If the UI exposes `Auto`, a separate `language_mode="auto"` evaluation reporting detected languages, confusion matrix, LID accuracy, and Auto-mode WER/CER is mandatory before claiming Auto support.
