# README for AI

This is the onboarding guide for any AI tool reading this vault for the first time.

## What is this?

This is a personal AI-Brain — an Obsidian vault that stores my reusable engineering knowledge: coding rules, workflow definitions, prompt templates, checklists, templates, product context, and multi-agent architecture.

It is not a project repository. It is a cross-project knowledge base that AI tools should read for context and rules, but should never edit unless I explicitly ask.

## What is the active system?

The system has evolved in layers. Each layer is usable independently:

| Layer | Purpose | Key files |
|-------|---------|-----------|
| **Core** | Essential rules for any AI interaction | [[CORE-RULES]] |
| **V2 — Elite Coding Brain** | Plan-before-code workflow and task classification | [[Elite-Coding-Workflow]], [[Task-Type-Rules]] |
| **V3 — Project Intelligence** | Project onboarding, maps, risks, quality gates, tests | [[Project-Map-Template]], [[Quality-Gates-Template]], [[Risk-Registry-Template]], [[Test-Scenarios-Template]] |
| **V4 — Multi-Agent Orchestrator** | Conceptual agent roles for complex tasks | [[Orchestrator-Agent]], [[Orchestrator-Workflow]] |

## Which file to read first

Always start with [[CORE-RULES]]. It is a compact summary (~3KB) of who I am, how I work, and what I expect from AI. Everything else is an expansion of those rules.

## File classification

### Core — always read

| File | Purpose |
|------|---------|
| [[CORE-RULES]] | Compact entrypoint: identity, workflow, rules |
| [[Elite-Coding-Workflow]] | Full 7-step coding workflow |
| [[Task-Type-Rules]] | 10 task types, checklists, priority order |
| [[Project-Memory-Sync-Rules]] | Where to save knowledge: AI-Brain vs project docs |
| [[Tool-Choice-Matrix]] | Which AI tool to use for which job |
| [[AI-Brain-Priority-Tiers]] | Which files have the highest read priority |
| [[Context-Budget-Rules]] | How to avoid reading unnecessary vault context |
| [[Language-Policy]] | Conversation vs code language expectations |
| [[Tool-Handoff-Protocol]] | How different AI tools should pass work across contexts |
| [[AI-Brain-Maintenance-Policy]] | How the vault should grow without becoming noisy |
| [[MCP-Safety-Rules]] | Safety defaults for future MCP/tool access |
| [[MCP-Resource-Plan]] | Planned AI-Brain resource exposure for future tooling |

### Task-specific — read when relevant

| File | When to use |
|------|-------------|
| [[Feature-Spec-Prompt]] | Planning a new feature |
| [[Debug-Prompt]] | Investigating a bug |
| [[Code-Review-Prompt]] | Reviewing code changes |
| [[Codex-Task-Prompt]] | Starting a scoped coding task |
| [[Codex-Diff-Review-Prompt]] | Reviewing a diff after implementation |
| [[Run-Orchestrated-Coding-Task]] | Practical single-model orchestrator prompt for a coding task |
| [[Run-Multi-Agent-Diff-Review]] | Practical multi-agent-style diff review prompt |
| [[Project-Onboarding-Prompt]] | Onboarding a new project |
| [[AI-Coding-Command-Library]] | Choosing the right workflow command |
| [[Real-Project-Test-Plan]] | Testing the AI-Brain against a real repository |
| [[AI-Brain-Pre-Test-Readiness]] | Final readiness checklist before real project testing |
| [[Pre-Flight-Checklist]] | Before starting a coding task |
| [[Post-Flight-Review]] | After completing a coding task |
| [[Definition-of-Done]] | Checking if a task is truly complete |
| [[Code-Change-Checklist]] | Validating a code change |
| [[AI-Code-Quality-Rubric]] | Scoring AI-generated code quality |
| [[Failure-Modes-and-Recovery]] | When AI goes wrong: symptoms, recovery, prevention |

### Templates — use when creating project docs

| File | Creates |
|------|---------|
| [[Reusable-Project-Template]] | New product/project brief |
| [[Decision-Template]] | Technical/product decision record |
| [[Bug-Fix-Template]] | Bug fix record |
| [[Project-Map-Template]] | Project file map for AI navigation |
| [[Quality-Gates-Template]] | Quality control checklist per project |
| [[Risk-Registry-Template]] | Risk tracking per project |
| [[Test-Scenarios-Template]] | Test scenario registry per project |
| [[Project-Folder-Structure]] | Ideal project folder layout |
| [[Global-Project-Starter-Pack]] | AI-ready project bootstrap |

