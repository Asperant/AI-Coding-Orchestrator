# Tool Handoff Protocol

Purpose: define how ChatGPT, Codex, Claude, IDE AI, Obsidian, and future MCP should hand work off to each other.

## Roles

- ChatGPT: strategy, framing, system design, workflow shaping
- Codex: repo-aware coding tasks, implementation, review, project onboarding
- Claude: audits, large document review, broad comparison work
- IDE AI: local edits, inline assistance, quick refactors, nearby context help
- Obsidian: long-term memory, reusable notes, decisions, lessons, examples
- MCP: controlled tool access later

## Handoff rule

Each tool should hand off the smallest useful package:

- task summary
- relevant files
- constraints
- expected output
- known risks

## Practical examples

- Strategy decided in ChatGPT -> implementation done in Codex
- Repo changes made in Codex -> long-term lesson captured in Obsidian
- Large documentation audit done in Claude -> resulting rules summarized back into AI-Brain
- Future MCP access -> only the minimum approved resources and tools are exposed

## Safety note

Tool handoff should reduce ambiguity, not multiply context. Pass only what the next tool actually needs.
