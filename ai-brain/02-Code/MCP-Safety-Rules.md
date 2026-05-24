# MCP Safety Rules

Purpose: prepare for future MCP or similar tool access without weakening security or trust.

## Core rule

Use the minimum permission needed for the task.

## Rules

- Read-only first when possible.
- No production database access by default.
- No service-role, admin, or root-equivalent secrets in normal AI workflows.
- Filesystem access should be limited to explicitly approved project folders.
- GitHub tokens should be scoped as narrowly as possible.
- AI should not exfiltrate secrets, tokens, keys, or private data.
- If AI sees credentials or likely secrets, it should stop and surface the risk immediately.
- Every MCP tool should have one clear purpose and a bounded scope.
- Write actions require explicit user approval.
- Destructive actions require explicit user approval.
- No automatic deletion behavior.

## Practical defaults

- Prefer read-only connectors before write-capable connectors.
- Prefer project-local access before broader machine access.
- Prefer scoped repo access before org-wide access.
- Prefer explicit command approval before open-ended execution.