### Reference / future architecture — do not enforce

| File | Purpose |
|------|---------|
| [[Orchestrator-Agent]] | Conceptual design: single-spokesperson AI |
| [[Orchestrator-Workflow]] | Conceptual design: multi-agent flow |
| [[Planner-Agent]] | Agent role: planning |
| [[Coder-Agent]] | Agent role: implementation |
| [[Reviewer-Agent]] | Agent role: code review |
| [[Security-Agent]] | Agent role: security/privacy |
| [[Tester-Agent]] | Agent role: testing |
| [[Architect-Agent]] | Agent role: architecture |
| [[Product-Agent]] | Agent role: product/UX |
| [[Release-Agent]] | Agent role: deploy/release |
| [[Multi-Agent-Review-Template]] | Template: consolidated agent report |

These agent files describe a target architecture. No current AI tool executes them as real agents. Use them as role-switching prompts or conceptual reference when handling complex tasks.

### Examples — filled references that teach the expected standard

These are not empty templates. They are realistic, filled examples showing what good output looks like for each template. Use them to understand the expected quality, depth, and format before producing your own output.

| File | Demonstrates |
|------|--------------|
| [[Example-Decision]] | Filled decision record: choosing a local AI fallback |
| [[Example-Bug-Fix]] | Filled bug fix record: app freeze from empty AI response |
| [[Example-Lesson]] | Filled lesson: AI pipeline fallback testing requirements |
| [[Example-Multi-Agent-Review]] | Filled multi-agent review: diff touching AI result flow |
| [[Example-Project-Map]] | Filled project map: React + Express + AI service app |
| [[Real-Decision-AI-Brain-Global-vs-Project-Docs]] | Real decision record: how architectural AI-Brain decisions should be documented |

## How to behave before editing files

1. Read [[CORE-RULES]] first.
2. Inspect the project files before proposing changes.
3. Classify the task type using [[Task-Type-Rules]].
4. Propose a small plan before writing code.
5. Never edit AI-Brain files unless I explicitly ask.
6. Never edit files outside the approved scope.
7. After implementation, provide changed files, risks, and test steps.

## How to use each layer

### CORE-RULES

Read it at the start of every session. It contains the compressed essentials. If you only read one file, read this one.

### V2 — Elite Coding Brain

Use [[Elite-Coding-Workflow]] as the step-by-step process for any coding task. Use [[Task-Type-Rules]] to classify the task before starting. Use [[Pre-Flight-Checklist]] before coding and [[Post-Flight-Review]] after.

### V3 — Project Intelligence

When working inside a specific project, check if these exist in the project's `docs/` folder: `project-map.md`, `quality-gates.md`, `risk-registry.md`, `test-scenarios.md`. If they don't exist, use the AI-Brain templates to create them.

### V4 — Multi-Agent Orchestrator

For complex tasks, mentally apply the orchestrator pattern: understand → classify → plan → implement small → review → test → record. You don't need to formally invoke agents. Think of them as review lenses: "Would the Security Agent flag this? Would the Architect Agent object?"

## AI-Brain vs project docs

AI-Brain is a **global, cross-project engineering system**. It stores reusable workflows, prompts, checklists, templates, and coding principles that apply to any project.

Project-specific product context should live inside each project's repository, not here. These files belong in the project repo:

```text
AGENTS.md                    → project-specific AI rules
docs/product-context.md      → what the product is, who it serves
docs/architecture.md         → tech stack, data flow, main decisions
docs/project-map.md          → folder/file map for AI navigation
docs/risk-registry.md        → project-specific risks
docs/test-scenarios.md       → project-specific test cases
```

Only cross-project product principles (e.g., "never use diagnostic language in personal awareness apps") should be stored in AI-Brain.

| Knowledge type | Save to |
|---------------|---------|
| Reusable across projects | AI-Brain |
| Specific to one repository | Project `docs/` |
| Both reusable and project-specific | Summary in AI-Brain, details in project docs |

Full rules: [[Project-Memory-Sync-Rules]]

## Final rule

Do not edit any file in this vault unless I explicitly ask. Read, learn, apply — but do not modify.
