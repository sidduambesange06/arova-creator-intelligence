# Arova Creator Intelligence — 100-Query Synthetic Multimodal Retrieval Benchmark

**Date:** 2026-11-01T13:58:41.439436+00:00  
**Dataset:** `sample_data/visual_retrieval_golden_100.json` (100 synthetic queries, 100 synthetic corpus passages)  
**Evaluation Scope:** Curated synthetic evaluation golden set. (Note: Benchmark validation against independently labelled real-world video footage is staged on the Beta roadmap)  
**Hardware Environment:** AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD | Windows 10 | Python 3.11.9  
**Evaluation Mode:** Local CPU Inference (`torch 2.6.0+cpu`, quantized sentence-transformers)

---

## 1. Methodology & Pipeline Architecture

- **Corpus Composition:** 100 curated ground-truth annotated synthetic segments spanning 10 core engineering and creator video domains (FFmpeg pipelines, Whisper ASR, PySceneDetect scene cuts, ChromaDB vector indexing, SQLite FTS5 BM25 lexical search, Cross-Encoder re-ranking, Reciprocal Rank Fusion, FastMCP STDIO transport, Hallmark workstation UI, and Deny-by-default security).
- **Stage 1 (Retrieval):** Dual retrieval combining Dense MiniLM semantic cosine similarity (`all-MiniLM-L6-v2`, 384 dimensions) and Lexical SQLite FTS5 BM25 keywords, fused using Reciprocal Rank Fusion (RRF, $k=60$).
- **Stage 2 (Re-Ranking):** PyTorch Cross-Encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) computing joint query-passage cross-attention scores across top candidates.

---

## 2. Benchmark Retrieval Performance

| Information Retrieval Metric | Stage 1 (Hybrid RRF) | Stage 2 (Cross-Encoder) | Delta (%) |
|---|---|---|---|
| **MRR@10** | `0.9673` | `1.0000` | `+3.4%` |
| **NDCG@10** | `0.9727` | `1.0000` | `+2.8%` |
| **Recall@1** | `0.9600` | `1.0000` | — |
| **Recall@3** | `0.9700` | `1.0000` | — |
| **Recall@5** | `0.9900` | `1.0000` | — |
| **Recall@10** | `0.9900` | `1.0000` | — |

---

## 3. Latency Breakdown (Local CPU Profile)

| Stage | Median (p50) Latency | 95th Percentile (p95) Latency |
|---|---|---|
| **Stage 1 (Embedding + FTS5 + RRF)** | `7.34 ms` | `9.01 ms` |
| **Stage 2 (Cross-Encoder Re-Ranking)** | `8.71 ms` | `10.80 ms` |
| **Total Query Latency** | `16.05 ms` | `19.81 ms` |

---

## 4. Verification Verdict

All 100 synthetic queries were evaluated against verified relevance labels. The benchmark confirms that two-stage retrieval delivers robust precision across spoken voice and visual on-screen text without cloud dependencies. Real-world benchmark validation against independently labelled video footage remains a dedicated Beta roadmap deliverable.
