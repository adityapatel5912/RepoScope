"""
parse_cache.py
Content-addressed cache of per-file parse results.

Milestone 6.2 — Caching & Incremental Indexing (Sprint 3).

The expensive part of building RepoScope's graph is parsing source code.
Assembly — minting node ids, resolving imports, resolving call sites — is
cheap by comparison. So the incremental strategy is:

    parse   → expensive, depends ONLY on the bytes of one file
    assemble → cheap, depends on the whole repository

If the two are separated, then re-indexing a repository after one file
changed only needs to re-parse that file. Everything else is reused.

**The cache is keyed by the file's SHA-256, not by its path.** That is the
whole point: a content-addressed cache cannot go stale. If a file's bytes
change, its hash changes, and the old entry is simply never looked up
again. A path-keyed cache would need mtime heuristics and would eventually
serve a stale parse result — the kind of bug that shows up as "the graph
disagrees with the code" weeks later.

Two layers:

    ParseCache      the persistent, on-disk store (a single JSON file)
    its LRU eviction the in-memory working set, bounded so a 50,000-file
                    repository does not exhaust the process

Usage:

    cache = ParseCache(root / ".reposcope" / "parse-cache.json")
    cache.load()
    facts = cache.get_for(path, rel)      # parses on a miss
    cache.save()
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("reposcope.parse_cache")

#: Where the cache lives inside a repository.
CACHE_DIRNAME = ".reposcope"
CACHE_FILENAME = "parse-cache.json"

#: Bumped when the on-disk shape changes. An older cache is discarded
#: rather than misread.
CACHE_VERSION = 1

#: Default number of entries kept in memory. Each entry is the parse result
#: of one file — symbols, imports and call sites. At roughly 2 KB per file
#: that is about 40 MB, which is a reasonable ceiling for a laptop.
DEFAULT_MAX_ENTRIES = 20_000

#: Read files in chunks so a 200 MB binary does not have to fit in memory.
_CHUNK = 64 * 1024


def hash_bytes(data: bytes) -> str:
    """The SHA-256 of a byte string."""
    return hashlib.sha256(data).hexdigest()


def hash_file(path: str | Path) -> tuple[str, int]:
    """
    Return (sha256, size) for a file, reading it in chunks.

    The size comes from the same read, so it can never disagree with the
    hash — a stat() call would be one more thing to go wrong.
    """
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


@dataclass
class FileFacts:
    """
    Everything one file contributes to the graph.

    This is the unit of caching. It holds raw, UNRESOLVED imports — the
    module specifier exactly as it was written — because resolution needs
    the whole repository and therefore cannot be cached per file.
    """

    rel: str
    suffix: str
    size: int
    sha256: str
    symbols: list[dict] = field(default_factory=list)
    imports: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "rel": self.rel,
            "suffix": self.suffix,
            "size": self.size,
            "sha256": self.sha256,
            "symbols": self.symbols,
            "imports": self.imports,
            "calls": self.calls,
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "FileFacts":
        return cls(
            rel=str(raw.get("rel", "")),
            suffix=str(raw.get("suffix", "")),
            size=int(raw.get("size", 0)),
            sha256=str(raw.get("sha256", "")),
            symbols=list(raw.get("symbols") or []),
            imports=list(raw.get("imports") or []),
            calls=list(raw.get("calls") or []),
            warnings=list(raw.get("warnings") or []),
        )


class ParseCache:
    """
    A bounded, content-addressed cache of parse results.

    The in-memory table is an LRU: the least recently *used* entry is
    evicted when the table is full. A plain FIFO would evict a hot file
    that is parsed on every scan, which is exactly the entry you want to
    keep.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        self.path = Path(path) if path else None
        self.max_entries = max(1, int(max_entries))
        self._entries: "OrderedDict[str, FileFacts]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    # ── Lookup ──────────────────────────────────────────────────────────────

    def get(self, sha256: str) -> FileFacts | None:
        """Return the cached facts for a content hash, or None."""
        if not sha256:
            return None
        facts = self._entries.get(sha256)
        if facts is None:
            self.misses += 1
            return None
        self._entries.move_to_end(sha256)
        self.hits += 1
        return facts

    def put(self, facts: FileFacts) -> None:
        """Store parse results, evicting the least recently used entry."""
        if not facts.sha256:
            return
        self._entries[facts.sha256] = facts
        self._entries.move_to_end(facts.sha256)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def get_for(
        self,
        path: str | Path,
        rel: str,
        parser: Callable[[bytes, str], FileFacts],
    ) -> FileFacts:
        """
        Return the facts for a file, parsing it only on a cache miss.

        `parser` receives the file's bytes and its repo-relative path, and
        returns a `FileFacts` with the hash already filled in.
        """
        file_path = Path(path)
        try:
            digest, size = hash_file(file_path)
        except OSError as exc:
            log.warning("Could not hash %s: %s", rel, exc)
            return FileFacts(
                rel=rel,
                suffix=file_path.suffix,
                size=0,
                sha256="",
                warnings=[f"unreadable: {exc}"],
            )

        cached = self.get(digest)
        if cached is not None:
            # The facts are keyed by content, but the RELATIVE PATH is not
            # part of the content — the same bytes at a different path are a
            # different file in the graph. Rebind the path.
            cached.rel = rel
            return cached

        data = file_path.read_bytes()
        facts = parser(data, rel)
        facts.sha256 = digest
        facts.size = size
        self.put(facts)
        return facts

    # ── Persistence ─────────────────────────────────────────────────────────

    def load(self) -> int:
        """
        Read the on-disk cache. Returns the number of entries loaded.

        A missing, unreadable or malformed cache is not an error — it just
        means every file gets parsed once. A cache must never be able to
        break the index.
        """
        if not self.path or not self.path.is_file():
            return 0
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Ignoring unreadable parse cache %s: %s", self.path, exc)
            return 0
        if not isinstance(raw, dict) or raw.get("version") != CACHE_VERSION:
            log.info("Parse cache version mismatch — starting fresh")
            return 0

        entries = raw.get("entries")
        if not isinstance(entries, dict):
            return 0

        loaded = 0
        for digest, value in entries.items():
            if not isinstance(value, dict):
                continue
            try:
                facts = FileFacts.from_dict(value)
            except (TypeError, ValueError):
                continue
            if facts.sha256 != digest:
                # The key must be the content hash. A mismatch means the
                # file was tampered with or written by a different scheme.
                continue
            self._entries[digest] = facts
            loaded += 1
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
        log.info("Loaded %d parse-cache entries from %s", loaded, self.path)
        return loaded

    def save(self) -> None:
        """Write the cache to disk, atomically."""
        if not self.path:
            return
        payload = {
            "version": CACHE_VERSION,
            "entries": {
                digest: facts.to_dict() for digest, facts in self._entries.items()
            },
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("Could not write parse cache %s: %s", self.path, exc)

    # ── Introspection ───────────────────────────────────────────────────────

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "path": str(self.path) if self.path else None,
            "entries": len(self._entries),
            "max_entries": self.max_entries,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
        }

    def clear(self) -> None:
        self._entries.clear()
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ParseCache(entries={len(self._entries)}, path={self.path!r})"


def default_cache_path(repo_root: str | Path) -> Path:
    """Where the parse cache lives for a given repository root."""
    return Path(repo_root) / CACHE_DIRNAME / CACHE_FILENAME
