# M4 Multilingual ASR Decision & Baseline Summary

- **Date:** 2026-11-20
- **Branch:** `feat/m4-multilingual-asr` (stacked on stabilization checkpoint `e36c524` -> `feat/m4-indic-asr-research` `9747503` -> `feat/m3-baseline-execution` `761c9ed`)
- **Dataset (Frozen Held-Out):** `m4_multilingual_eval_50clip@1.0.0` (`50` clips = `10` × `5` languages, `563.92s`, `manifest_sha256: 4426c1e10c85c5caf304db120cd83e445740a077778fdde7086647749c9a1480`; preserves frozen `m4_kn_eval_10clip` verbatim)
- **Dataset (Internal Dev):** `m4_multilingual_dev_50clip@1.0.0` (`50` clips = `10` × `5` languages, `742.84s`, `manifest_sha256: 07a0a362931b144fc715be4b0091b1513c50705013b899821665187718ca0c25`; preserves frozen `m4_kn_dev_10clip` verbatim)
- **Reference Baseline Model:** `faster-whisper-small` (`Systran/faster-whisper-small`, revision `536b0662742c02347bc0e980a01041f333bce120`, Apache-2.0, `cpu`, `int8`, `cpu_threads=4`, `language_mode=forced`, `beam_size=5`, `vad_filter=False`, `word_timestamps=False`, `v2_indic_unicode_safe_nfc`)
- **First Multilingual Challenger:** `deepdml/faster-whisper-large-v3-turbo-ct2` (revision `4df90f75321148c3a29a9e2351b7ddf8f5b115a8`, MIT, `1,621,669,956` bytes = `1,546.54 MiB`) — **`AWAITING_USER_DOWNLOAD_AUTHORIZATION`** (zero weights downloaded)

---

## 1. Per-Language Decision Table (Forced Mode, Frozen 50-Clip Held-Out Split)

| Language | baseline WER | candidate WER | empty/total | RTF | measured memory | timing status | decision | evidence path |
|---|---:|---:|---:|---:|---|---|---|---|
| `en_us` | `11.00%` (`16S/0D/6I` / `200w`, macro `11.49%`, CER `6.26%`) | `BLOCKED_DOWNLOAD_APPROVAL` | `0/10` | `0.4244x` (`35.46s` / `83.56s`) | `995.09 MB` OS peak WSET (`994.82 MB` 50ms RSS) | `pre-fix: 1/10 EOF +0.54s overshoot; fixed by provider clamp` | `KEEP_DEFAULT_PENDING_CHALLENGER` (baseline meets `<=15%` control) | `reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.json` |
| `hi_in` | `59.48%` (`112S/7D/19I` / `232w`, macro `59.54%`, CER `23.78%`) | `BLOCKED_DOWNLOAD_APPROVAL` | `0/10` | `0.8809x` (`104.38s` / `118.50s`) | `995.09 MB` OS peak WSET (`994.82 MB` 50ms RSS) | `segment_only_valid` (`10/10`) | `KEEP_DEFAULT_PENDING_CHALLENGER` (baseline below `<=35%` usability target) | `reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.json` |
| `kn_in` | `111.03%` (`88S/48D/15I` / `136w`, macro `110.24%`, CER `94.08%`) | `BLOCKED_DOWNLOAD_APPROVAL` | `2/10` (`20%`) | `5.3508x` (`590.08s` / `110.28s`) | `995.09 MB` OS peak WSET (`994.82 MB` 50ms RSS) | `pre-fix: 1/10 EOF overshoot; fixed by provider clamp` | `UNUSABLE_BASELINE_PENDING_CHALLENGER` (fails `<=65%` WER & `<=10%` empty) | `reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.json` |
| `ta_in` | `65.52%` (`77S/7D/11I` / `145w`, macro `65.45%`, CER `15.97%`) | `BLOCKED_DOWNLOAD_APPROVAL` | `0/10` | `1.3958x` (`165.41s` / `118.50s`) | `995.09 MB` OS peak WSET (`994.82 MB` 50ms RSS) | `segment_only_valid` (`10/10`) | `KEEP_DEFAULT_PENDING_CHALLENGER` (baseline below `<=40%` usability target) | `reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.json` |
| `te_in` | `116.06%` (`64S/129D/31I` / `193w`, macro `117.00%`, CER `99.55%`) | `BLOCKED_DOWNLOAD_APPROVAL` | `3/10` (`30%`) | `5.1977x` (`691.72s` / `133.08s`) | `995.09 MB` OS peak WSET (`994.82 MB` 50ms RSS) | `pre-fix: 2/10 EOF overshoot; fixed by provider clamp` | `UNUSABLE_BASELINE_PENDING_CHALLENGER` (fails `<=65%` WER & `<=10%` empty) | `reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.json` |

