# WREN PROMPT - PHASE 4

**From:** Rook
**To:** Wren
**Phase:** 4 only - token-compact context, MCP surface, and five real skills
**Your branch:** `wren/phase-4-context`
**Base:** local `rook/phase-4-context` (planning documents only)
**Your worktree:** `D:\Aditya\Hackathon Projects\RepoScope-wren-phase4`
**Status:** contract frozen; you implement the whole phase, Rook verifies.

> **Do not push anything.** The owner has explicitly withheld push permission.
> Commit locally on `wren/phase-4-context` and stop. Rook reviews and
> integrates. Do not touch `main` or `experimental`. Do not read, print, or
> commit `.env`; the GitHub PAT must never appear in a command line, log,
> document, or test.

---

## 1. Mission

Phase 4 ships the context-compression layer that the rest of V2.5-V2.8 depends
on, and it turns the five Phase 3 skill descriptors into real `SKILL.md`
bundles.

You own the whole implementation:

- the deterministic context compressor and AST skeleton;
- the context-pack HTTP endpoint;
- five new MCP tools and three new MCP resources;
- the five canonical skill bodies and their checked-in copies;
- harness-generator preview/apply support for skill files;
- the Skills panel and its browser journey;
- the measured TOON benchmark and the documentation updates.

Rook owns the planning documents, the verification pass, branch integration,
and the owner-approved merge. Rook will not edit implementation files while
you hold the Phase 4 claim.

### In scope

- `backend/context_compressor.py`
- `backend/skill_library.py`
- `backend/api/routers/context.py`
- `backend/api/__init__.py`
- `backend/mcp_server/tools.py`
- `backend/mcp_server/server.py`
- `backend/harness_generator.py`
- `backend/tests/test_context_compressor.py`
- `backend/tests/test_context_api.py`
- `backend/tests/test_skill_library.py`
- `backend/tests/test_mcp_v25.py`
- `backend/tests/test_mcp_server.py` (expected tool/resource sets only)
- `backend/tests/test_harness_generator.py` and `test_harness_api.py`
- `benchmarks/toon_benchmark.py`
- `.claude/skills/<id>/SKILL.md` and `.agents/skills/<id>/SKILL.md`
- `frontend/src/api/client.ts`
- `frontend/src/components/harness/SkillsSection.tsx`
- `frontend/tests/e2e/harness.spec.ts`
- `pyproject.toml`, `.github/workflows/qa.yml`
- `docs/MCP.md` (new), `docs/TOON_BENCHMARK.md` (new)
- `docs/API.md`, `docs/AGENT_INTEGRATION.md`, `docs/FEATURES.md`
- `README.md`, `CHANGELOG.md`
- `docs/coordination/WREN.md`, `docs/coordination/COMS.md`,
  `docs/coordination/DIALOGUE.md` (your entries only)

### Out of scope

- Phase 5+ work: citation verifier, reverse-prompt compiler, security suite,
  packaging, release tags, deployment.
- Any graph schema, parser, resolver, or `graph_builder.py` change.
- Any existing MCP tool name, resource URI, endpoint path, or response key
  change. The existing 8 tools and 5 resources must keep working exactly.
- Any `.opencode/skills/` copy. OpenCode already reads `.claude/skills/` and
  `.agents/skills/`.
- Any new frontend dependency, package-lock churn, or `GraphView.tsx` change.
- Any claim that static reachability proves dead code.
- Any 85% token-saving claim. All token numbers must be measured.

If the contract below conflicts with the source, stop and report it in
`DIALOGUE.md` and `COMS.md`. Do not silently invent a different shape.

---

## 2. Start state and preflight

The Rook planning branch is local and unpushed. Its tip contains
`docs/coordination/PHASE_4_RESEARCH.md`, this prompt, the frozen plan section,
and the Phase 4 coordination board. `main` is at `7ff5291` (Phase 3 merged).

Create your worktree from the local planning branch:

```powershell
git worktree add "D:\Aditya\Hackathon Projects\RepoScope-wren-phase4" -b wren/phase-4-context rook/phase-4-context
cd "D:\Aditya\Hackathon Projects\RepoScope-wren-phase4"
git branch --show-current
git log --oneline -4
git merge-base --is-ancestor 7ff5291 HEAD
git status --short
```

Requirements:

- `git branch --show-current` prints `wren/phase-4-context`.
- `git merge-base --is-ancestor 7ff5291 HEAD` exits `0`.
- `git log --oneline -4` shows the planning commit
  `docs(phase-4): freeze context, MCP, and skill execution plan` at or near
  the tip.
- `git status --short` is empty.

If the worktree or branch already exists, stop and report it. Do not reuse or
delete another agent's work. Do not fetch `origin`; this branch is local.

Install and establish a green baseline **before editing**:

```powershell
npm --prefix frontend ci
python -m pytest -q
python -m compileall -q backend
python -m pip check
npm --prefix frontend run build
cd frontend
npx playwright test tests/e2e/harness.spec.ts
cd ..
```

Expected baseline: `473 passed, 1 skipped` (the Windows file-symlink test),
frontend build green, harness journey 5/5 green. If any baseline command is
red, stop and report the exact error. Do not fix unrelated code.

The local environment already has `toon-format` 1.2.0. If it is missing,
install only the optional package:

```powershell
python -m pip install "toon-format>=1.2,<2"
```

Do not add it to `backend/requirements.txt`.

---

## 3. Frozen public surface

The final MCP surface is exactly **13 tools and 8 resources**.

### 3.1 Existing tools (names, signatures, and behavior unchanged)

1. `get_architecture_overview`
2. `calculate_blast_radius`
3. `get_dependency_lineage`
4. `explain_architectural_rule`
5. `get_repo_map`
6. `find_dependency_cycles`
7. `get_hotspots`
8. `find_unreachable_symbols`

### 3.2 New tools

9. `get_mindmap_hierarchy`
10. `get_ast_skeleton`
11. `get_context_pack`
12. `diff_interface_contracts`
13. `get_ranked_reading_path`

### 3.3 Existing resources (URIs unchanged)

