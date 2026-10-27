---
name: blast-radius-guard
description: Measure the direct and transitive impact of a file or symbol change before editing. Use before modifying a shared module, when a refactor touches an exported symbol, or when deciding which tests and consumers must be checked. Do not use for general architecture discovery; use zero-grep-architect instead.
---

## When to use
- Before editing a shared utility, interface, middleware, or core backend service.
- When refactoring an exported function, class, type signature, or data model.
- When planning test coverage to determine which downstream test suites must run.
- When reviewing high-risk dependencies flagged during architecture reviews.
- Before deprecating or modifying arguments of public API methods.
- When evaluating the safety of breaking changes across package boundaries.

## Do not use
- For general repository exploration or layer discovery; use `zero-grep-architect` instead.
- For reviewing pre-existing pull request diffs; use `pr-contract-shield` instead.
- When investigating unreferenced or orphaned symbols; use `dead-code-surgeon` instead.
- For running security vulnerability audits or runtime dynamic profiling.
- For finding raw text strings or regex matches inside file contents.

## Budget
- Choose a target budget between 4,000 and 8,000 tokens for impact discovery.
- Start with `detail=skeleton` via `get_context_pack` to inspect symbol signatures cheaply.
- Request `detail=full` only for the direct callers identified in the blast radius.
- Utilize `since_hash` with `get_context_pack` across iterations to avoid re-reading unchanged packs.
- Never dump full file contents across the entire repository or unimpacted modules.
- If the token estimate approaches the budget cap, omit leaf utilities first.
- Keep prompt context lean by focusing strictly on the calculated blast radius.

## Workflow
1. Call `get_ast_skeleton` with `file_path` to view declared symbols, lines, and signatures.
2. Call `calculate_blast_radius` with `target_file` and optional `target_symbol` to compute transitive impact.
3. Call `get_dependency_lineage` with `direction="downstream"` to map the dependent hierarchy.
4. Call `get_hotspots` to check if the target file combines high churn with high centrality.
5. Call `get_context_pack` with candidate consumer paths and `budget=8000` to inspect affected call sites.
6. Identify all direct consumers and downstream test suites that require regression validation.
7. Synthesize a structured blast radius report citing exact lines and affected modules.
8. Provide concrete recommendations on safe refactoring order and test invocation.

## Decision rules
- Direct dependents (depth 1) must always be inspected and verified.
- Transitive dependents with risk score > 5 require explicit regression testing.
- If target symbol is not exported, blast radius is strictly bounded to its declaring file.
- When blast radius touches multiple architectural layers, flag as cross-layer refactor.
- Centrality hubs identified by `get_hotspots` require extra caution and human review.
- Do not recommend refactoring based on filename alone; verify call graph connectivity.
- Third-party packages and external dependencies are treated as boundaries.
- Cycles detected in lineage must be flagged as high-risk coupling zones.

## Output contract
- Report `target`: `path:line` citation of the modified symbol or file.
- Report `direct_consumers`: list of file paths and symbol names directly importing the target.
- Report `transitive_count`: total count of affected downstream nodes in the graph.
- Report `risk_score`: calculated blast radius score on a 0 to 10 scale.
- Report `hotspot_status`: whether the target is an active churn-centrality hotspot.
- Report `verification_plan`: recommended test paths and verification steps for developer.
- Format all source references using the canonical `path/to/file.ext:line` notation.

## Stop conditions
- If blast radius exceeds 20 files, pause and ask human developer before proceeding.
- If target symbol cannot be resolved in the graph, stop and ask for path clarification.
- If circular dependencies prevent a deterministic ordering, report cycle and consult human.
- Stop immediately if requested file path traverses outside the repository root.
- If the index is empty or stale, instruct user to re-index before proceeding.
