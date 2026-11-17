# M2 Acceptance & Verification Report — Indic Creator Bench (`V12 Phase 1`)

**Project:** Arova Creator Intelligence (`sidduambesange06/arova-creator-intelligence`)  
**Milestone:** `M2` — Indic Creator Bench (`V12 Phase 1`: Dataset Contracts, Manifest Loader, 10-Clip Smoke Corpus & Batch/ASR Provenance)  
**Runtime Loop:** Existing V11.0 Autonomous Engineering Loop (`[[PROJECT_STATUS]]`, `.arova-loop/`)  
**Git Baseline:** Branch `test/tears-of-steel-full-media-validation`, `HEAD = fce662f1460d262664530f36dde260e7e0a8b815` (zero commits/pushes made; zero audio `.wav` files tracked)  
**Audit Date:** 2026-11-15 (`UTC`)  
**Verdict:** **`8/8 ACCEPTANCE GATES PASS — M2 DATA FOUNDATION VERIFIED (ASR INFERENCE NOT_RUN BY DESIGN)`**

---

## 1. Executive Summary

M2 establishes the versioned, security-hardened, and independently verifiable data foundation for the **Arova Indic Creator Bench**:

1. **Versioned Contracts (`1.0.0`):** Published JSON Schema Draft 2020-12 definitions for Dataset Descriptor (`dataset_descriptor_v1.schema.json`), Sample Record (`sample_record_v1.schema.json`), and ASR & Batch Provenance (`provenance_v1.schema.json`).
2. **Hardened Manifest Loader & Integrity Validator:** Implemented in `backend/app/ai/evaluation/indic_bench.py`, reusing `backend/app/core/security.py::compute_sha256` with strict relative-path containment (`PATH_ESCAPE`), segment-by-segment symlink rejection (`SYMLINK_ESCAPE`), regular-file & byte SHA-256 verification (`CHECKSUM_MISMATCH`), `soundfile.info()` stream validation (`UNSUPPORTED_AUDIO_FORMAT`), schema/version checks (`UNSUPPORTED_SCHEMA`, `INVALID_MANIFEST`), duplicate ID checks (`DUPLICATE_SAMPLE`), script/language checks (`INVALID_LANGUAGE_METADATA`), and `VALID` / `PARTIAL` / `INVALID` reporting.
3. **10-Clip Real Smoke Corpus:** Extracted 10 unmodified real speech WAV clips (2 each across `hi_in` Devanagari, `kn_in` Kannada, `ta_in` Tamil, `te_in` Telugu, and `en_us` Latin control) from pinned local `google/fleurs` parquets (`168de341b3db6859a9bac1c50a2ef5e3b47647e0`, `CC-BY-4.0`) into git-ignored `data/indic_creator_bench/m2_smoke_10clip/audio/`, with frozen descriptor & JSONL contracts in `sample_data/indic_creator_bench/m2_smoke_10clip/`. Hinglish is explicitly excluded (`reports/asr_eval/hinglish_template.json` records `status: "NO_VERIFIED_REFERENCE"`).
4. **Indic Unicode Safety & Deterministic Provenance:** Implemented `v2_indic_unicode_safe_nfc` normalization preserving combining matras, viramas, nukta, and ZWJ/ZWNJ joiners (verified directly on real FLEURS Telugu `\u200c` ZWNJ text `గేమ్స్‌లో`), zero-denominator-safe WER/CER metrics, and secret-safe `ASRRunProvenance` / `BatchRunProvenance` builders with canonical SHA-256 config fingerprinting.

---

## 2. Acceptance Gates Verification (`G1`–`G8`)

| Gate | Requirement | Verification Evidence | Status |
| :--- | :--- | :--- | :--- |
| **`G1`** | M1 transition verified; Git baseline & V11.0 state recovered safely | Branch `test/tears-of-steel-full-media-validation`, `HEAD = fce662f1460d262664530f36dde260e7e0a8b815`, zero dependency file edits (`pyproject.toml`, `backend/pyproject.toml`, `frontend/package.json`), zero DB migrations, zero commits | **PASS** |
| **`G2`** | Dataset & sample schemas versioned, documented, and validated | Draft 2020-12 schemas created under `sample_data/indic_creator_bench/schemas/` (`dataset_descriptor_v1.schema.json`, `sample_record_v1.schema.json`, `provenance_v1.schema.json`) and enforced via `Draft202012Validator` | **PASS** |
| **`G3`** | Manifest loader passes schema, integrity, and filesystem-security tests | `test_indic_creator_bench_m2.py` (`14/14` passed) covers valid corpus, `UNSUPPORTED_SCHEMA`, `DUPLICATE_SAMPLE`, `MISSING_ASSET`, `PARTIAL`, `CHECKSUM_MISMATCH`, `PATH_ESCAPE`, `SYMLINK_ESCAPE`, `UNSUPPORTED_AUDIO_FORMAT`, `MISSING_REFERENCE`, `INVALID_LANGUAGE_METADATA` | **PASS** |
| **`G4`** | Exactly 10 real samples have valid local audio, verified source, and attribution | `validate_indic_bench.py` verified `10/10` clips (`hi_in`: 2, `kn_in`: 2, `ta_in`: 2, `te_in`: 2, `en_us`: 2) at `16000 Hz`, `1ch`, `WAV`, `CC-BY-4.0`, pinned `google/fleurs` commit `168de341b3db6859a9bac1c50a2ef5e3b47647e0`; Hinglish excluded | **PASS** |
| **`G5`** | Original Indic references preserved; Unicode-safe text & safe metric handling | `raw_transcription` preserved untouched (`raw_unchanged = true`, `self_wer = 0.0`, `self_cer = 0.0` on all 10 clips); `v2_indic_unicode_safe_nfc` preserves matras, viramas, nukta, ZWJ/ZWNJ; safe empty-reference WER/CER handling verified | **PASS** |
| **`G6`** | Batch/ASR provenance contract deterministic, reproducible, and secret-safe | `ASRRunProvenance` (`b0129a49e425b8db3c160daee2191d45a647941b07d71eba2445dd497ddd24a8`) & `BatchRunProvenance` (`e15a276ce786d05503724ef9147736cc104d6f48e8c1fc65fd844fa65ac64041`) validated against `provenance_v1.schema.json` with secret-leak rejection tests passing; `execution_status: "NOT_RUN"` | **PASS** |
| **`G7`** | Regression suites and system health verification pass | Targeted M2 pytest `14/14` passed (`1.71s`), full backend/MCP pytest `256/256` passed (`41.95s`), `scripts/validate_indic_bench.py` exited `0`, and `scripts/system_health_audit.py` verified `7/7 HEALTHY` | **PASS** |
| **`G8`** | Existing loop state (`.arova-loop/`), GitHub-facing docs, and Obsidian `docs/` synchronized | `.arova-loop/*`, `docs/{PROJECT_STATUS,DEVELOPMENT_LOG,TECHNICAL_DECISIONS,FEATURE_STATUS}.md`, and `sample_data/indic_creator_bench/m2_smoke_10clip/README.md` updated cleanly | **PASS** |

