---
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
