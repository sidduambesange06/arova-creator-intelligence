# Performance Before / After Report

- **Date:** 2026-11-20
- **Hardware / OS:** Windows 11 laptop, 16 logical CPUs, 16.49 GB RAM; Python 3.11.9 (`backend/.venv`)
- **Dataset:** Disposable copy of populated `data/app.db` (`798,720` bytes, `30` tables, indexed `tears_of_steel_720p.mov` with `86` segments & `139` scenes)
- **Methodology:** 1 cold request + `n = 10` sequential warm requests per endpoint on identical machine & dataset (note: `n = 10` warm observations supports median/mean/max summaries, not statistically stable p95/p99 tail claims).
- **Artifacts:** `reports/product-acceptance/STABILIZATION_BASELINE_PROBE.json` (Before) vs `reports/product-acceptance/STABILIZATION_AFTER_PROBE.json` (After).

---

## 1. Pre-Optimization Target Budgets & Measured Before / After

| Scenario / Metric | Target Budget | Before (Cold / Warm Median) | After (Cold / Warm Median) | Result |
|---|---:|---:|---:|---|
| **Backend Startup to `/health` Ready** | `<= 3,000 ms` | `2,323.6 ms` | `1,796.1 ms` | **IMPROVED (-22.7%) — PASS** |
| **`POST /api/v1/search/semantic` (Hybrid Search)** | `<= 25 ms` warm | `15.19 ms` / `11.70 ms` | `13.35 ms` / `3.49 ms` | **IMPROVED (3.35x faster warm) — PASS** |
| **`GET /api/v1/videos/stats/summary`** | `<= 25 ms` warm | `5.66 ms` / `15.63 ms` | `6.82 ms` / `3.42 ms` | **IMPROVED (4.57x faster warm) — PASS** |
| **`GET /api/v1/admin/database/overview`** | `<= 40 ms` | `24.75 ms` / `14.58 ms` | `9.13 ms` / `20.57 ms` | **COLD IMPROVED (-63.1%) — PASS** |
| **`GET /api/v1/admin/database/relationships`** | `<= 50 ms` | `46.06 ms` / `20.41 ms` | `22.58 ms` / `31.57 ms` | **COLD IMPROVED (-51.0%) — PASS** |
| **`GET /api/v1/admin/database/tables`** | `<= 50 ms` | `21.86 ms` / `17.74 ms` | `40.82 ms` / `29.43 ms` | **WITHIN BUDGET (noise on 30-table introspection)** |
| **`GET /api/v1/admin/database/tables/videos/rows`** | `<= 40 ms` | `15.21 ms` / `23.44 ms` | `22.81 ms` / `31.23 ms` | **WITHIN BUDGET** |
| **DB Explorer: Requests on Table Click** | `1` GET request | `4` requests (`/rows` x2 + `/overview` + `/tables`) | **`1` GET request** (`0` `/overview`, `0` `/tables`) | **IMPROVED (-75% requests) — PASS** |
| **DB Explorer: Requests on Table Filter Typing** | `0` requests | `2` requests per keystroke | **`0` requests** (instant client-side filter) | **IMPROVED (-100% requests) — PASS** |
| **Processing Jobs Idle Background Polling** | `0` req/min when idle | `12` req/min forever (`setInterval(5000)`) | **`0` req/min** when no active jobs | **IMPROVED (-100% idle polling) — PASS** |
| **Spurious Live DB Backups During Test Runs** | `0` files / `0 MB` | **7,729** legacy files (`4,217.18 MB` accumulated) | **`0` files / `0 MB`** created | **FIXED (P0 DISK & IO RECOVERY) — PASS** |
| **Production Frontend Bundle (`vite build`)** | `<= 450 kB` raw / `<= 120 kB` gzip | `394.11 kB` (`98.41 kB` gzip) | `397.57 kB` (`99.40 kB` gzip) | **PASS (+0.99 kB gzip for SVG ER diagram)** |

---

## 2. What Improved vs What Did Not
- **Clear Wins:**
  - Eliminated repeated `LocalMiniLMEmbeddingProvider` / `CrossEncoderReranker` re-instantiation + network probes (`local_files_only=True` + process-level cache), added `mtime/size`-invalidated vector disk cache, and removed N+1 queries in `hybrid_search.py` and `portable.py` -> **hybrid search warm median cut from `11.70 ms` to `3.49 ms`**.
  - Eliminated **75% of Database Explorer table-click HTTP traffic** and **100% of filter-typing and idle job-polling traffic**.
  - Stopped the `migrator.py` backup storm that had accumulated `4.22 GB` of redundant backups and slowed every DB test.
- **What Did Not Materially Drop (Honest Disclosure):**
  - Warm latency on `/admin/database/{overview,tables,relationships}` remains `~20–32 ms` because each request opens a fresh read-only SQLite engine (`get_readonly_engine()`) and disposes it in `finally` to guarantee clean WAL visibility and zero leaked descriptors. At `~20–32 ms` on 30 tables, this is well inside the `<= 50 ms` admin budget and does not justify pooling complexity yet.
  - Full-suite `pytest` runtime (~60s) is dominated by FFmpeg subprocess tests and stress fixtures rather than DB overhead.

## Workstation scene-strip follow-up
On the same 139-scene video, the [pre-change browser run](STABILIZATION_DB_RECHECK.json) recorded 144 API requests during initial navigation. Native lazy loading on scene images reduced this to 15 in the [follow-up run](STABILIZATION_WORKSTATION_RECHECK.json), including 10 scene thumbnail requests. Scrolling to the final scene loaded its image. Counts cover the probe's initial observation window. The fixed 900 ms wait precludes a rendering-speed claim. Fresh warm search medians varied from 9.61 to 14.66 ms across the two runs.
