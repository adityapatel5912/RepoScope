"""
key_rotator.py
Round-robin rotation across multiple API keys per provider, defeating
per-key rate limits. Loads comma-separated key lists from env, falling
back to the legacy single-key variable names.

  GROQ_API_KEYS=gsk_1,gsk_2      (legacy: GROQ_API_KEY)
  NVIDIA_API_KEYS=nvapi_1,...    (legacy: NVIDIA_API_KEY)
  OPENROUTER_API_KEYS=sk-or-1,.  (legacy: OPENROUTER_API_KEY)
  GITHUB_TOKENS=ghp_1,...        (legacy: GITHUB_PAT / GITHUB_TOKEN)

Keys are never logged; only counts are exposed.
"""
import os
from threading import Lock

from dotenv import load_dotenv

load_dotenv()  # ensure keys are visible even when imported before runtime_config


class KeyRotator:
    """Thread-safe round-robin rotator over a provider's API keys."""

    def __init__(self, provider: str, env_var: str, *legacy_envs: str):
        self.provider = provider
        self.keys = self._load(env_var, legacy_envs)
        self.index = 0
        self.lock = Lock()

    @staticmethod
    def _load(env_var: str, legacy_envs: tuple) -> list:
        raw = os.getenv(env_var, "")
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        if not keys:
            for legacy in legacy_envs:
                single = os.getenv(legacy, "").strip()
                if single:
                    keys = [single]
                    break
        return keys

    def next_key(self) -> str:
        if not self.keys:
            return ""
        with self.lock:
            key = self.keys[self.index % len(self.keys)]
            self.index += 1
            return key

    def count(self) -> int:
        return len(self.keys)


OPENROUTER_ROTATOR = KeyRotator("openrouter", "OPENROUTER_API_KEYS", "OPENROUTER_API_KEY")
GROQ_ROTATOR = KeyRotator("groq", "GROQ_API_KEYS", "GROQ_API_KEY")
NVIDIA_ROTATOR = KeyRotator("nvidia", "NVIDIA_API_KEYS", "NVIDIA_API_KEY")
GITHUB_ROTATOR = KeyRotator("github", "GITHUB_TOKENS", "GITHUB_PAT", "GITHUB_TOKEN")


def is_rate_limit_error(exc: Exception) -> bool:
    """True when an exception looks like an HTTP 429 / rate-limit hit."""
    s = str(exc).lower()
    return "429" in s or "rate" in s or "quota" in s or "too many requests" in s


def _is_eol_error(exc: Exception) -> bool:
    """True when a model has reached end-of-life (HTTP 410 Gone)."""
    s = str(exc).lower()
    return "410" in s or "end of life" in s or "gone" in s or "no longer available" in s
