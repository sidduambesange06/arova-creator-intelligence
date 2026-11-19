# M4.1 Fair Specialist Indic ASR Evaluation Plan (v1.1 — Pre-Execution Contract)

- **Date:** 2026-11-19
- **Branch:** `feat/m4-indic-asr-research`
- **Infrastructure Reused:** Existing M2/M3 manifest schemas (`sample_data/indic_creator_bench/schemas/`), integrity validator (`backend/app/ai/evaluation/indic_bench.py`), Unicode-safe normalizer (`v2_indic_unicode_safe_nfc`), provider seam (`backend/app/ai/providers/transcription.py`), and baseline runner (`backend/app/ai/evaluation/asr_baseline.py`). No second benchmark framework was created.

---

## 1. Strict Dataset Separation, Provenance & Overlap Audit

All Kannada partitions are materialized deterministically from the pinned local `google/fleurs` test parquet (`168de341b3db6859a9bac1c50a2ef5e3b47647e0`, `CC-BY-4.0`) at `D:\ArovaStep2ASRProgram\eval_data\fleurs\kn_in\test\0000.parquet` (`SHA-256: 4c1d7d489d34472c631f42cf306f3ba9b912e5d3eaee4d45c172db56c4ff7273`, `342` unique eligible non-smoke rows) via `scripts/materialize_m4_kannada_splits.py` (`seed=404`).

| Split | Dataset ID | Purpose | Clips / Duration | Frozen `manifest_sha256` | Overlap Audit |
|---|---|---|---|---|---|
| **Smoke** | `m2_smoke_10clip` | Pipeline & contract regression ONLY (contains 2 `kn_in` clips) | 10 clips (2 `kn_in`) | Frozen in `sample_data/indic_creator_bench/m2_smoke_10clip/` | Excluded from both M4 Kannada partitions; never used to claim model superiority. |
| **Internal Dev** | `m4_kn_dev_10clip` | Adapter sanity, conversion verification, decoding & boundary checks | 10 `kn_in` clips (`156.12s`) | `853943795ab20d941dc1d09081eba27cf6dbe903984dad07ed03b99712dce69c` | Zero overlap with `m2_smoke_10clip` and `m4_kn_eval_10clip` by `source_sample_id`, `audio_sha256`, and normalized text (verified by unit test). |
| **Frozen Held-Out Eval** | `m4_kn_eval_10clip` | Final baseline-vs-candidate Kannada comparison (**zero tuning permitted**) | 10 `kn_in` clips (`110.28s`) | `f30350a95db7cfa8d19cc9d23d48ac4535a414cc02d30fea242c8398c579a5e0` | Zero overlap with `m2_smoke_10clip` and `m4_kn_dev_10clip` by `source_sample_id`, `audio_sha256`, and normalized text (verified by unit test). |

### Mandatory Methodology Disclosures
1. **Utterance ID Namespacing:** All M4 splits use revision-namespaced IDs (`fleurs_168de341_kn_in_<row_id>`) so IDs remain unique across corpus revisions.
2. **Sample Size Scope:** `10` held-out Kannada clips (`110.28s`) is a bounded **first-gate feasibility and regression screen** sized for local CPU execution — it does **not** establish population-level accuracy across domains, dialects, or noisy creator footage. Expanding to a larger held-out set (`>= 50` clips + creator-domain audio) is required before any production promotion claim.
3. **Speaker Overlap:** FLEURS test parquet exposes `gender` (`0`/`1`) and row `id`, not persistent speaker IDs across utterances; **speaker disjointness across splits is `UNKNOWN` and explicitly disclosed**.
4. **Training Contamination Risk:** `vasista22/whisper-kannada-small` was fine-tuned on public Kannada speech corpora (including ULCA/Indic/CommonVoice/FLEURS-adjacent sources); exact exclusion of FLEURS `kn_in/test` from its training set is **unverified (`CONTAMINATION_RISK_DISCLOSED`)**.
5. **Reference Provenance:** Verbatim `raw_transcription` provided by `google/fleurs` (`reference_provenance="dataset_provided_fleurs_test"`, schema field `reference_status="verified"`). These references are **dataset-provided**, not newly human-verified by Arova, and are never derived from any candidate ASR model. Hinglish remains excluded (`NO_VERIFIED_REFERENCE`).

---

## 2. Scope-Separated Pre-Registered Acceptance Criteria (Fixed Before Candidate Execution)

Because `vasista22/whisper-kannada-small` is a **monolingual Kannada specialist**, acceptance gates are strictly separated by provider capability scope so monolingual models are never evaluated against impossible multilingual criteria and never silently run on unsupported languages.

