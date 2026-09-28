"""
json_utils.py
LLM-JSON recovery helpers shared by the scaffold and onboarding endpoints.
Free/reasoning models routinely produce (a) stray trailing commas and
(b) output truncated mid-string by the token budget — these helpers turn
both into usable JSON instead of a 502.
"""
import json
import re


def loads_tolerant(s: str) -> dict:
    """json.loads with trailing-comma salvage."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([}\]])", r"\1", s)
        return json.loads(fixed)


def extract_json_object(text: str) -> dict:
    """First JSON object in an LLM reply (fence-tolerant, comma-salvaging)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in model output")
    return loads_tolerant(cleaned[start : end + 1])


def _close_json(base: str) -> str | None:
    """Append the closers needed to terminate a truncated JSON document.

    Walks the text tracking string/escape state and the bracket stack, then
    closes any open string and pops the stack. Returns None when the result
    cannot even be attempted (no opening brace)."""
    start = base.find("{")
    if start == -1:
        return None
    in_str = False
    esc = False
    stack: list[str] = []
    for ch in base[start:]:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    stack.pop()
    closers = ['"'] if in_str else []
    closers += ["}" if c == "{" else "]" for c in reversed(stack)]
    return base + "".join(closers)


def salvage_truncated_json(text: str, max_tries: int = 8) -> dict | None:
    """Recover a usable object from output truncated by a token limit.

    Strategy: close the document as-is; if still invalid (truncation landed
    mid-key / mid-token), trim back to the previous complete member boundary
    and retry. Returns None when nothing parseable remains."""
    start = text.find("{")
    if start == -1:
        return None
    base = text[start:]
    for _ in range(max_tries):
        candidate = _close_json(base)
        if candidate:
            try:
                return loads_tolerant(candidate)
            except json.JSONDecodeError:
                pass
        cut = max(base.rfind("}"), base.rfind(","))
        if cut <= 0:
            return None
        base = base[:cut]
    return None
