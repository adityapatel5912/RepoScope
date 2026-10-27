"""
backend/skill_library.py
Canonical skill bodies and validators for RepoScope Phase 4.

Provides:
- The 5 canonical skill descriptors and bodies for AI coding agents.
- Canonical bodies for Claude Code (.claude/skills/) and Antigravity (.agents/skills/).
- Validation utilities ensuring frontmatter conformance, tool allowlist compliance,
  and section ordering.
"""

from __future__ import annotations

import re
from typing import Sequence

try:
    from token_metrics import estimate_tokens
except ImportError:
    from backend.token_metrics import estimate_tokens

ALLOWED_TOOLS = {
    "get_architecture_overview",
    "calculate_blast_radius",
    "get_dependency_lineage",
    "explain_architectural_rule",
    "get_repo_map",
    "find_dependency_cycles",
    "get_hotspots",
    "find_unreachable_symbols",
    "get_mindmap_hierarchy",
    "get_ast_skeleton",
    "get_context_pack",
    "diff_interface_contracts",
    "get_ranked_reading_path",
}

FORBIDDEN_TOOLS = {
    "get_symbol_blast_radius",
    "find_orphan_nodes_and_cycles",
    "run_security_scan",
    "compile_reverse_prompt",
}

ALLOWED_RESOURCES = {
    "reposcope://graph/summary",
    "reposcope://hotspots",
    "reposcope://repo-map",
    "reposcope://dead-code",
    "reposcope://cycles",
    "reposcope://mindmap",
    "reposcope://api-routes",
    "reposcope://context-pack",
}

REQUIRED_SECTIONS = [
    "## When to use",
    "## Do not use",
    "## Budget",
    "## Workflow",
    "## Decision rules",
    "## Output contract",
    "## Stop conditions",
]

FIRST_TOOL_CALL = {
    "blast-radius-guard": "get_ast_skeleton",
    "zero-grep-architect": "get_architecture_overview",
    "pr-contract-shield": "diff_interface_contracts",
    "onboarding-navigator": "get_ranked_reading_path",
    "dead-code-surgeon": "find_unreachable_symbols",
}

SKILL_IDS: tuple[str, ...] = (
    "blast-radius-guard",
    "zero-grep-architect",
    "pr-contract-shield",
    "onboarding-navigator",
    "dead-code-surgeon",
)

SKILL_BODIES: dict[str, str] = {
    "blast-radius-guard": """---
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
""",
    "zero-grep-architect": """---
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
""",
    "pr-contract-shield": """---
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
""",
    "onboarding-navigator": """---
name: onboarding-navigator
description: Build a ranked, budgeted reading path through an unfamiliar repository. Use when a developer is new to the codebase, when you need the shortest path from entry points to core modules, or when deciding what to read first. Do not use it to generate quizzes or claims that are not grounded in the graph.
---

## When to use
- Guiding a new developer or agent through an unfamiliar codebase for the first time.
- Generating a ranked reading path from entry points down to core domain modules and helpers.
- Understanding the core dependencies without loading arbitrary or irrelevant source files.
- Creating a structured onboarding curriculum for a team or subsystem.
- Deciding which files to inspect first when tackling a complex feature request.
- Mapping foundational abstractions before beginning architectural refactorings.

## Do not use
- For generating trivia, quizzes, or ungrounded architectural summaries.
- For deep impact analysis of planned code changes; use `blast-radius-guard`.
- For reviewing interface breakages in a pull request; use `pr-contract-shield`.
- For auditing dead or unused code; use `dead-code-surgeon`.
- For speculative guesses about code logic not substantiated by the code graph.

## Budget
- Allocate 4,000 to 8,000 tokens for initial codebase orientation.
- Use `detail=skeleton` in `get_context_pack` to progressively disclose symbol structures.
- Rely on `get_ranked_reading_path` and `reposcope://repo-map` before reading bodies.
- Never dump all files at once; follow the three-tier progressive reading order.
- Budget reading in increments of 3 to 5 files per learning session.
- Leverage `since_hash` to cache reading lists across multiple conversational turns.
- Request `detail=full` only when deep-diving into a specific core algorithm.

## Workflow
1. Call `get_ranked_reading_path` with `max_files=12` to obtain tiered file recommendations.
2. Inspect `reposcope://repo-map` to observe PageRank centrality scores and token savings.
3. Call `get_architecture_overview` to understand overarching layers and execution entry points.
4. Call `get_mindmap_hierarchy` or inspect `reposcope://mindmap` for hierarchical module nesting.
5. Call `get_context_pack` on the top 3 entry point files with `detail=skeleton` and `budget=6000`.
6. Guide the reader through Level 1 (Entry Points), Level 2 (Core Modules), and Level 3 (Leaves).
7. Summarize domain boundaries and recommend next targeted deep-dives.
8. Provide actionable next steps for developer task alignment.

## Decision rules
- Always present files in strict ranked order: Entry Points first, then Core Modules, then Leaves.
- Level 1 files explain where execution begins; focus on entrypoint signatures and routes.
- Level 2 files explain core domain models and business logic workflows.
- Level 3 files provide utilities and leaves; defer reading until core concepts are grasped.
- Deduplicate paths so no file appears in multiple tiers or recommendations.
- Keep explanations grounded in static graph connectivity rather than speculative prose.
- High incoming edge counts indicate core shared abstractions that warrant careful study.
- Low connectivity leaf utilities should be deferred until core mechanics are understood.

## Output contract
- Report `reading_order`: ordered list of files with rank, level title, and `path:line` citation.
- Report `rationales`: deterministic `why` explanation for each recommended file.
- Report `entry_points`: primary startup files identified by `get_architecture_overview`.
- Report `pillar_map`: overview of module grouping across the six architectural pillars.
- Report `next_steps`: concrete suggestions on which modules to explore based on developer goals.
- Ensure all file references include clickable `path/to/file.ext:line` links.

## Stop conditions
- Stop when the 12-file reading roadmap is established; do not read full bodies of all files.
- If repository index is empty, stop and inform developer that indexing is required.
- Do not make assertions about runtime behavior that cannot be verified in the graph.
- Stop if requested reading path exceeds 50 files; restrict scope to core modules.
- Stop if the user asks to begin editing; transition immediately to appropriate engineering skill.
""",
    "dead-code-surgeon": """---
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
""",
}


