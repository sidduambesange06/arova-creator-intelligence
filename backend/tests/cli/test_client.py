import io
import json
from pathlib import Path
import sys
from typing import Any
from unittest.mock import MagicMock, patch
import urllib.error

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest

from arova.client import ArovaClient, ArovaClientError


def _mock_http_response(payload: Any, status: int = 200) -> MagicMock:
    body_bytes = json.dumps(payload).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body_bytes
    mock_resp.status = status
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


def test_client_health() -> None:
    client = ArovaClient(base_url="http://127.0.0.1:8000")
    with patch("urllib.request.urlopen", return_value=_mock_http_response({"status": "ok"})) as mock_open:
        res = client.health()
        assert res == {"status": "ok"}
        req = mock_open.call_args[0][0]
        assert req.full_url == "http://127.0.0.1:8000/api/v1/health"
        assert req.get_method() == "GET"


def test_client_list_and_get_videos() -> None:
    client = ArovaClient(base_url="http://127.0.0.1:8000")

    # list_videos
    with patch("urllib.request.urlopen", return_value=_mock_http_response([{"id": "v1"}])) as mock_open:
        res = client.list_videos(collection_id="c1", status="completed")
        assert res == [{"id": "v1"}]
        req = mock_open.call_args[0][0]
        assert "collection_id=c1" in req.full_url
        assert "status=completed" in req.full_url
        assert req.get_method() == "GET"

    # get_video
    with patch("urllib.request.urlopen", return_value=_mock_http_response({"id": "v1", "filename": "demo.mp4"})) as mock_open:
        res = client.get_video("v1")
        assert res["filename"] == "demo.mp4"
        req = mock_open.call_args[0][0]
        assert req.full_url == "http://127.0.0.1:8000/api/v1/videos/v1"


def test_client_search_and_ask() -> None:
    client = ArovaClient(base_url="http://127.0.0.1:8000")

    # search
    with patch("urllib.request.urlopen", return_value=_mock_http_response({"results": []})) as mock_open:
        res = client.search(query="video test", top_k=3, use_reranker=True)
        assert res == {"results": []}
        req = mock_open.call_args[0][0]
        assert req.full_url == "http://127.0.0.1:8000/api/v1/search/semantic"
        assert req.get_method() == "POST"
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["query"] == "video test"
        assert payload["top_k"] == 3

    # ask
    with patch("urllib.request.urlopen", return_value=_mock_http_response({"answer": "Evidence found", "citations": []})) as mock_open:
        res = client.ask(question="what happened?", video_id="v1")
        assert res["answer"] == "Evidence found"
        req = mock_open.call_args[0][0]
        assert req.full_url == "http://127.0.0.1:8000/api/v1/ai/ask"
        assert req.get_method() == "POST"
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["query"] == "what happened?"
        assert payload["video_id"] == "v1"


def test_client_error_handling() -> None:
    client = ArovaClient(base_url="http://127.0.0.1:8000")

    # HTTPError 404
    mock_err = urllib.error.HTTPError(
        url="http://127.0.0.1:8000/api/v1/videos/missing",
        code=404,
        msg="Not Found",
        hdrs=MagicMock(),
        fp=io.BytesIO(b'{"detail": "Video missing not found"}'),
    )
    with patch("urllib.request.urlopen", side_effect=mock_err):
        with pytest.raises(ArovaClientError) as exc_info:
            client.get_video("missing")
        assert exc_info.value.status_code == 404
        assert "Video missing not found" in exc_info.value.detail

    # URLError 503
    mock_conn_err = urllib.error.URLError(reason="Connection refused")
    with patch("urllib.request.urlopen", side_effect=mock_conn_err):
        with pytest.raises(ArovaClientError) as exc_info:
            client.health()
        assert exc_info.value.status_code == 503
        assert "Connection failed" in exc_info.value.detail
