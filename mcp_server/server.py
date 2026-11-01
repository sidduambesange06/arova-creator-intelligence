import os
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp.server.mcpserver import MCPServer
from mcp_server.tools import video_tools


def create_mcp_server(enable_exports: bool | None = None) -> MCPServer:
    """Create and configure FastMCP server instance.
    
    By default, only the 8 official read-only retrieval tools are exposed to AI agents.
    export_video_clip is state-mutating and requires explicit developer opt-in via
    AROVA_ENABLE_MCP_EXPORTS=1 environment variable or --enable-exports CLI argument.
    """
    if enable_exports is None:
        enable_exports = (
            os.getenv("AROVA_ENABLE_MCP_EXPORTS", "").lower() in ("1", "true", "yes")
            or "--enable-exports" in sys.argv
        )

    server = MCPServer(
        name="arova-creator-intelligence",
        instructions=(
            "Official Model Context Protocol (MCP) server for Arova Creator Intelligence. "
            "Provides read-only tools to list videos, probe metadata, execute hybrid search, "
            "find clips, summarize videos, extract chapters, and inspect library stats."
        ),
        version="0.1.0",
    )

    @server.tool(description="List indexed videos with optional collection and processing status filters")
    def list_videos(
        collection_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        return video_tools.list_videos(collection_id=collection_id, status=status)

    @server.tool(description="Retrieve complete metadata, technical dimensions, codec, and collections for a video")
    def get_video_metadata(video_id: str) -> dict[str, Any]:
        return video_tools.get_video_metadata(video_id=video_id)

    @server.tool(description="Perform hybrid two-stage semantic video search (Stage-1 Dense+BM25 RRF + Stage-2 Cross-Encoder)")
    def search_video_content(
        query: str,
        top_k: int = 5,
        use_reranker: bool = True,
    ) -> list[dict[str, Any]]:
        return video_tools.search_video_content(query=query, top_k=top_k, use_reranker=use_reranker)

    @server.tool(description="Search exact lexical spoken words across all video transcripts")
    def search_transcripts(
        query: str,
        video_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return video_tools.search_transcripts(query=query, video_id=video_id)

    @server.tool(description="Find candidate timestamped video clips matching a query within duration bounds")
    def find_video_clips(
        query: str,
        min_duration: float = 5.0,
        max_duration: float = 60.0,
    ) -> list[dict[str, Any]]:
        return video_tools.find_video_clips(query=query, min_duration=min_duration, max_duration=max_duration)

    @server.tool(description="Generate or retrieve a grounded factual summary for a video strictly from transcript segments")
    def summarize_video(video_id: str) -> dict[str, Any]:
        return video_tools.summarize_video(video_id=video_id)

    @server.tool(description="Retrieve timestamped chapter breakdown and section markers for a video")
    def get_video_chapters(video_id: str) -> list[dict[str, Any]]:
        return video_tools.get_video_chapters(video_id=video_id)

    @server.tool(description="Retrieve inventory counts and runtime metrics for the video library")
    def get_media_library_stats() -> dict[str, Any]:
        return video_tools.get_media_library_stats()

    if enable_exports:
        @server.tool(description="Export a lossless trimmed subclip from an indexed video given start and end timestamps (developer opt-in)")
        def export_video_clip(video_id: str, start_time: float, end_time: float) -> dict[str, Any]:
            return video_tools.export_video_clip(video_id=video_id, start_time=start_time, end_time=end_time)

    return server


mcp = create_mcp_server()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
