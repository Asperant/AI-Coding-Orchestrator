# Context Budget Rules

Purpose: prevent AI tools from reading too much context unnecessarily.

## Core rule

Do not read the entire vault by default.

## Small tasks

For small tasks, read only:

- [[CORE-RULES]]
- the relevant prompt, checklist, or small supporting file

## Coding tasks

For coding tasks, read:

- [[CORE-RULES]]
- [[Task-Type-Rules]]
- relevant project docs inside the repository

Add [[Elite-Coding-Workflow]] or checklists only when the task needs them.

## Complex reviews

For complex reviews, use V3/V4 prompt files and supporting docs:

- [[Run-Orchestrated-Coding-Task]]
- [[Run-Multi-Agent-Diff-Review]]
- project V3 docs where available

## Examples

Use examples only when output quality needs calibration, not as default reading.

## Practical warning

More context is not automatically better. Prefer the smallest set of files that gives the AI enough confidence to act safely.
