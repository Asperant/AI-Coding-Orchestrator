# Multi-Agent Coding Orchestrator Architecture

## Purpose

This architecture defines a personal AI coding orchestrator that lets the user speak to one Orchestrator AI while it internally coordinates specialist agents for planning, coding, review, testing, security, architecture, product, and release concerns.

## Core user experience

- I speak only to the Orchestrator.
- I can ask for a feature, bug fix, refactor, code review, project onboarding, or release review.
- The Orchestrator decides which specialist agents are needed.
- I get one consolidated answer, not multiple noisy agent outputs.

## Core components

- **AI-Brain**: reusable global rules, prompts, decisions, lessons, and system guidance
- **Orchestrator runtime**: the control layer that classifies tasks, selects agents, and consolidates outcomes
- **Specialist agents**: planning, coding, review, test, security, architecture, product, and release lenses
- **MCP tool layer**: controlled tool and resource access
- **Codex / coding execution layer**: repo-aware implementation and code-facing execution
- **Project repository**: the real codebase being inspected or changed
- **Project docs**: project-specific product, architecture, risk, and test context
- **User approval gates**: explicit checkpoints before risky or broad actions

## Agent roles

- **Orchestrator**: the only user-facing role; coordinates the rest. See [[Orchestrator-Agent]].
- **Planner**: creates the smallest safe plan before implementation. See [[Planner-Agent]].
- **Coder**: applies the scoped change only after planning or approval. See [[Coder-Agent]].
- **Reviewer**: checks scope, correctness, regressions, and unnecessary complexity. See [[Reviewer-Agent]].
- **Tester**: checks manual test needs, edge cases, and regression scenarios. See [[Tester-Agent]].
- **Security**: evaluates auth, permissions, secrets, privacy, and sensitive-output concerns. See [[Security-Agent]].
- **Architect**: checks structure, responsibility boundaries, and active vs legacy path correctness. See [[Architect-Agent]].
- **Product**: checks UX, trust language, MVP scope, and user-visible wording. See [[Product-Agent]].
- **Release**: checks config, migration, deployment, and rollback implications. See [[Release-Agent]].

## Default workflow

```text
User request
-> Orchestrator
-> classify task
-> read AI-Brain and project docs
-> Planner
-> approval if needed
-> Coder
-> Reviewer / Tester
-> conditional agents
-> final consolidated response
-> memory sync suggestion
```

## MCP role

MCP provides controlled tool access, not intelligence by itself. The Orchestrator and its specialist roles remain responsible for judgment, prioritization, and safe execution.

Future MCP tools may include:

- filesystem
- git/diff
- GitHub
- database/schema read-only
- browser/search
- Figma/design later

Safety rules:

- read-only first
- minimum permissions
- no production database by default
- no admin/service keys
- explicit approval for write/destructive actions

Related rules:

- [[MCP-Safety-Rules]]
- [[MCP-Resource-Plan]]

## Codex role

Codex or IDE coding tools can act as the coding execution layer. They inspect repositories, prepare scoped patches, run reviews, and summarize outcomes, but Orchestrator rules govern how and when coding happens.

## Project docs role

Each project should provide:

- `AGENTS.md`
- `docs/product-context.md`
- `docs/architecture.md`
- `docs/project-map.md`
- `docs/quality-gates.md`
- `docs/risk-registry.md`
- `docs/test-scenarios.md`

These docs provide project-local truth that the Orchestrator must respect alongside [[CORE-RULES]], [[Task-Type-Rules]], and [[Project-Memory-Sync-Rules]].

## Approval gates

The following actions require explicit approval:

- broad rewrite
- new dependency
- database migration
- auth/payment/security-sensitive change
- production config change
- destructive file operation
- secret/token handling
- release/deploy action

## Non-goals

- not fully autonomous uncontrolled coding
- not automatic production deployment
- not bypassing user approval
- not giving every tool full filesystem access
- not replacing project documentation

## First operational target

The first useful target is that the Orchestrator can take a user request, inspect a project, create a small plan, and either stop for approval or produce a safe scoped patch followed by a review/test summary.

## Success criteria

- uses [[CORE-RULES]]
- respects project docs
- classifies task type
- keeps changes small
- runs review/test/security lenses when relevant
- produces one consolidated answer
- suggests memory/project docs updates