### Scope A — M4.2a Monolingual Kannada Specialist (`vasista22/whisper-kannada-small`)
Eligible to be marked **`PROMISING_EXPERIMENTAL`** (never automatically replacing the default multilingual provider) ONLY if it passes **ALL** criteria on the frozen **`m4_kn_eval_10clip`** split against the fresh `faster-whisper-small` baseline run on identical audio and hardware:

| Gate | Pre-Registered Threshold | Rationale |
|---|---|---|
| **Kannada (`kn_in`) Micro WER** | Absolute reduction `>= 35` percentage points vs fresh `faster-whisper-small` baseline **AND** Micro WER `<= 0.65` | Proves genuine Kannada script recognition over baseline failure rather than marginal noise. |
| **Kannada (`kn_in`) Micro CER** | Reported with full Word & Char `S/D/I` edit breakdown alongside Micro/Macro WER | Exposes partial-word/matra accuracy vs complete hallucinations or deletions. |
| **Language Boundary Enforcement** | Any non-`kn` or `language=None` call MUST raise explicit `UNSUPPORTED_LANGUAGE` before loading/running | Zero silent fallback to another model, auto-detection, or cloud. |
| **Empty-Hypothesis Rate** | `<= 10%` (`<= 1 / 10` clips on `m4_kn_eval_10clip`) | Prevents silent zero-output failures. |
| **Coverage & Reliability** | `0%` unhandled failures (`failed_items == 0`, `coverage_complete == True` on valid Kannada audio). Failed clips are **never** dropped from denominators or pass counts. | Guarantees production stability under `TranscriptionProvider`. |
| **Resource & Latency Budget** | OS peak working set (`os_peak_wset_mb`) and 50ms sampled peak RSS (`rss_sampled_max_mb`) `<= 3,500 MB` on 16 GB Windows laptop; transcription-only CPU RTF `<= 6.0x` | Fits local-first laptop envelope without OOM or unusable latency. |
| **Timestamp Honesty** | Must emit valid segment timestamps (`start_time < end_time`) and set `words=None` (`supports_word_timestamps=False`) unless word alignment is independently verified | Preserves M3.2/M3.4 honesty guarantees (never fabricates word timings). |

### Scope B — Deferred Future Experiments (NOT Part of M4.2a)
- **M4.2b (`vasista22/whisper-telugu-small`):** Separate Telugu-only held-out split (`m4_te_eval_10clip`) with analogous Telugu-only gates.
- **M4.2c (`deepdml/faster-whisper-large-v3-turbo-ct2`):** Separate multilingual 5-language held-out split (`kn_in`, `te_in`, `hi_in`, `ta_in`, `en_us`) enforcing English (`<= 0.15` WER) and Hindi/Tamil non-regression (`<= +0.03` WER vs baseline) alongside Kannada/Telugu gains.

---

## 3. Fair Comparison & Measurement Protocol

1. **Fresh Baseline on Identical Inputs:** Run `faster-whisper-small` (`cpu`, `int8`, `language_mode="forced"`, `word_timestamps=False`) on frozen `m4_kn_eval_10clip` on this exact machine (`reports/product-acceptance/M4_KANNADA_BASELINE_REPORT.{md,json}`). Historical `m2_smoke_10clip` scores are NOT reused as the comparator.
2. **Identical Normalization & Edit Decomposition:** Both baseline and candidate use `v2_indic_unicode_safe_nfc`, unclamped Levenshtein micro/macro WER & CER, explicit `Substitutions / Deletions / Insertions` (`S/D/I`), empty-hypothesis count/rate, and side-by-side raw reference & hypothesis preservation.
3. **Comparable Decoding Conditions:**
   - Primary condition: `language_mode="forced"`, `beam_size=5`, `vad_filter=False`, `condition_on_previous_text=False`, `word_timestamps=False` (pure transcription latency separated from word-alignment cost).
   - Sequential execution (never run baseline and candidate concurrently); cold model load timed separately from per-utterance inference.
4. **Honest Memory & Resource Instrumentation:**
   - Measured via `psutil` (`7.2.2`) in-process: background `50ms` continuous RSS sampler (`rss_sampled_max_mb`, `rss_sample_count`) + Windows OS high-water mark (`os_peak_wset_mb` from `PeakWorkingSetSize`), labeled with `memory_measurement_scope: "single_process_no_children"`.
   - VRAM (`NOT_MEASURED` on CPU) and Energy (`NOT_MEASURED`) are stated explicitly.
