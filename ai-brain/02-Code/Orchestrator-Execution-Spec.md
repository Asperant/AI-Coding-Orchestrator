# Orchestrator Execution Spec

## Purpose

This is the practical execution blueprint for the multi-agent coding orchestrator described in [[Multi-Agent-Coding-Orchestrator-Architecture]].

## Intended usage

- I start the orchestrator from a project folder.
- I talk to one Orchestrator interface.
- I ask for feature work, bug fixes, refactors, reviews, onboarding, or release checks.
- The system reads AI-Brain and project docs.
- The system coordinates agent roles internally.
- The system asks approval before risky or broad changes.
- The final response is consolidated.

## Runtime shape

The planned runtime is a local app or CLI service.

- local project folder is the working directory
- AI-Brain path: `/home/asrin/Desktop/AI-Brain`
- config file for approved folders and tools
- session log / report output folder
- user approval gates

## Core modules

Expected conceptual modules:

- config loader
- AI-Brain reader
- project context reader
- task classifier
- orchestrator controller
- agent runner
- tool/MCP gateway
- approval gate manager
- report writer
- memory sync suggester

## Agent execution model

In the first practical implementation, specialist agents may be simulated as role-specific passes under one Orchestrator runtime.

Roles:

- Planner
- Coder
- Reviewer
- Tester
- Security
- Architect
- Product
- Release

Rules:

- This is not uncontrolled autonomy.
- The Orchestrator decides which roles to run.
- The final output is consolidated.
- Raw agent output is shown only when useful or requested.

## Input types

The runtime should support:

- new feature request
- bug fix request
- refactor request
- code review / diff review
- project onboarding
- release readiness check
- documentation update
- memory sync request

## Output format

Default final response:

- Summary
- Decision
- Files inspected
- Files changed, if any
- Key findings
- Risks
- Tests
- Memory/docs update
- Next small action

## Tool access model

Planned tool access:

- filesystem read/write for approved folders
- git diff/status access
- project docs read
- AI-Brain read
- AI-Brain write only with approval
- future GitHub MCP
- future database/schema read-only MCP

Related rules:

- [[MCP-Safety-Rules]]
- [[MCP-Resource-Plan]]

## Approval rules

The following require user approval:

- editing files
- broad rewrite
- new dependency
- deleting/moving/renaming files
- database migration
- auth/payment/security changes
- production config changes
- writing to AI-Brain
- writing to project docs
- running destructive commands

## Safety defaults

- read-only first
- no production database by default
- no service-role/admin secrets
- stop if credentials are detected
- keep changes small
- prefer plan-before-code
- do not bypass project docs

## Implementation stack candidates

Possible implementation paths:

- Python + OpenAI Agents SDK
- Node.js + OpenAI SDK
- Codex-driven local workflow
- MCP-enabled local runtime

Do not choose blindly yet. The final stack should be selected based on local setup and tool compatibility.

## First build target

A first real build target should be a local orchestrator that can:

1. read [[CORE-RULES]]
2. read project `AGENTS.md` and `docs/project-map.md` if present
3. classify a task
4. produce a planner output
5. optionally review git diff
6. generate one consolidated report
7. avoid editing files unless explicitly approved

## Success criteria

The system is ready when:

- it can run inside a real project folder
- it can inspect context
- it can produce scoped plans
- it can review diffs through agent lenses
- it respects approval gates
- it can suggest memory/docs updates
- it produces one clear answer

## Non-goals for first working build

- no automatic production deploy
- no unrestricted filesystem access
- no automatic database writes
- no hidden background changes
- no multi-agent noise dump
