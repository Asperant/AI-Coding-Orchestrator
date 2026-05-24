# AI-Coding-Orchestrator

Local-first, approval-gated orchestration that connects a personal AI-Brain to OpenAI Codex.

## What it does

AI-Coding-Orchestrator is a cautious execution layer for AI-assisted engineering. It reads your AI-Brain rules and project context, builds compact Codex task packages, runs Codex only under explicit approval and scope constraints, reviews the resulting diff, runs optional safe tests, and proposes what should be remembered afterward.

It is designed for engineers who want AI help without giving up file scope control, review gates, or engineering memory.

## Why it exists

Raw AI coding flows are often missing three things:

- project-specific memory
- deterministic safety gates
- a clean review-and-verification loop

This project exists to solve that gap. It turns personal engineering knowledge and project docs into a scoped orchestration flow that is designed for cautious AI-assisted engineering, not “just run the model and hope.”

## Core workflow

1. Read AI-Brain rules and project context.
2. Classify the task and generate a planner report.
3. Build a scoped edit plan and compact AI-Brain Guidance.
4. Generate a Codex task package.
5. Evaluate the Codex execution safety contract.
6. Run Codex only after explicit prompt and execution approval.
7. Review the post-Codex diff.
8. Enforce allowed-file scope on changed files.
9. Run an optional safe allowlisted test command.
10. Produce a Verification Gate decision and a Knowledge Update Proposal.

## Key capabilities

- Reads AI-Brain rules, preferences, workflows, and project memory.
- Reads project context and AI-ready docs from approved paths.
- Generates planner reports and edit plans before execution.
- Builds compact Codex task packages with AI-Brain Guidance.
- Runs Codex only after explicit approval and scope checks.
- Enforces allowed files before and after execution.
- Reviews post-Codex diffs with a deterministic multi-agent decision layer.
- Runs optional safe allowlisted tests.
- Produces a Verification Gate decision for the full run.
- Produces a Knowledge Update Proposal, but does not auto-write memory.

## Safety model

The system is designed around deterministic safety gates rather than trust in model behavior.

- Allowed-file-only execution: Codex is scoped to explicitly approved files.
- Approved paths: project-aware reads and writes are blocked outside approved roots.
- AI-Brain cannot be edited by Codex.
- External project writes are blocked unless explicitly approved and implemented.
- Stop-on-secrets: secret-like content is blocked or redacted in prompts, reports, and read surfaces.
- No broad wildcard edits: prompt packages explicitly forbid broad rewrite behavior.
- Post-Codex scope enforcement: changed files are checked against the allowed file list.
- Test command allowlist: only known-safe test commands are accepted.
- Destructive tools are disabled or blocked by policy.
- Runtime mock data is disabled in normal product flows.
- External writes stay preview-only unless explicitly implemented.

This is not “guaranteed safe.” It is a deliberately constrained orchestration layer built to reduce risk and make unsafe states visible.

## AI-Brain integration

AI-Brain is your personal engineering knowledge base.

It provides:

- coding rules
- workflow preferences
- checklists
- reusable engineering lessons
- architecture notes
- decision memory

The orchestrator reads that material, compacts it into Codex-facing AI-Brain Guidance, and keeps AI-Brain read-only by default.

After a plan, review, or run, the orchestrator can generate a **Knowledge Update Proposal** that explains:

- what should be recorded
- where it likely belongs
- why it matters

That proposal is preview-only. AI-Brain is **not** updated automatically.

## Multi-agent decision layer

The orchestrator includes a deterministic multi-agent layer for planning and review.

Roles include:

- Planner
- Reviewer
- Tester
- Security
- Architect
- Product
- Release

Today this layer is rule-based and deterministic by default. It is used to:

- summarize planning concerns
- review diffs
- surface risks
- recommend tests
- shape Pre-Codex Agent Guidance

This is not a hidden autonomous swarm. It is a structured decision layer that makes reasoning easier to inspect.

## Codex execution flow

Codex execution is available, but it is tightly gated.

The run flow:

