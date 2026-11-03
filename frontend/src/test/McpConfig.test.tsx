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

  it("loads media library stats, displays 8 default tools plus optional export, and provides valid client snippets", async () => {
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

    // Verify 8 default read-only tools header
    expect(screen.getByText(/Default Read-Only Tools \(8\)/i)).toBeInTheDocument();

    const readOnlyTools = [
      "list_videos",
      "get_video_metadata",
      "search_video_content",
      "search_transcripts",
      "find_video_clips",
      "summarize_video",
      "get_video_chapters",
      "get_media_library_stats",
    ];
    for (const tool of readOnlyTools) {
      expect(screen.getByTestId(`mcp-tool-${tool}`)).toBeInTheDocument();
    }

    // Verify optional write tool is explicitly separated and flagged as disabled by default
    expect(screen.getByText(/Optional Write Capabilities \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Disabled by Default \(Opt-In\)/i)).toBeInTheDocument();
    expect(screen.getByTestId("mcp-tool-export_video_clip")).toBeInTheDocument();

    // 1. Claude Desktop snippet validation
    const claudeCode = screen.getByTestId("mcp-config-code").textContent ?? "";
    const claudeParsed = JSON.parse(claudeCode);
    expect(claudeParsed).toHaveProperty("mcpServers");
    expect(claudeParsed.mcpServers).toHaveProperty("arova-creator-intelligence");
    expect(claudeParsed.mcpServers["arova-creator-intelligence"].args).toEqual(["-m", "mcp_server.server"]);

    // 2. Cursor IDE snippet validation
    fireEvent.click(screen.getByRole("button", { name: "Cursor IDE" }));
    const cursorCode = screen.getByTestId("mcp-config-code").textContent ?? "";
    const cursorParsed = JSON.parse(cursorCode);
    expect(cursorParsed).toHaveProperty("mcpServers");
    expect(cursorParsed.mcpServers).toHaveProperty("arova-creator-intelligence");

    // 3. VS Code snippet validation (.vscode/mcp.json schema: top-level 'servers')
    fireEvent.click(screen.getByRole("button", { name: "VS Code" }));
    const vscodeCode = screen.getByTestId("mcp-config-code").textContent ?? "";
    const vscodeParsed = JSON.parse(vscodeCode);
    expect(vscodeParsed).toHaveProperty("servers");
    expect(vscodeParsed.servers).toHaveProperty("arova-creator-intelligence");
    expect(vscodeParsed.servers["arova-creator-intelligence"].command).toBe("python");
  });
});
