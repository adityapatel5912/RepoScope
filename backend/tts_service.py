"""
tts_service.py
Voice Code Tours — text-to-speech through OpenRouter's audio-capable models.

Model chain (env-overridable via Models_TTS, comma-separated):
  1. fish-audio/s2.1-pro-free:free
  2. deepgram/flux-tts:free

Two request strategies per model, in order:
  a. POST {base}/audio/speech        (OpenAI-compatible; returns raw audio bytes)
  b. POST {base}/chat/completions    with modalities ["text", "audio"];
     audio comes back base64 in choices[0].message.audio.data

Keys come from the request's BYOK headers when present, else the standard
OPENROUTER_ROTATOR round-robin (429 → next key, preserving rotation logic).
"""
import base64
import logging
import os

import httpx

from key_rotator import OPENROUTER_ROTATOR

log = logging.getLogger("reposcope.tts")

DEFAULT_TTS_MODELS = "fish-audio/s2.1-pro-free:free,deepgram/flux-tts:free"
MAX_TEXT_CHARS = 1200


def _tts_models() -> list[str]:
    raw = os.getenv("Models_TTS", DEFAULT_TTS_MODELS)
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or DEFAULT_TTS_MODELS.split(",")


def _openrouter_key(provider: dict | None) -> str | None:
    """BYOK OpenRouter key when given, else a server rotator key."""
    if provider and provider.get("api_key") and provider.get("source") == "byok":
        return provider["api_key"]
    return OPENROUTER_ROTATOR.next_key() or None


def _base_url(provider: dict | None) -> str:
    if provider and provider.get("base_url") and provider.get("source") == "byok":
        return provider["base_url"].rstrip("/")
    return os.getenv("Base_URL_OPENROUTER", "https://openrouter.ai/api/v1").rstrip("/")


async def _speech_endpoint(base: str, key: str, model: str, text: str) -> tuple[bytes, str]:
    """Strategy A: dedicated /audio/speech endpoint → raw audio bytes."""
    async with httpx.AsyncClient(timeout=60) as c:
        res = await c.post(
            f"{base}/audio/speech",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "input": text,
                "voice": "narrator",
                "response_format": "mp3",
            },
        )
        if res.status_code in (404, 405):
            raise RuntimeError("no /audio/speech endpoint on this base URL")
        if res.status_code == 429:
            raise RateLimit("429")
        res.raise_for_status()
        ctype = (res.headers.get("content-type") or "audio/mpeg").split(";")[0]
        fmt = {"audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav",
               "audio/ogg": "ogg"}.get(ctype, "mp3")
        return res.content, fmt


async def _chat_modalities(base: str, key: str, model: str, text: str) -> tuple[bytes, str]:
    """Strategy B: chat/completions with audio modality → base64 in message.audio."""
    async with httpx.AsyncClient(timeout=90) as c:
        res = await c.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "modalities": ["text", "audio"],
                "audio": {"voice": "narrator", "format": "mp3"},
                "messages": [
                    {"role": "system", "content":
                        "You are a text-to-speech engine. Repeat the user's text "
                        "verbatim as natural, clear narration."},
                    {"role": "user", "content": text},
                ],
            },
        )
        if res.status_code == 429:
            raise RateLimit("429")
        res.raise_for_status()
        data = res.json()
        audio = ((data.get("choices") or [{}])[0].get("message") or {}).get("audio") or {}
        b64 = audio.get("data")
        if not b64:
            raise RuntimeError("model returned no audio data")
        return base64.b64decode(b64), (audio.get("format") or "mp3")


class RateLimit(RuntimeError):
    """Raised on HTTP 429 so the caller knows to rotate to the next key."""


async def synthesize(text: str, provider: dict | None = None) -> dict:
    """Turn narration text into base64 audio. Returns
    {audio_base64, format, model, provider}."""
    text = (text or "").strip()[:MAX_TEXT_CHARS]
    if not text:
        raise ValueError("empty text")

    byok = bool(provider and provider.get("api_key") and provider.get("source") == "byok")
    attempts = 1 if byok else max(OPENROUTER_ROTATOR.count(), 1)
    base = _base_url(provider)
    strategies = (_speech_endpoint, _chat_modalities)
    models = _tts_models()
    last_exc: Exception | None = None

    # Rotate keys on rate limits (same policy as the LLM chain)
    for _ in range(attempts):
        key = _openrouter_key(provider)
        if not key:
            raise RuntimeError("No OpenRouter key available for TTS "
                               "(set OPENROUTER_API_KEYS or use BYOK)")
        for model in models:
            for strategy in strategies:
                try:
                    audio, fmt = await strategy(base, key, model, text)
                    return {
                        "audio_base64": base64.b64encode(audio).decode("ascii"),
                        "format": fmt,
                        "model": model,
                        "provider": "openrouter",
                    }
                except RateLimit as exc:
                    last_exc = exc
                    break          # rotate key, restart model chain
                except Exception as exc:  # noqa: BLE001 — try next strategy/model
                    last_exc = exc
                    log.info("TTS %s via %s failed: %s", model, strategy.__name__, exc)
                    continue
            else:
                continue
            break  # rate-limited → rotate to the next key

    raise RuntimeError(f"All TTS routes failed. Last error: {last_exc}")