1. `reposcope://graph/summary`
2. `reposcope://hotspots`
3. `reposcope://repo-map`
4. `reposcope://dead-code`
5. `reposcope://cycles`

### 3.4 New resources

6. `reposcope://mindmap`
7. `reposcope://api-routes`
8. `reposcope://context-pack`

`backend/tests/test_mcp_server.py` must assert exactly these sets. The stdio
transport test uses the same set, so update both `EXPECTED_TOOLS` and
`EXPECTED_RESOURCES`, not just the in-memory session test.

### 3.5 HTTP surface

Add exactly one route:

```
GET /api/context/pack
  ?paths=backend/main.py,backend/repo_map.py   (optional, comma-separated)
  &format=json|toon                            (default json)
  &detail=skeleton|full                        (default skeleton)
  &budget=8000                                 (default 8000, 500..200000)
  &since_hash=sha256:...                       (optional)
```

No other public endpoint is added in Phase 4.

---

## 4. `backend/context_compressor.py`

This module is deterministic and pure with respect to the graph. It reads
source bodies only in `detail=full`; it never calls an LLM, never writes, and
never parses a repository a second time.

### 4.1 Public constants and API

```python
CONTEXT_SCHEMA_VERSION = 1
DEFAULT_BUDGET_TOKENS = 8000
MIN_BUDGET_TOKENS = 500
MAX_BUDGET_TOKENS = 200000
MAX_BODY_LINES = 120
MAX_BODY_CHARS = 12000

class ContextError(ValueError):
    def __init__(self, status_code: int, detail: str) -> None: ...

def normalize_signature(signature: str) -> str: ...
def resolve_context_path(root: str | Path, relpath: str) -> Path | None: ...
def build_ast_skeleton(graph: dict, root: str | None, file_path: str,
                       max_symbols: int = 200) -> dict: ...
def build_context_pack(graph: dict, root: str | None,
                       paths: str | Sequence[str] | None = None,
                       detail: str = "skeleton",
                       budget: int = DEFAULT_BUDGET_TOKENS,
                       since_hash: str | None = None) -> dict: ...
def context_hash(payload: dict) -> str: ...
def encode_json(payload: dict) -> str: ...
def encode_toon(payload: dict) -> str: ...
def decode_toon(text: str) -> dict: ...
def toon_available() -> bool: ...
```

`ContextError.status_code` is `400` for a bad `detail`, a bad `budget`, a
path that cannot be represented safely, or an unavailable TOON dependency.
The HTTP router translates it to `HTTPException`.

### 4.2 Context-pack payload - exact shape

```json
{
  "schema_version": 1,
  "available": true,
  "detail": "skeleton",
  "budget": 8000,
  "files": [
    {
      "path": "backend/repo_map.py",
      "role": "service",
      "pillar": "backend",
      "route_count": 0,
      "symbols": [
        {
          "name": "build_repo_map",
          "kind": "function",
          "line": 123,
          "end_line": 193,
          "exported": true,
          "complexity": 8,
          "role": "service",
          "signature": "def build_repo_map(graph: dict, budget_tokens: int = DEFAULT_BUDGET_TOKENS, root: str | None = None, tokenizer: Tokenizer | None = None, max_symbols: int = DEFAULT_MAX_SYMBOLS) -> dict:"
        }
      ]
    }
  ],
  "omitted": [
    {"path": "backend/big.py", "reason": "budget"}
  ],
  "caps": [
    {"path": "backend/big.py", "symbol": "big_function",
     "reason": "max-lines", "limit": 120}
  ],
  "truncated": true,
  "counts": {
    "files_included": 1,
    "files_requested": 2,
    "symbols_included": 1
  },
  "hash": "sha256:<64 lowercase hex>",
  "tokens": {"pack": 412, "budget": 8000},
  "format": "json",
  "root": "<absolute repository root>"
}
```

Rules:

- `files` is ordered: explicit `paths` order, or ranked order when no paths
  are supplied.
- `omitted[].reason` is one of `budget`, `not-indexed`, `ambiguous`,
  `outside-root`, `unreadable`.
- `caps[].reason` is `max-lines` or `max-chars`. `limit` is the integer cap
  that applied.
- `truncated` is true when any file was omitted for budget or safety, any body
  was capped, or any requested file could not be included.
- `counts.files_requested` is the number of explicit paths, or the number of
  ranked candidates considered when `paths` is empty.
- `root` is metadata only. It is excluded from the hash.
- No timestamp, elapsed time, random value, or absolute path may appear in
  `files` or `caps`. Paths inside entries are repository-relative.
- If the graph is empty, return
  `{"schema_version": 1, "available": false, "reason": "the index is empty"}`.

### 4.3 File and symbol selection

- `paths` may be a comma-separated string or a sequence. Split, trim, drop
  empty parts, and deduplicate while preserving order.
- With no `paths`, use `onboarding.rank_rows(graph)` and flatten rows 1..5 in
  that order. This is the same deterministic ranking the onboarding UI uses.
  Do not call `build_onboarding` (it invokes an LLM).
- Resolve an explicit path by exact `file:<path>`, then exact node label,
  then a unique file-label suffix. If more than one file matches, omit it as
  `ambiguous`. If none matches, omit it as `not-indexed`.
- Reject absolute paths, drive-qualified paths, and any component equal to
  `..` as `outside-root`. Never read outside the repository root.
- For each file, emit exactly `path`, `role`, `pillar`, `route_count`, and
  `symbols`; include every symbol node whose `file` equals that path. Sort
  symbols by `line`, then `name`, then `kind`.
- Symbol fields are `name`, `kind`, `line`, `end_line`, `exported`,
  `complexity`, `role`, and `signature`. Use the graph's values with safe
  defaults (`0`, `""`, `false`, `1`). `role` falls back to the file role.
- `signature` is the graph signature with all whitespace collapsed to single
  spaces and capped at 500 characters. If the graph signature is empty, use
  the first non-empty source line at `line`, whitespace-collapsed. Do not
  fabricate a signature.
- `detail=skeleton` omits only `body`/`body_*` fields. It keeps paths, lines,
  end lines, roles, signatures, and kinds.
