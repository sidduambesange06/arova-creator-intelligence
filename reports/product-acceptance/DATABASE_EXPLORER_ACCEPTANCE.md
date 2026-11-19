# Database Explorer & Visual ER Schema Acceptance Report

- **Date:** 2026-11-20
- **Branch / Commits:** `fix/app-recovery-stabilization` (`d45eb29`, `40bf322`, `156bb92`, `0b61c0f`)
- **Frontend Served:** Production build (`npm run build && npm run preview` on `http://127.0.0.1:4173`)
- **Backend Served:** FastAPI (`uvicorn app.main:app` on `http://127.0.0.1:8000`) backed by disposable SQLite online-backup copy of populated `data/app.db` (`798,720` bytes, `30` tables, `0004_transcript_word_timings`)
- **Browser:** Isolated Headless Chrome (`--headless=new`, clean profile on `D:\`) via CDP

---

## 1. Root Cause of Original Failure (Before Repair)
1. **Blank Locked Screen:** Opening `Developer Tools -> Database Explorer` with no token stored rendered **zero content** below the tab bar (`has_locked_guidance: false`), giving no indication that `ADMIN_AUTH_TOKEN` was required or how to unlock it.
2. **Missing ER Visualization:** The `ER Relationships` tab rendered a flat card grid with text arrows (`big_svg_diagram_count: 0`, `has_zoom_controls: false`, `has_list_toggle: false`).
3. **CORS / Preview Blockers:** `X-Admin-Token` was omitted from `CORSMiddleware.allow_headers`, and Vite production preview (`:4173`) was omitted from default `CORS_ORIGINS`.
4. **Redundant Query Storm:** Clicking a table fired **4** API requests including re-running `GET /overview` (`PRAGMA integrity_check` + 30 counts) and `GET /tables` (30 counts).

---

## 2. Verified Acceptance Matrix (After Repair)

| Acceptance Scenario | Expected Behavior | Verified Result | Evidence |
|---|---|---|---|
| **Discoverable Navigation** | Accessible from sidebar `Developer Tools -> Database Explorer` | **PASS** | Live Chrome navigation from `Mission Overview` -> `Database Explorer` |
| **Locked State (No Token)** | Explicit `Locked` badge & instructions for `ADMIN_AUTH_TOKEN` (no blank screen, no hardcoded secret) | **PASS** | `locked_panel_visible: true`, `status_badge: "Locked"`, `has_env_guidance: true` ([db_explorer_locked_desktop.png](file:///c:/Users/Siddhu%20Ambesanage/Downloads/OPEN%20SORCE%20DEVELOPMENT/reports/product-acceptance/screenshots/db_explorer_locked_desktop.png)) |
| **Unauthorized State (Bad Token)** | HTTP `401` explicit `Unauthorized` alert; zero leaked data | **PASS** | `unauthorized_panel_visible: true`, `status_badge: "Unauthorized"` + `test_stabilization_db_safety.py` + `DatabaseExplorer.test.tsx` |
| **Populated Authorized DB** | Real 30-table schema, `0004_transcript_word_timings` revision, `OK` integrity, paginated rows with redaction & BLOB size masking | **PASS** | `status_badge: "Authorized"`, `has_videos_table: true`, `has_revision: true`, `has_integrity_ok: true` |
| **Interactive SVG ER Diagram** | Visual SVG nodes + real SQLite FK Bezier curves, zoom/pan/fit/reset, click node highlights edges + inspector, honest `0 inferred` label | **PASS** | `svg_present: true`, `1628x1180`, **`23` app table nodes**, **`24` actual SQLite FK paths**, `zoom_in_works: true`, `honest_zero_inferred_label: true` ([db_explorer_er_diagram_desktop.png](file:///c:/Users/Siddhu%20Ambesanage/Downloads/OPEN%20SORCE%20DEVELOPMENT/reports/product-acceptance/screenshots/db_explorer_er_diagram_desktop.png)) |
| **Accessible List Alternative** | Keyboard/screen-reader table view of PKs & actual SQLite FKs | **PASS** | Verified in `DatabaseExplorer.test.tsx` (`columnheader: Actual SQLite Foreign Keys`) & live click toggle |
| **Zero Redundant Requests** | Client-side table filtering fires `0` API calls; clicking a table fires ONLY 1 GET (`/rows` or `/tables/{t}`) | **PASS** | `client_side_filter_api_calls: 0`, `rows_click_get_calls: 1` (down from 4) |
| **Lock / Session Wipe** | Clicking `Lock` removes `sessionStorage` token and clears all loaded data | **PASS** | `lock_clears_session_and_data: true` |
| **Empty Database & FTS5 Safety** | 0-row schema & `transcript_chunks_fts` handled cleanly without 500 errors | **PASS** | `test_stabilization_db_safety.py::test_database_explorer_reads_are_strictly_readonly_and_support_empty_and_fts` |
| **Read-Only Non-Mutation Proof** | Zero database mutations; live `data/app.db` untouched | **PASS** | `db_records_immutable: true`, `live_db_immutable: true`, byte-for-byte SHA-256 verified in unit test (`mode=ro` + `PRAGMA query_only=ON`) |
| **Production Console / Page Errors** | Zero unexpected console errors or uncaught page errors | **PASS** | `non_401_console_errors: []`, `total_page_errors: []` |
