# Decision 001: AI-Brain vs Project Docs

This is a real decision record using [[Decision-Template]].

## Decision

AI-Brain is a global, cross-project engineering system. Project-specific product, architecture, risk, and test context belongs inside each project's repository docs.

## Context

As the AI-Brain system became more practical, it started to serve two very different jobs:

1. storing reusable engineering workflows, prompts, lessons, and decision rules
2. helping real repositories onboard into the system

Without a clear split, project-specific context leaks into the global vault, becomes stale, and makes onboarding harder for both AI tools and humans.

## Options considered

1. Keep both global and project-specific context in AI-Brain.
2. Put almost everything into project repositories and keep AI-Brain minimal.
3. Split by scope: reusable cross-project knowledge in AI-Brain, project-specific context in project docs.
4. Split by tool or agent type instead of by scope.

## Chosen option

Option 3: split by scope.

## Why

- It keeps AI-Brain reusable across projects.
- It keeps repositories self-documenting for real implementation work.
- It reduces stale product and architecture notes in the global vault.
- It gives AI tools a stable rule for where to save new knowledge.
- It supports future MCP exposure because global resources and project resources stay clearly separated.

## Trade-offs

Pros:

- Clear memory boundary
- Better onboarding for real repositories
- Less global clutter
- Easier maintenance over time

Cons:

- Some information may exist in two places
- Teams must decide where to save new knowledge
- Repositories need their own docs created early

## Risks

- If project docs are missing, AI may still rely too much on AI-Brain.
- If the boundary is applied inconsistently, duplicate or conflicting notes may appear.
- If summaries are too short, reusable lessons may not be extracted clearly enough.

## Revisit trigger

- If project repos consistently lack `docs/` support
- If AI tools with MCP blur the line between global and project memory
- If repeated confusion appears about where decisions, bug fixes, or test scenarios should live

## Related links

- [[Project-Memory-Sync-Rules]]
- [[Decisions-README]]
- [[Real-Decision-AI-Brain-Global-vs-Project-Docs]]