- `detail=full` adds `body`, `body_truncated`, `body_lines`, and `body_chars`
  to each symbol. Read from `line` through `end_line` inclusive, starting at
  `line`, capped at 120 lines and 12,000 characters. Add one `caps` entry per
  applied cap. Mark `body_truncated` true if either cap applied. If the file
  cannot be read, keep the symbol metadata, omit `body`, and add the file to
  `omitted` with `reason: "unreadable"`.
- A body is source text, not a summary. Do not strip docstrings or comments.

### 4.4 Budget behavior

- Validate `budget` against `500..200000`; an out-of-range value is a
  `ContextError` with a precise message. Do not silently clamp an explicit
  budget.
- Build candidate file entries in order. Add a candidate only if the
  neutralized payload (the pack without `hash`, `tokens`, `format`, `root`,
  and `since_hash`) still estimates at or below `budget`. If it does not fit,
  add it to `omitted` as `budget` and continue with later candidates.
- After finalization, if the measured pack still exceeds `budget`, drop the
  last included file to `omitted` as `budget` and recompute until it fits or
  no files remain. A first file larger than the budget is therefore omitted,
  not silently over-budget.
- `tokens.pack` is `estimate_tokens(encode_json(neutralized_payload))`.
  This deliberately excludes the token fields themselves to avoid a circular
  measurement. The token count is an estimate from `token_metrics`, not a BPE
  tokenizer; say so in the docs.
- `tokens.budget` echoes the effective budget.

### 4.5 Hash and delta behavior

`context_hash(payload)`:

1. Deep-copy the payload.
2. Recursively drop these keys:
   `format`, `since_hash`, `hash`, `root`, `tokens`, `token_count`,
   `estimated_tokens`, `full_context_tokens`, `reduction_pct`, `saving_pct`,
   `generated_at`.
3. Serialize with `json.dumps(..., sort_keys=True, separators=(",", ":"),
   ensure_ascii=False)`.
4. Return `"sha256:" + hashlib.sha256(bytes).hexdigest()`.

Consequences that tests must prove:

- Same graph + same `paths` + same `detail` + same `budget` -> same hash.
- JSON and TOON share the same content hash because `format` is excluded.
- Changing only `tokens.pack`, `root`, or `format` does not change the hash.
- Changing `detail`, `budget`, selected files, symbols, `omitted`, `caps`, or
  `counts` changes the hash.

`since_hash`:

- If supplied and equal to the computed hash, return a compact JSON envelope
  and no files:

```json
{
  "schema_version": 1,
  "available": true,
  "unchanged": true,
  "detail": "skeleton",
  "budget": 8000,
  "hash": "sha256:<64 lowercase hex>",
  "format": "json"
}
```

- The unchanged envelope is always compact JSON, even when the request asked
  for `format=toon`. `unchanged: true` is the signal that no TOON body was
  produced.
- If it does not match, return the full pack and echo `since_hash` at the top
  level. The echo is excluded from the hash.

### 4.6 `build_ast_skeleton` payload

```json
{
  "schema_version": 1,
  "available": true,
  "root": "<absolute root>",
  "file": "backend/repo_map.py",
  "role": "service",
  "pillar": "backend",
  "route_count": 0,
  "symbols": [
    {"name": "...", "kind": "function", "line": 1, "end_line": 2,
     "exported": true, "complexity": 1, "role": "service",
     "signature": "..."}
  ],
  "truncated": false,
  "counts": {"symbols": 1, "returned": 1}
}
```

`max_symbols` is clamped to `1..1000`. If more symbols exist, include the
first `max_symbols` in line order and set `truncated: true`. A missing or
unindexed file returns `available: false` with a precise `reason` and a short
`candidates` list when a suffix was ambiguous. This tool never includes
bodies.

### 4.7 TOON adapter

- `toon_format` is imported lazily inside `_load_toon()`; it must not be
  imported at module import time.
- `REPOSCOPE_TOON=0` is a kill switch. `encode_toon` and `decode_toon` raise
  `ContextError(400, "TOON output is disabled (REPOSCOPE_TOON=0). Use format=json.")`.
- If the package is absent, raise
  `ContextError(400, "TOON output requires the optional dependency. Install with: pip install reposcope[toon]")`.
- `encode_toon` normalizes the payload through
  `json.loads(json.dumps(payload))` before calling
  `toon_format.encode(payload, sort_keys=True)`. This keeps the benchmark
  round-trip comparison type-stable.
- `decode_toon(text)` calls `toon_format.decode(text)`.
- `toon_available()` returns false when the package is absent or the kill
  switch is set; it must not raise.

---

## 5. `backend/api/routers/context.py`

Mount it in `backend/api/__init__.py`.

```python
router = APIRouter(prefix="/api/context", tags=["context"])
```

Exact route:

```python
@router.get("/pack")
async def context_pack(
    paths: str = Query(""),
    format: Literal["json", "toon"] = Query("json"),
    detail: Literal["skeleton", "full"] = Query("skeleton"),
    budget: int = Query(8000, ge=500, le=200000),
    since_hash: str | None = Query(None),
):
    ...
```

Behavior:

- Resolve the graph and root with `orchestrator.current_graph()`. If the root
  is `None`, fall back to `repo_tracker.load_state().get("local_path")`.
- If there is no graph and no root, return `503` with
  `{"detail": "No repository is loaded"}`.
- If there is a root but no graph, pass the empty graph to the compressor; it
  returns `available: false` rather than crashing.
- Build the pack, translate `ContextError` to `HTTPException`.
- For `format=json`, return compact JSON (`encode_json`) with
  `media_type="application/json"`.
- For `format=toon`, return `text/toon; charset=utf-8` from `encode_toon`.
- Set `X-RepoScope-Context-Hash` to the pack hash on every pack response,
  including the unchanged envelope.
- Set `X-RepoScope-Context-Unchanged: 1` on the unchanged envelope.
- The unchanged envelope is always JSON (see 4.5), even for a TOON request.
- Do not pretty-print the pack body. The compact JSON form is the baseline the
  TOON benchmark measures against.

