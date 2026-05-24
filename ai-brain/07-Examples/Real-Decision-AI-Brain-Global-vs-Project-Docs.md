# Real Decision: AI-Brain Global vs Project Docs

This is a real decision record using [[Decision-Template]].

## Decision

Global reusable engineering knowledge belongs in AI-Brain. Project-specific product context, architecture, risks, and test scenarios belong in each repository's `docs/` folder.

## Context

While building the AI-Brain system, early versions mixed global engineering rules with project-specific product details. The [Example Project] product note included tech stack details, product descriptions, and project-specific AI usage notes alongside cross-project coding rules and prompt templates. This caused several problems:

- AI tools could not distinguish between reusable knowledge and project-locked context.
- Project-specific details became stale when the actual project evolved (e.g., tech stack changed from Flutter to React).
- The AI-Brain grew with content that only applied to one project, making it harder to use across projects.
- The boundary between "what to save here" and "what to save in the project" was unclear.

## Options

1. **Everything in AI-Brain.** Store all knowledge — global and project-specific — in the Obsidian vault. Simple, but creates staleness and scope confusion.
2. **Everything in project repos.** Store all docs inside each project. No global system, but duplicates reusable knowledge across projects.
3. **Split by reusability.** Global, cross-project engineering knowledge in AI-Brain. Project-specific context in each project's `docs/` folder. Summaries of cross-project lessons flow back to AI-Brain.
4. **Split by tool.** Store Codex-specific docs in one place, ChatGPT knowledge elsewhere, IDE AI rules in another. Fragmented and hard to maintain.

## Chosen option

Option 3: Split by reusability.

## Why

- Clear boundary: if it applies to only one project, it goes in that project's docs.
- AI-Brain stays lean, reusable, and relevant across all projects.
- Project repos become self-contained — a new AI tool can onboard by reading the project's own docs.
- Cross-project lessons (e.g., "AI pipelines need fallback tests") still flow back to AI-Brain as universal principles.
- This matches how professional engineering teams separate global standards from project documentation.

## Trade-offs

Pros:

- AI-Brain stays compact and universally applicable.
- Project repos are self-documenting.
- No stale project-specific data in the global system.
- Clear decision rule for where to save knowledge.
- New projects can be onboarded independently.

Cons:

- Requires discipline to save knowledge to the right place.
- Some knowledge lives in two places (summary in AI-Brain, details in project docs).
- A new project has no docs until someone creates them.
- AI tools need to be told which project docs to read in addition to AI-Brain.

## Risks

- If the user forgets to create project docs, the project has no AI-readable context. Mitigation: use [[Project-Onboarding-Prompt]] and [[Global-Project-Starter-Pack]] to bootstrap docs.
- If the user saves project-specific details to AI-Brain out of convenience, the vault grows stale. Mitigation: [[Project-Memory-Sync-Rules]] provides the decision rule.
- If cross-project lessons are never extracted from project work, AI-Brain stays empty. Mitigation: [[Post-Flight-Review]] includes a memory sync check.

## Revisit trigger

- If a new tool (e.g., MCP) can automatically sync project context to AI tools, the split may become less important.
- If AI-Brain grows beyond 100 files, audit whether project-specific content leaked in.
- If multiple projects need the same product principle, consider extracting it to AI-Brain.
