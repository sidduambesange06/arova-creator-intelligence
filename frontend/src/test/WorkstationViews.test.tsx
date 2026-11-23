import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CommandItem, CommandPaletteModal } from "../components/CommandPaletteModal";
import { DiscoverySourcesView } from "../features/discovery/DiscoverySourcesView";
import { OverviewView } from "../features/overview/OverviewView";
import { PrivacyAiView } from "../features/privacy-ai/PrivacyAiView";
import { ProcessingJobsView } from "../features/processing/ProcessingJobsView";
import { StorageBackupView } from "../features/storage/StorageBackupView";
import { VideoWorkstationView } from "../features/workstation/VideoWorkstationView";

describe("Cinematic Instrument Workstation Views", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("OverviewView", () => {
    it("renders cockpit metrics, opens ingest modal, and uploads sidecar subtitles", async () => {
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
        const url = String(input);
        if (url.includes("/api/v1/videos/stats/summary")) {
          return new Response(
            JSON.stringify({
              total_videos: 12,
              total_duration_sec: 420.5,
              total_collections: 3,
              total_transcripts_indexed: 12,
              total_scene_cuts: 48,
              engine: "Arova Engine",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/videos/vid-1/subtitles") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              id: "trans-1",
              video_id: "vid-1",
              language: "en",
              model_name: "sidecar-subtitles",
              full_text: "Hello world",
              segments: [],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/videos")) {
          return new Response(
            JSON.stringify([
              {
                id: "vid-1",
                filename: "tears_of_steel.mp4",
                duration: 60.0,
                width: 1920,
                height: 1080,
                fps: 24,
                codec: "h264",
                format: "mp4",
                file_size: 1048576,
                file_hash: "hash123",
                file_path: "C:/videos/tears_of_steel.mp4",
                processing_status: "completed",
                created_at: "2026-11-09T00:00:00Z",
                collection_ids: [],
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/jobs")) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response("{}", { status: 200 });
      });

      const onNavigate = vi.fn();
      render(<OverviewView onNavigate={onNavigate} />);

      await waitFor(() => {
        expect(screen.getByText("Your media, understood.")).toBeInTheDocument();
        expect(screen.getAllByText("12").length).toBeGreaterThan(0);
        expect(screen.getByText("420.5s")).toBeInTheDocument();
      });

      // Open Index Local Media modal
      fireEvent.click(screen.getByRole("button", { name: /Index Local Media/i }));
      expect(screen.getByText("Index Media File / Folder")).toBeInTheDocument();

      // Switch to Subtitle tab
      fireEvent.click(screen.getByText("Attach Sidecar Subtitles (.srt / .vtt)"));
      const textarea = screen.getByPlaceholderText(/Dialogue line here/i);
      fireEvent.change(textarea, {
        target: { value: "1\n00:00:00,000 --> 00:00:02,000\nTest subtitle." },
      });

      fireEvent.click(screen.getByRole("button", { name: "Attach Subtitles" }));

      await waitFor(() => {
        expect(
          screen.getByText(/Subtitles imported successfully for video vid-1!/i)
        ).toBeInTheDocument();
      });

      expect(fetchSpy).toHaveBeenCalled();
    });
  });

  describe("VideoWorkstationView", () => {
    it("renders precision player, multi-track timeline, and triggers lossless clip export", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
        const url = String(input);
        if (url.includes("/api/v1/videos/vid-1/export-clip") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              video_id: "vid-1",
              clip_filename: "clip_vid-1_10s_20s.mp4",
              start_time: 10.0,
              end_time: 20.0,
              duration: 10.0,
              file_size: 500000,
              download_url: "/api/v1/videos/clips/clip_vid-1_10s_20s.mp4",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/videos/vid-1/transcript")) {
          return new Response(
            JSON.stringify({
              id: "t-1",
              video_id: "vid-1",
              language: "en",
              model_name: "faster-whisper",
              full_text: "Precision timeline speech dialogue.",
              segments: [
                {
                  id: "seg-1",
                  start_time: 0.0,
                  end_time: 5.0,
                  text: "Precision timeline speech dialogue.",
                  confidence: 0.99,
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/videos/vid-1/scenes")) {
          return new Response(
            JSON.stringify([
              {
                id: "sc-1",
                video_id: "vid-1",
                scene_index: 0,
                start_time: 0.0,
                end_time: 12.0,
                thumbnail_path: null,
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/videos")) {
          return new Response(
            JSON.stringify([
              {
                id: "vid-1",
                filename: "cinema_cut.mp4",
                duration: 60.0,
                width: 3840,
                height: 2160,
                fps: 30,
                codec: "prores",
                format: "mov",
                file_size: 104857600,
                file_hash: "hashprores",
                file_path: "C:/media/cinema_cut.mp4",
                processing_status: "completed",
                created_at: "2026-11-09T00:00:00Z",
                collection_ids: [],
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/annotations")) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        return new Response("{}", { status: 200 });
      });

      render(<VideoWorkstationView initialVideoId="vid-1" />);

      await waitFor(() => {
        expect(screen.getByText("Multi-Track Intelligence Timeline")).toBeInTheDocument();
        expect(screen.getByText("Precision timeline speech dialogue.")).toBeInTheDocument();
        expect(screen.getByText("Scene #1")).toBeInTheDocument();
      });

      // Export clip
      fireEvent.click(screen.getByRole("button", { name: "Export Lossless MP4 Clip" }));

      await waitFor(() => {
        expect(screen.getByText(/Clip ready: clip_vid-1_10s_20s.mp4/i)).toBeInTheDocument();
        expect(screen.getByText("Download MP4")).toBeInTheDocument();
      });

      // Verify new transport controls, range selection, and transcript filtering
      expect(screen.getByRole("button", { name: "-5s" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "+5s" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Preview Selection" })).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Set Range" }));
      expect(screen.getByText(/Set In: 0.00s/i)).toBeInTheDocument();
      expect(screen.getByText(/Set Out: 5.00s/i)).toBeInTheDocument();

      const filterInput = screen.getByLabelText("Filter transcript segments");
      fireEvent.change(filterInput, { target: { value: "nonexistent phrase" } });
      expect(screen.getByText(/No dialogue segments match the current filter/i)).toBeInTheDocument();
    });

    it("exports SRT/VTT/ASS subtitles with object URL cleanup, gates karaoke on real word timings, and displays honest OCR states", async () => {
      const origCreateObjectURL = URL.createObjectURL;
      const origRevokeObjectURL = URL.revokeObjectURL;
      const createUrlSpy = vi.fn().mockReturnValue("blob:mock-sub-url");
      const revokeUrlSpy = vi.fn();
      URL.createObjectURL = createUrlSpy;
      URL.revokeObjectURL = revokeUrlSpy;
      const anchorClickSpy = vi
        .spyOn(HTMLAnchorElement.prototype, "click")
        .mockImplementation(() => {});

      try {

      const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
        const url = String(input);
        if (url.includes("/api/v1/videos/vid-w/transcript")) {
          return new Response(
            JSON.stringify({
              id: "tx-w",
              video_id: "vid-w",
              language: "hi",
              model_name: "faster-whisper-small",
              full_text: "नमस्ते भारत",
              segments: [
                {
                  id: "seg-w1",
                  start_time: 0.0,
                  end_time: 1.5,
                  text: "नमस्ते भारत",
                  confidence: -0.14,
                  timing_source: "asr_estimated",
                  words: [
                    { word: "नमस्ते", start: 0.0, end: 0.7, probability: 0.94 },
                    { word: "भारत", start: 0.75, end: 1.5, probability: 0.91 },
                  ],
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/videos/vid-w/ocr/status")) {
          return new Response(
            JSON.stringify({
              video_id: "vid-w",
              version_id: "ver-99887766",
              status: "engine_unavailable",
              engine_available: false,
              engine_name: null,
              engine_version: null,
              stage_status: "succeeded",
              skip_reason: "ocr_engine_unavailable:DEPENDENCY_MISSING",
              error_message: null,
              extracted_count: 0,
              frames: [],
              remediation_hint: "Install rapidocr-onnxruntime or tesseract to enable OCR.",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/videos/vid-w/subtitles/export")) {
          return new Response("[Script Info]\n[Events]\nDialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,{\\k70}नमस्ते", {
            status: 200,
            headers: { "Content-Type": "text/plain; charset=utf-8" },
          });
        }
        if (url.includes("/api/v1/videos/vid-w/scenes")) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        if (url.includes("/api/v1/annotations")) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        if (url.includes("/api/v1/videos")) {
          return new Response(
            JSON.stringify([
              {
                id: "vid-w",
                filename: "hindi_clip.mp4",
                duration: 1.5,
                width: 1280,
                height: 720,
                fps: 24,
                codec: "h264",
                format: "mp4",
                file_size: 204800,
                file_hash: "sha256_w",
                file_path: "C:/videos/hindi_clip.mp4",
                processing_status: "completed",
                created_at: "2026-11-19T00:00:00Z",
                collection_ids: [],
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("{}", { status: 200 });
      });

      render(<VideoWorkstationView initialVideoId="vid-w" />);

      await waitFor(() => {
        expect(screen.getByTestId("timing-mode-badge")).toHaveTextContent(
          /ASR-estimated word timing/i
        );
        expect(screen.getByTestId("ocr-state-badge")).toHaveTextContent("OCR Engine Unavailable");
        expect(
          screen.getByText(/Install rapidocr-onnxruntime or tesseract/i)
        ).toBeInTheDocument();
      });

      // Enable ASS karaoke (only rendered because real words exist) and export ASS
      const karaokeCheckbox = screen.getByLabelText(/ASS Karaoke/i);
      fireEvent.click(karaokeCheckbox);
      fireEvent.click(screen.getByRole("button", { name: "Export ASS subtitles" }));

      await waitFor(() => {
        expect(screen.getByRole("status")).toHaveTextContent("Exported hindi_clip.ass");
      });

      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/videos/vid-w/subtitles/export?format=ass&karaoke=true")
      );
      expect(createUrlSpy).toHaveBeenCalledTimes(1);
      expect(anchorClickSpy).toHaveBeenCalledTimes(1);
      expect(revokeUrlSpy).toHaveBeenCalledWith("blob:mock-sub-url");
      } finally {
        URL.createObjectURL = origCreateObjectURL;
        URL.revokeObjectURL = origRevokeObjectURL;
      }
    });

    it("hides karaoke when word timings are absent and renders clickable OCR frame evidence when completed_with_text", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
        const url = String(input);
        if (url.includes("/api/v1/videos/vid-o/transcript")) {
          return new Response(
            JSON.stringify({
              id: "tx-o",
              video_id: "vid-o",
              language: "en",
              model_name: "subtitles:sidecar.srt",
              full_text: "Segment only line",
              segments: [
                {
                  id: "seg-o1",
                  start_time: 0.0,
                  end_time: 3.0,
                  text: "Segment only line",
                  confidence: 1.0,
                  timing_source: "subtitle_cue",
                  words: null,
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/videos/vid-o/ocr/status")) {
          return new Response(
            JSON.stringify({
              video_id: "vid-o",
              version_id: "ver-ocr12345",
              status: "completed_with_text",
              engine_available: true,
              engine_name: "rapidocr_onnxruntime",
              engine_version: "1.4.4",
              stage_status: "succeeded",
              skip_reason: null,
              error_message: null,
              extracted_count: 1,
              frames: [
                {
                  scene_index: 2,
                  timestamp_sec: 14.5,
                  text: "API Endpoint: GET /health",
                  thumbnail_path: "data/thumbnails/scene2.jpg",
                },
              ],
              remediation_hint: null,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/videos/vid-o/subtitles/export")) {
          return new Response(JSON.stringify({ detail: "Export failed" }), { status: 500 });
        }
        if (url.includes("/api/v1/videos/vid-o/scenes")) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        if (url.includes("/api/v1/annotations")) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        if (url.includes("/api/v1/videos")) {
          return new Response(
            JSON.stringify([
              {
                id: "vid-o",
                filename: "ocr_demo.mp4",
                duration: 30.0,
                width: 1280,
                height: 720,
                fps: 24,
                codec: "h264",
                format: "mp4",
                file_size: 409600,
                file_hash: "sha256_o",
                file_path: "C:/videos/ocr_demo.mp4",
                processing_status: "completed",
                created_at: "2026-11-19T00:00:00Z",
                collection_ids: [],
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("{}", { status: 200 });
      });

      render(<VideoWorkstationView initialVideoId="vid-o" />);

      await waitFor(() => {
        expect(screen.getByTestId("timing-mode-badge")).toHaveTextContent(/Segment-level only/i);
        expect(screen.getByTestId("ocr-state-badge")).toHaveTextContent(
          "Completed — 1 Frame(s)"
        );
        expect(screen.getByText("API Endpoint: GET /health")).toBeInTheDocument();
        expect(screen.getByText("ver:ver-ocr1")).toBeInTheDocument();
      });

      // Karaoke option must NOT be rendered when word timings are absent
      expect(screen.queryByLabelText(/ASS Karaoke/i)).not.toBeInTheDocument();

      // Clicking OCR frame seeks player cleanly
      fireEvent.click(screen.getByRole("button", { name: /Seek to OCR frame at 14.5s/i }));

      // Subtitle export failure displays accessible alert
      fireEvent.click(screen.getByRole("button", { name: "Export SRT subtitles" }));
      await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveTextContent("Export failed");
      });
    });
  });

  describe("DiscoverySourcesView", () => {
    it("renders discovery roots and triggers on-demand scan", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
        const url = String(input);
        if (url.includes("/roots/root-1/scan") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              id: "scan-101",
              root_id: "root-1",
              status: "completed",
              started_at: "2026-11-09T10:00:00Z",
              finished_at: "2026-11-09T10:01:00Z",
              checkpoint: null,
              counts: { scanned_files: 50, discovered_media: 15, new_assets: 15 },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/roots/root-1/scans")) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        if (url.includes("/lib-1/roots")) {
          return new Response(
            JSON.stringify([
              {
                id: "root-1",
                library_id: "lib-1",
                label: "Primary Production Vault",
                root_type: "local_fixed",
                volume_id: null,
                marker_id: null,
                policy: "local_only",
                status: "active",
                last_scan_at: null,
                locations_count: 15,
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/libraries")) {
          return new Response(
            JSON.stringify([
              {
                id: "lib-1",
                label: "Master Studio Vault",
                execution_profile: "fully_offline_no_ai",
                created_at: "2026-11-09T00:00:00Z",
                roots_count: 1,
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("{}", { status: 200 });
      });

      render(<DiscoverySourcesView />);

      await waitFor(() => {
        expect(screen.getByText("Primary Production Vault")).toBeInTheDocument();
        expect(screen.getByText("local_only")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: "Scan Selected Root Now" }));

      await waitFor(() => {
        expect(screen.getByText(/Scan finished with status: completed/i)).toBeInTheDocument();
      });
    });
  });

  describe("ProcessingJobsView", () => {
    it("renders 7-stage DAG progress and cancel/resume controls", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
        const url = String(input);
        if (url.includes("/api/v1/jobs/job-1/stages")) {
          return new Response(
            JSON.stringify([
              {
                id: "st-1",
                version_id: "ver-1",
                stage: "transcribe_speech",
                fingerprint: "sha256transcribe123",
                status: "completed",
                attempt: 1,
                lease_until: null,
                heartbeat_at: null,
                error_code: null,
                error_detail: null,
                output_ref: null,
                started_at: "2026-11-09T10:00:00Z",
                finished_at: "2026-11-09T10:02:00Z",
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/jobs/versions/ver-1/artifacts")) {
          return new Response(
            JSON.stringify([
              {
                id: "art-1",
                version_id: "ver-1",
                kind: "transcript_json",
                producer_stage: "transcribe_speech",
                producer_model: "faster-whisper",
                producer_revision: "1.0",
                config_hash: null,
                is_current: true,
                trust: "verified_local",
                created_at: "2026-11-09T10:02:00Z",
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/jobs/job-1/cancel") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              id: "job-1",
              video_id: "vid-1",
              job_type: "multimodal_dag",
              status: "cancelled",
              progress: 0.5,
              error_message: null,
              created_at: "2026-11-09T10:00:00Z",
              completed_at: null,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/jobs")) {
          return new Response(
            JSON.stringify([
              {
                id: "job-1",
                video_id: "vid-1",
                job_type: "multimodal_dag",
                status: "running",
                progress: 0.5,
                error_message: null,
                created_at: "2026-11-09T10:00:00Z",
                completed_at: null,
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response("{}", { status: 200 });
      });

      render(<ProcessingJobsView />);

      await waitFor(() => {
        expect(screen.getByText("7-Stage DAG Progress")).toBeInTheDocument();
        expect(screen.getByText("transcribe_speech")).toBeInTheDocument();
        expect(screen.getByText("Cancel Job")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: "Cancel Job" }));

      await waitFor(() => {
        expect(screen.getByText(/Job job-1 cancelled/i)).toBeInTheDocument();
      });
    });
  });

  describe("PrivacyAiView", () => {
    it("renders provider cards, tests credential verification, and displays Indic matrix", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
        const url = String(input);
        if (url.includes("/api/v1/ai/providers/verify") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              provider: "google-gemini",
              status: "verified",
              model: "gemini-2.5-flash",
              message: "API key and quota verified successfully",
              latency_ms: 184.2,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/ai/providers")) {
          return new Response(
            JSON.stringify([
              {
                id: "google-gemini",
                name: "Google Gemini (Interactions & Live API)",
                configured: true,
                local: false,
                default_model: "gemini-2.5-flash",
                available_models: ["gemini-2.5-flash", "gemini-1.5-pro"],
              },
              {
                id: "local_llama_cpp",
                name: "Local Llama.cpp / Ollama Engine",
                configured: true,
                local: true,
                default_model: "llama-3.2-3b-instruct",
                available_models: ["llama-3.2-3b-instruct"],
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/ai/consents")) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        if (url.includes("/api/v1/ai/runs")) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        return new Response("{}", { status: 200 });
      });

      render(<PrivacyAiView />);

      await waitFor(() => {
        expect(screen.getByText(/Configured AI Providers/i)).toBeInTheDocument();
        expect(screen.getByText("Google Gemini (Interactions & Live API)")).toBeInTheDocument();
        expect(screen.getByText("Local Llama.cpp / Ollama Engine")).toBeInTheDocument();
        expect(screen.getByText("Hindi")).toBeInTheDocument();
        expect(screen.getAllByText("Kannada").length).toBeGreaterThan(0);
      });

      // Click verify credentials
      const verifyBtns = screen.getAllByRole("button", { name: /Verify Credentials/i });
      fireEvent.click(verifyBtns[0]);

      expect(screen.getByText(/Verify Provider: google-gemini/i)).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Run Test Probe" }));

      await waitFor(() => {
        expect(screen.getByText(/API key and quota verified successfully/i)).toBeInTheDocument();
        expect(screen.getByText("Latency: 184.2ms")).toBeInTheDocument();
      });
    });
  });

  describe("StorageBackupView", () => {
    it("renders export wizard and triggers dry-run archive import", async () => {
      vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
        const url = String(input);
        if (url.includes("/api/v1/portable/import/dry-run") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              valid: true,
              format_version: "1.0.0",
              export_id: "exp-101",
              total_entries: 5,
              records_to_import: { videos: 2, transcripts: 2 },
              matching_existing_records: {},
              duplicate_conflicts: 0,
              proposed_id_remappings: 0,
              estimated_size_bytes: 5242880,
              warnings: [],
              errors: [],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        if (url.includes("/api/v1/videos")) {
          return new Response(
            JSON.stringify([
              {
                id: "vid-1",
                filename: "clip.mp4",
                duration: 10.0,
                width: 1920,
                height: 1080,
                fps: 30,
                codec: "h264",
                format: "mp4",
                file_size: 1024,
                file_hash: "hash",
                file_path: "C:/clip.mp4",
                processing_status: "completed",
                created_at: "2026-11-09T00:00:00Z",
                collection_ids: [],
              },
            ]),
            { status: 200 }
          );
        }
        if (url.includes("/api/v1/libraries/duplicates")) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        return new Response("{}", { status: 200 });
      });

      render(<StorageBackupView />);

      await waitFor(() => {
        expect(screen.getByText("Export Portable Archive (.arova)")).toBeInTheDocument();
        expect(screen.getByText("Import Portable Archive")).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText(/e.g. C:\/exports\/my_archive.arova/i);
      fireEvent.change(input, { target: { value: "C:/exports/test.arova" } });

      fireEvent.click(screen.getByRole("button", { name: "1. Dry-Run Preview" }));

      await waitFor(() => {
        expect(screen.getByText("VALID ARCHIVE")).toBeInTheDocument();
        expect(screen.getByText("Total Entries: 5")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "2. Commit Import" })).toBeInTheDocument();
      });
    });
  });

  describe("CommandPaletteModal", () => {
    it("renders modal, filters commands, and handles selection", () => {
      const onClose = vi.fn();
      const onSelectAction = vi.fn();
      const commands: CommandItem[] = [
        {
          id: "cmd-1",
          title: "Index Local Media",
          subtitle: "Scan files into vault",
          category: "Action",
          onSelect: onSelectAction,
        },
        {
          id: "cmd-2",
          title: "Precision Workstation",
          subtitle: "Open timeline editor",
          category: "Navigation",
          onSelect: vi.fn(),
        },
      ];

      render(<CommandPaletteModal isOpen={true} onClose={onClose} commands={commands} />);

      expect(screen.getByPlaceholderText("Type a command or search views...")).toBeInTheDocument();
      expect(screen.getByText("Index Local Media")).toBeInTheDocument();

      // Filter query
      const input = screen.getByPlaceholderText("Type a command or search views...");
      fireEvent.change(input, { target: { value: "Index" } });

      expect(screen.getByText("Index Local Media")).toBeInTheDocument();
      expect(screen.queryByText("Precision Workstation")).not.toBeInTheDocument();

      // Click to select
      fireEvent.click(screen.getByText("Index Local Media"));
      expect(onSelectAction).toHaveBeenCalledTimes(1);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