Add API tests in `backend/tests/test_context_api.py` covering defaults,
explicit paths, full detail, budget, since_hash, TOON disabled/missing/round
trip, and the 503 state. Use `monkeypatch.setattr(orchestrator, "current_graph", ...)`
like `test_mindmap_api.py`; do not rely on the developer's loaded repository.

---

## 6. MCP tools and resources

### 6.1 `backend/mcp_server/tools.py`

Add these deterministic functions. They take the in-process `graph` and
`root` from the server, exactly like the existing tools.

```python
def mindmap_hierarchy(graph: dict, root: str | None = None,
                      include_symbols: bool = True,
                      max_nodes: int = 2000) -> dict: ...

def ast_skeleton(graph: dict, root: str | None, file_path: str,
                 max_symbols: int = 200) -> dict: ...

def context_pack(graph: dict, root: str | None,
                 paths: str = "", detail: str = "skeleton",
                 budget: int = 8000, since_hash: str | None = None) -> dict: ...

def diff_interface_contracts(graph: dict, file_path: str,
                             patch: str | None = None,
                             old_source: str | None = None,
                             new_source: str | None = None,
                             include_consumers: bool = True) -> dict: ...

def ranked_reading_path(graph: dict, root: str | None = None,
                        max_files: int = 12) -> dict: ...

def api_routes_resource(graph: dict, root: str | None = None,
                        limit: int = 500) -> dict: ...
```

#### `mindmap_hierarchy`

Return the result of `build_mindmap_payload(graph, include_symbols=...,
max_nodes=...)`, plus `available: true`, `root`, `include_symbols`, and
`max_nodes`. Set `payload["source"]["root"] = root`. Do not add
`generated_at`; the tool/resource must be deterministic. Clamp `max_nodes` to
`1..200000`. If the graph has no nodes, return `available: false` with
`reason: "the index is empty"`.

#### `ast_skeleton`

Return `build_ast_skeleton(graph, root, file_path, max_symbols)` directly.
This is the only skeleton surface; it never returns bodies.

#### `context_pack`

Return `build_context_pack(graph, root, paths=paths, detail=detail,
budget=budget, since_hash=since_hash)`. This MCP tool is JSON only. Do not add
a `format` parameter; TOON is an HTTP export, and returning a TOON string from
a structured MCP tool would break clients. Document that in the tool
description and in `docs/MCP.md`.

#### `diff_interface_contracts`

Validation and behavior:

- `file_path` is required. If empty, return `available: false`.
- Exactly one input mode: `patch`, or both `old_source` and `new_source`.
  Supplying neither, both modes, or only one of the source pair returns
  `available: false` with a precise reason.
- With `patch`, call `contract_diff.sources_from_patch(patch)` to get
  `(old_source, new_source)`.
- Call `contract_diff.diff_sources(old_source, new_source, file_path)`.
- If `include_consumers` and `graph` is non-empty, call
  `contract_diff.attach_consumers(findings, graph)`.
- Serialize with `contract_diff.findings_to_dicts`.
- Return:

```json
{
  "available": true,
  "file": "src/api.ts",
  "findings": [ ... ],
  "counts": {"breaking": 1, "warning": 0, "info": 0, "total": 1},
  "consumers_attached": true,
  "note": "No finding is not proof that no consumer breaks; dynamic dispatch, reflection, and unsupported languages are invisible to this check."
}
```

Severity values stay `BREAKING`, `WARNING`, `INFO` in findings; the counts
keys are lowercase. Do not invent a `security` mode.

#### `ranked_reading_path`

Use `onboarding.rank_rows(graph)` and `graph_utils.build_adjacency`. Do not
call `build_onboarding`; it invokes an LLM.

Return:

```json
{
  "available": true,
  "root": "<absolute root>",
  "levels": [
    {
      "level": 1,
      "title": "Entry Points",
      "description": "Start here - these files are where execution begins.",
      "files": [
        {"path": "backend/main.py", "role": "entrypoint", "pillar": "backend",
         "line": 1, "incoming": 0, "outgoing": 12, "score": 12,
         "why": "Backbone file with the highest reverse-dependency score."}
      ]
    }
  ],
  "path": [
    {"rank": 1, "level": 1, "path": "backend/main.py", "role": "entrypoint",
     "pillar": "backend", "line": 1, "incoming": 0, "outgoing": 12,
     "score": 12,
     "why": "Backbone file with the highest reverse-dependency score."}
  ],
  "total_files": 42,
  "returned": 12,
  "truncated": true,
  "caveat": "Ranking uses static graph connectivity; it is a starting path, not a measure of code quality."
}
```

- Levels are `1 = Entry Points`, `2 = Core Modules`, `3 = Utils & Leaves`.
- Level 1 uses row 1; level 2 uses rows 2-3; level 3 uses rows 4-5.
- Cap each level at 6 files, then flatten to `max_files` (clamp `1..50`),
  preserving level order and within-level rank order.
- `score = incoming * 2 + outgoing`, matching `rank_rows`.
- `why` is deterministic: "Backbone file with the highest reverse-dependency
  score." for level 1, "Core module in the middle of the dependency path."
  for level 2, "Leaf or low-traffic helper; safe to read after the core." for
  level 3.
- If two nodes have the same path, keep the first. `rank_rows` already
  deduplicates by sorting, but assert it in tests.

#### `api_routes_resource`

```json
{
  "available": true,
  "root": "<absolute root>",
  "routes": [ ... ],
  "total": 12,
  "truncated": false
}
```

Use `graph.get("api_routes", [])`; cap at `limit` (clamp `1..2000`). If the
graph is empty, return `available: false`. Do not re-parse.

### 6.2 `backend/mcp_server/server.py`

Add the five `@mcp.tool()` wrappers with exact names and default arguments:

