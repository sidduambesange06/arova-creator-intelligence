# Arova Creator Intelligence — Real-Media Benchmark System

The Arova Real-Media Benchmark System provides reproducible, isolated, and evidence-driven evaluation of the media indexing, speech recognition, scene detection, hybrid retrieval, and grounded Q&A pipelines on real-world media assets.

---

## Architecture & Directory Structure

```text
benchmarks/
    README.md
    manifests/
        tears_of_steel.json
    annotations/
        tears_of_steel/
            transcript_reference.json
            scene_reference.json
            retrieval_queries.json
            grounded_qa_reference.json
    schemas/
        benchmark_manifest.schema.json
        benchmark_result.schema.json

scripts/
    benchmarks/
        run_benchmark.py
        collect_environment.py
        validate_results.py

reports/
    benchmarks/
        alpha-baseline/
            README.md
            final_report.md
            environment.json
            ingestion.json
            asr.json
            scene_detection.json
            ocr.json
            retrieval.json
            grounded_qa.json
            api_performance.json
            resource_usage.json
            failures.json
```

---

## Isolation Guarantees

The benchmark runner executes with strict isolation:
1. **Source Immutability:** Original source video media is strictly opened read-only; pre- and post-processing SHA-256 hashes are verified identical.
2. **Dedicated Workspace:** All benchmark databases, vector stores, and thumbnails are stored under `C:\Arova-Benchmark\workspace\data\` (or custom `--workspace`).
3. **Application State Untouched:** Production databases (`backend/data/app.db`, `./data/app.db`) and user media libraries are never opened or modified.

---

## Execution Guide

### 1. Collect System Environment
```bash
python scripts/benchmarks/collect_environment.py
```

### 2. Run Real-Media Benchmark
```bash
python scripts/benchmarks/run_benchmark.py --manifest benchmarks/manifests/tears_of_steel.json
```
*Optional override:*
```bash
python scripts/benchmarks/run_benchmark.py --manifest benchmarks/manifests/tears_of_steel.json --video "C:\Arova-Benchmark\media\tears_of_steel_720p.mov" --workspace "C:\Arova-Benchmark\workspace"
```

### 3. Validate Benchmark Results Against Schema
```bash
python scripts/benchmarks/validate_results.py --result reports/benchmarks/alpha-baseline/environment.json --schema benchmarks/schemas/benchmark_result.schema.json
```

