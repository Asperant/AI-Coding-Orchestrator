# Real Project Onboarding Test

## Result

Codex successfully onboarded a real repository into the AI engineering system.

## Repository summary

The repository appears to be a two-part product:

- React 19 + Vite 8 frontend
- Express backend under `server/`
- Ollama-based local AI flow
- Firebase / Firestore integration
- face-api.js based client-side face signal processing
- react-router-dom routing
- recharts reporting

## Created files

Codex created these minimal onboarding files:

- `AGENTS.md`
- `docs/product-context.md`
- `docs/architecture.md`
- `docs/testing-checklist.md`

## Important risks discovered

- Legacy naming risk around `geminiService.js` vs local AI backend
- Camera/privacy behavior must match product explanation
- Firebase data minimization should be reviewed
- Local AI fallback behavior must be clear
- Ollama/server behavior should be tested

## Manual test focus

- Home → permission → question flow → analysis → result
- Server closed fallback behavior
- Ollama running queue behavior
- Firebase config missing behavior
- Camera permission denied behavior

## Lesson

A new or existing project should first be inspected by Codex before creating AI-ready files.

Minimal onboarding should start with:

- `AGENTS.md`
- `docs/product-context.md`
- `docs/architecture.md`
- `docs/testing-checklist.md`

Other files like `prompts/`, `.github/pull_request_template.md`, and `docs/ai-coding-rules.md` can be added later only when useful.

A useful project-level `AGENTS.md` should not only describe general rules.  
It should also tell Codex which files to inspect first for common task types.

## Improvement after review

After reviewing the first 4 onboarding files, we improved the project `AGENTS.md`.

Added:

- `Key Files by Task` section
- AI result flow file mapping
- adaptive question file mapping
- result scoring/copy file mapping
- client state file mapping
- privacy/camera file mapping
- ops behavior file mapping

Important operational note added:

Current AI path is `/api/ai-jobs`; queue/rate-limit behavior is part of product behavior, and legacy `/api/ai-json` should not be assumed active.

