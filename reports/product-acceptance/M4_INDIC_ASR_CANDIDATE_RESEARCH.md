# M4.0 Specialist Indic ASR Candidate Research (v1.1)

- **Research Date:** 2026-11-19
- **Branch:** `feat/m4-indic-asr-research` (merged `feat/m3-baseline-execution` `761c9ed`)
- **Primary Problem Being Solved:** In M3.1 (`faster-whisper-small`, CPU `int8`), Kannada (`kn_in`) and Telugu (`te_in`) both recorded **100.0% micro WER** (including an empty hypothesis on `fleurs_kn_in_1970`) and slow `6.2x–8.5x` RTF, while Hindi (`54.4%` WER) and Tamil (`61.1%` WER) showed high error rates. English (`9.4%` WER, `0.30x` RTF) serves as a non-regression control for multilingual comparators.
- **Host Storage Constraint (Verified 2026-11-19):** `C:\` has only `3.28 GB` free; `D:\` has **`69.13 GB` free**. All M4 model downloads, temporary conversion artifacts, and converted CTranslate2 weights are strictly targeted to `D:\ArovaStep2ASRProgram\models\`.

---

## 1. Shortlisted Candidates (Verified Against Official Repositories & HuggingFace API, 2026-11-19)

| Field | Candidate 1 (SELECTED FIRST): `vasista22/whisper-kannada-small` | Candidate 2 (DEFERRED TO M4.2b): `vasista22/whisper-telugu-small` | Candidate 3 (DEFERRED TO M4.2c): `deepdml/faster-whisper-large-v3-turbo-ct2` | Candidate 4 (DEFERRED — GATED): `ai4bharat/indic-conformer-600m-multilingual` | Comparator (Remote): Bhashini ULCA / Dhruva API |
|---|---|---|---|---|---|
| **Publisher** | Vasista Sai Lodagala / IIT Madras Speech Lab | Vasista Sai Lodagala / IIT Madras Speech Lab | OpenAI (`openai/whisper-large-v3-turbo`) / `deepdml` CT2 export | AI4Bharat (IIT Madras) | Digital India BHASHINI / AI4Bharat |
| **Immutable Revision (HF SHA)** | `6f8e7b770513d941e4713b20adde26af32b2970b` | `717212f9c4c16a78a86ddcb98f93c7f73ef8a5cc` | Official: `41f01f3fe87f28c78e2fbf8b568835947dd65ed9`<br>CT2: `4df90f75321148c3a29a9e2351b7ddf8f5b115a8` | `2a77d305038dfc502fd9464e7d028b90381976cb` | N/A (remote service) |
| **Gating / Access** | **Ungated (`gated=False`)** | **Ungated (`gated=False`)** | **Ungated (`gated=False`)** | **`gated=auto`** (requires HF account + token acceptance) | Requires Bhashini credentials + user consent |
| **Executable Repo Code** | **None (0 `.py` files; `trust_remote_code=False`)** | **None (0 `.py` files; `trust_remote_code=False`)** | **None (0 `.py` files; `trust_remote_code=False`)** | Requires `trust_remote_code=True` | Remote API |
| **Full Repo vs Required Transfer Size** | Repo total `1,846.2 MB` (includes both Flax `922.16 MB` and PyTorch `922.30 MB`). **Required transfer for CT2 conversion: `~924.0 MB`** (`pytorch_model.bin` + config/tokenizer JSONs only; excludes `flax_model.msgpack`). Converted CT2 `int8`: `~250–480 MB`. | Same dual-framework structure (`~924.0 MB` required PyTorch transfer; excludes Flax) | `1,546.5 MB` (CT2 fp16; runs `int8` in RAM) | `2,438.1 MB` (~2.44 GB) | `0 MB` local (network upload required) |
| **Languages & Boundary** | **Kannada (`kn`) ONLY** — non-Kannada calls MUST raise `UNSUPPORTED_LANGUAGE` (zero silent fallback) | **Telugu (`te`) ONLY** | 99 languages incl. `kn`, `te`, `hi`, `ta`, `en`; Dravidian CPU accuracy unverified | 22 scheduled Indian languages; **no English** | 22 Indian languages + English |
| **Code / Weight License** | **Apache-2.0** (weights); MIT (`faster-whisper` / `ctranslate2`) | **Apache-2.0** (weights); MIT runtime | **MIT** (OpenAI weights & CT2 runtime) | MIT (code & weights) | Service Terms (remote API) |
| **Execution Mode** | Local offline CTranslate2 via existing `FasterWhisperProvider` after one-time local `ct2-transformers-converter --quantization int8` | Same as Candidate 1 | Direct drop-in via existing `FasterWhisperProvider` | Local (`onnxruntime`/`transformers` + `trust_remote_code=True`) | **Remote cloud only** (strictly behind 5-gate `AIConsent`) |
| **Timestamps** | Segment-level native; Whisper cross-attention word alignment disabled (`supports_word_timestamps=False`) unless verified on fine-tuned weights | Same as Candidate 1 | Native segment + Whisper word timestamps | Segment-level (CTC/RNNT frame alignments) | Provider-dependent |
| **Official Source URL** | https://huggingface.co/vasista22/whisper-kannada-small | https://huggingface.co/vasista22/whisper-telugu-small | https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2 | https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual | https://bhashini.gov.in/ |

---

## 2. Single Candidate Selection for First Bounded M4.2a Experiment

- **Unambiguous Selection (M4.2a):** **`vasista22/whisper-kannada-small`** (pinned HF revision `6f8e7b770513d941e4713b20adde26af32b2970b`), converted locally on `D:\` to CTranslate2 `int8` and loaded strictly offline through the hardened `FasterWhisperProvider(supported_languages={"kn"}, supports_word_timestamps=False)`.
- **Why One Single Candidate First (Replacing Earlier Ambiguous "AND/OR"):**
  1. **Lowest transfer & RAM footprint:** Selective download of `pytorch_model.bin` + tokenizer/config JSONs transfers **`~924.0 MB`** (excluding `flax_model.msgpack`) to `D:\`, and converts to a `~250–480 MB` CTranslate2 `int8` checkpoint that runs within the exact same Whisper-small CPU memory envelope as the baseline.
  2. **Cleanest license & security posture:** **Apache-2.0**, **ungated**, **zero executable `.py` code** (`trust_remote_code=False`), and reuses the existing `FasterWhisperProvider` seam with zero new ASR framework.
  3. **Cleanest scientific test:** Evaluates one monolingual Kannada specialist against a fresh `faster-whisper-small` baseline on identical frozen Kannada held-out audio (`m4_kn_eval_10clip`), isolating Kannada ASR viability before spending bandwidth on Telugu (`M4.2b`) or a `1.55 GB` multilingual comparator (`M4.2c`).
  4. **Deferred candidates:** `ai4bharat/indic-conformer-600m-multilingual` remains deferred because it is `gated=auto`, `2.44 GB`, and requires `trust_remote_code=True`. `vasista22/whisper-telugu-small` (`M4.2b`) and `deepdml/faster-whisper-large-v3-turbo-ct2` (`M4.2c`) are deferred to subsequent bounded experiments.
- **Explicit Exclusion:** No unverified/guessed model IDs are included. Bhashini remains strictly a separate, consent-gated remote comparator and was NOT called.
- **Download Authorization Status:** No large model weights have been downloaded yet. Exact files, SHA-256 verification plan, and destination paths are specified in `reports/product-acceptance/M4_MODEL_ACQUISITION_MANIFEST.md`.