```python
@mcp.tool()
def get_mindmap_hierarchy(include_symbols: bool = True,
                          max_nodes: int = 2000) -> dict: ...

@mcp.tool()
def get_ast_skeleton(file_path: str, max_symbols: int = 200) -> dict: ...

@mcp.tool()
def get_context_pack(paths: str = "", detail: str = "skeleton",
                     budget: int = 8000, since_hash: str | None = None) -> dict: ...

@mcp.tool()
def diff_interface_contracts(file_path: str, patch: str | None = None,
                             old_source: str | None = None,
                             new_source: str | None = None,
                             include_consumers: bool = True) -> dict: ...

@mcp.tool()
def get_ranked_reading_path(max_files: int = 12) -> dict: ...
```

Each docstring must state what it returns, that it is deterministic, and the
caveat that applies (static reachability is an estimate; no finding is not
proof; ranking is not code quality). Descriptions are part of the MCP
contract and are asserted to be non-empty.

Add the three resources:

```python
@mcp.resource("reposcope://mindmap")
def mindmap_resource() -> str: ...

@mcp.resource("reposcope://api-routes")
def api_routes_resource() -> str: ...

@mcp.resource("reposcope://context-pack")
def context_pack_resource() -> str: ...
```

- `reposcope://mindmap`: `T.mindmap_hierarchy(graph, root_text,
  include_symbols=True, max_nodes=2000)`.
- `reposcope://api-routes`: `T.api_routes_resource(graph, root_text)`.
- `reposcope://context-pack`: `T.context_pack(graph, root_text)` with the
  default `detail=skeleton` and `budget=8000`.
- Serialize with `json.dumps(..., indent=2, sort_keys=True)`, matching the
  existing resources.

Add `backend/tests/test_mcp_v25.py` with real in-memory MCP sessions, the same
style as `test_mcp_server.py`. Test each new tool and each new resource,
including the no-body guarantee for skeleton, the context-pack default, the
since_hash envelope, the contract diff, and the reading path. Update
`test_mcp_server.py` to 13/8 but keep its existing assertions unchanged.

---

## 7. Five real skills

### 7.1 Canonical source and copies

- Canonical bodies live in `backend/skill_library.py` as
  `SKILL_BODIES: dict[str, str]`.
- Checked-in copies live at:
  - `.claude/skills/<id>/SKILL.md`
  - `.agents/skills/<id>/SKILL.md`
- There is no `.opencode/skills/` copy. OpenCode reads both project directories.
- The canonical string and both checked-in copies must be byte-identical after
  normalizing CRLF to LF and ensuring exactly one trailing newline.
- `backend/tests/test_skill_library.py` must compare all ten files to the
  canonical dictionary and fail with the exact path if one drifts.

### 7.2 Frontmatter - exact IDs and descriptions

Every file starts with:

```markdown
---
name: <id>
description: <one-line description>
---
```

Use these exact names and descriptions. Do not add YAML keys.

| id | description |
|---|---|
| `blast-radius-guard` | Measure the direct and transitive impact of a file or symbol change before editing. Use before modifying a shared module, when a refactor touches an exported symbol, or when deciding which tests and consumers must be checked. Do not use for general architecture discovery; use `zero-grep-architect` instead. |
| `zero-grep-architect` | Answer architecture, ownership, entry-point, and dependency questions from RepoScope's graph instead of broad grep or file reads. Use when you need the shape of a repository, the owner of a module, or the path between two files. Do not use it for contract diffs or dead-code removal. |
| `pr-contract-shield` | Review interface contract changes and architectural boundary crossings before opening or updating a pull request. Use when a patch changes exported signatures, parameters, return types, or imports across layers. Do not use it as a security scanner or as a replacement for tests. |
| `onboarding-navigator` | Build a ranked, budgeted reading path through an unfamiliar repository. Use when a developer is new to the codebase, when you need the shortest path from entry points to core modules, or when deciding what to read first. Do not use it to generate quizzes or claims that are not grounded in the graph. |
| `dead-code-surgeon` | Investigate symbols that static reachability marks as unreachable, then remove them only after human confirmation. Use when cleaning dead code, deprecating an unused helper, or reviewing an unreachable-symbol report. This skill treats reachability as an estimate, never as proof. |

Rules:

- `name` is lowercase, hyphenated, at most 64 characters, and equals the
  parent directory.
- `description` is at most 1,024 characters, says what the skill does AND when
  to use it, and names at least one non-trigger where useful.
- The frontmatter is the only YAML. The body is instructions, not marketing.

### 7.3 Body contract

Each body is 60-100 lines and under 5,000 estimated tokens. Use these exact
section headings in this order:

```markdown
## When to use
## Do not use
## Budget
## Workflow
## Decision rules
## Output contract
## Stop conditions
```

Required content:

- **Budget:** choose 4,000-8,000 tokens. Start with `detail=skeleton`. Request
  `detail=full` only for symbols that survive the skeleton pass. Never dump
  the repository.
- **Workflow:** numbered steps. The first RepoScope tool call is frozen:

| skill | first tool call |
|---|---|
| `blast-radius-guard` | `get_ast_skeleton` |
| `zero-grep-architect` | `get_architecture_overview` |
| `pr-contract-shield` | `diff_interface_contracts` |
| `onboarding-navigator` | `get_ranked_reading_path` |
| `dead-code-surgeon` | `find_unreachable_symbols` |

- **Output contract:** name the exact fields the agent must report and the
  `path:line` citation format. Do not promise a field the tool does not
  return.
- **Stop conditions:** say when to ask a human instead of reading more code.
- **Dead-code caveat:** `dead-code-surgeon` must contain the exact sentence
  "Static reachability is an estimate, not proof of dead code." and must say
  that a candidate is not deleted until a human confirms dynamic dispatch,
  reflection, plugin registration, and external consumers.
- **PR caveat:** `pr-contract-shield` must say that no finding is not proof
  that no consumer breaks, and that unsupported languages and dynamic calls
  are invisible.
- **Architecture caveat:** `zero-grep-architect` must not claim the graph is
  complete for dynamic dispatch or generated code.

Tool/resource allowlist:

- Every backticked token matching `^(get_|find_|calculate_|explain_|diff_)`
  must be one of the 13 real tools.
