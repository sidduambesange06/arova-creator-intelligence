# M4.2a Model Acquisition & Conversion Manifest — `vasista22/whisper-kannada-small`

- **Status:** `AWAITING_USER_DOWNLOAD_AUTHORIZATION` (zero weights downloaded as of 2026-11-19)
- **Model Identifier:** `vasista22/whisper-kannada-small`
- **Pinned Immutable Revision (HF Commit SHA):** `6f8e7b770513d941e4713b20adde26af32b2970b`
- **Source URL:** https://huggingface.co/vasista22/whisper-kannada-small/tree/6f8e7b770513d941e4713b20adde26af32b2970b
- **Gating / Terms:** `gated=False` (no HF login or gated terms acceptance required)
- **License:** `Apache-2.0` (weights); `MIT` (`faster-whisper` / `ctranslate2` runtime)
- **Executable Repository Code:** None (`0` `.py` files in revision; `trust_remote_code=False`)

---

## 1. Exact Selective Download File List (HF API Verified 2026-11-19)

The upstream repository totals `1,846.2 MB` because it hosts duplicate Flax (`flax_model.msgpack`, `922.16 MB`) and PyTorch (`pytorch_model.bin`, `922.30 MB`) weights. Selective download fetches **only** the PyTorch weights and tokenizer/config JSON files required for local CTranslate2 `int8` conversion:

| File | Size (Bytes) | Size (MB) | Included? | Purpose |
|---|---:|---:|---|---|
| `pytorch_model.bin` | `967,104,087` | `922.30` | **YES** | PyTorch Whisper-small fine-tuned weights |
| `vocab.json` | `1,036,584` | `0.99` | **YES** | Tokenizer vocabulary |
| `merges.txt` | `493,864` | `0.47` | **YES** | BPE merges |
| `preprocessor_config.json` | `185` | `<0.01` | **YES** | Mel spectrogram feature extractor config |
| `normalizer.json` | `52,715` | `0.05` | **YES** | Tokenizer normalizer |
| `config.json` | `1,254` | `<0.01` | **YES** | Model architecture config |
| `generation_config.json` | `3,522` | `<0.01` | **YES** | Decoding defaults |
| `tokenizer_config.json` | `829` | `<0.01` | **YES** | Tokenizer config |
| `added_tokens.json` | `2,095` | `<0.01` | **YES** | Added special tokens |
| `special_tokens_map.json` | `2,080` | `<0.01` | **YES** | Special token mapping |
| `flax_model.msgpack` | `966,955,517` | `922.16` | **NO (EXCLUDED)** | Unused Flax weights |
| `training_args.bin` | `3,384` | `<0.01` | **NO (EXCLUDED)** | Unused training pickle (excluded for hygiene) |
| **Total Selective Transfer** | **`~968,697,215`** | **`~924.0 MB`** | | |

---

## 2. Storage & Conversion Plan (External Drive `D:\` Only)

- **Verified Disk Free Space (2026-11-19):** `C:\` has `3.28 GB` free (do NOT place weights on `C:\`); `D:\` has **`69.13 GB` free**.
- **Source Download Directory:** `D:\ArovaStep2ASRProgram\models\vasista22-whisper-kannada-small-src\` (`~924 MB`, deletable after verified CT2 conversion if desired).
- **Converted Offline Runtime Directory:** `D:\ArovaStep2ASRProgram\models\vasista22-whisper-kannada-small-ct2-int8\` (`~250–480 MB` final `model.bin` + tokenizer/config files).
- **Peak Temporary Disk Space During Conversion:** `~2.5 GB` on `D:\` (`HF_HOME` and `TMPDIR` pinned to `D:\ArovaStep2ASRProgram\tmp\`).
- **One-Time Conversion Command (run only after user approves download):**
  - Requires `transformers` + `torch` (CPU) + `ctranslate2` (`ct2-transformers-converter`) in an isolated conversion venv on `D:\` (never bloating `backend/pyproject.toml` runtime dependencies!).
  - Exact command:
    ```powershell
    ct2-transformers-converter `
      --model D:\ArovaStep2ASRProgram\models\vasista22-whisper-kannada-small-src `
      --output_dir D:\ArovaStep2ASRProgram\models\vasista22-whisper-kannada-small-ct2-int8 `
      --copy_files tokenizer_config.json vocab.json merges.txt normalizer.json preprocessor_config.json added_tokens.json special_tokens_map.json `
      --quantization int8
    ```
- **Runtime Execution (strictly offline, zero extra backend deps):**
  - Executed via existing `FasterWhisperProvider(model_size_or_path="D:\\ArovaStep2ASRProgram\\models\\vasista22-whisper-kannada-small-ct2-int8", model_id="vasista22/whisper-kannada-small", model_revision="6f8e7b770513d941e4713b20adde26af32b2970b", supported_languages={"kn"}, supports_word_timestamps=False)` with `HF_HUB_OFFLINE=1` and `local_files_only=True`.
