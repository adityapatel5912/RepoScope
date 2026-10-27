# Phase 4 research handoff — skills, agent conventions, and context compaction

**Author:** Wren (research deliverable; consumed by Rook)
**Research date:** 2026-10-27
**Status:** complete; this document freezes the Phase 4 skill scope. It is not a
substitute for the implementation plan in
`docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` §7.

---

## 1. Executive decision

Phase 4 ships the five architectural skills that were promised in Phase 3, but
each body is written as a **context-discipline workflow**, not as a generic
description of RepoScope. The five skills are:

| Skill | Job | Context-optimization role |
|---|---|---|
| `blast-radius-guard` | Measure impact before an edit | Spend a bounded context pack on the blast radius instead of reading the repository |
| `zero-grep-architect` | Answer architecture and ownership questions from the graph | Replace broad `grep`/file reads with graph tools and the repo map |
| `pr-contract-shield` | Check interface contracts and layer boundaries before a PR | Ask for the smallest evidence set, then attach exact consumers |
| `onboarding-navigator` | Build a ranked reading path | Use progressive disclosure instead of dumping every file at once |
| `dead-code-surgeon` | Remove unreachable symbols safely | Treat reachability as evidence, not proof, and verify consumers first |

The five `SKILL.md` bodies are real files under `.claude/skills/<id>/SKILL.md`
and `.agents/skills/<id>/SKILL.md`. The harness generator emits the same
bodies for both locations. OpenCode reads `.claude/skills/` and
`.agents/skills/` already, so Phase 4 does **not** add a third physical copy
under `.opencode/skills/`.

**TOON remains opt-in.** The external benchmark shows a large saving against
pretty-printed JSON, but almost none against compact JSON on mixed/nested
data. RepoScope must measure its own packs before making a claim. JSON remains
the default; `format=toon` is an explicit request.

---

## 2. Sources checked

Official format and discovery behavior:

- Agent Skills specification — `https://agentskills.io/specification`
- Claude Code skills best practices —
  `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices`
- Antigravity skills — `https://antigravity.google/docs/skills`
- OpenCode skills — `https://opencode.ai/docs/skills`
- OpenCode MCP servers — `https://opencode.ai/docs/mcp-servers`

Token-compaction evidence:

- TOON format and benchmark — `https://github.com/toon-format/toon`
- Aider repo-map article — `https://aider.chat/2023/10/22/repomap.html`
- Anthropic context-engineering guidance —
  `https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents`
- Agent Skills for Context Engineering —
  `https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering`

RepoScope's frozen sources:

- `docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` §7 and Appendix E
- `backend/harness_generator.py` (nine-agent registry, five skill descriptors)
- `backend/mcp_server/server.py` and `backend/mcp_server/tools.py` (8 tools, 5
  resources before Phase 4)
- `backend/mindmap.py`, `backend/repo_map.py`, `backend/contract_diff.py`,
  `backend/onboarding.py`, `backend/token_metrics.py`
- `docs/coordination/WREN.md`, `ROOK.md`, and `DIALOGUE.md`

Vendor pages change. The implementation records `verified_at` dates; it does
not claim that a page will say the same thing forever.

---

## 3. What the Agent Skills spec requires

A `SKILL.md` file is a directory-level bundle. The minimum contract is:

1. YAML frontmatter with `name` and `description`.
2. `name` is lowercase, hyphenated, at most 64 characters, and matches its
   parent directory.
3. `description` is at most 1,024 characters and says both **what the skill
   does** and **when to use it**.
4. The body is instructions, not a second description. It should be short
   enough for progressive disclosure; the common guidance is well under 500
   lines and roughly 5k tokens.
5. Relative links resolve from the skill directory. Keep references one level
   deep; do not create a maze of nested links.
6. Optional `scripts/`, `references/`, and `assets/` directories are for
   deterministic helpers and long supporting material. Do not put executable
   code in the body when a script would be testable.

RepoScope requirements add three constraints:

- The body must name **only real RepoScope MCP tools/resources**. Stale names
  such as `get_symbol_blast_radius`, `find_orphan_nodes_and_cycles`,
  `run_security_scan`, and `compile_reverse_prompt` are forbidden in Phase 4.
- The body must not claim that a reachability result is proof of dead code.
- The body must not instruct an agent to write outside the repository or to
  install unaudited companion skills.

---

## 4. Agent discovery matrix