- Every `reposcope://...` token must be one of the 8 real resources.
- The following stale names are forbidden anywhere in the body or docs:
  `get_symbol_blast_radius`, `find_orphan_nodes_and_cycles`,
  `run_security_scan`, `compile_reverse_prompt`.
- Each skill should use at least two real tools. `dead-code-surgeon` should
  name `reposcope://dead-code`. `onboarding-navigator` should name
  `reposcope://mindmap` or `reposcope://repo-map`. `pr-contract-shield` should
  name `reposcope://api-routes` when API routes are relevant.
- Do not mention the 85% claim, automatic OpenCode selection, or installing
  external companion skills.

### 7.4 `backend/skill_library.py`

Provide:

```python
SKILL_IDS: tuple[str, ...] = (...)
SKILL_BODIES: dict[str, str] = {...}

def skill_body(skill_id: str) -> str: ...
def validate_skill_bodies() -> list[str]: ...
```

`validate_skill_bodies()` returns a list of human-readable problems (empty
means valid): missing frontmatter, name/dir mismatch, description too long,
body too large, forbidden tool name, unknown resource URI, missing required
section, missing dead-code caveat. It does not write files and does not raise.
Use it from tests; it is also a useful import-time-free diagnostic.

### 7.5 Harness integration

`backend/harness_generator.py`:

- Keep the five `SKILLS` descriptors and their IDs, labels, targets, and file
  paths unchanged. Freeze order.
- `list_skills()` returns each descriptor plus `content` (the canonical body)
  and `content_available: true`; the top-level `content_available` is `true`.
  Do not return descriptor-only entries.
- `build_preview()` appends skill files after the agent's MCP/instruction
  files:
  - Claude Code gets the five `.claude/skills/<id>/SKILL.md` files.
  - Antigravity gets the five `.agents/skills/<id>/SKILL.md` files.
  - The other seven agents get no skill files.
- Each appended entry has the same shape as existing preview files:
  `path`, `format: "markdown"`, `content`, `exists`, `diff`, `will_write`.
- Skill files are written whole; do not run them through the RepoScope
  markdown-section merger. If an existing skill file differs, show the unified
  diff and set `requires_force`. If it is identical, `will_write: false` and
  `diff: null`.
- `apply_config()` already writes every preview file atomically. Confirm it
  writes skill files, returns them in `applied`/`unchanged`, and still refuses
  writes when `REPOSCOPE_HARNESS_APPLY` is not `1`.
- Update the Antigravity note that says `.agents/skills/` belongs to Phase 4.
  It is now written.
- `backend/api/routers/harness.py` docstrings must stop saying bodies are
  absent.

Tests:

- `test_harness_generator.py`: five bodies available; Claude preview has
  exactly 7 files (2 config + 5 skills); Antigravity has exactly 7 (2 + 5);
  the other seven still have 2; preview writes nothing; apply writes all 7;
  second apply is unchanged; a changed existing skill file needs force; a
  directory/symlink escape is still rejected.
- `test_harness_api.py`: `/api/harness/skills` returns five entries with
  `content_available: true` and non-empty `content`; `/api/harness/config`
  includes the skill files; apply writes them when enabled.
- Remove or rewrite the Phase 3 test that asserted Antigravity skills are
  never written. Do not delete the path-safety tests.

---

## 8. Frontend

### 8.1 `frontend/src/api/client.ts`

Extend `HarnessSkill` with `content: string`. Keep `HarnessSkills` unchanged.

### 8.2 `frontend/src/components/harness/SkillsSection.tsx`

- Replace the Phase 4 teaser text with:
  "RepoScope ships 5 specialized skills for AI coding agents. Applying the
  harness writes each skill to `.claude/skills/<id>/SKILL.md` and
  `.agents/skills/<id>/SKILL.md`."
- Replace the `Available in Phase 4` badge with `Ready` when
  `skill.content_available` is true.
- Add a per-card button `Preview SKILL.md` / `Hide SKILL.md` that toggles a
  `<pre>` containing `skill.content`. Use `aria-expanded`, `aria-controls`,
  and a stable `id`. The preview must scroll inside the card and must not
  create horizontal page overflow at 1280x800.
- Add `data-testid="harness-skill-body-<id>"` to the `<pre>`.
- Keep the existing targets and file-path rows.
- Do not add a new API call; the body already arrives with the skills payload.

### 8.3 `frontend/tests/e2e/harness.spec.ts`

Update the Skills section:

- Assert five cards, each with `Ready`, and no `Available in Phase 4`.
- Open the first card's preview, assert the body contains
  `name: blast-radius-guard` and `get_ast_skeleton`, and assert the button
  toggles closed.
- Capture the skills screenshot with one preview open.
- Keep the existing preview/apply, force, focus, responsive, and console-error
  assertions intact. Do not weaken them.
- If a preview file tab now shows skill files, assert Claude's file list
  includes `.claude/skills/blast-radius-guard/SKILL.md`; do not assert that
  the skills tab is the only source.

---

## 9. Documentation

### 9.1 `docs/MCP.md` (new)

A complete reference for the 13 tools and 8 resources:

- Configuration examples for stdio and Streamable HTTP; do not add SSE.
- A table of every tool: name, arguments, what it returns, and its caveat.
- A table of every resource: URI, payload, and when to read it.
- The context-pack contract from section 4, including `detail`, `budget`,
  `since_hash`, `omitted`, `caps`, `tokens`, and `hash`.
- The JSON default and TOON opt-in policy. State the measured benchmark result
  from `docs/TOON_BENCHMARK.md`; do not claim 85%.
- The five skills and how an agent should invoke them. State that OpenCode's
  skill tool is explicit, not metadata-triggered.
- The static-reachability caveat and the "no finding is not proof" caveat.
- A short "what changed in Phase 4" section that preserves the existing 8
  tools and 5 resources.

### 9.2 `docs/TOON_BENCHMARK.md` (new)

Include:

- Date, machine/OS, Python version, `toon-format` version.
- Corpus: at least five real repositories, each with the exact commit SHA and
  commit date. Proposed corpus:
  `psf/requests`, `pallets/flask`, `encode/httpx`, `expressjs/express`,
  `sindresorhus/got`.
