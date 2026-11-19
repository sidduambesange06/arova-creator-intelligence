# M4.1 Fair Specialist Indic ASR Evaluation Plan

- **Date:** 2026-11-19
- **Branch:** `feat/m4-indic-asr-research` (stacked on `feat/m3-baseline-execution` `9b17ef8`)
- **Infrastructure Reused:** Existing M2/M3 manifest schemas (`sample_data/indic_creator_bench/schemas/`), integrity validator (`backend/app/ai/evaluation/indic_bench.py`), Unicode-safe normalizer (`v2_indic_unicode_safe_nfc`), and baseline runner (`backend/app/ai/evaluation/asr_baseline.py`). No second benchmark framework will be created.

---

## 1. Strict Dataset Separation & Provenance

All local audio splits will be materialized deterministically from the pinned local `google/fleurs` test parquets (`168de341b3db6859a9bac1c50a2ef5e3b47647e0`, `CC-BY-4.0`) already stored at `D:\ArovaStep2ASRProgram\eval_data\fleurs\{en_us,hi_in,kn_in,ta_in,te_in}\test\0000.parquet`:

| Split | Purpose | Size Target | Overlap Policy |
|---|---|---|---|
| **Smoke Set (`m2_smoke_10clip`)** | Integration & contract regression ONLY | 10 clips (2/lang across 5 langs) | Frozen in `sample_data/indic_creator_bench/m2_smoke_10clip/`; never used to claim model superiority. |
| **Development Set (`m4_dev_25clip`)** | Adapter configuration, language-code mapping, decoding sanity checks | 25 clips (5/lang: `kn_in`, `te_in`, `hi_in`, `ta_in`, `en_us`) | Strictly disjoint `source_sample_id` from smoke and held-out sets; deterministic seed (`seed=101`). |
| **Held-Out Evaluation Set (`m4_eval_50clip`)** | Final baseline-vs-candidate comparison | 50 clips (10/lang: `kn_in`, `te_in`, `hi_in`, `ta_in`, `en_us`) | Strictly disjoint `source_sample_id` from smoke and dev sets (`seed=202`); zero tuning permitted on this split. |

### Overlap, Contamination & Reference Quality Disclosures
- **Speaker Overlap:** FLEURS test parquet metadata exposes `gender` (`0`/`1`) and `id`, not persistent speaker IDs across utterances; therefore **speaker disjointness across splits is `UNKNOWN` and explicitly disclosed**.
- **Training Contamination Risk:** Publicly fine-tuned Indic models (`vasista22/whisper-*`, `openai/whisper-large-v3-turbo`, `ai4bharat/indic-conformer`) may have seen FLEURS train/dev splits or overlapping CommonVoice/IndicCorp corpora; exact training-set exclusion of FLEURS `test` is **unverified (`CONTAMINATION_RISK_DISCLOSED`)** unless explicitly stated by the model card.
- **Reference Transcripts:** Independent verbatim `raw_transcription` from `google/fleurs` (`reference_status="verified"`). Never derived from any candidate ASR model. Hinglish remains excluded (`NO_VERIFIED_REFERENCE`).

---

## 2. Pre-Registered Acceptance Criteria (Defined Before Running Any M4 Experiment)

A candidate specialist adapter is eligible to be marked **`PROMISING_EXPERIMENTAL`** (never automatically replacing the default provider) only if it satisfies ALL criteria on the **same `m4_eval_50clip` held-out set** against a fresh `faster-whisper-small` baseline run on identical hardware:

| Dimension | Pre-Registered Threshold | Justification |
|---|---|---|
| **Kannada (`kn_in`) Micro WER** | Absolute reduction >= `35` percentage points vs `faster-whisper-small` AND Micro WER <= `0.65` | M3.1 baseline had `100%` WER; candidate must prove genuine Kannada script recognition, not marginal noise. |
| **Telugu (`te_in`) Micro WER** | Absolute reduction >= `35` percentage points vs `faster-whisper-small` AND Micro WER <= `0.65` | Same rationale as Kannada (`100%` baseline WER). |
| **Hindi (`hi_in`) & Tamil (`ta_in`)** | If supported by candidate: Micro WER must not regress by more than `+0.03` vs baseline | Prevents trading Dravidian gains for Indo-Aryan/Tamil regressions on multilingual models. |
| **English (`en_us`) Control** | If supported by candidate: Micro WER <= `0.15` (if monolingual Indic model, `en_us` explicitly marked `UNSUPPORTED_LANGUAGE`, never silently run) | Preserves English usability or explicit routing boundary. |
| **Empty-Hypothesis Rate** | <= `10%` on supported languages | Prevents silent zero-output failures like `fleurs_kn_in_1970`. |
| **Runtime Failure Rate** | `0%` unhandled crashes (`failed_items == 0` on valid audio) | Ensures production stability under `TranscriptionProvider` contract. |
| **Resource & Latency Budget** | Peak RSS <= `3,500 MB` on 16 GB Windows laptop; CPU RTF <= `6.0x` on Kannada/Telugu | Fits local-first workstation envelope without OOM. |
| **Timestamp Contract** | Must honestly emit segment timestamps (`start_time <= end_time`) and set `words=None` if word alignment is unsupported (never fabricate word timings) | Preserves M3.2/M3.4 workstation honesty guarantees. |

---

## 3. Fair Comparison Protocol

1. **Fresh Baseline on Identical Inputs:** Execute `faster-whisper-small` (`cpu`, `int8`) on `m4_eval_50clip` on the same machine immediately adjacent to the candidate run (historical 10-clip smoke scores are NOT reused as the comparator).
2. **Identical Normalization & Metrics:** Both baseline and candidate evaluated with `v2_indic_unicode_safe_nfc`, unclamped Levenshtein micro/macro WER & CER, and raw hypothesis/reference saved side-by-side.
3. **Comparable Decoding Conditions:**
   - Primary condition: `language_mode="forced"` (explicit target language code).
   - Transcription-only timing (`word_timestamps=False`) measured separately from word-alignment timing (`word_timestamps=True`) so models without native word alignment are compared fairly on pure ASR latency.
   - Sequential execution (never run two models concurrently) with cold model init timed separately from per-utterance decode.
   - Record exact memory measurement method (discrete `psutil` RSS observations if installed, else `NOT_MEASURED`), VRAM `NOT_MEASURED` on CPU, and energy `NOT_MEASURED`.
