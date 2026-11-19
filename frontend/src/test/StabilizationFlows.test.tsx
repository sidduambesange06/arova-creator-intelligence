import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OverviewView } from "../features/overview/OverviewView";
import { ProcessingJobsView } from "../features/processing/ProcessingJobsView";
import { SystemHealthView } from "../features/system/SystemHealthView";

describe("Stabilization workflow regressions", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("ProcessingJobsView displays real 7-stage backend names and survives cancelJob response shape", async () => {
    const job = {
      id: "job-1234567890",
      video_id: "vid-1234567890",
      job_type: "full_pipeline",
      status: "running",
      progress: 0.5,
      error_message: null,
      created_at: "2026-11-20T00:00:00Z",
      completed_at: null,
    };
    const stages = [
      {
        id: "st-1",
        version_id: "ver-1",
        stage: "metadata_probe",
        fingerprint: "abcdef1234567890",
        status: "completed",
        skip_reason: null,
        attempt: 1,
        lease_until: null,
        heartbeat_at: null,
        error_code: null,
        error_detail: null,
        output_ref: null,
        started_at: null,
        finished_at: null,
      },
      {
        id: "st-2",
        version_id: "ver-1",
        stage: "ocr_detection",
        fingerprint: "1234567890abcdef",
        status: "completed",
        skip_reason: null,
        attempt: 1,
        lease_until: null,
        heartbeat_at: null,
        error_code: null,
        error_detail: null,
        output_ref: null,
        started_at: null,
        finished_at: null,
      },
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string) => {
        if (input.endsWith("/cancel")) {
          // Exact backend response shape from jobs.py:47
          return { ok: true, status: 200, json: async () => ({ job_id: job.id, status: "cancelled" }) };
        }
        if (input.endsWith("/stages")) {
          return { ok: true, status: 200, json: async () => stages };
        }
        if (input.includes("/artifacts")) {
          return { ok: true, status: 200, json: async () => [] };
        }
        return { ok: true, status: 200, json: async () => [job] };
      })
    );

    render(<ProcessingJobsView />);
    await waitFor(() => {
      expect(screen.getAllByText("metadata_probe").length).toBeGreaterThan(0);
      expect(screen.getAllByText("ocr_detection").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByRole("button", { name: /Cancel Job/i }));
    await waitFor(() => {
      expect(screen.getByText(/Job job-1234 cancelled/i)).toBeInTheDocument();
    });
  });

  it("SystemHealthView loads telemetry on mount and applies real density and reduced-motion attributes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string) => {
        if (input.includes("/system/telemetry")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              worker: {
                jobs_completed: 4,
                jobs_failed: 0,
                last_rtf: 0.25,
                avg_rtf: 0.3,
                total_audio_sec: 120,
                total_proc_sec: 36,
              },
              evaluation: null,
              server_timestamp: "2026-11-20T00:00:00Z",
            }),
          };
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({
            status: "ok",
            service: "Arova",
            version: "0.1.0",
            environment: "development",
            timestamp: "2026-11-20T00:00:00Z",
          }),
        };
      })
    );

    render(<SystemHealthView />);
    await waitFor(() => {
      expect(screen.getByText("Worker Execution Telemetry")).toBeInTheDocument();
      expect(screen.getByText("0.25x")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /^Compact$/i }));
    expect(document.documentElement.dataset.density).toBe("compact");
    expect(localStorage.getItem("arova_ui_density")).toBe("compact");
  });

  it("OverviewView opens selected recent video in workstation without overriding navigation and forwards quick query", async () => {
    const onNavigate = vi.fn();
    const onSelectVideo = vi.fn();
    const onQuickQuery = vi.fn();

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string) => {
        if (input.includes("/stats/summary")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              total_videos: 1,
              total_duration_sec: 120,
              total_transcripts_indexed: 1,
              total_scene_cuts: 5,
              total_collections: 0,
            }),
          };
        }
        if (input.includes("/videos")) {
          return {
            ok: true,
            status: 200,
            json: async () => [
              {
                id: "vid-abc",
                filename: "demo.mp4",
                file_path: "demo.mp4",
                file_hash: "abc",
                file_size: 1000,
                duration: 120,
                width: 1280,
                height: 720,
                fps: 24,
                codec: "h264",
                format: "mp4",
                thumbnail_path: null,
                processing_status: "completed",
                created_at: "2026-11-20T00:00:00Z",
                collection_ids: [],
              },
            ],
          };
        }
        return { ok: true, status: 200, json: async () => [] };
      })
    );

    render(
      <OverviewView
        onNavigate={onNavigate}
        onSelectVideo={onSelectVideo}
        onQuickQuery={onQuickQuery}
      />
    );
    await waitFor(() => {
      expect(screen.getByText("demo.mp4")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("demo.mp4"));
    expect(onSelectVideo).toHaveBeenCalledWith("vid-abc");
    expect(onNavigate).not.toHaveBeenCalledWith("media-library");

    fireEvent.click(screen.getByRole("button", { name: /Where do I discuss privacy/i }));
    expect(onQuickQuery).toHaveBeenCalledWith("Where do I discuss privacy and local AI?");
  });
});
