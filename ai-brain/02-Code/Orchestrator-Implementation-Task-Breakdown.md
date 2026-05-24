# Orchestrator Implementation Task Breakdown

## Purpose

This file breaks the Phase 1 read-only orchestrator into small, safe coding tasks.

## Implementation principles

- build small
- read-only first
- no file edits in Phase 1
- no destructive commands
- keep config explicit
- separate control plane from tool plane
- test each module before adding the next

## Task 0 — Create app skeleton

**Goal:**  
Create `orchestrator-app/` with basic files.

**Files:**

- `README.md`
- `pyproject.toml`
- `.env.example`
- `config/default.yaml`
- `config/approved_paths.yaml`
- `src/main.py`
- `src/cli.py`
- `reports/.gitkeep`
- `tests/`

**Acceptance:**

- project structure exists
- CLI can run a hello/status command
- no project files are touched

## Task 1 — Config loader

**Goal:**  
Load AI-Brain path, approved project paths, report path, and mode settings.

**Acceptance:**

- config loads from YAML
- missing config gives clear error
- approved paths are explicit

## Task 2 — AI-Brain reader

**Goal:**  
Read required AI-Brain files.

**Required initial files:**

- `CORE-RULES.md`
- `README-FOR-AI.md`
- `AI-Brain-Priority-Tiers.md`
- `Context-Budget-Rules.md`

**Acceptance:**

- can read files safely
- missing files reported clearly
- no write behavior

## Task 3 — Project context reader

**Goal:**  
Detect project-level context files.

**Detect:**

- `AGENTS.md`
- `docs/product-context.md`
- `docs/architecture.md`
- `docs/project-map.md`
- `docs/quality-gates.md`
- `docs/risk-registry.md`
- `docs/test-scenarios.md`

**Acceptance:**

- reports which files exist
- reports which files are missing
- does not create files

## Task 4 — Task classifier

**Goal:**  
Classify user request using task types.

**Types:**

- feature
- bug fix
- refactor
- test writing
- database change
- UI change
- AI pipeline change
- security/privacy change
- performance change
- documentation change
- release/deploy review

**Acceptance:**

- returns task type
- returns confidence
- returns risk level
- handles ambiguous requests

## Task 5 — Planner report

**Goal:**  
Generate a read-only planning report.

**Output:**

- task summary
- task type
- files likely relevant
- project docs found
- risks
- suggested tests
- smallest safe next action

**Acceptance:**

- report is useful without editing files
- uncertainty is explicit
- no implementation happens

## Task 6 — Git status/diff reader

**Goal:**  
Read git status and git diff in read-only mode.

**Acceptance:**

- can detect changed files
- can summarize diff presence
- does not commit, stage, reset, checkout, or modify anything

## Task 7 — Multi-agent diff review report

**Goal:**  
Use role lenses to review current diff.

**Always:**

- Reviewer
- Tester

**Conditional:**

- Security
- Architect
- Product
- Release

**Acceptance:**

- one consolidated report
- no raw noisy agent dump
- clear decision value
- tests and risks included

## Task 8 — Report writer

**Goal:**  
Write reports to a safe reports directory.

**Acceptance:**

- writes markdown report
- timestamped filename
- includes mode and project path
- does not write to project docs or AI-Brain unless explicitly approved

## Task 9 — Approval gate manager placeholder

**Goal:**  
Define approval checks for future edit mode.

**Acceptance:**

- can identify actions requiring approval
- does not enable editing yet

## Task 10 — MCP gateway placeholder

**Goal:**  
Create a placeholder boundary for future MCP tools.

**Acceptance:**

- no real MCP tool access yet
- documents intended future integration
- read-only assumption preserved

## Final Phase 1 acceptance checklist

- CLI runs from a project folder
- reads AI-Brain core context
- detects project docs
- classifies task
- produces planner report
- can review git diff
- writes consolidated report
- makes zero source code changes

## Related links

- [[Orchestrator-Phase-1-Build-Plan]]
- [[Orchestrator-Execution-Spec]]
- [[Multi-Agent-Coding-Orchestrator-Architecture]]
- [[MCP-Safety-Rules]]
- [[Context-Budget-Rules]]
- [[AI-Brain-Priority-Tiers]]
