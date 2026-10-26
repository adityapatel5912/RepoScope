# DIVY — work log and claims

Owner: Divy. Integrator for the schema, contracts, CI, packaging, and merges.
This file records claims, commits, tests, and limits. It is not a substitute
for the commit history.

## Current assignment

- Phase 0 — CI stabilization and dependency truth.
- Phase 1 — graph schema v2, deterministic resolver, API linker, mind-map
  contract.
- Then write the Phase 2 handoff for Parv and wait for the handoff review.

## Claims (Phase 0)

| File | Status | Notes |
|---|---|---|
| `backend/requirements.txt` | claimed | Add runtime dependencies. |
| `pyproject.toml` | claimed | Mirror dependencies and pin MCP. |
| `.github/workflows/qa.yml` | claimed | Health assertion, matrix, build job. |
| `backend/main.py` | claimed | Additive health fields only. |
| `backend/tests/test_health.py` | claimed | Explicit endpoint assertions. |
| `backend/tests/test_dependency_contract.py` | claimed | New dependency contract test. |
| `docs/QA_REPORT.md` | claimed | Before/after baseline. |
| `CHANGELOG.md` | claimed | Unreleased CI entry. |

## Claims (Phase 1)

| File | Status | Notes |
|---|---|---|
| `backend/graph_store.py` | claimed | Schema v2, additive persistence, evidence validation. |
| `backend/parse_cache.py` | claimed | Routes, API calls, heritage; cache v3. |
| `backend/symbol_resolver.py` | claimed | New resolver/scanners. |
| `backend/mindmap_classifier.py` | claimed | Six pillars and roles. |
| `backend/mindmap.py` | claimed | Payload builder. |
| `backend/api/routers/mindmap.py` | claimed | Frozen API. |
| `backend/api/__init__.py` | claimed | Mount router. |
| `backend/graph_builder.py` | claimed | Finalization and v2 edges. |
| `backend/graph_analysis.py` | claimed | Dependency edge types. |
| `backend/tests/test_graph_v2.py` | claimed | New schema tests. |
| `backend/tests/test_symbol_resolver.py` | claimed | New resolver tests. |
| `backend/tests/test_mindmap_classifier.py` | claimed | New classifier tests. |
| `backend/tests/test_mindmap_api.py` | claimed | New L2 test. |
| `backend/tests/test_graph_golden.py` | claimed | Pin v1 subset, assert v2 additivity. |
| `docs/API.md` | claimed | Additive endpoint docs. |
| `docs/FEATURES.md` | claimed | Limits and flags. |

## Results

### Phase 0

Status: in progress.

### Phase 1

Status: in progress.

## Open decisions

- None. The mind-map contract is frozen; Parv consumes it without editing
  backend graph code.
