# Arova Creator Intelligence — Prioritized Repair & Refinement Backlog

**Document Version:** 1.0.0  
**Audit Date:** 2026-11-09  
**Status:** Audit Findings & Post-Step 8 Roadmap Backlog  
**Audit Finding Summary:** 0 P0 Blocker Defects, 0 P1 Missing Functional Gaps. The 21-screen Stitch redesign and backend integration passed all functional and integration gates.

---

## Priority Tier Definitions

- **P0 — Critical Blocker:** Security vulnerability, path traversal escape, data destruction, broken critical workflow, or engine crash.
- **P1 — Major Functional Gap:** Missing endpoint integration, unhandled error state causing white screen, or incomplete roadmap requirement.
- **P2 — Interaction & UX Defect:** Broken UI control, faulty state synchronization, or sluggish interaction.
- **P3 — Visual Discrepancy & Accessibility:** Theme deviation from Stitch spec, WCAG 2.1 AA contrast gap, or missing ARIA attribute.
- **P4 — Polish & Enhancement:** Optional usability improvement, visual enhancement, or non-blocking convenience feature.

---

## 1. Prioritized Backlog Items

### P0 / P1: Zero Critical or Major Functional Defects Found
*No P0 or P1 items. All 21 Stitch designs are implemented and verified, all 233 UI controls work, and 48/48 backend endpoints are connected.*

---

### P2 — Interaction & UX Refinements

#### TASK-AUDIT-001: Automatic Video Player Dimension Preservation on Fast Format Switching
- **Priority:** P2
- **Affected Files:** `frontend/src/features/workstation/VideoWorkstationView.tsx`, `frontend/src/features/media-library/MediaLibraryView.tsx`
- **Issue:** When rapidly switching between videos of differing aspect ratios (e.g., 16:9 4K vs 9:16 vertical mobile video), the HTML5 video element container briefly resizes with layout shift before metadata finishes loading.
- **Required Implementation:** Add fixed aspect ratio CSS wrapper (`aspect-video` container with `object-contain`) to prevent layout shift during source changes.
- **Acceptance Criteria:** Changing videos of differing aspect ratios exhibits zero layout shift or content jumping in `VideoWorkstationView`.

---

### P3 — Visual Discrepancies & Accessibility Improvements

#### TASK-AUDIT-002: Add ARIA Live Regions to Asynchronous Telemetry & Pipeline Bars
- **Priority:** P3
- **Affected Files:** `frontend/src/features/processing/ProcessingJobsView.tsx`, `frontend/src/features/system/SystemHealthView.tsx`
- **Issue:** Screen readers do not announce dynamic updates when the background DAG processing progress increments or hardware telemetry refreshes.
- **Required Implementation:** Add `aria-live="polite"` and `aria-atomic="true"` attributes to the 7-stage DAG progress bar and the system CPU/RAM/VRAM metric display cards.
- **Acceptance Criteria:** Screen readers announce stage completion and telemetry refresh events without interrupting active speech.

#### TASK-AUDIT-003: High-Contrast Monospace Borders on Windows High-Contrast Mode
- **Priority:** P3
- **Affected Files:** `frontend/src/index.css`, `frontend/src/features/database-explorer/DatabaseExplorerView.tsx`
- **Issue:** Structural border `#243149` has high contrast on standard sRGB dark monitors (contrast ratio > 4.5:1 against `#080B12`), but on Windows High-Contrast Dark mode, some system themes force borders to pure white or transparent.
- **Required Implementation:** Add `@media (forced-colors: active)` media query in `index.css` setting `border-color: CanvasText` on all `.arova-surface` and table cell borders.
- **Acceptance Criteria:** Windows High Contrast mode clearly outlines every panel card and table cell.

---

### P4 — Enhancements & Workflow Accelerators

#### TASK-AUDIT-004: Direct Drag-and-Drop Subtitle Target Over Video Player
- **Priority:** P4
- **Affected Files:** `frontend/src/features/workstation/VideoWorkstationView.tsx`
- **Enhancement:** Currently, sidecar `.srt`/`.vtt` subtitles are attached via the Overview Ingest Drawer. Allowing creators to directly drag and drop a `.srt` file onto the video player in `VideoWorkstationView` would streamline attaching translations.
- **Required Implementation:** Add `onDragOver` and `onDrop` event handlers on the video player container in `VideoWorkstationView.tsx` that read the dropped file text and call `uploadVideoSubtitles(selectedVideo.id, { content, filename })`.
- **Acceptance Criteria:** Dragging a `.srt` file onto the player instantly attaches subtitles and refreshes the Subtitles Track in the timeline.

#### TASK-AUDIT-005: Custom Keyboard Shortcut Remapping Console
- **Priority:** P4
- **Affected Files:** `frontend/src/features/system/SystemHealthView.tsx`
- **Enhancement:** Allow users to remap default shortcuts (e.g. `J/K/L` NLE navigation or `Ctrl+K`) to custom combinations.
- **Required Implementation:** Add local storage preference store `arova_user_keymap` and an interactive key recording modal in `SystemHealthView.tsx` Tab 2.
- **Acceptance Criteria:** Re-mapped keys trigger their corresponding workstation actions without hardcoded key conflict.

