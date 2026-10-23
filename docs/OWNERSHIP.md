# Ownership

## Status: planned overlay, not shipped

The analysis API exposes `GET /api/analysis/ownership?path=...`, but the
ownership data is **not populated** in the current release. The endpoint is a
seam for a future CODEOWNERS / git-history overlay, not a verified feature.

Do not present ownership badges, owners, or “who to ask” recommendations as
available until:

1. a source of truth is defined (CODEOWNERS, git author history, or a manual
   mapping);
2. the data is loaded into the graph or resolved at request time;
3. the canvas and extension render it;
4. the manual checklist has an ownership item with evidence.

For now, use the file tree, hotspots, and dependency lineage instead.

See [`ROADMAP_V2.md`](ROADMAP_V2.md) for the planned work.