- Method: build the graph, build a default skeleton context pack at
  `budget=8000`, encode the same payload as compact JSON and TOON, measure
  bytes and `estimate_tokens`, decode TOON, and compare it to the payload.
- A per-repository table: files/symbols, JSON bytes/tokens, TOON bytes/tokens,
  saving percent, round-trip pass/fail.
- Median saving percent and an explicit decision. JSON remains the default
  regardless. If median saving is below 20%, say so plainly. If round-trip
  fails, stop and report a blocker; do not ship a lossy serializer.
- Reproduction command using `benchmarks/toon_benchmark.py`.
- Limitations: estimated tokens, not a BPE tokenizer; one pack shape; network
  and repository state can change; do not compare against pretty JSON.

No 85% claim anywhere. If the measured number is negative, report it.

### 9.3 `docs/API.md`

- Add `GET /api/context/pack` to the core table and a full section with query
  parameters, response fields, hash/since_hash behavior, TOON errors, and
  examples.
- Update the harness skills row: bodies are shipped, not Phase 4.
- Link to `docs/MCP.md` for the tool/resource reference.

### 9.4 `docs/AGENT_INTEGRATION.md`

- Rewrite section 7 (Phase 4 Skills Preview) as shipped skills. Remove
  "will be delivered in Phase 4".
- Add the discovery matrix:
  - Claude Code: `.claude/skills/<id>/SKILL.md`.
  - Antigravity: `.agents/skills/<id>/SKILL.md`.
  - OpenCode: reads `.claude/skills/` and `.agents/skills/`; its skill tool is
    explicit. Do not claim metadata-only automatic selection.
- State that the harness writes both copies for Claude and Antigravity, and
  that other agents can read the same files if their implementation supports
  Agent Skills.
- Update the Antigravity section to mention the skill files are written.
- Keep the existing nine-target registry table and Phase 3 safety rules.

### 9.5 `docs/FEATURES.md`, `README.md`, `CHANGELOG.md`

- Update every "8 tools and 5 resources" count to "13 tools and 8 resources".
- Add the new tool/resource names and one sentence each.
- Replace the "SKILL.md bodies are Phase 4" known gap with the shipped state.
- Add a Phase 4 changelog entry under `[Unreleased]`: context pack, AST
  skeleton, delta hash, five MCP tools, three resources, five skills,
  measured TOON result, and the absence of an unproven 85% claim.
- Do not rewrite unrelated README claims or screenshots.

---

## 10. Measured TOON benchmark

Add `benchmarks/toon_benchmark.py` (standard library + the repo's own modules;
`toon_format` is optional).

Recommended interface:

```powershell
python benchmarks/toon_benchmark.py `
  --repo "requests=C:\Users\Admin\AppData\Local\Temp\reposcope-toon-bench\requests" `
  --repo "flask=..." `
  --repo "httpx=..." `
  --repo "express=..." `
  --repo "got=..." `
  --budget 8000 `
  --detail skeleton `
  --out "C:\Users\Admin\AppData\Local\Temp\reposcope-toon-bench\results.json"
```

The script must:

1. Insert `<repo-root>/backend` on `sys.path` and import
   `build_graph_from_repo`, `build_context_pack`, `estimate_tokens`.
2. For each repository, record `git -C <path> rev-parse HEAD` and
   `git -C <path> log -1 --format=%cI` without invoking a shell that prints
   secrets.