1. requires an approved project path
2. requires explicit `--allowed-file` entries
3. requires `--confirm-codex-prompt`
4. requires `--confirm-codex-execution`
5. generates a Codex prompt package first
6. checks the Codex execution contract
7. runs Codex only if all gates pass
8. reviews the resulting diff
9. enforces scope on changed files
10. optionally runs an allowlisted test command

Execution notes:

- project path must be approved
- allowed file must exist
- Codex CLI and authentication must be available for real execution
- no automatic staging, commit, reset, checkout, or stash is performed

## MCP tools status

MCP support is optional and supporting. It is not the main product.

What is currently true:

- Local read surfaces exist for filesystem, git, project knowledge, logs, and package metadata.
- GitHub read support exists through safe foundations and read-only `gh` CLI paths where configured.
- Missing provider/config returns `unavailable` or blocked safely. It does not fake success.
- Runtime mock data is disabled in normal product flows.
- Some MCP-style tools remain preview-only or disabled by design, especially writes and destructive actions.

The live validation helper script exists here:

```bash
scripts/check_mcp_live_connectors.sh
```

It is useful for local connector validation and dry-run checklists, but MCP is still a supporting layer around the main orchestrator.

## Installation

Python requirement: `3.10+`

Recommended local install:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install PyYAML
python -m pip install -e . --no-build-isolation
orchestrator --help
```

Optional install verification:

```bash
./scripts/verify_install.sh
```

Cleanup generated Python artifacts:

```bash
./scripts/clean_generated.sh
```

Notes:

- Do not use `sudo`.
- If editable install is unavailable on your machine, direct `PYTHONPATH=src python3 src/main.py ...` commands still work.

## Configuration

Key local config points:

- `config/default.yaml` and `config/approved_paths.yaml` are tracked public-safe defaults.
- `config/default.example.yaml` and `config/approved_paths.example.yaml` show the same shape for local setup and review.
- `AI_BRAIN_PATH` can override the default AI-Brain location.
- `.env.example` contains placeholder-only local environment examples. Do not store real tokens in tracked files.

Example:

```bash
export AI_BRAIN_PATH=/path/to/AI-Brain
```

Important configuration rules:

- project paths must be inside approved roots
- AI-Brain path is read-only by default
- report output stays under the orchestrator’s `reports/` directory

Recommended local setup:

- review `config/default.example.yaml` and `config/approved_paths.example.yaml`
- edit `config/default.yaml` to point at your real AI-Brain, or set `AI_BRAIN_PATH`
- edit `config/approved_paths.yaml` to include only trusted local project roots
- if you prefer to keep machine-specific config untracked, use `config/default.local.yaml` and `config/approved_paths.local.yaml`

## Quickstart

Status check:

```bash
cd orchestrator
PYTHONPATH=src python3 src/main.py --run-orchestrator --mode status
```

Basic plan:

```bash
cd orchestrator
PYTHONPATH=src python3 src/main.py --run-orchestrator --mode plan --project /path/to/project --task "fix telemetry bug"
```

### Approved paths before demo execution

The orchestrator only runs Codex flows against approved local paths.

Before running the demo or any real Codex execution:

- verify that your target project path is approved
- add only trusted local project paths
- expect the demo script to stop clearly if its smoke repo path is not approved

You can inspect the current approved paths with either command:

```bash
cd orchestrator
orchestrator --show-approved-paths
```

or:

```bash
cd orchestrator
PYTHONPATH=src python3 src/main.py --show-approved-paths
```

For configuration details, see the `Configuration` section above.

## Demo: plan mode

```bash
cd orchestrator
PYTHONPATH=src python3 src/main.py --run-orchestrator --mode plan --project /path/to/project --task "review the current auth risk and suggest the safest next coding task"
```

What you should see:

- planner report
- agent runtime summary
- knowledge update proposal
- optional context sections if you enable them

## Demo: Codex prompt preview

```bash
cd orchestrator
PYTHONPATH=src python3 src/main.py --project /path/to/project --task "tighten the README wording without changing behavior" --codex-prompt --confirm-codex-prompt --allowed-file README.md --include-ai-brain-context
```

What this does:

- reads project and AI-Brain context
- builds compact AI-Brain Guidance
- generates a Codex task package
- does **not** execute Codex

## Demo: full run with test gate

```bash
cd orchestrator
PYTHONPATH=src python3 src/main.py --run-orchestrator --mode run --project /path/to/project --task "tighten the README wording without changing behavior" --allowed-file README.md --confirm-codex-prompt --confirm-codex-execution --include-ai-brain-context --test-command "PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_*.py"
```

Requirements for this flow:

- project path must be approved
- allowed file must exist
- Codex CLI/auth must be available for execution

What this does:

- runs the scoped Codex flow
- reviews the diff
- enforces changed-file scope
- runs an optional safe test gate
- emits a Verification Gate decision
- emits a Knowledge Update Proposal

## Demo E2E script

For a repeatable local smoke demo of the main orchestrator workflow, run:

```bash
cd orchestrator
bash scripts/demo_e2e_orchestrator.sh
```

What it validates:

- AI-Brain Guidance reaches the Codex-facing task package
- Codex runs in an allowed-file-only scope
- post-Codex diff review runs
- scope enforcement runs against changed files
- the safe test gate runs
- the final Verification Gate is produced

What it does not do:

- no GitHub push
- no AI-Brain write
- no external provider calls
- no broad file edits

The demo script creates a dedicated local smoke repo, checks that the demo path is approved, prints the exact orchestrator command it will run, and stops clearly if Codex CLI is unavailable.

Compact successful output looks like this:

```text
Coding Run Summary:
- Codex result: passed
- Scope: passed
- Tests: passed
- Verification: Approved

