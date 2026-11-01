from __future__ import annotations

import json
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


class ArovaClientError(Exception):
    """Raised when an API request to Arova server fails."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"Arova API Error [{status_code}]: {detail}")
        self.status_code = status_code
        self.detail = detail


class ArovaClient:
    """Thin, zero-dependency Python REST client wrapper for Arova Creator Intelligence.
    
    Provides access to core health, video inventory, hybrid search, and grounded Q&A endpoints.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        data_bytes = None

        if payload is not None:
            headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                detail = err_json.get("detail", err_body)
            except Exception:
                detail = err_body
            raise ArovaClientError(status_code=exc.code, detail=str(detail)) from exc
        except urllib.error.URLError as exc:
            raise ArovaClientError(status_code=503, detail=f"Connection failed to {url}: {exc.reason}") from exc

    def health(self) -> dict[str, Any]:
        """Check API server health status."""
        return self._request("GET", "/api/v1/health")

    def list_videos(self, collection_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        """List indexed videos in the media library."""
        params = {}
        if collection_id:
            params["collection_id"] = collection_id
        if status:
            params["status"] = status
        query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
        return self._request("GET", f"/api/v1/videos{query_str}")

    def get_video(self, video_id: str) -> dict[str, Any]:
        """Retrieve full metadata for a specific video."""
        return self._request("GET", f"/api/v1/videos/{video_id}")

    def search(self, query: str, top_k: int = 5, use_reranker: bool = True) -> dict[str, Any]:
        """Execute two-stage hybrid semantic video search."""
        payload = {
            "query": query,
            "top_k": top_k,
            "use_reranker": use_reranker,
        }
        return self._request("POST", "/api/v1/search/semantic", payload=payload)

    def ask(self, question: str, video_id: str | None = None) -> dict[str, Any]:
        """Ask a factual question about indexed video content with timecode citations."""
        payload = {
            "query": question,
            "video_id": video_id,
        }
        return self._request("POST", "/api/v1/ai/ask", payload=payload)
