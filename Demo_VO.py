"""
Demo_VO.py
Generates Demo.mp3 — the RepoScope demo voiceover — using the
Fish Audio TTS model via OpenRouter.

Reads OPENROUTER_API_KEYS (or legacy OPENROUTER_API_KEY) from .env.

Usage:
    python Demo_VO.py
Output:
    Demo.mp3  (in the same directory)
"""

import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

# ── Model / voice config ──────────────────────────────────────────────────
MODEL_ID = "fish-audio/s2.1-pro-free:free"
VOICE_ID = "d8a1340984ee4b63ad1ffae27a6a4339"
OUTPUT_FILE = "Demo.mp3"

# ── Voiceover script ──────────────────────────────────────────────────────
# Pronunciations fixed:
#   RepoScope  → "Ree-poh-Scope"
#   GitHub     → "Git-Hub" (natural pause)
#   FastAPI    → "Fast A-P-I"
#   SSE        → "S-S-E"
#   PAT        → "P-A-T"
#   PyPI       → "Pie-P-I"
#   dagre      → "da-greh"
#   uvicorn    → "you-vi-corn"
#   BYOK       → "Bring Your Own Key"
#   PNG        → "P-N-G"
#   SVG        → "S-V-G"
SCRIPT = """\
Every developer has inherited a codebase and spent the first week figuring out what's going on. \
Today that means five different tools that don't talk to each other.

Repo Scope loads any Git-Hub repo in seconds and renders it as a connectivity pyramid — \
the most-imported files at the top, documentation and test data at the bottom.

The file decision underscore model dot py sits at the top because the whole app depends on it. \
Its key functions appear as child nodes directly below it, \
with every import drawn as a directed edge.

Ask anything in plain English. \
Every answer cites the file, the function, and the line that supports it — no hallucinated API.

Before you change anything, Repo Scope shows the blast radius — \
every caller that depends on the function you're about to touch, \
with a risk score and suggested tests.

For new team members, code tours walk through any module step by step — \
the graph follows along.

Track commits, pull requests, and issues on demand. \
Paste your Git-Hub PAT to unlock private repos — \
it stays in memory, never on disk.

Export the graph as P-N-G or S-V-G. \
Full source, live demo, and pitch deck are in the README. \
Built entirely with IBM Bob And Z Code. \
Repo Scope — see your repo, understand it, track it.\
"""


def get_api_key() -> str:
    raw = os.getenv("OPENROUTER_API_KEYS", "") or os.getenv("OPENROUTER_API_KEY", "")
    key = raw.split(",")[0].strip()
    if not key:
        sys.exit("ERROR: No OpenRouter API key found. Set OPENROUTER_API_KEYS in .env")
    return key


def generate_tts(script: str, api_key: str) -> bytes:
    print(f"Sending script to {MODEL_ID} …")
    url = "https://openrouter.ai/api/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_ID,
        "input": script,
        "voice": VOICE_ID,
        "response_format": "mp3",
    }
    with httpx.Client(timeout=120) as client:
        resp = client.post(url, json=payload, headers=headers)

    if resp.status_code != 200:
        sys.exit(
            f"ERROR: OpenRouter returned {resp.status_code}\n{resp.text}"
        )

    content_type = resp.headers.get("content-type", "")
    if "audio" not in content_type and "octet" not in content_type:
        sys.exit(
            f"ERROR: Expected audio response, got '{content_type}'\n{resp.text[:500]}"
        )

    return resp.content


def main():
    api_key = get_api_key()
    audio_bytes = generate_tts(SCRIPT, api_key)
    out_path = os.path.join(os.path.dirname(__file__), OUTPUT_FILE)
    with open(out_path, "wb") as f:
        f.write(audio_bytes)
    size_kb = len(audio_bytes) // 1024
    print(f"OK  Saved {OUTPUT_FILE}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