| Agent | Project skill location | Global location | How the skill is exposed | Phase 4 action |
|---|---|---|---|---|
| Claude Code | `.claude/skills/<name>/SKILL.md` | User-level Claude skills directory | Discovered from project skills; invoked as a skill/command | Write real bodies |
| Antigravity | `.agents/skills/<name>/SKILL.md` | `~/.gemini/config/skills/` | Workspace skills are discovered by the agent | Write real bodies |
| OpenCode | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` | OpenCode global skill directory | Native `skill` tool; permission-controlled; no metadata-only automatic selection in OpenCode 1 | Reuse `.claude`/`.agents`; do not add a third copy |

The important consequence: a single canonical body per skill can be written to
both `.claude/skills/` and `.agents/skills/`, and all three agents can read it.
The generator must still emit both paths because Claude Code and Antigravity
do not share a project directory.

OpenCode's skill tool is explicit. Its documentation should not promise
automatic selection based on frontmatter; the repository's instruction files
should tell the agent when to call `skill` and which RepoScope skill to load.

---

## 5. Context-engineering findings

### 5.1 Progressive disclosure

Load metadata first, then the skill body, then references/scripts only when the
task needs them. A skill body that repeats the entire architecture wastes the
context it is supposed to save. Each RepoScope skill therefore follows this
shape:

1. **Trigger** — when to use and when not to use it.
2. **Cheap orientation** — one graph or map call.
3. **Targeted evidence** — one blast-radius, contract, or reading-path call.
4. **Decision rules** — what counts as safe, risky, or unknown.
5. **Output contract** — the exact fields and citations to report.
6. **Stop conditions** — when to ask for a human decision instead of reading
   more code.

### 5.2 Budgets, not prose

Every skill tells the agent to choose a token budget and to use
`get_context_pack` with `detail=skeleton` first. Full source is requested only
for the symbols that survive the skeleton pass. This mirrors the compression
research: rank, select, then expand.

### 5.3 Stable, citable evidence

Graph signatures are source excerpts, not normalized signatures. Phase 4 must
normalize at read time rather than rewriting the parser or graph schema.
Every evidence item keeps `path`, `line`, `end_line`, and `role` so an agent
can cite it.

### 5.4 TOON is not a default

The published TOON benchmark reports roughly 42.6% fewer tokens than
pretty-printed JSON overall, but roughly +1.6% versus compact JSON on mixed
data. Flat, uniform arrays do well (about 35% savings); nested or non-uniform
objects can be worse. RepoScope's context pack contains nested file and symbol
objects, so the conservative baseline is **compact JSON**, not pretty JSON.
The 85% claim in the source draft is not supported and must not ship.

---

## 6. Why these five skills

The original five IDs are retained because they are already exposed by the
Phase 3 registry and the UI. Changing IDs would break that contract for no
product benefit. What changes in Phase 4 is the depth and the context
discipline of the bodies.

### 6.1 `blast-radius-guard`

Use before changing a file or a symbol. It fetches a bounded skeleton, calls
`calculate_blast_radius` and `get_dependency_lineage`, optionally checks
`get_hotspots`, then reports direct and transitive consumers plus the smallest
verification set. It must not recommend a refactor based on a filename alone.

### 6.2 `zero-grep-architect`

Use for architecture, ownership, entry-point, and "where does this live?"
questions. It starts with `get_architecture_overview`, then
`get_mindmap_hierarchy`, `get_dependency_lineage`, or
`explain_architectural_rule`. It explicitly forbids using `grep` as the first
tool when the graph can answer the question.

### 6.3 `pr-contract-shield`

Use before opening or updating a PR. It calls `diff_interface_contracts` with a
unified patch or old/new source, attaches exact consumers with
`calculate_blast_radius`, checks new cycles, and checks matching
source/import boundary rules. It reports breaking, warning, and unknown
findings separately.

### 6.4 `onboarding-navigator`

Use when a developer is new to the repository. It calls
`get_ranked_reading_path` and a small `get_context_pack`, and produces a
short path from entry points to core modules to leaves. It must not dump all
files or generate quizzes that are not grounded in the graph.

### 6.5 `dead-code-surgeon`

Use when a symbol appears unreachable. It calls `find_unreachable_symbols`,
then `calculate_blast_radius` and `get_dependency_lineage` for the candidate.
It states the static-analysis caveat in the output. A candidate is deleted
only after a human confirms the dynamic/plugin/reflection cases that static
analysis cannot see.

### 6.6 Companion skills not bundled

Superpowers, Anthropic's `skill-creator`/`mcp-builder`/`frontend-design`/
`webapp-testing`, and the public context-engineering skill collection are
useful references. They are external, independently versioned, and not
audited for this repository. RepoScope documents them as optional companions;
it does not bundle or auto-install them in Phase 4.

---

## 7. Evaluation and triggering

The implementation must prove the skills are usable, not merely present:

1. **Frontmatter test** — every skill has `name`, `description`; name matches
   its directory; description length is within spec.
2. **Tool allowlist test** — every backticked RepoScope tool name in every body
   belongs to the 13-tool Phase 4 surface. Every resource URI belongs to the
   8-resource surface.
3. **Body-size test** — each body is under 500 lines and roughly 5k estimated
   tokens.
4. **Generator test** — `GET /api/harness/skills` returns
   `content_available: true` and a body; the preview/apply path writes the
   same body to `.claude/skills/<id>/SKILL.md` and
   `.agents/skills/<id>/SKILL.md`.
5. **Trigger regression** — at least one test per skill asserts the frontmatter
   description contains its intended trigger vocabulary, and the body contains
   the expected first tool call.
6. **Agent matrix test** — `docs/AGENT_INTEGRATION.md` names all three
   discovery paths and does not promise automatic OpenCode selection.

---

## 8. Handoff to Rook

Rook owns the backend and the measured baseline. Wren's research hands over:

- the five IDs and their job-to-context mapping;
- the frontmatter and body constraints;
- the agent discovery matrix;
- the TOON decision rule: JSON default, compact JSON baseline, no 85% claim;
- the evaluation list above.

Wren owns the Phase 4 frontend after Rook freezes the response shape. The UI
must show `Ready` (not "Available in Phase 4"), explain that skills are written
to both project locations, and keep the existing preview/apply safety gate.
