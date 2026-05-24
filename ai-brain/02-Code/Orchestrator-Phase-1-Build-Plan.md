# Orchestrator Phase 1 Build Plan

## Goal

Build a read-only local orchestrator skeleton that can run from a project folder, read AI-Brain and project docs, classify a task, produce a planner report, optionally review git diff, and write a consolidated report without editing project files.

## Chosen stack

- Python-centered hybrid approach
- Python runtime
- OpenAI Agents SDK-ready design
- Codex execution layer later
- MCP-ready tool boundary later

## Why this stack

This stack is preferred because it balances practical local execution with long-term orchestration goals.

- Better long-term orchestration fit than pure Codex workflow
- More useful as a real control plane than pure MCP
- Cleaner orchestration shape for this goal than pure Node as a first choice
- Still leaves room to add Codex execution and MCP access later without rewriting the core design

## Phase 1 scope

- read AI-Brain core files
- read project `AGENTS.md` if present
- read project `docs/project-map.md` if present
- detect project docs
- classify task type
- generate planner output
- optionally inspect git status/diff
- generate consolidated report
- no file edits

## Phase 1 non-goals

- no automatic coding
- no automatic file edits
- no MCP write tools
- no GitHub automation
- no database access
- no background automation
- no production deploy

## Proposed app folder structure

```text
orchestrator-app/
  README.md
  pyproject.toml
  .env.example
  config/
    default.yaml
    approved_paths.yaml
  src/
    main.py
    cli.py
    core/
    brain/
    project/
    orchestration/
    tools/
  reports/
  tests/
```

## Core modules for Phase 1

- `config_loader`: loads AI-Brain path, approved folders, modes, and defaults
- `ai_brain_reader`: reads compact AI-Brain files needed for the current task
- `project_context_reader`: detects and reads `AGENTS.md` and key project docs if present
- `task_classifier`: classifies the task using AI-Brain rules
- `orchestrator_controller`: coordinates the read-only planning/report flow
- `git_gateway` read-only: reads `git status` and `git diff` when needed
- `report_writer`: writes or prints the consolidated report
- `approval_gate_manager` as placeholder: reserved for later phases with write actions
- `mcp_gateway` as placeholder: reserved for later MCP-enabled tool access

## Input and output

Input:

- user task
- working directory
- optional mode: `plan` / `diff-review` / `onboard`

Output:

- Summary
- Task type
- Files inspected
- Relevant project docs found
- Planner output
- Risks
- Suggested tests
- Memory/docs update suggestion
- Next small action

## Safety rules

- read-only by default
- no editing in Phase 1
- no destructive commands
- no secrets
- stop if credentials are detected
- approved paths only
- report uncertainty clearly

## Acceptance criteria

The Phase 1 build is complete when:

- it runs from a project folder
- reads AI-Brain `CORE-RULES`
- detects project `AGENTS.md` / `docs`
- classifies a task
- produces planner output
- can produce git diff review report if diff exists
- writes or prints one consolidated report
- makes zero file changes unless explicitly allowed in a later phase

## First coding task after this plan

Create the `orchestrator-app` folder skeleton with `README`, `pyproject`, config files, and a basic read-only CLI entrypoint.

## Related links

- [[Multi-Agent-Coding-Orchestrator-Architecture]]
- [[Orchestrator-Execution-Spec]]
- [[MCP-Safety-Rules]]
- [[MCP-Resource-Plan]]
- [[Real-Project-Test-Plan]]
