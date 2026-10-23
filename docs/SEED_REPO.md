# Fixtures and demo repositories

RepoScope no longer ships a separate `demo-repo/` directory. The committed
fixtures live under `backend/tests/fixtures/`, and the app's one-click demos
are public GitHub repositories loaded through the normal GitHub path.

## Committed fixtures

| Fixture | Purpose |
|---|---|
| `backend/tests/fixtures/multilang/` | Python, TypeScript, TSX, JavaScript, and Go files with a deliberate cross-language import chain. Used by the parser and golden-graph tests. |
| `backend/tests/fixtures/circular/` | A known three-node import cycle plus an isolated acyclic pair. Used by cycle detection. |
| `backend/tests/fixtures/nested/` | Deeply nested packages, `__init__.py` chains, and `src/` layouts. Used by relative-import and package resolution. |
| `backend/tests/fixtures/real_small/` | A tiny, permissively licensed real repository (MIT/Apache-2.0) with its licence retained. Used as the reality check and as the small-repository screenshot. |
| `backend/tests/fixtures/qualified/` | Qualified and ambiguous symbol names. Used by qualified symbol resolution. |
| `backend/tests/fixtures/boundary/` | Import pairs that exercise the architecture rules. Used by `arch_rules` and the PR boundary checks. |

Golden-refresh is explicit only:

```bash
python -m pytest backend/tests/test_graph_golden.py --regen-golden
```

Never regenerate a golden snapshot just to make a failing parser test green.
A changed snapshot is a reviewable claim about the parser's output.

## Loading a fixture by hand

The local-mode API accepts any directory:

```bash
curl -X POST http://127.0.0.1:4100/api/local/load \
  -H "Content-Type: application/json" \
  -d '{"path":"/absolute/path/to/RepoScope/backend/tests/fixtures/real_small","watch":false}'
```

Then reload the canvas. The sidebar reports the fixture's file, node, and edge
counts. This is how the small-repository screenshot in
[`SCREENSHOTS.md`](SCREENSHOTS.md) was captured.

## Demo repositories

The in-app demo picker loads public repositories through the GitHub path. They
are not vendored; loading one requires network access and, for higher rate
limits, a GitHub token. The current demo walkthrough is in
[`DEMO.md`](DEMO.md).

## What is not a fixture

- `data/repo_state.json` is runtime state. It is not a fixture and should not
  be committed with a private repository's contents.
- `qa-report/` and `frontend/test-results/` are generated output.
- The browser folder preview uses the file-system access API and is not a
  server fixture.
