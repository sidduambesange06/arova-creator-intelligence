import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { McpConfigView } from "../features/settings/McpConfigView";

const SAMPLE_STATS = {
  total_videos: 4,
  total_duration_sec: 180.5,
  total_collections: 2,
  total_transcripts_indexed: 4,
  total_scene_cuts: 16,
  engine: "Arova Creator Intelligence v0.1.0 (Local video RAG)",
};

describe("McpConfigView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads media library stats, displays all MCP tools, and toggles client config snippets", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/videos/stats/summary")) {
        return new Response(JSON.stringify(SAMPLE_STATS), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("{}", { status: 200 });
    });

    render(<McpConfigView />);

    // Check stats rendering
    await waitFor(() => {
      expect(screen.getByText("Total Videos")).toBeInTheDocument();
      expect(screen.getAllByText("4")).toHaveLength(2);
      expect(screen.getByText("180.5s")).toBeInTheDocument();
      expect(screen.getByText("16")).toBeInTheDocument();
    });

    // Check all 8 tools are listed
    const tools = [
      "list_videos",
      "get_video_metadata",
      "search_video_content",
      "search_transcripts",
      "find_video_clips",
      "summarize_video",
      "get_video_chapters",
      "get_media_library_stats",
      "export_video_clip",
    ];
    for (const tool of tools) {
      expect(screen.getByTestId(`mcp-tool-${tool}`)).toBeInTheDocument();
    }

    // Default tab is Claude Desktop
    expect(screen.getByTestId("mcp-config-code")).toHaveTextContent("mcpServers");

    // Click Cursor IDE tab
    fireEvent.click(screen.getByRole("button", { name: "Cursor IDE" }));
    expect(screen.getByTestId("mcp-config-code")).toHaveTextContent('"type": "stdio"');

    // Click VS Code tab
    fireEvent.click(screen.getByRole("button", { name: "VS Code" }));
    expect(screen.getByTestId("mcp-config-code")).toHaveTextContent("Local video RAG");
  });
});
