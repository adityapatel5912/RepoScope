"""
runtime_config.py
LLM provider chain with multi-key rotation:
  1. Groq        (GROQ_API_KEYS / GROQ_API_KEY)             — primary
  2. OpenRouter  (OPENROUTER_API_KEYS / OPENROUTER_API_KEY) — secondary
  3. NVIDIA NIM  (NVIDIA_API_KEYS / NVIDIA_API_KEY)         — tertiary

On a 429 / rate-limit error the next key for the same provider is tried;
when a provider's keys are exhausted the chain falls through to the next
provider. Base URLs and models come from env:

  Base_URL_GROQ,       Models_GROQ
  Base_URL_OPENROUTER, Models_OPENROUTER
  Base_URL_NVIDIA,     Models_NVIDIA
"""
import os
import ssl
from openai import OpenAI
from dotenv import load_dotenv

from key_rotator import (
    OPENROUTER_ROTATOR, GROQ_ROTATOR, NVIDIA_ROTATOR, is_rate_limit_error, _is_eol_error,
)

load_dotenv()

# Unset SSLKEYLOGFILE if it points to a restricted path — prevents PermissionError
# when the OpenAI/httpx client tries to create an SSL context on Windows.
_keylog = os.environ.get("SSLKEYLOGFILE", "")
if _keylog:
    try:
        open(_keylog, "a").close()
    except (PermissionError, OSError):
        del os.environ["SSLKEYLOGFILE"]


def _first_model(models_env: str, fallback: str) -> str:
    """Return the first comma-separated model name from an env var."""
    raw = os.getenv(models_env, fallback)
    return raw.split(",")[0].strip()


def _make_client(base_url: str, api_key: str) -> OpenAI:
    """Create an OpenAI-compatible client, ignoring SSL keylog issues."""
    return OpenAI(base_url=base_url, api_key=api_key or "placeholder")


# ── Provider chain (clients are built per attempt so rotated keys apply) ────
def _get_providers() -> list[tuple]:
    return [
        (
            GROQ_ROTATOR,
            lambda key: _make_client(
                os.getenv("Base_URL_GROQ", "https://api.groq.com/openai/v1"), key),
            _first_model("Models_GROQ", "qwen/qwen3.8-27b"),
            "Groq",
        ),
        (
            OPENROUTER_ROTATOR,
            lambda key: _make_client(
                os.getenv("Base_URL_OPENROUTER", "https://openrouter.ai/api/v1"), key),
            _first_model("Models_OPENROUTER", "google/gemma-4-31b-it:free"),
            "OpenRouter",
        ),
        (
            NVIDIA_ROTATOR,
            lambda key: _make_client(
                os.getenv("Base_URL_NVIDIA", "https://integrate.api.nvidia.com/v1"), key),
            _first_model("Models_NVIDIA", "meta/muse-glimmer-30b"),
            "NVIDIA NIM",
        ),
    ]


def ask_llm(system_prompt: str, user_query: str, graph_context: str = "") -> str:
    """
    Try OpenRouter → Groq → NVIDIA NIM in order, rotating through every
    key of a provider on rate-limit errors before falling to the next.
    Returns the first successful response.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Context:\n{graph_context}\n\nQuestion: {user_query}",
        },
    ]

    last_exc: Exception | None = None
    for rotator, make_client, model, name in _get_providers():
        for _ in range(max(rotator.count(), 1)):
            key = rotator.next_key()
            if not key:
                break  # provider has no keys configured
            try:
                client = make_client(key)
                r = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1024,
                )
                content = r.choices[0].message.content
                if content and content.strip():
                    return content
                # HTTP 200 but empty content (filter/refusal) → treat as a
                # provider failure and fall through to the next key/provider.
                last_exc = RuntimeError(f"empty response content from provider")
                continue
            except Exception as exc:
                last_exc = exc
                if is_rate_limit_error(exc) or _is_eol_error(exc):
                    continue  # next key / rotate past dead model
                break         # non-rate error → next provider
        # provider exhausted (or unconfigured) → fall through

    raise RuntimeError(f"All LLM providers failed. Last error: {last_exc}")
