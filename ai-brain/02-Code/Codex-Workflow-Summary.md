# Codex Workflow Summary

This note summarizes my current Codex workflow.

## Workflow

1. Start with [[Codex-Task-Prompt]] so Codex inspects the codebase, understands the current structure, creates a small plan, and says which files it will change.
2. Apply only the first small step. Avoid large rewrites, unrelated file changes, and unnecessary dependencies.
3. Run a diff review with [[Codex-Diff-Review-Prompt]] to check for bugs, scope drift, security risks, and missing tests.
4. Validate the change with [[Code-Change-Checklist]].
5. Save reusable outcomes to AI-Brain when relevant, such as prompts, architecture decisions, bug fixes, test checklists, and product decisions.