- **Baseline Corpus Summary:** `50/50` succeeded, `0` crashes, `5/50` (`10%`) empty hypotheses (`2` Kannada, `3` Telugu), Cold Init `1.8633s`, Total Inference `1,587.0527s` over `563.92s` audio (`Corpus RTF 2.8143x`), `50ms` Sampled Max RSS `994.82 MB` (`25,415` samples), OS Peak Working Set `995.09 MB` (`single_process_no_children`), VRAM & Energy `NOT_MEASURED`.
- **Important Diagnostic Catch (Timing Validity):** Independent timing validation caught `4/50` baseline utterances (`fleurs_168de341_en_us_1885`, `kn_in_1663`, `te_in_1743`, `te_in_1921`) where Whisper predicted segment `end_time` past the actual audio EOF (e.g., `9.48s` on an `8.94s` English clip). `FasterWhisperProvider.transcribe()` was fixed to clamp segment and word boundaries to `[0.0, info.duration]` and drop post-EOF hallucination segments (`test_provider_clamps_segment_and_word_timings_to_audio_duration`).

---

## 2. Exact Reproduction Commands

### Materialize & Validate Frozen 5-Language Splits
```powershell
$env:PYTHONPATH = "backend;."
.venv\Scripts\python.exe scripts/materialize_m4_multilingual_splits.py
uv run --project backend --no-sync python scripts/validate_indic_bench.py --dataset-root data/indic_creator_bench/m4_multilingual_dev_50clip
uv run --project backend --no-sync python scripts/validate_indic_bench.py --dataset-root data/indic_creator_bench/m4_multilingual_eval_50clip
```

### Reproduce 5-Language `faster-whisper-small` Baseline (Forced, CPU `int8`, `cpu_threads=4`)
```powershell
$env:PYTHONPATH = "backend;."
$env:HF_HUB_OFFLINE = "1"
$env:AROVA_MODELS_HOME = "D:\ArovaStep2ASRProgram\models"
uv run --project backend --no-sync python scripts/run_m3_asr_baseline.py `
  --dataset-root data/indic_creator_bench/m4_multilingual_eval_50clip `
  --model-size-or-path D:\ArovaStep2ASRProgram\models\faster-whisper-small `
  --model-id faster-whisper-small `
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 `
  --device cpu --compute-type int8 --cpu-threads 4 `
  --language-mode forced --beam-size 5 --no-word-timestamps `
  --checkpoint D:\ArovaStep2ASRProgram\tmp\m4_small_eval50_forced.ckpt.jsonl `
  --json-out reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.json `
  --md-out reports/product-acceptance/M4_MULTILINGUAL_BASELINE_SMALL_FORCED.md
```

### Next Command (Immediately After User Approves `1,546.54 MiB` Download to `D:`)
1. Download `deepdml/faster-whisper-large-v3-turbo-ct2@4df90f75321148c3a29a9e2351b7ddf8f5b115a8` into `D:\ArovaStep2ASRProgram\models\faster-whisper-large-v3-turbo\` and verify `model.bin` SHA-256 `e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da`.
2. Run the exact matched 50-clip forced-mode evaluation (`cpu`, `int8`, `cpu_threads=4`, `beam_size=5`, `--no-word-timestamps`) + Auto-LID confusion evaluation if Auto mode is exposed in UI.
3. Apply `evaluate_multilingual_language_decision()` per language; only if a language misses its gate, evaluate the corresponding pinned specialist (`vasista22/whisper-kannada-small` / `vasista22/whisper-telugu-small`).

---

## 3. Experimental Status & Next Unresolved Gates
- **Current Product Default:** Unchanged (`faster-whisper-small`; reliable on English `11.00%` WER, draft-only on Hindi `59.48%` / Tamil `65.52%`, unusable on Kannada `111.03%` / Telugu `116.06%`).
- **Next Unresolved Gate #1:** User download authorization for `deepdml/faster-whisper-large-v3-turbo-ct2` (`1,546.54 MiB` to `D:\ArovaStep2ASRProgram\models\faster-whisper-large-v3-turbo\`, `~3.1 GiB` peak temp on `D:` with `69.12 GB` free).
- **Next Unresolved Gate #2:** Authorized real creator recordings (names, music, spontaneous speech) required before changing any language's product default beyond `PASS_EXPERIMENTAL`.
- **Next Unresolved Gate #3:** Mixed-language / Hinglish remains excluded (`NO_VERIFIED_REFERENCE`).