Scope enforcement result:
Passed: yes

Test execution result:
Ran: yes
Passed: yes

Verification Gate:
Final verification decision: Approved

Knowledge Update Proposal:
Write status: not_written
```

Accuracy notes for the demo:

- actual Codex execution still requires local Codex CLI/auth
- the demo does not push to GitHub
- the demo does not write AI-Brain
- the demo does not call external providers
- the demo only mutates its generated smoke repo/demo directory

## Live validation commands

### MCP Live Validation

Run the main test suite:

```bash
cd orchestrator
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```

Run README command smoke tests:

```bash
cd orchestrator
PYTHONPATH=src python3 -m unittest tests.test_readme_commands_smoke
```

Run the MCP live validation checklist in dry-run mode:

```bash
cd orchestrator
scripts/check_mcp_live_connectors.sh
```

Enable live local connector reads intentionally:

```bash
cd orchestrator
RUN_MCP_LIVE_READS=1 scripts/check_mcp_live_connectors.sh
```

## What is intentionally not automatic

The orchestrator is intentionally conservative.

It does **not** automatically:

- write to AI-Brain after a run
- write to project docs after a run
- bypass allowed-file scope
- push to GitHub
- commit or reset git state
- treat unavailable providers as successful
- invent runtime mock data
- push to GitHub as part of the demo flow

The **Knowledge Update Proposal is not auto-written**. It is a structured recommendation only.

## Current status

Current status is intentionally scoped and truthful:

- Core run pipeline has been live-validated on a smoke repo.
- AI-Brain Guidance reaches the Codex prompt package.
- A scoped Codex edit flow has completed successfully under approval and scope constraints.
- Post-Codex review, scope enforcement, and the test gate have passed in E2E validation.
- GitHub publishing is not yet done.
- GitHub push/publishing is not part of the current automated flow.

This project is not positioned as “fully autonomous” or “production ready everywhere.” It is a local-first Codex orchestration layer with strong constraints and visible safety boundaries.

## Roadmap

Realistic near-term roadmap:

- improve AI-Brain retrieval and compaction quality
- finish GitHub publish cleanup
- strengthen project docs onboarding
- explore an optional VS Code extension
- explore an optional UI or desktop wrapper

## Development/testing

Useful local commands:

```bash
cd orchestrator
./scripts/check_repo_hygiene.sh
PYTHONPATH=src python3 -m unittest tests.test_readme_commands_smoke
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile src/**/*.py
```

Recommended developer habits:

- keep changes small and scoped
- validate with tests after changes
- use prompt preview before real Codex execution when a task is risky
- treat MCP and external providers as optional supporting surfaces, not the core workflow

## License

This project is licensed under the MIT License.

See [LICENSE](../LICENSE) for the full text.
