import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MediaLibraryView } from "../features/media-library/MediaLibraryView";

const SAMPLE_VIDEO = {
  id: "vid-101",
  filename: "architecture_walkthrough.mp4",
  file_path: "C:/videos/architecture_walkthrough.mp4",
  file_hash: "a1b2c3d4e5f60000111122223333444455556666777788889999aaaabbbbcccc",
  file_size: 204800,
  duration: 45.5,
  width: 1920,
  height: 1080,
  fps: 30,
  codec: "h264",
  format: "mp4",
  thumbnail_path: "C:/data/media/thumbnails/vid-101.jpg",
  processing_status: "indexed",
  created_at: "2026-10-30T13:30:00Z",
  collection_ids: [],
};

describe("MediaLibraryView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads indexed videos, seeks player to timestamp, and imports new media", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/api/v1/videos/import") && init?.method === "POST") {
        return new Response(
          JSON.stringify({ imported: [SAMPLE_VIDEO], skipped_duplicates: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url.includes("/api/v1/videos")) {
        return new Response(JSON.stringify([SAMPLE_VIDEO]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/v1/collections")) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("{}", { status: 200 });
    });

    render(<MediaLibraryView />);

    await waitFor(() => {
      expect(screen.getByTestId("video-card-vid-101")).toBeInTheDocument();
    });

    expect(screen.getByTestId("video-inspector-player")).toHaveTextContent("1920x1080");

    const jumpInput = screen.getByLabelText("Jump to (sec):");
    fireEvent.change(jumpInput, { target: { value: "12.5" } });
    fireEvent.click(screen.getByText("Seek Player"));

    const pathInput = screen.getByLabelText("Local video file or folder path");
    fireEvent.change(pathInput, { target: { value: "./demo.mp4" } });
    fireEvent.click(screen.getByText("Import Local Media"));

    await waitFor(() => {
      expect(screen.getByText(/Imported 1 video\(s\)/i)).toBeInTheDocument();
    });

    expect(fetchSpy).toHaveBeenCalled();
  });
});