def skill_body(skill_id: str) -> str:
    """Return the canonical skill body for skill_id."""
    if skill_id not in SKILL_BODIES:
        raise KeyError(f"Unknown skill_id: {skill_id!r}. Expected one of {SKILL_IDS}")
    return SKILL_BODIES[skill_id]


def validate_skill_bodies() -> list[str]:
    """Validate all canonical skill bodies against Agent Skills and RepoScope constraints."""
    problems: list[str] = []

    if set(SKILL_BODIES.keys()) != set(SKILL_IDS):
        problems.append(
            f"SKILL_BODIES keys {sorted(SKILL_BODIES.keys())} do not match SKILL_IDS {sorted(SKILL_IDS)}"
        )

    for skill_id in SKILL_IDS:
        body = SKILL_BODIES.get(skill_id)
        if not body:
            problems.append(f"{skill_id}: missing body")
            continue

        lines = body.strip().splitlines()
        line_count = len(lines)
        if line_count < 60 or line_count > 100:
            problems.append(
                f"{skill_id}: line count {line_count} is outside the allowed range [60, 100]"
            )

        tokens = estimate_tokens(body)
        if tokens > 5000:
            problems.append(f"{skill_id}: token estimate {tokens} exceeds 5000 limit")

        # Frontmatter validation
        if not body.startswith("---\n"):
            problems.append(f"{skill_id}: missing leading frontmatter '---'")
        match = re.search(r"^---\n(.*?)\n---", body, re.DOTALL)
        if not match:
            problems.append(f"{skill_id}: invalid frontmatter delimiter")
        else:
            fm_text = match.group(1)
            name_m = re.search(r"^name:\s*([^\s]+)", fm_text, re.MULTILINE)
            if not name_m or name_m.group(1) != skill_id:
                problems.append(f"{skill_id}: frontmatter name does not match '{skill_id}'")

            desc_m = re.search(r"^description:\s*(.+)$", fm_text, re.MULTILINE)
            if not desc_m:
                problems.append(f"{skill_id}: frontmatter missing description")
            else:
                desc = desc_m.group(1).strip()
                if len(desc) > 1024:
                    problems.append(
                        f"{skill_id}: description length {len(desc)} exceeds 1024 characters"
                    )

        # Section ordering check
        last_idx = -1
        for sec in REQUIRED_SECTIONS:
            idx = body.find(sec)
            if idx == -1:
                problems.append(f"{skill_id}: missing required section heading '{sec}'")
            elif idx < last_idx:
                problems.append(f"{skill_id}: section '{sec}' appears out of required order")
            else:
                last_idx = idx

        # First tool call validation
        exp_first = FIRST_TOOL_CALL.get(skill_id)
        if exp_first:
            workflow_match = re.search(r"## Workflow\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
            if workflow_match:
                wf_text = workflow_match.group(1)
                first_line = wf_text.strip().splitlines()[0] if wf_text.strip() else ""
                if f"`{exp_first}`" not in first_line:
                    problems.append(
                        f"{skill_id}: first workflow step must call `{exp_first}`, found: {first_line!r}"
                    )

        # Forbidden tools
        for fb in FORBIDDEN_TOOLS:
            if fb in body:
                problems.append(f"{skill_id}: contains forbidden tool name '{fb}'")

        # Backticked tool allowlist check
        backticked_tools = re.findall(
            r"`((?:get_|find_|calculate_|explain_|diff_)[a-z_]+)`", body
        )
        for bt in backticked_tools:
            if bt not in ALLOWED_TOOLS:
                problems.append(f"{skill_id}: backticked tool `{bt}` not in ALLOWED_TOOLS")

        # Resource URI check
        resource_uris = re.findall(r"reposcope://[a-z0-9\-_/]+", body)
        for r_uri in resource_uris:
            if r_uri not in ALLOWED_RESOURCES:
                problems.append(f"{skill_id}: resource URI '{r_uri}' not in ALLOWED_RESOURCES")

        # Caveat checks
        if skill_id == "dead-code-surgeon":
            if "Static reachability is an estimate, not proof of dead code." not in body:
                problems.append(
                    f"{skill_id}: missing exact sentence 'Static reachability is an estimate, not proof of dead code.'"
                )
            for phrase in (
                "dynamic dispatch",
                "reflection",
                "plugin registration",
                "external consumers",
            ):
                if phrase not in body:
                    problems.append(
                        f"{skill_id}: missing required caveat term '{phrase}'"
                    )

        if skill_id == "pr-contract-shield":
            if "No finding is not proof that no consumer breaks" not in body:
                problems.append(
                    f"{skill_id}: missing required PR caveat 'No finding is not proof that no consumer breaks'"
                )

        if skill_id == "zero-grep-architect":
            if (
                "Do not claim the graph is complete for dynamic dispatch or generated code"
                not in body
            ):
                problems.append(
                    f"{skill_id}: missing required architecture caveat 'Do not claim the graph is complete for dynamic dispatch or generated code'"
                )

    return problems
