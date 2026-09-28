"""
test_feature_3_voice.py
Voice Code Tours — /api/tts model chain (server TTS via OpenRouter) with
key rotation, plus a regression check that /api/tour/generate still works.
"""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import main
import tts_service
import tour_generator


@pytest.fixture()
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def clean_rotator(monkeypatch):
    """Isolate the OpenRouter rotator from the developer's real .env keys."""
    rotator = tts_service.OPENROUTER_ROTATOR
    monkeypatch.setattr(rotator, "keys", ["k1", "k2"])
    monkeypatch.setattr(rotator, "index", 0)


# ── /api/tts chain ───────────────────────────────────────────────────────────

def test_tts_speech_endpoint_success(monkeypatch):
    """Strategy A (/audio/speech) answers → base64 mp3, no fallback needed."""
    async def fake_speech(base, key, model, text):
        assert key == "k1"
        return b"FAKEAUDIO", "mp3"

    async def fail_chat(*a, **k):
        raise AssertionError("must not run")

    monkeypatch.setattr(tts_service, "_speech_endpoint", fake_speech)
    monkeypatch.setattr(tts_service, "_chat_modalities", fail_chat)
    out = asyncio.run(tts_service.synthesize("hello world"))
    assert out["format"] == "mp3"
    assert out["model"]
    assert out["audio_base64"]


def test_tts_rotates_key_on_rate_limit(monkeypatch):
    """429 on key 1 → retry with key 2 (rotation preserved)."""
    calls: list[str] = []

    async def fake_speech(base, key, model, text):
        calls.append(key)
        if len(calls) < 2:
            raise tts_service.RateLimit("429")
        return b"AUDIO", "wav"

    async def fail_chat(*a, **k):
        raise AssertionError("chat fallback must not run")

    monkeypatch.setattr(tts_service, "_speech_endpoint", fake_speech)
    monkeypatch.setattr(tts_service, "_chat_modalities", fail_chat)
    out = asyncio.run(tts_service.synthesize("narrate this"))
    assert calls[0] == "k1" and calls[-1] == "k2"
    assert out["format"] == "wav"


def test_tts_falls_back_to_chat_modalities(monkeypatch):
    """/audio/speech 404s → chat/completions modalities returns base64."""
    import base64

    async def fail_speech(base, key, model, text):
        raise RuntimeError("404 no endpoint")

    async def fake_chat(base, key, model, text):
        return b"CHAT_AUDIO", "mp3"

    monkeypatch.setattr(tts_service, "_speech_endpoint", fail_speech)
    monkeypatch.setattr(tts_service, "_chat_modalities", fake_chat)
    out = asyncio.run(tts_service.synthesize("fallback test"))
    assert base64.b64decode(out["audio_base64"]) == b"CHAT_AUDIO"


def test_tts_all_routes_fail(monkeypatch):
    async def fail(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(tts_service, "_speech_endpoint", fail)
    monkeypatch.setattr(tts_service, "_chat_modalities", fail)
    with pytest.raises(RuntimeError, match="All TTS routes failed"):
        asyncio.run(tts_service.synthesize("doomed"))


# ── Tour regression (voice rides on tours) ──────────────────────────────────

def test_tour_generate_still_works(client, tmp_path, monkeypatch):
    (tmp_path / "auth_router.py").write_text("def check():\n    return 1\n")
    (tmp_path / "auth.py").write_text("import auth_router\n\ndef gate():\n    return auth_router.check()\n")
    state = {"repo": "octo/tiny", "local_path": str(tmp_path), "readme": "# x"}
    monkeypatch.setattr(main, "load_state", lambda: state)

    def fake_ask(system, prompt, graph_context="", provider=None):
        return "This file handles the auth gate."

    monkeypatch.setattr(tour_generator, "ask_llm", fake_ask)
    res = client.post("/api/tour/generate", json={"topic": "auth"})
    assert res.status_code == 200, res.text
    tour = res.json()
    assert tour["total_steps"] >= 1
    assert tour["steps"][0]["explanation"]
