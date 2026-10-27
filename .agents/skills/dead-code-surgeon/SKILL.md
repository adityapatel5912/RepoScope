---
name: dead-code-surgeon
description: Investigate symbols that static reachability marks as unreachable, then remove them only after human confirmation. Use when cleaning dead code, deprecating an unused helper, or reviewing an unreachable-symbol report. This skill treats reachability as an estimate, never as proof.
---

## When to use
- Investigating symbols and files identified as unreachable from repository entry points.
- Preparing dead-code deprecation or pruning proposals for code review.
- Auditing unreachable symbols listed in `reposcope://dead-code`.
- Identifying orphaned utilities left behind after a major refactoring pass.
- Assessing code cleanliness metrics and tech debt reduction opportunities.
- Pruning obsolete internal helper functions during code health sprints.

## Do not use
- For deleting symbols automatically without human developer confirmation.
- For evaluating breaking changes to public APIs; use `pr-contract-shield`.
- For general repository exploration; use `zero-grep-architect`.
- For discovering impact before modifying active code; use `blast-radius-guard`.
- For destructive bulk file deletions without per-symbol verification.

## Budget
- Allocate 4,000 to 8,000 tokens for unreachable symbol investigation.
- Use `detail=skeleton` via `get_context_pack` to inspect candidate signatures and lines.
- Inspect `reposcope://dead-code` to identify candidate symbols without wasting tool calls.
- Never batch-delete multiple files without verifying each candidate individually.
- Spend context only on candidate symbols and their immediate declaring files.
- Use `since_hash` when inspecting multiple dead-code batches to avoid re-reading index data.
- Refrain from fetching bodies until static call absence is confirmed.

## Workflow
1. Call `find_unreachable_symbols` to fetch candidate symbols not reached from entry points.
2. Inspect `reposcope://dead-code` to correlate candidates with historical churn or hotspots.
3. Call `calculate_blast_radius` on each candidate symbol to verify zero dependents.
4. Call `get_dependency_lineage` to confirm no hidden incoming references exist.
5. Check for dynamic dispatch, reflection, plugin registration, or external consumers.
6. Present a verification report to the human developer with removal recommendations.
7. Await explicit human confirmation before taking any destructive action.
8. If confirmed, formulate a minimal removal patch and verify tests remain green.

## Decision rules
- Static reachability is an estimate, not proof of dead code.
- A candidate is not deleted until a human confirms dynamic dispatch, reflection, plugin registration, and external consumers.
- Symbols exported in library entry points or public SDK modules must never be pruned.
- Unreachable private helpers with zero references are prime candidates for safe pruning.
- Check test fixtures and test utilities: static graph entry points may exclude test roots.
- Flag any candidate referenced dynamically via string reflection or dictionary lookup.
- If a candidate symbol has comments mentioning pending features, recommend KEEP.
- Unreachable code in active churn files may represent work-in-progress code.

## Output contract
- Report `candidate`: name and kind of candidate symbol cited as `path:line`.
- Report `reachability_evidence`: confirmation of zero static paths from entry points.
- Report `blast_radius_check`: verification from `calculate_blast_radius` showing zero callers.
- Report `dynamic_risks`: potential dynamic dispatch, reflection, or test usage to verify.
- Report `recommendation`: explicit KEEP, VERIFY_MANUALLY, or CANDIDATE_FOR_REMOVAL status.
- Provide clear `path/to/file.ext:line` citations for all inspected candidate symbols.

## Stop conditions
- Never delete any code without explicit human developer approval.
- If candidate symbol appears in route tables or external interfaces, immediately abort pruning.
- If unsure whether reflection or dynamic import is used, stop and flag for human review.
- If the candidate file contains syntax or indexing errors, abort analysis on that file.
- Stop immediately if user rejects candidate removal; do not argue or re-propose without evidence.
