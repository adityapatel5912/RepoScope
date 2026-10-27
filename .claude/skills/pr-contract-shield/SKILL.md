---
name: pr-contract-shield
description: Review interface contract changes and architectural boundary crossings before opening or updating a pull request. Use when a patch changes exported signatures, parameters, return types, or imports across layers. Do not use it as a security scanner or as a replacement for tests.
---

## When to use
- Inspecting a git diff or pull request for breaking changes to exported functions and types.
- Detecting unintentional architectural boundary crossings introduced by new imports.
- Checking whether modified API endpoints affect consumers cited in `reposcope://api-routes`.
- Verifying whether a refactoring preserves backwards compatibility for external consumers.
- Pre-merge reviews to ensure interface stability across modular boundaries.
- Preventing unintended breaking changes in shared client/server communication contracts.

## Do not use
- As a replacement for running the test suite, linter, or type checker.
- As a security scanner or static vulnerability audit tool.
- For general codebase exploration; use `zero-grep-architect` instead.
- For cleaning unreachable code symbols; use `dead-code-surgeon` instead.
- For automated refactoring or auto-applying patch suggestions without review.

## Budget
- Allocate 5,000 to 8,000 tokens for pull request contract review.
- Start with `diff_interface_contracts` on modified files to isolate signature changes.
- Use `get_context_pack` with `detail=skeleton` to verify affected consumer call sites.
- Never load entire unmodified modules into the prompt context.
- Keep diff inspections focused strictly on modified symbol declarations.
- Reuse context pack hashes via `since_hash` across review turns to minimize token spend.
- Drop private implementation functions from inspection to conserve context budget.

## Workflow
1. Call `diff_interface_contracts` with `file_path` and `patch` (or `old_source` and `new_source`).
2. Call `calculate_blast_radius` on any symbol with breaking contract findings.
3. Call `explain_architectural_rule` for any newly added import statements in the diff.
4. Call `find_dependency_cycles` to ensure the patch does not introduce new dependency loops.
5. Inspect `reposcope://api-routes` if the modified file registers HTTP or RPC routes.
6. Categorize findings into breaking changes, warnings, and architectural notes.
7. Assemble an actionable PR review comment citing exact line numbers.
8. Recommend migration steps or deprecation pathways for affected downstream teams.

## Decision rules
- Parameter removals, renames, or new required parameters are classified as BREAKING.
- Exported return type alterations are classified as BREAKING.
- Boundary crossings between forbidden layers (e.g. storage to client) are flagged as VIOLATIONS.
- Caveat: No finding is not proof that no consumer breaks; unsupported languages and dynamic calls are invisible to this check.
- Optional parameter additions with default values are classified as non-breaking WARNINGS.
- If new circular dependencies are detected, flag as an architectural regression.
- Renaming unexported private functions inside a file is safe and classified as INFO.
- Changes to API route decorators or URL paths must be flagged for API contract sync.

## Output contract
- Report `breaking_changes`: list of breaking contract findings citing `path:line` and symbol.
- Report `affected_consumers`: downstream consumers identified via `calculate_blast_radius`.
- Report `boundary_violations`: architectural rule infractions reported with layer names.
- Report `cycle_impact`: whether new dependency cycles were introduced by the patch.
- Report `recommendations`: non-breaking migration guidance or required consumer updates.
- Format all code citations using exact `path/to/file.ext:line` references.

## Stop conditions
- If diff modifies files not supported by contract parsers, note limitation and alert developer.
- If breaking change affects more than 10 downstream files, pause and require human sign-off.
- Stop after contract evaluation is complete; do not attempt automatic code fixes.
- If patch format is malformed or invalid diff, abort check and request valid unified diff.
- Stop if diff touches generated lockfiles, binary files, or vendored assets.
