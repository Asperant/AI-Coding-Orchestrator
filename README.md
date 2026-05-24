# AI-Coding-Orchestrator

**An AI-Brain-guided Codex orchestration system for safer, scoped AI-assisted engineering.**

## What this is
AI-Coding-Orchestrator connects a personal, reusable engineering memory (AI-Brain) to an OpenAI Codex-powered orchestrator. It ensures that AI coding tasks are strictly bounded, heavily contextualized by your own coding rules, and manually approved before any file is touched.

## Why it exists
Most AI coding assistants lack persistent memory across projects or execute changes without strict safety boundaries. This system bridges the gap by enforcing a "read-only brain" and a "write-only orchestrator" workflow. It prevents AI models from hallucinating unapproved features, making breaking changes without tests, or forgetting past technical decisions.

## Repository structure

This monorepo contains two main components:
- **`ai-brain/`**: The reusable engineering memory and context repository. It holds rules, patterns, decisions, and documentation for AI-assisted development. By default, this is read-only.
  > *Note: The AI-Brain folder currently keeps Obsidian-style numbered folders. A flatter public template layout may be introduced later.*
- **`orchestrator/`**: The runtime application. It reads context from `ai-brain` and safely builds, scopes, and executes Codex task packages.

## How the system works

1. **AI-Brain supplies engineering rules and workflow memory:** The orchestrator reads your cross-project standards from `ai-brain/`.
2. **Orchestrator builds compact AI-Brain Guidance:** It packages only the relevant rules and context for the specific task.
3. **Codex receives a scoped task package:** The AI model is given a strict scope, allowed files, and the Guidance package.
4. **Scope enforcement checks changed files:** The orchestrator verifies that Codex did not touch unauthorized files.
5. **Post-Codex review evaluates the diff:** The generated changes are reviewed against the initial task and safety rules.
6. **Test gate runs allowlisted tests:** The orchestrator runs user-defined test commands to verify functionality.
7. **Verification Gate produces the final decision:** The system synthesizes the scope, tests, and diff review into a final Approved or Blocked state.
8. **Knowledge Update Proposal suggests what should be remembered, without auto-writing:** If lessons were learned, a deterministic proposal is generated for the user to manually record in the AI-Brain or project docs.

## Core features
- **Local-first, approval-gated orchestration:** No change is executed without human confirmation.
- **Persistent AI-Brain:** A central repository for all your technical standards, checklists, and prompts.
- **Deterministic scoping:** Strict file-level boundaries for AI edits.
- **Automated test gates:** Test commands run automatically to block broken code.
- **Knowledge Update Proposals:** Smart suggestions for updating documentation without side effects.

## Safety model
- **AI-Brain is read-only by default:** Codex cannot overwrite your global engineering rules.
- **Codex execution requires explicit approval:** You must confirm the prompt and the execution plan before any code is generated.
- **Approved paths are required:** The orchestrator will only operate on directories explicitly whitelisted in your configuration.
- **No GitHub push automation:** GitHub push/publishing is not part of the current automated flow.
- **Runtime mock data is disabled in normal product flows:** Real executions rely on actual provider responses.
- **External provider tools return unavailable/blocked when not configured:** If you don't provide a token (e.g., Figma, GitHub), the MCP tool safely blocks the request.

## AI-Brain
Your AI-Brain is the single source of truth for how you build software. It includes prompts, checklists, and agent rules.
- See [ai-brain/CORE-RULES.md](ai-brain/CORE-RULES.md) to understand the core instructions.
- See [ai-brain/README-FOR-AI.md](ai-brain/README-FOR-AI.md) for the AI onboarding guide.

## Orchestrator
The runtime CLI application that manages the Codex interaction.
- See the [orchestrator/README.md](orchestrator/README.md) for detailed CLI usage, commands, and architecture.

## Demo E2E script
To see the system in action without modifying your real projects, run the end-to-end smoke demo:
```bash
cd orchestrator
bash scripts/demo_e2e_orchestrator.sh
```
This script creates a safe, temporary repository and runs a complete planning and execution cycle. See [orchestrator/scripts/demo_e2e_orchestrator.sh](orchestrator/scripts/demo_e2e_orchestrator.sh) for details.

## Quickstart

```bash
# Enter the orchestrator directory
cd orchestrator

# Activate your virtual environment
source .venv/bin/activate

# Check your configured approved paths
PYTHONPATH=src python3 src/main.py --show-approved-paths
```

## Installation

```bash
git clone https://github.com/yourusername/AI-Coding-Orchestrator.git
cd AI-Coding-Orchestrator/orchestrator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration
1. Copy the example configurations in `orchestrator/config/`:
   ```bash
   cp default.example.yaml default.local.yaml
   cp approved_paths.example.yaml approved_paths.local.yaml
   ```
2. Update `approved_paths.local.yaml` with the absolute paths of the projects you want the orchestrator to access.
3. Ensure the `ai_brain_path` in your config points to the `ai-brain/` directory (defaults to `../../ai-brain`).

## Current status
The AI-Coding-Orchestrator is functional for single-model coding tasks and diff reviews using OpenAI Codex. The AI-Brain layout and orchestrator capabilities are continuously evolving.

## What is intentionally not automatic
- **The Knowledge Update Proposal is not automatically written.** You must manually apply useful documentation updates.
- **Git operations are not automated.** You review and commit the changes.
- **Dependency installation is not automated.** You manage your own project dependencies.

## Roadmap
- Multi-agent orchestration for complex architecture planning.
- Autonomous sync option for approved Knowledge Update Proposals.
- Extended MCP (Model Context Protocol) tool integrations.

## License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for the full text.
