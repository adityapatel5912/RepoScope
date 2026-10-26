# Fixture: multi-language project

A tiny project spanning Python, TypeScript, TSX, JavaScript, and Go.

Purpose: pin the node ids and edge types that `graph_builder` produces for
each language, and prove that cross-file import resolution works for every
one of them.

The golden snapshot lives at `golden.json` in this directory and is
regenerated only with:

    cd backend && python -m pytest tests/test_graph_golden.py --regen-golden

| File | Imports | Exercises |
|---|---|---|
| `app.py` | `helpers` (bare stem) | Python AST + stem fallback resolution |
| `helpers.py` | — | Leaf module |
| `user.ts` | `./format` | TS relative import |
| `format.ts` | — | Leaf module |
| `Card.tsx` | `./format`, `./Button` | TSX relative imports |
| `Button.tsx` | — | Leaf component |
| `slug.js` | `./format` | JS relative import |
| `greeter.go` | `fmt` (external) | Go — external import must not become an edge |

`greeter.go` is deliberate: `fmt` is a standard-library package, so it must
NOT produce a dangling edge to a file that does not exist.
