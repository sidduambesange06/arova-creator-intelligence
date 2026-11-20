# M4 Model Acquisition & Conversion Manifest

This manifest tracks pinned, verified external model weights for M4 evaluation. No weights listed as `AWAITING_USER_DOWNLOAD_AUTHORIZATION` have been downloaded yet. All model storage and temporary caches target external drive `D:\` (`69.12 GB` free as of 2026-11-20; `C:\` has `25.84 GB` free). Weights stay strictly outside Git and runtime inference enforces `HF_HUB_OFFLINE=1` + `local_files_only=True`.

---

## Section A — First Multilingual Challenger (PRIORITY): `deepdml/faster-whisper-large-v3-turbo-ct2`

- **Status:** `AWAITING_USER_DOWNLOAD_AUTHORIZATION` (not present in `D:\ArovaStep2ASRProgram\models\` as of 2026-11-20)
- **Model Identifier:** `deepdml/faster-whisper-large-v3-turbo-ct2` (registered catalog ID: `faster-whisper-large-v3-turbo`)
- **Pinned Immutable Revision (HF Commit SHA):** `4df90f75321148c3a29a9e2351b7ddf8f5b115a8`
- **Upstream Base Model:** `openai/whisper-large-v3-turbo` (`41f01f3fe87f28c78e2fbf8b568835947dd65ed9`, MIT)
- **Source URL:** https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2/tree/4df90f75321148c3a29a9e2351b7ddf8f5b115a8
- **Gating / Terms:** `gated=False` (no HF account or gated terms required)
- **License:** `MIT` (verified in upstream `README.md` YAML frontmatter `license: mit`; `faster-whisper` / `ctranslate2` runtime is MIT)
- **Executable Repository Code:** None (`0` `.py` files in revision; `trust_remote_code=False`)
- **CTranslate2 Compatibility (Verified via `config.json` & `preprocessor_config.json`, 2026-11-20):**
  - Stored in FP16 CTranslate2 format (`library_name: ctranslate2`); dynamically quantized to `int8` at load time via `WhisperModel(..., device="cpu", compute_type="int8", local_files_only=True)` — zero conversion step or extra dependencies needed.
  - Supports all 5 target languages (`en`, `hi`, `kn`, `ta`, `te` in `lang_ids`), `feature_size: 128`, and includes native Whisper `alignment_heads` (`[[2,4],[2,11],[3,3],[3,6],[3,11],[3,14]]`).

### Exact File Inventory (HF API Verified 2026-11-20)

| File | Size (Bytes) | Size (MiB) | LFS SHA-256 | Purpose |
|---|---:|---:|---|---|
| `model.bin` | `1,617,884,929` | `1,542.93` | `e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da` | CTranslate2 FP16 Whisper large-v3-turbo weights |
| `tokenizer.json` | `2,710,337` | `2.58` | — | Fast HuggingFace tokenizer |
| `vocabulary.json` | `1,068,114` | `1.02` | — | CTranslate2 vocabulary |
| `README.md` | `2,454` | `<0.01` | — | Model card & MIT license metadata |
| `config.json` | `2,263` | `<0.01` | — | `alignment_heads`, `lang_ids`, `suppress_ids` |
| `.gitattributes` | `1,519` | `<0.01` | — | Git LFS attributes |
| `preprocessor_config.json` | `340` | `<0.01` | — | 128-mel feature extractor config |
| **Total Download Size** | **`1,621,669,956`** | **`1,546.54 MiB` (`1.51 GiB`)** | | **Direct CT2 drop-in (no conversion)** |

### Storage & Temporary Space Plan (`D:\` Only)
- **Destination Directory:** `D:\ArovaStep2ASRProgram\models\faster-whisper-large-v3-turbo\`
- **HF Cache / Temp Directory:** `D:\ArovaStep2ASRProgram\hf_home\` (`HF_HOME` and `TMPDIR` pinned to `D:\ArovaStep2ASRProgram\`)
- **Required Temporary Space During Download:** `~3.1 GiB` peak on `D:\` (HF cache blob + `local_dir` materialization; `~1.51 GiB` steady state if HF cache blob is cleaned after SHA-256 verification).
- **Available Free Space on `D:\`:** `69.12 GB` (well above `15 GiB` budget cap and `5 GiB` free floor enforced by `models_registry.py`).
- **Predicted RAM:** Estimate only (~`1.5–2.5 GB` CPU `int8`); actual `os_peak_wset_mb` and `50ms` sampled RSS will be measured during evaluation.

---

## Section B — Deferred Monolingual Fallback Specialist (Kannada): `vasista22/whisper-kannada-small`

- **Status:** `DEFERRED_PENDING_MULTILINGUAL_RESULT` (evaluate ONLY if `deepdml/faster-whisper-large-v3-turbo-ct2` misses the Kannada gate; zero weights downloaded)
- **Model Identifier:** `vasista22/whisper-kannada-small`
- **Pinned Immutable Revision (HF Commit SHA):** `6f8e7b770513d941e4713b20adde26af32b2970b`
- **Source URL:** https://huggingface.co/vasista22/whisper-kannada-small/tree/6f8e7b770513d941e4713b20adde26af32b2970b
- **Gating / Terms:** `gated=False` | **License:** `Apache-2.0` | **Executable Code:** None (`0` `.py` files)
- **Selective Transfer Size (PyTorch only, excluding `flax_model.msgpack` `922.16 MB` and `training_args.bin`):** `~968,697,215` bytes (`~924.0 MB`)
- **Destination & Peak Temp on `D:\`:** `D:\ArovaStep2ASRProgram\models\vasista22-whisper-kannada-small-src\` -> `D:\ArovaStep2ASRProgram\models\vasista22-whisper-kannada-small-ct2-int8\` (`~2.5 GB` peak temp during one-time local `ct2-transformers-converter --quantization int8` in isolated venv on `D:\`).

---

## Section C — Deferred Monolingual Fallback Specialist (Telugu): `vasista22/whisper-telugu-small`

- **Status:** `DEFERRED_PENDING_MULTILINGUAL_RESULT` (evaluate ONLY if `deepdml/faster-whisper-large-v3-turbo-ct2` misses the Telugu gate; zero weights downloaded)
- **Pinned Immutable Revision (HF Commit SHA):** `717212f9c4c16a78a86ddcb98f93c7f73ef8a5cc`
- **License:** `Apache-2.0` | **Gating:** `gated=False` | **Executable Code:** None (`0` `.py` files)
- **Selective Transfer Size:** `~924.0 MB` (PyTorch only, excluding Flax) to `D:\ArovaStep2ASRProgram\models\`.
