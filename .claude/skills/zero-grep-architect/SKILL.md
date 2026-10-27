---
name: zero-grep-architect
description: Answer architecture, ownership, entry-point, and dependency questions from RepoScope's graph instead of broad grep or file reads. Use when you need the shape of a repository, the owner of a module, or the path between two files. Do not use it for contract diffs or dead-code removal.
---

## When to use
- Answering high-level codebase architecture, layer hierarchy, and module ownership questions.
- Finding entry points, core domain services, and dependency pathways between components.
- Investigating whether an import violates declared architectural boundary rules.
- Mapping how data and control flow from public routes down to storage utilities.
- Onboarding to a new subsystem without reading thousands of irrelevant lines.
- Tracing reverse dependencies to understand why a low-level module exists.

## Do not use
- For measuring change impact on specific symbols; use `blast-radius-guard`.
- For reviewing pull request contract breaks; use `pr-contract-shield`.
- For dead code identification and pruning; use `dead-code-surgeon`.
- For finding string literals or comment text where `grep` is actually appropriate.
- For generating unit test boilerplate or modifying implementation logic.

## Budget
- Allocate 4,000 to 6,000 tokens for architectural orientation.
- Prefer graph summary tools and `reposcope://mindmap` over reading raw source files.
- Never run unstructured broad grep commands when the graph already indexes relationships.
- Use `get_context_pack` with `detail=skeleton` if symbol inspection is required.
- Cap exploration at depth 3 to avoid context explosion on large codebases.
- Utilize `since_hash` when refreshing context to preserve tokens during multi-turn exploration.
- Restrict reading to structural skeletons rather than full implementation bodies.

## Workflow
1. Call `get_architecture_overview` to understand top hubs, layers, and entry points.
2. Call `get_mindmap_hierarchy` or inspect `reposcope://mindmap` for vertical pillar structure.
3. Call `get_dependency_lineage` to trace the dependency path between two specific modules.
4. Call `explain_architectural_rule` when evaluating whether an import crosses layer boundaries.
5. Call `get_repo_map` with `token_budget=6000` if a plain-text overview is requested.
6. Examine route definitions in `reposcope://api-routes` if web endpoints are involved.
7. Synthesize findings citing specific file paths and architectural layers.

## Decision rules
- Classify modules by their declared pillar: frontend, backend, data, infrastructure, tests, docs.
- Treat entry points as execution origins; do not assume helper libraries are entry points.
- Caveat: Do not claim the graph is complete for dynamic dispatch or generated code.
- If an import violates layer rules, mark it explicitly as an architectural boundary violation.
- When explaining relationships, trace both incoming dependencies and outgoing calls.
- Prefer structural connectivity over directory naming when classifying component roles.
- Identify bidirectional cycles as tight coupling smells requiring architectural attention.
- High PageRank nodes are recognized as architectural backbone modules.

## Output contract
- Report `layers`: identified architectural tiers and module distribution across pillars.
- Report `entry_points`: list of execution root files cited as `path:line`.
- Report `hubs`: central coordination files with incoming and outgoing connection counts.
- Report `lineage_path`: step-by-step dependency path connecting queried components.
- Report `boundary_status`: conformance with architectural rules via `explain_architectural_rule`.
- Format all file references using standard `path/to/file.ext:line` markdown links.

## Stop conditions
- Stop when the architectural structure is determined; do not read implementation details.
- If asked to modify files, switch to `blast-radius-guard` before making any edits.
- If dynamic plugin loading obscures relationships, document the gap and consult human.
- Stop if the repository index is missing; advise user to load repository first.
- Stop if queried file is outside repository root or cannot be indexed.
