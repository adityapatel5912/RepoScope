# Fixture: circular imports

Two independent dependency cycles plus one isolated module.

| Cycle | Members |
|---|---|
| Python | `alpha.py` → `beta.py` → `gamma.py` → `alpha.py` |
| TypeScript | `a.ts` → `b.ts` → `c.ts` → `a.ts` |
| Acyclic | `isolated.py` → `alpha.py` (reaches in, nothing reaches back) |

Used by `backend/tests/test_graph_golden.py` to pin the edge set, and by
the cycle-detection tests in `backend/tests/test_graph_analysis.py` to
assert that `graph_analysis.find_cycles` finds exactly two cycles of
length 3 — and does not report the isolated module as a cycle.

The two cycles are in separate languages but live in the same directory.
They are separate strongly-connected components because no edge joins them.
