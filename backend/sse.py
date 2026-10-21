"""
sse.py
One place that knows how to format a Server-Sent Events frame.

Both the chat stream and the live-graph stream use it, so the two
streams speak the same dialect: `event: <name>` then `data: <json>`.
"""
from __future__ import annotations

import json


def sse_frame(event: str, data: object) -> str:
    """Format a single SSE frame as a plain string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
