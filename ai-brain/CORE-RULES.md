# Core Rules

This is the compact entrypoint for any AI tool working with me. Read this first.

## Who I am

I build software products and use AI as an engineering partner. I work on projects. My tools include Codex, ChatGPT, IDE AI assistants, Obsidian, Supabase, and GitHub.

## How I want AI to work with me

- One small step at a time.
- Practical implementation first, no overwhelming theory.
- Clear reasoning behind every suggestion.
- Professional engineering standards.
- Reusable systems over throwaway answers.

## Coding preferences

- Minimal safe changes only.
- Readable code over clever code.
- Follow existing architecture and style first.
- No unnecessary abstractions.
- No unrelated file rewrites.
- No new dependencies unless clearly justified.
- Testing and review after every change.

## Workflow: plan before code

Every coding task must follow this order:

1. **Understand** — classify the task, clarify the goal.
2. **Inspect** — read relevant files, check AGENTS.md, docs/, and project structure.
3. **Plan** — propose a small, scoped implementation plan before writing code.
4. **Implement small** — apply only the approved small change.
5. **Review diff** — check for bugs, scope drift, security risks, edge cases.
6. **Test** — provide manual test steps, success/error scenarios, regression risks.
7. **Record** — save reusable knowledge to AI-Brain or project docs.

Full workflow: [[Elite-Coding-Workflow]]

## Task classification

AI must classify every task before starting. Types include: feature, bug fix, refactor, test writing, database change, UI change, AI pipeline change, security/privacy change, performance change, documentation change.

If a task spans multiple types, address the riskiest type first.

Priority order: Security > Database > AI Pipeline > Auth/Payment > Bug Fix > Feature > Refactor > UI > Test > Docs.

Full rules: [[Task-Type-Rules]]

## Small scoped changes

- Do not edit unrelated files.
- Do not do large rewrites alongside features.
- Do not add dependencies without justification.
- If the task grows beyond the plan, stop and re-plan.

## Review, test, and risk expectations

After every code change, AI must report:

1. Changed files and what changed.
2. Risk areas (auth, database, payment, privacy, AI pipeline, secrets).
3. Manual test steps.
4. Regression risks.
5. Suggested automated tests.

A task is not done until it is understood, scoped, reviewed, testable, and any reusable knowledge has been identified.

Full checklists: [[Pre-Flight-Checklist]] · [[Post-Flight-Review]] · [[Definition-of-Done]]

## Memory sync rule

Knowledge must go to the right place:

- **Reusable across projects** → save to AI-Brain.
- **Specific to one repository** → save to project `docs/`.
- **Both** → summary in AI-Brain, details in project docs.

After every significant task, ask: should a decision, bug fix, lesson, or risk be recorded?

Full rules: [[Project-Memory-Sync-Rules]]

## Orchestrator principle

When handling complex tasks, AI should act as an internal orchestrator:

- Understand the request and classify the task.
- Select which concerns matter (planning, security, architecture, product, testing, release).
- Plan before coding, review after coding.
- Consolidate findings into one clear, actionable answer.
- Do not overwhelm the user with multiple agent reports — deliver one decision.

Full design: [[Orchestrator-Agent]] · [[Orchestrator-Workflow]]

## Important rule

Any AI assistant working with me should help me build systems gradually, with small concrete actions. When in doubt, ask before changing.
