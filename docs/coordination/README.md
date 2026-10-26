# RepoScope coordination — communication rules

This directory is the coordination board for the two-agent build of
RepoScope V2.5–V2.8. The aliases **Rook** and **Wren** are the only names
used here. The board is a record; **git commits, tests, and the graph
contract are the source of truth**.

## 1. Who owns what

| Area | Rook | Wren |
|---|---|---|
| Graph schema, resolver, store, parser facts | owner | read-only |
| Mind-map API contract | owner | consumer |
| Mind-map components, layout, accessibility | review | owner |
| Harness API and write safety | owner | registry, fixtures, UI |
| TOON/context compressor, MCP server | owner | docs and skills copy |
| Citation verifier, reverse prompt, scaffolder | owner | UI |
| Tour, onboarding, metrics, impact, security UI | review | owner |
| CI, packaging, commits to `experimental`, release | owner | read-only |
| Adversarial verification | review | owner |

A file has **one writer at a time**. The writer claims it in their work
MD before editing. A claimed file is not edited by the other agent; send a
handoff instead. The integrator may reassign a claim, but must say so in
`DIALOGUE.md` first.

## 2. Branches and worktrees

- `main` is the owner's branch. It is merged only after the owner tests
  `experimental`.
- `experimental` is the single integration branch.
- Each agent works in a **separate worktree** on a short-lived child branch
  named `rook/<phase>` or `wren/<phase>`.
- A consumer branch may be based on the producer's phase branch when the
  consumer needs an unmerged contract implementation (Phase 3: Wren's UI branch
  is based on Rook's backend commit). The consumer still pushes only its own
  branch; the integrator merges.
- Merge into `experimental` only when the phase gate is green.
- Never force-push or rebase a shared branch.
- Do not run two agents in the same working directory.

## 3. Contract-first handoffs

Before either agent implements against an interface, the integrator writes
the contract in `docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` and announces it in
`DIALOGUE.md`. The consumer does not infer the contract from source code.

A handoff is complete only when it contains:

1. branch and commit hash;
2. files changed and claims released;
3. commands run and their results;
4. known limits or skipped checks, with the reason;
5. the next open decision, if any.

## 4. The phase loop

```
Rook plans and freezes the contract
      ↓
Rook implements 1–2 phases, runs the full gate, commits
      ↓
Rook writes a self-contained prompt for Wren
      ↓
Wren works in a separate worktree on a child branch
      ↓
Wren pushes the child branch and posts a handoff after the gate is green
      ↓
Rook reviews, re-runs the gate on a clean checkout, and merges
      ↓
Rook starts the next batch
```

Parallel work is allowed only when the contract is already frozen and the
files are disjoint. The graph schema, citations, impact, and security are
hard dependencies; do not parallelize across them.

## 5. Status vocabulary

- `planned` — in the plan, not started.
- `claimed` — writer announced, no commit yet.
- `in-progress` — edits exist.
- `blocked` — cannot proceed; reason and owner are in `DIALOGUE.md`.
- `handed-off` — author is done; reviewer must verify.
- `done` — gate green and commit merged into `experimental`.
- `reopened` — a regression or review finding; link the test.

## 6. Verification rules

- The author does not self-certify a merge.
- The reviewer runs the gate on a clean checkout or a fresh worktree.
- A failing test is never deleted to make a gate green. Fix it or document
  the exact reason it cannot run in this environment.
- New behavior gets a test at the lowest layer that can prove it, plus an
  L2 contract test. A user-visible surface gets an L3 journey or a written
  reason automation is impossible.
- Every phase commit is separate. Do not mix two phases in one commit.

## 7. Secrets

- The GitHub PAT lives only in `.env` and is never committed, printed,
  pasted into a coordination file, or sent to an LLM.
- `.env` is ignored by git. If a command needs the token, read it from the
  environment at runtime; do not put it in a command line or a log.
- Agent configs contain placeholders, never real keys.

## 8. Communication format

`DIALOGUE.md` is append-only. A message has a timestamp, an author alias,
and a short subject. Do not rewrite another agent's entry; append a
correction.

`ROOK.md` and `WREN.md` are each agent's work log: claims, commits, tests,
and limits. The reviewer writes review results in their own file and links
the handoff in `DIALOGUE.md`.

## 9. Definition of done

A phase is done when the gate is green on a clean checkout, the contract is
documented, the user-visible surface is tested, the rollback is understood,
and the phase lands as one `--no-ff` integration merge on `experimental`. A
split-ownership phase may have one scoped commit per writer on child branches;
the integrator squashes them into the single phase commit and adds a
`Co-authored-by` trailer. No unrelated or fix commits.
