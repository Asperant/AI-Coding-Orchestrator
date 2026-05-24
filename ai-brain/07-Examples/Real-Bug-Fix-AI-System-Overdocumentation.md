# Real Bug Fix: AI System Overdocumentation

This is a real system-level bug fix record using [[Bug-Fix-Template]].

## Bug

The AI-Brain system risked becoming over-documented and under-activated. It had many useful files, but the number of entrypoints, layers, examples, and overlapping references made real usage harder than it should have been.

## Expected behavior

The system should help an AI tool become more practical on real repositories:

- start from one compact entrypoint
- find the next relevant file quickly
- apply a small workflow
- save knowledge to the right place

## Actual behavior

The vault increasingly had strong content but too many paths into that content. Some files overlapped in purpose, conceptual architecture was easier to find than practical prompts, and real decisions were not clearly separated from examples. This increased onboarding friction and made the system feel heavier than its intended use.

## Error / log

```text
No runtime error.
Process failure mode: too many valid entrypoints, not enough priority clarity.
```

## Root cause

- The system grew by adding good pieces faster than it clarified activation order.
- Conceptual architecture and practical execution aids were both present, but not always clearly separated.
- Real records and examples were both useful, but they did not yet have a strong location boundary.

## Fix

- Added a compact `CORE-RULES.md` entrypoint and reinforced it in onboarding.
- Added practical orchestrator prompts for real usage.
- Added `06-Decisions/` for real cross-project decisions.
- Added clearer memory-sync guidance between AI-Brain and project docs.
- Added recommendation-only cleanup notes instead of destructive restructuring.

## Changed files or areas

- `CORE-RULES.md` as the compact entrypoint
- `README-FOR-AI.md` and `Home.md` as onboarding/navigation layers
- `06-Decisions/` for real decision records
- `02-Code/Project-Memory-Sync-Rules.md` for memory boundary clarification
- `02-Code/Archive-and-Merge-Recommendations.md` for non-destructive cleanup planning

## Test / verification

- A real repository onboarding task could be completed using the current AI-Brain structure.
- AI tools were explicitly tested on coding workflow, V3 docs, and V4 orchestrator prompts.
- Wiki links between onboarding, decision, example, and memory-sync notes were checked.
- The system now distinguishes between examples, real decisions, and project-specific docs more clearly.

## Lesson learned

- A strong AI system needs activation discipline as much as documentation quality.
- New notes should improve execution clarity, not just add coverage.
- If a system grows in layers, it needs explicit priority tiers and real-world testing against repositories and diffs.
