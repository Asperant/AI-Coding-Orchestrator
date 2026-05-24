# Tool Choice Matrix

This file clarifies which AI tool should be used for which job.

## Tools

### ChatGPT

Best for:

- Product thinking and brainstorming
- Architecture discussions and trade-off analysis
- Long-form reasoning about design decisions
- Exploring ideas before committing to implementation
- Writing product copy and user-facing text
- Explaining complex concepts

Not for:

- Direct code editing inside a project
- Running commands or tests
- File system access
- Tasks that require project-level context persistence across sessions

### Codex (OpenAI)

Best for:

- Executing scoped coding tasks inside a project
- Inspecting files and proposing implementation plans
- Applying small code changes with diff review
- Running terminal commands and tests
- Writing code that follows existing project style

Not for:

- Open-ended product brainstorming
- Long architecture discussions
- Tasks that require reading many AI-Brain files at once (context window limits)
- Creative writing or copy work

### Claude / Antigravity (IDE AI)

Best for:

- Deep code analysis and refactoring within an open workspace
- Reading and understanding large codebases
- Multi-file edits with context awareness
- Code review with access to the full project
- Audit and documentation tasks

Not for:

- Tasks outside the current workspace
- Product brainstorming without code context
- Tasks that need persistent memory between sessions (unless the tool provides it)

### IDE AI Assistants (Copilot, etc.)

Best for:

- Inline code completion while typing
- Quick function generation from comments
- Boilerplate reduction
- Small local edits within a single file

Not for:

- Multi-file architectural changes
- Code review or risk assessment
- Planning or reasoning about trade-offs
- Anything that requires understanding the full project context

### Obsidian (AI-Brain)

Best for:

- Storing reusable engineering knowledge
- Cross-project rules, prompts, templates, and checklists
- Decision records and lessons learned
- Long-term knowledge persistence
- Navigation hub for AI workflows

Not for:

- Running code or tests
- Real-time coding assistance
- Project-specific documentation (that belongs in `docs/`)

### MCP (future)

Best for:

- Connecting AI tools to AI-Brain as a read-only knowledge source
- Exposing prompts, templates, and rules as structured resources
- Enabling AI tools to query project context programmatically

Not yet available. Design the integration when ready.

## Handoff Rules

| From | To | When |
|------|------|------|
| ChatGPT | Codex / IDE AI | Idea is clear, ready to implement |
| Codex / IDE AI | ChatGPT | Need to think through a design decision |
| Any tool | Obsidian | Reusable knowledge produced during work |
| Obsidian | Any tool | Starting a new task, need rules/context |
| Any tool | Codex | Need to run commands, tests, or apply changes |
| Any tool | IDE AI | Need deep codebase analysis or multi-file review |

## Where to Save Knowledge

| Knowledge type | Save to | Tool that saves it |
|---------------|---------|-------------------|
| Cross-project rules and lessons | AI-Brain (Obsidian) | Manual or AI-assisted |
| Project-specific docs | Project `docs/` folder | Codex / IDE AI |
| Temporary analysis | Chat history (ephemeral) | Any tool |
| Reusable prompt or template | AI-Brain `03-Prompts/` or `02-Code/` | Manual or AI-assisted |

## Core Principle

Use the right tool for the right job. Do not force a brainstorming conversation into a code editor, and do not force an implementation task into a chat window.
