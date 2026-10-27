"""
test_chat_citations.py
Integration tests for Phase 5: Verified chat citations API & SSE stream.

Covers:
- GET /api/citation/verify debug endpoint
- POST /api/chat/stream citations SSE event emission
- Old-client compatibility (extra event ignored without breaking)
"""
import json
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_citation_verify_endpoint_hit():
    """Verify an existing file/symbol in the RepoScope repository."""
    resp = client.get("/api/citation/verify", params={"path": "backend/main.py", "line": 20})
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "backend/main.py"
    assert data["verified"] is True
    assert "start_line" in data
    assert "preview" in data


def test_citation_verify_endpoint_miss():
    """Verify that a nonexistent file returns 200 with verified: false."""
    resp = client.get("/api/citation/verify", params={"path": "nonexistent_file.xyz", "line": 42})
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "nonexistent_file.xyz"
    assert data["verified"] is False
    assert data["reason"] == "file not found"
    assert data["preview"] == ""


def test_chat_stream_citations_event(fake_ai_provider):
    """Verify that chat_stream yields a final 'citations' event before 'done'."""
    mock_answer = (
        "Here is the API definition:\n"
        "Check `backend/main.py:20` for imports and [backend/fake.py:99] for fake."
    )
    with patch("main.ask_llm", return_value=mock_answer):
        resp = client.post(
            "/api/chat/stream",
            json={"mode": "understanding", "message": "Where is main?", "repo": None},
        )
        assert resp.status_code == 200
        text = resp.text

        events = []
        for chunk in text.split("\n\n"):
            chunk = chunk.strip()
            if not chunk:
                continue
            lines = chunk.split("\n")
            ev_name = None
            data_val = None
            for l in lines:
                if l.startswith("event: "):
                    ev_name = l[len("event: "):]
                elif l.startswith("data: "):
                    data_val = l[len("data: "):]
            if ev_name:
                events.append((ev_name, json.loads(data_val) if data_val else None))

        event_names = [e[0] for e in events]
        assert "context" in event_names
        assert "token" in event_names
        assert "citations" in event_names
        assert "done" in event_names

        # Citations event must occur before done
        cit_idx = event_names.index("citations")
        done_idx = event_names.index("done")
        assert cit_idx < done_idx

        # Citations payload content check
        cit_event = next(e[1] for e in events if e[0] == "citations")
        assert cit_event["type"] == "citations"
        assert isinstance(cit_event["citations"], list)
        assert len(cit_event["citations"]) >= 1


def test_old_client_compatibility(fake_ai_provider):
    """
    An old SSE client that only knows (context, token, tracking, done, error)
    must continue to parse the stream without any exceptions or errors.
    """
    mock_answer = "Review `backend/main.py:25`."
    with patch("main.ask_llm", return_value=mock_answer):
        resp = client.post(
            "/api/chat/stream",
            json={"mode": "understanding", "message": "hello", "repo": None},
        )
        assert resp.status_code == 200

        received_tokens = []
        done_called = False

        for chunk in resp.text.split("\n\n"):
            chunk = chunk.strip()
            if not chunk:
                continue
            lines = chunk.split("\n")
            event = ""
            data_str = ""
            for line in lines:
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: "):
                    data_str = line[6:]

            # Old client dispatch logic
            if event == "context":
                pass
            elif event == "token":
                received_tokens.append(json.loads(data_str).get("t", ""))
            elif event == "tracking":
                pass
            elif event == "done":
                done_called = True
            elif event == "error":
                pytest.fail("Old client received unexpected error event")
            # Other events (e.g. 'citations') are safely ignored

        assert done_called is True
        assert len(received_tokens) > 0
