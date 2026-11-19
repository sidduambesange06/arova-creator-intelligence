# M4.0 Specialist Indic ASR Candidate Research

- **Research Date:** 2026-11-19
- **Branch:** `feat/m4-indic-asr-research` (stacked on `feat/m3-baseline-execution` `9b17ef8`)
- **Primary Problem Being Solved:** In M3.1 (`faster-whisper-small`, CPU `int8`), Kannada (`kn_in`) and Telugu (`te_in`) both recorded **100.0% micro WER** (including an empty hypothesis on `fleurs_kn_in_1970`) and slow `6.2x–8.5x` RTF, while Hindi (`54.4%` WER) and Tamil (`61.1%` WER) showed high error rates. English (`9.4%` WER, `0.30x` RTF) serves as a non-regression control.

---

## 1. Shortlisted Candidates (Verified Against Official Repositories & HuggingFace API, 2026-11-19)

| Field | Candidate 1: `ai4bharat/indic-conformer-600m-multilingual` | Candidate 2: `vasista22/whisper-{kannada,telugu,hindi,tamil}-small` | Candidate 3: `openai/whisper-large-v3-turbo` (`deepdml/faster-whisper-large-v3-turbo-ct2`) | Comparator (Remote): Bhashini ULCA / Dhruva API |
|---|---|---|---|---|
| **Publisher** | AI4Bharat (IIT Madras) | Vasista Sai Lodagala / IIT Madras Speech Lab | OpenAI (base) / `deepdml` (CTranslate2 conversion) | Digital India BHASHINI / AI4Bharat |
| **Model Identifier(s)** | `ai4bharat/indic-conformer-600m-multilingual` | `vasista22/whisper-kannada-small`, `vasista22/whisper-telugu-small` (+ `hindi-small`, `tamil-small`) | `openai/whisper-large-v3-turbo` / `deepdml/faster-whisper-large-v3-turbo-ct2` | Configured remote pipeline ID (never hardcoded) |
| **Immutable Revision (HF SHA)** | `2a77d305038dfc502fd9464e7d028b90381976cb` | `kn`: `6f8e7b770513d941e4713b20adde26af32b2970b`<br>`te`: `717212f9c4c16a78a86ddcb98f93c7f73ef8a5cc`<br>`hi`: `fb4a24afc20c42906deed31c3689e4be31da41fe`<br>`ta`: `ac0d71cd70d4c66aec7126996cd9e56e97e698b7` | Official: `41f01f3fe87f28c78e2fbf8b568835947dd65ed9`<br>CT2: `4df90f75321148c3a29a9e2351b7ddf8f5b115a8` | N/A (remote service versioned by provider) |
| **Gating / Access** | **`gated=auto`** (requires HF account + token acceptance) | **Ungated (`gated=False`)** | **Ungated (`gated=False`)** | Requires Bhashini API credentials + user consent |
| **Artifact Size** | `2,438.1 MB` (~2.44 GB) | `1,846.2 MB` PyTorch per language (~250–480 MB after `ct2` `int8` conversion) | `1,547.3 MB` (Official) / `1,546.5 MB` (CT2 fp16; runs `int8` in RAM) | `0 MB` local (network upload required) |
| **Languages & Code-Switching** | 22 scheduled Indian languages (`kn`, `te`, `hi`, `ta`, etc.); **no English**; limited code-switching | Monolingual per checkpoint (`kn`, `te`, `hi`, `ta` separately); **no English / no code-switching** | 99 languages incl. `kn`, `te`, `hi`, `ta`, `en`; multilingual but Dravidian (`kn`/`te`) accuracy unverified on CPU | 22 Indian languages + English; remote ASR models |
| **Code / Weight License** | MIT (code & weights) | Apache-2.0 (weights); CTranslate2/faster-whisper MIT | MIT (OpenAI weights & CTranslate2 runtime) | Service Terms (remote API; non-redistributable) |
| **Execution Mode** | Local (`onnxruntime` / `transformers` with `trust_remote_code=True`) | Local (`faster-whisper` / CTranslate2 after one-time local conversion, or `transformers`) | Local (direct drop-in via existing `FasterWhisperProvider` CTranslate2) | **Remote cloud only** (strictly behind 5-gate `AIConsent`) |
| **Windows / Python 3.11 / CPU Fit** | Medium-High friction: gated HF auth + `trust_remote_code=True` + ~2.44 GB download + ONNX/PyTorch stack on 16 GB RAM | High runtime fit once converted to CT2 `int8` (~380 MB RSS on CPU); one-time conversion requires `transformers` + `ct2-transformers-converter` | **Highest runtime fit**: zero new Python deps, ungated, ~1.55 GB download, ~1.5–2.2 GB RAM on CPU | High network privacy risk; excluded from offline default |
| **Timestamps** | Segment-level (CTC/RNNT frame alignments; no native Whisper word alignment) | Segment-level + Whisper cross-attention word timestamps (must verify quality on fine-tuned weights) | Native segment + Whisper word timestamps | Provider-dependent (segment-level typical) |
| **Maintenance & Integration Risk** | High: `trust_remote_code=True` security review + HF gating blocks zero-auth local installs | Medium: per-language model routing + one-time conversion step; unmaintained since 2023 fine-tune | Low integration complexity; accuracy on Kannada/Telugu may still trail specialist Indic fine-tunes | High privacy/consent overhead; zero offline support |
| **Official Source URLs** | https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual | https://huggingface.co/vasista22/whisper-kannada-small <br> https://huggingface.co/vasista22/whisper-telugu-small | https://huggingface.co/openai/whisper-large-v3-turbo <br> https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2 | https://bhashini.gov.in/ |

---

## 2. Candidate Selection for First Bounded M4.2 Experiment

- **Selected First Local Candidate (M4.2a):** **`vasista22/whisper-kannada-small`** (and companion **`vasista22/whisper-telugu-small`**) converted locally to CTranslate2 `int8` (or executed via an optional `IndicWhisperSpecialistProvider` adapter) — **AND/OR** **`deepdml/faster-whisper-large-v3-turbo-ct2`** as the single-checkpoint multilingual comparator.
- **Decision Rationale:**
  1. `ai4bharat/indic-conformer-600m-multilingual` is **`gated=auto`** (blocks unauthenticated reproducible installs), `2.44 GB`, and requires `trust_remote_code=True`. It is deferred until either ungated ONNX weights with audited loader code are verified or the founder approves HF-token-gated evaluation.
  2. `vasista22/whisper-kannada-small` & `vasista22/whisper-telugu-small` are **Apache-2.0**, **ungated**, directly fine-tuned on Kannada/Telugu speech, and share the exact Whisper-small footprint (~380 MB RSS in `int8`) that fits comfortably on this 16 GB Windows laptop!
  3. `deepdml/faster-whisper-large-v3-turbo-ct2` is **MIT**, **ungated**, covers all 5 languages (`kn`, `te`, `hi`, `ta`, `en`) in one checkpoint, and requires **zero new runtime dependencies** (runs directly on `FasterWhisperProvider`).
- **Download & Authorization Checkpoint:** Both candidates require a `~1.55–1.85 GB` weight download to external storage (`D:\ArovaStep2ASRProgram\models`). Per M4 engineering rules, no large weights were downloaded during this research slice; M4.2 execution will begin once the download target is approved.
- **Explicit Exclusion:** No unverified/guessed model IDs (e.g., "SraVaani") are included. Bhashini remains strictly a separate, consent-gated remote comparator and was NOT called.
