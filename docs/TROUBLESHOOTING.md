# RepoScope — Troubleshooting

Quick fixes for the failures we've actually seen. Most diagnoses start with
`curl localhost:8000/api/health` and `backend/logs/app.log`.

## Graph renders without edges
**Cause**: the edge list never reached the layout. `buildPyramidGraph` must
receive BOTH `rawNodes` and `rawEdges` — inside it, edges are matched against
placed node IDs, so a `source`/`target` that isn't an exact node id
(`file:rel`, `func:rel:name`, `class:rel:Name`, `repo:root`) gets filtered
out. In dev mode the console prints
`[EDGE DIAG] nodes: N · edges in: M · matching IDs: K`.
**Fix**: if `edges in: 0`, the `context` SSE event had no edges (check
`GET /api/repo/graph`). If `matching IDs: 0`, an id transform is mangling
node ids somewhere between backend and layout — ids must pass through
untouched. Rendered edges are also capped at 1,000.

## Nodes overlap
**Cause**: horizontal pitch smaller than node width, or the collision pass
disabled. The layout enforces a minimum center-to-center gutter of
`(widthA + widthB) / 2 + 24px` per row via `fixOverlaps`.
**Fix**: keep `NODE_GAP_X > NODE_W` and `CHILD_GAP_X > CHILD_W` in
`GraphView.tsx`; increase `NODE_GAP_X` / `RANK_GAP_Y` if rows look cramped.
Nodes are also draggable — a hand-moved node can sit anywhere until the next
re-layout.

## Graph is too wide
Rows wrap at `MAX_PER_ROW` (18) nodes; beyond that, lower the constant or
zoom out. If Fit view collapses the pyramid into a thin strip, use the
toolbar zoom + Focus instead — the resize refit deliberately keeps the
camera when fit zoom would drop below 0.3 (see next entry).

## Graph renders as a flat horizontal strip
**Cause**: the whole tree is fit into the viewport at minimum zoom — either
the ReactFlow `fitView` prop re-firing after the initial camera, or the
resize handler refitting a very wide graph.
**Fix**: already fixed in the current code — the camera is owned by
`buildGraph` (root-centered at readable zoom), the resize refit only runs
when the fit zoom stays ≥ 0.3, and ReactFlow has no `fitView` prop. If you
re-introduce it, the strip comes back. Use the toolbar's Fit/zoom + Focus
for navigation, and Code Tours to walk deep trees.

## Graph is empty / "No graph loaded"
The graph renders from the chat `context` event. Ask any question after
loading a repo, or check `GET /api/repo/graph`. If the backend log shows
`Graph built: 0 nodes`, the clone may have failed — check the URL and
`GITHUB_TOKENS`.

## Chat is empty or errors immediately
1. `curl localhost:8000/api/health` — `checks` must show ≥ 1 key somewhere.
2. Keys live in `.env` (loaded from the repo root). After editing `.env`,
   restart uvicorn.
3. Backend log line `All LLM providers failed` → all keys exhausted/invalid.
4. Vite must proxy `/api` → `http://localhost:8000` (default in
   `frontend/vite.config.ts`).

## Rate limit (429) errors
Add more keys: `GROQ_API_KEYS=gsk_1,gsk_2`. Rotation is automatic per
provider; providers chain OpenRouter → Groq → NVIDIA NIM. Verify counts via
`/api/health → checks`.

## Repo load fails
- Private repo → save a PAT in the BYOK card first (`ghp_…`/`github_pat_…`).
- `Authentication failed` → PAT expired or lacks `repo` scope.
- Windows `rmtree` errors during re-clone → repo_loader falls back to a
  `{hash}-2` directory automatically; retry once if state looks stale.

## File tree is empty
The tree renders from the graph's file nodes — ask one chat question after
loading the repo. Still empty? Check `GET /api/repo/graph` for
`"type": "file"` nodes.

## Export PNG is blank or missing fonts
Exports use `html-to-image` with `skipFonts: true` (Google Fonts can't be
inlined cross-origin). If the PNG is blank, zoom so nodes are visible before
exporting — the export captures the current viewport.

## Tour / Impact returns 404
The topic matched no nodes **in the currently loaded repo**. Broaden the
topic, or re-load the repo you meant (demo buttons reset state — note that
loading a different repo replaces the backend's active repo).

## Health check failing
- Process up? `curl localhost:8000/health` → `{"status":"ok"}`.
- Port busy (Windows `winerror 10048`) → another uvicorn is bound; kill it:
  `netstat -ano | findstr :8000` → `taskkill /PID <pid> /F`.
- `memory_mb: 0` → psutil missing: `pip install psutil`.

## Vite: "Invalid hook call" / duplicate React crash
Two dev servers sharing `frontend/node_modules/.vite` corrupt the dependency
cache. Kill every Vite process, delete `frontend/node_modules/.vite`, start
one server.

## Keys show `0` in /api/health despite .env having them
Key rotators read env at import time and call `load_dotenv()` themselves. If
you run uvicorn from a different working directory, dotenv can't find `.env` —
always start the backend from `backend/` (or export env vars directly).
