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

mcp = MCPServer(
    name="arova-creator-intelligence",
    instructions=(
        "Official Model Context Protocol (MCP) server for Arova Creator Intelligence. "
        "Provides 8 read-only tools to list videos, probe video metadata, execute two-stage hybrid search, "
        "find candidate clips, extract grounded summaries/chapters, and inspect library stats."
    ),
    version="0.1.0",
)


@mcp.tool(description="List indexed videos with optional collection and processing status filters")
def list_videos(
    collection_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    return video_tools.list_videos(collection_id=collection_id, status=status)


@mcp.tool(description="Retrieve complete metadata, technical dimensions, codec, and collections for a video")
def get_video_metadata(video_id: str) -> dict[str, Any]:
    return video_tools.get_video_metadata(video_id=video_id)


@mcp.tool(description="Perform hybrid two-stage semantic video search (Stage-1 Dense+BM25 RRF + Stage-2 Cross-Encoder)")
def search_video_content(
    query: str,
    top_k: int = 5,
    use_reranker: bool = True,
) -> list[dict[str, Any]]:
    return video_tools.search_video_content(query=query, top_k=top_k, use_reranker=use_reranker)


@mcp.tool(description="Search exact lexical spoken words across all video transcripts")
def search_transcripts(
    query: str,
    video_id: str | None = None,
) -> list[dict[str, Any]]:
    return video_tools.search_transcripts(query=query, video_id=video_id)


@mcp.tool(description="Find candidate timestamped video clips matching a query within duration bounds")
def find_video_clips(
    query: str,
    min_duration: float = 5.0,
    max_duration: float = 60.0,
) -> list[dict[str, Any]]:
    return video_tools.find_video_clips(query=query, min_duration=min_duration, max_duration=max_duration)


@mcp.tool(description="Generate or retrieve a grounded factual summary for a video strictly from transcript segments")
def summarize_video(video_id: str) -> dict[str, Any]:
    return video_tools.summarize_video(video_id=video_id)


@mcp.tool(description="Retrieve timestamped chapter breakdown and section markers for a video")
def get_video_chapters(video_id: str) -> list[dict[str, Any]]:
    return video_tools.get_video_chapters(video_id=video_id)


@mcp.tool(description="Retrieve inventory counts and runtime metrics for the video library")
def get_media_library_stats() -> dict[str, Any]:
    return video_tools.get_media_library_stats()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
