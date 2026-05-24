# Decision 002: Project Map Must Include Task-Based Inspect Order

This is a real decision record using [[Decision-Template]].

## Decision

Project maps should include task-based inspect order for common task types, not only folder descriptions or broad file groupings.

## Context

The first real project onboarding test validated that the AI-Brain workflow can guide a real repository onboarding successfully. During that test, Codex inspected the repository before editing, identified the tech stack and main folders, created minimal AI-ready files, and later reviewed them without changing code. The strongest improvement discovered during review was that `docs/project-map.md` became much more useful once it included task-based inspect order for common issues such as telemetry, command flow, map/network problems, and high-impact state containers.

Without inspect order, project maps describe structure but still leave too much ambiguity about where AI should look first when solving a real task.

## Options considered

1. Keep project maps focused only on folders and file descriptions.
2. Add task-based inspect order only when a repository becomes complex.
3. Require project maps to include short task-based inspect order for common task types.
4. Move inspect order guidance out of project maps and into AGENTS.md only.

## Chosen option

Option 3: require project maps to include short task-based inspect order for common task types.

## Why

- It turns project maps into practical execution guides, not just structure summaries.
- It reduces ambiguity for AI tools during real debugging, onboarding, and review tasks.
- It keeps the guidance project-specific, which aligns with [[Project-Memory-Sync-Rules]].
- It emerged from a real repository test rather than only theoretical design.
- It improves the usefulness of minimal onboarding without requiring large documentation.

## Trade-offs

Pros:

- Faster inspection on real tasks
- Better first-step guidance for AI tools
- Less drift between repo structure and actual debugging workflow
- Stronger value from small onboarding docs

Cons:

- Project maps become slightly longer
- Inspect-order guidance may need updating as architecture changes
- Teams must decide which task types are common enough to include

## Risks

- If inspect orders become too detailed, project maps may turn into bulky playbooks.
- If the inspect order is stale, AI may follow the wrong path first.
- If duplicated carelessly in many places, AGENTS.md and project-map.md may drift.

## Revisit trigger

- If repeated onboarding tests show that task-based inspect order adds noise instead of clarity
- If another document proves consistently better than project maps for first inspection guidance
- If repository structures become simple enough that inspect order adds no practical value

## Related links

- [[Project-Map-Template]]
- [[Real-Project-Test-Plan]]
- [[Project-Memory-Sync-Rules]]