---

## 3. 10-Clip Smoke Corpus Inventory & Checksums

Dataset ID: `indic_creator_bench_m2_smoke` (`1.0.0`, split: `smoke`)  
Manifest SHA-256: `6fd397de981ab35e0ac884b9e37873630f5920ce0f0b886e3c33ac93a46b93a4`  
Audio Materialization Location (Git-Ignored): `data/indic_creator_bench/m2_smoke_10clip/audio/`

| Utterance ID | Language | Script | Source Row ID | Stream | Duration | Audio SHA-256 | Reference Status |
| :--- | :--- | :--- | :---: | :--- | ---: | :--- | :--- |
| `fleurs_hi_in_1718` | `hi_in` | `Deva` | `1718` | `WAV 16000Hz 1ch` | `15.000s` | `6c1e02d23469dcb2717843a2f4db5f363841a4967376fb587a902fea992c8868` | `verified` |
| `fleurs_hi_in_1836` | `hi_in` | `Deva` | `1836` | `WAV 16000Hz 1ch` | `17.100s` | `c1c970d98d4ac10c9fe8e5eb7e22779945ff8fb75c71bf384ba2709261210c65` | `verified` |
| `fleurs_kn_in_1923` | `kn_in` | `Knda` | `1923` | `WAV 16000Hz 1ch` | `21.960s` | `9698d295a967f041de32620e7af1372699e4dff6ac9232c8ed8433e6785c6a8a` | `verified` |
| `fleurs_kn_in_1970` | `kn_in` | `Knda` | `1970` | `WAV 16000Hz 1ch` | `13.920s` | `006e3b910efffc2e4a1c657b6ff95a931cb91f92251068b15a978a33037d921f` | `verified` |
| `fleurs_ta_in_1740` | `ta_in` | `Taml` | `1740` | `WAV 16000Hz 1ch` | `7.740s` | `ca25c226a26abf6a84f120ebe2eb9402c261978ce2c6d209b7f454452808fd7c` | `verified` |
| `fleurs_ta_in_1732` | `ta_in` | `Taml` | `1732` | `WAV 16000Hz 1ch` | `15.000s` | `f1d3805ce8a47e16b36e7c85fd652296d7796c79555980e296cbd42e9059baee` | `verified` |
| `fleurs_te_in_1666` | `te_in` | `Telu` | `1666` | `WAV 16000Hz 1ch` | `10.080s` | `7012022d111ae03810895fad4b092784056686370f70bf57ab98dc3e2dcb7464` | `verified` |
| `fleurs_te_in_2002` | `te_in` | `Telu` | `2002` | `WAV 16000Hz 1ch` | `10.620s` | `89bca5318ba1737af78071c5fbaa796b50a69a5d8e56634bb1ece573eb8fc80d` | `verified` |
| `fleurs_en_us_1950` | `en_us` | `Latn` | `1950` | `WAV 16000Hz 1ch` | `11.460s` | `260bdd1a15e1d35bcc5d91667516ca3bc659285e10f94872182715bcd7880398` | `verified` |
| `fleurs_en_us_1938` | `en_us` | `Latn` | `1938` | `WAV 16000Hz 1ch` | `11.420s` | `3802ffc3e69c66e0d2e66652015bff0c6b1b8498bfb8670623eb4e34bc9e008d` | `verified` |

---

## 4. Explicit Scope Boundaries & Non-Claims

- **ASR Inference Status:** `NOT_RUN` — M2 delivers dataset schemas, manifest validation, 10-clip smoke corpus contracts, Indic Unicode safety, and ASR/batch provenance contracts only; model execution moves to `M3`.
- **Hinglish Policy:** Excluded (`status: "NO_VERIFIED_REFERENCE"` in `reports/asr_eval/hinglish_template.json`).
- **Git & Dependency Safety:** Zero files added to Git LFS or tracked audio binaries; `pyproject.toml`, `backend/pyproject.toml`, and `frontend/package.json` unchanged; zero ORM/Alembic DB mutations.
