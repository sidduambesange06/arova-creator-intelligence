# M3.3 Real-Pixel Optical OCR Execution Report

- **Generated UTC:** 2026-11-19T10:34:54.885738+00:00
- **Git HEAD:** `f4f9b75ad10a9293e62a5361ce54c0df89b0a09d`
- **Engine:** `rapidocr_onnxruntime==1.4.4` (`Apache-2.0`, bundled PP-OCRv4 ONNX models, zero runtime downloads)
- **Supported Scripts (Default Bundled Weights):** Latin (English) & Han (Chinese). **Indic scripts are NOT claimed or supported by these default weights.**
- **Source Media:** `tears_of_steel_720p.mov` (CC-BY 3.0) — SHA-256 immutable verified: `True` (`efa9062d9cdb7a338e40ad530dfdf234806743f29ae6a1a136b97ece4e588e8f`)
- **Normalization Policy:** `v2_indic_unicode_safe_nfc`
- **Corrupt Frame Safety:** `True`
- **RSS Max Observed (discrete psutil samples):** `None MB` | **VRAM / Energy:** `NOT_MEASURED`

## Summary Metrics

| Metric | Value |
|---|---|
| Frames Evaluated | `6` (4 text, 2 no-text) |
| Mean Clear-Text CER | `0.0429` |
| Mean All-Text CER | `0.0598` |
| Text Detection Misses | `0` |
| No-Text False Positives | `0` |
| Mean Latency (ms/frame) | `1667.65` |

## Per-Frame Real-Pixel Results

| Frame ID | Category | Timestamp (s) | Status | Latency (ms) | CER | Reference | Extracted |
|---|---|---:|---|---:|---:|---|---|
| `tos_f01_clear_opening` | `clear_text` | 6.0 | `extracted` | 1619.3 | `0.035714` | the Mango Open Movie project | the Mango Dpen Movie project |
| `tos_f03_difficult_overlay` | `difficult_text` | 45.0 | `extracted` | 1573.8 | `0.071429` | 40 YEARS LATER | 40 YEARSLATER |
| `tos_f06_credits_multiline` | `clear_text` | 608.0 | `extracted` | 2451.3 | `0.05` | Cast Old Thom DEREK DE LINT Barley SERGIO HASSELBAINK Captain ROGIER SCHIPPERS Thom VANJA RUKAVINA Celia DENISE REBERGEN Djenghis JODY BHE Tech head CHRIS HALEY | Cast OldThomDEREK DELINT Barley SERGIOHASSELBAINK CaptainROGIERSCHIPPERS Thom VANJARUKAVINA Celia DENISE REBERGEN Djenghis JoDYBHE Tech head CHRIS HALEY |
| `tos_f07_logo_and_url` | `difficult_text` | 625.0 | `extracted` | 1563.8 | `0.081967` | All CG and VFX realised entirely with blender www.blender.org | AllLCGandVFX realisedentirelywith blender' www.blender.org |
| `tos_f04_no_text_dialogue` | `no_text` | 120.0 | `empty` | 1500.5 | `0.0` | _(none)_ | _(none)_ |
| `tos_f05_no_text_closeup` | `no_text` | 240.0 | `empty` | 1297.2 | `0.0` | _(none)_ | _(none)_ |