3. Build the graph once per repository.
4. Build a skeleton pack at the requested budget.
5. Encode compact JSON with
   `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
6. Encode TOON with `toon_format.encode(payload, sort_keys=True)`.
7. Compare `toon_format.decode(toon_text)` to
   `json.loads(json.dumps(payload))`.
8. Record bytes, estimated tokens, saving percent, round-trip equality,
   graph node/edge counts, files included, and symbols included.
9. Print a Markdown table and, with `--out`, write the JSON results.
10. Exit non-zero if TOON is unavailable or any round-trip fails.

Clone the corpus with shallow clones into the approved temp directory; do not
commit the clones:

```powershell
$bench = Join-Path $env:TEMP "reposcope-toon-bench"
New-Item -ItemType Directory -Force $bench | Out-Null
git clone --depth 1 https://github.com/psf/requests.git "$bench\requests"
git clone --depth 1 https://github.com/pallets/flask.git "$bench\flask"
git clone --depth 1 https://github.com/encode/httpx.git "$bench\httpx"
git clone --depth 1 https://github.com/expressjs/express.git "$bench\express"
git clone --depth 1 https://github.com/sindresorhus/got.git "$bench\got"
git -C "$bench\requests" rev-parse HEAD
git -C "$bench\flask" rev-parse HEAD
git -C "$bench\httpx" rev-parse HEAD
git -C "$bench\express" rev-parse HEAD
git -C "$bench\got" rev-parse HEAD
```

If a clone fails, substitute another real repository and record its commit;
keep at least five distinct repositories. If you cannot obtain five, stop and
report the blocker. Never invent a commit, a repository, or a number.

Run both `--detail skeleton` (primary) and, if time permits, `--detail full`
(secondary). The decision rule uses the median skeleton saving. A negative
saving is a valid, reportable result.

Decision:

- JSON stays the default in every case.
- TOON stays opt-in in every case.
- If median saving is below 20% or any round-trip fails, the docs state the
  measured result and do not claim a saving.
- If any round-trip fails and cannot be fixed with JSON-safe payloads, stop
  and report a blocker. Do not ship a lossy `format=toon` path.

---

## 11. Build, test, and gate

Add tests at the lowest layer that proves the behavior, plus the L2 contract
and L3 journey. Do not delete or weaken existing tests.

Required test files/cases:

- `backend/tests/test_context_compressor.py`
  - skeleton keeps path/line/end_line/role/signature and omits body;
  - full includes body and caps at 120 lines / 12,000 chars;
  - budget is respected and omissions are reported;
  - deterministic hash; format/root/token changes do not change it;
  - `since_hash` unchanged/changed envelopes;
  - path traversal is omitted, never read;
  - unreadable/missing files do not crash;
  - TOON round-trip, kill switch, and missing dependency;
  - JSON and TOON share the content hash.
- `backend/tests/test_context_api.py`
  - route registered;
  - defaults are json/skeleton/8000;
  - explicit paths and full detail;
  - compact JSON response and hash header;
  - since_hash envelope;
  - TOON 400 when disabled or missing, 200 and round-trip when available;
  - 503 when no repository is loaded.
- `backend/tests/test_skill_library.py`
  - five IDs and order;
  - frontmatter name/description rules;
  - body size, sections, first tool call;
  - tool/resource allowlist and forbidden stale names;
  - dead-code caveat;
  - ten checked-in copies match the canonical bodies.
- `backend/tests/test_mcp_v25.py`
  - five new tools over a real in-memory MCP session;
  - three new resources;
  - context pack default and since_hash;
  - contract diff and reading path;
  - no body in skeleton;
  - caveats present.
- Update `backend/tests/test_mcp_server.py` to 13/8.
- Update `backend/tests/test_harness_generator.py` and `test_harness_api.py`.
- Update `frontend/tests/e2e/harness.spec.ts`.

Run the full gate from the worktree root:

```powershell
python -m pytest -q
python -m compileall -q backend
python -m pip check
npm --prefix frontend run build
npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json
cd frontend
npx playwright test tests/e2e/harness.spec.ts
npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"
npx playwright test tests/e2e/mindmap.spec.ts
cd ..
git diff --check
```

The baseline is `473 passed, 1 skipped`. The final count will be higher
because Phase 4 adds tests. The Windows symlink test remains the single
expected skip. J22 remains excluded locally because of its unchanged 100 ms
threshold; record the exact reason in your handoff. Do not exclude any new
Phase 4 test.

CI:

- Add `context_compressor` and `skill_library` to `[tool.setuptools].py-modules`.
- Add `[project.optional-dependencies].toon = ["toon-format>=1.2,<2"]`.
- Do not add TOON to `backend/requirements.txt`.
- In `.github/workflows/qa.yml`, after the backend requirements install in
  the L1 unit and L2 contract jobs, add
  `python -m pip install "toon-format>=1.2,<2"`. Leave the L3 browser job
  alone unless it runs the context tests.
- Run `python -m pip check` after any local optional install.

---

## 12. Handoff

Commit locally on `wren/phase-4-context`. One Phase 4 implementation commit
plus a small coordination commit is acceptable; do not mix Phase 5 work.

Suggested implementation commit:

```
feat(context): add skeleton, context packs, TOON flag, and MCP tools
```

Coordination commit:

```
docs(coordination): hand off Phase 4 implementation for review
```

Before stopping:

1. Update `docs/coordination/WREN.md` with claims, the exact commit(s), every
   command and result, the benchmark median, and known limits.
2. Update `docs/coordination/COMS.md` status to `handed-off`.
3. Append one `DIALOGUE.md` entry with timestamp, `Wren`, subject, branch,
   commit, files, gate results, benchmark result, and open decisions.
4. Do not push.
5. Do not merge into `main` or `experimental`.
6. Leave the worktree clean.

Handoff format (from `docs/coordination/README.md`):

1. branch and commit hash;
2. files changed and claims released;
3. commands run and their results;
4. known limits or skipped checks, with the reason;
5. the next open decision, if any.

Rook will create a fresh verification worktree, run the full gate, inspect the
diff, check the measured numbers, and merge only after owner approval.

---

## 13. Stop conditions

Stop and report in `DIALOGUE.md` and `COMS.md` if:

- the baseline is red before your first edit;
- the contract in this prompt conflicts with the source;
- a required change would alter the graph schema, an existing MCP tool name,
  an existing resource URI, or an existing endpoint response key;
- TOON round-trip fails and cannot be fixed with JSON-safe payloads;
- fewer than five real repositories can be measured;
- a test fails for a reason unrelated to Phase 4 and fixing it would touch
  another phase;
- the work would require reading, printing, or committing `.env` or the PAT.

Do not guess, do not fabricate benchmark numbers, and do not weaken a test to
make the gate green.

---

## 14. Acceptance checklist

- [ ] 13 MCP tools and 8 resources exactly; all existing names and URIs
      unchanged.
- [ ] `get_mindmap_hierarchy`, `get_ast_skeleton`, `get_context_pack`,
      `diff_interface_contracts`, and `get_ranked_reading_path` are
      deterministic and tested over a real MCP session.
- [ ] Context pack is deterministic; skeleton omits bodies only; full mode
      caps at 120 lines / 12,000 chars and reports caps.
- [ ] Budget, omitted files, unreadable files, ambiguous paths, and traversal
      attempts are reported safely.
- [ ] Hash excludes format/root/token fields; JSON and TOON share the hash;
      `since_hash` returns the compact unchanged envelope.
- [ ] TOON is lazily imported, `REPOSCOPE_TOON=0` is a kill switch, and a
      missing package returns 400 with install guidance.
- [ ] `docs/TOON_BENCHMARK.md` contains measured numbers for at least five
      real repositories with exact commits; no 85% claim.
- [ ] Five real skill bodies exist in canonical form and in both
      `.claude/skills/` and `.agents/skills/`.
- [ ] Skill frontmatter, size, sections, first tool call, allowlist, and
      dead-code caveat are tested.
- [ ] Harness preview/apply writes skill files for Claude and Antigravity;
      other agents are unchanged; force/path safety still holds.
- [ ] Skills panel shows `Ready` and a real body preview; Playwright asserts
      it; responsive layout has no horizontal overflow.
- [ ] `docs/MCP.md`, `docs/API.md`, `docs/AGENT_INTEGRATION.md`,
      `docs/FEATURES.md`, `README.md`, and `CHANGELOG.md` are updated.
- [ ] `python -m pytest -q`, `compileall`, `pip check`, frontend build, tsc,
      harness/journeys/mindmap Playwright, and `git diff --check` are green.
- [ ] No push, no `main`, no `experimental`, no Phase 5+, no `.opencode`
      skills copy, no secret exposure.
